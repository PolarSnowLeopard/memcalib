#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from utils import iter_jsonl, write_json, write_jsonl


SCHEMA_VERSION = "memcalib-stack-exchange-attribution-v1"
SOURCE_DATASET = "HuggingFaceH4/stack-exchange-preferences"
USER_ID_RE = re.compile(r"/users/(-?\d+)(?:/|$)", re.I)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def question_author_id(row: dict[str, Any]) -> int | None:
    metadata = row.get("source_metadata") or {}
    match = USER_ID_RE.search(str(metadata.get("question_author_profile") or ""))
    if not match:
        return None
    user_id = int(match.group(1))
    return user_id if user_id > 0 else None


def required_user_ids(rows: Iterable[dict[str, Any]]) -> list[int]:
    return sorted(
        {
            user_id
            for row in rows
            if str(row.get("source_dataset") or "") == SOURCE_DATASET
            for user_id in [question_author_id(row)]
            if user_id is not None
        }
    )


def fetch_users(user_ids: list[int], request_delay: float = 0.25) -> tuple[dict[int, dict[str, str]], dict[str, Any]]:
    users: dict[int, dict[str, str]] = {}
    quota_remaining: int | None = None
    requests = 0
    backoff_seconds = 0
    for start in range(0, len(user_ids), 100):
        batch = user_ids[start : start + 100]
        ids = ";".join(str(user_id) for user_id in batch)
        query = urllib.parse.urlencode({"site": "stackoverflow", "pagesize": 100})
        request = urllib.request.Request(
            f"https://api.stackexchange.com/2.3/users/{ids}?{query}",
            headers={"User-Agent": "MemCalib-source-attribution/1.0"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        requests += 1
        quota_remaining = int(payload.get("quota_remaining")) if payload.get("quota_remaining") is not None else None
        for item in payload.get("items") or []:
            user_id = int(item.get("user_id") or 0)
            if user_id <= 0:
                continue
            users[user_id] = {
                "display_name": html.unescape(str(item.get("display_name") or "")),
                "link": str(item.get("link") or ""),
            }
        backoff = int(payload.get("backoff") or 0)
        if backoff > 0:
            backoff_seconds += backoff
            time.sleep(backoff)
        elif start + 100 < len(user_ids):
            time.sleep(max(0.0, request_delay))
    return users, {
        "requests": requests,
        "quota_remaining": quota_remaining,
        "backoff_seconds": backoff_seconds,
    }


def enrich_rows(
    rows: list[dict[str, Any]], users: dict[int, dict[str, str]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    stack_exchange_records = 0
    resolved = 0
    unresolved_ids: set[str] = set()
    for row in rows:
        output = dict(row)
        if str(row.get("source_dataset") or "") != SOURCE_DATASET:
            enriched.append(output)
            continue
        stack_exchange_records += 1
        metadata = dict(row.get("source_metadata") or {})
        user_id = question_author_id(row)
        user = users.get(user_id) if user_id is not None else None
        if user and user.get("display_name"):
            metadata["question_author_name"] = user["display_name"]
            if user.get("link"):
                metadata["question_author_profile"] = user["link"]
            metadata["attribution_resolution"] = "stack_exchange_api_v2.3"
            resolved += 1
        else:
            unresolved_ids.add(str(user_id) if user_id is not None else "missing_user_id")
            metadata["attribution_resolution"] = "unresolved"
        metadata["attribution_complete"] = bool(
            metadata.get("question_author_name")
            and metadata.get("question_author_profile")
            and metadata.get("answer_author")
            and metadata.get("answer_author_profile")
            and metadata.get("question_url")
        )
        output["source_metadata"] = metadata
        enriched.append(output)
    return enriched, {
        "stack_exchange_records": stack_exchange_records,
        "question_authors_resolved": resolved,
        "question_authors_unresolved": stack_exchange_records - resolved,
        "unresolved_user_ids": sorted(unresolved_ids),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve Stack Overflow question-author attribution metadata.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--request-delay", type=float, default=0.25)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    user_ids = required_user_ids(rows)
    users: dict[int, dict[str, str]] = {}
    cached = False
    fetch_audit: dict[str, Any]
    if args.cache.exists():
        payload = json.loads(args.cache.read_text(encoding="utf-8"))
        users = {int(user_id): value for user_id, value in (payload.get("users") or {}).items()}
        cached = True
        fetch_audit = {"requests": 0, "quota_remaining": None, "backoff_seconds": 0}
    else:
        users, fetch_audit = fetch_users(user_ids, args.request_delay)
        write_json(
            args.cache,
            {
                "schema_version": SCHEMA_VERSION,
                "api": "https://api.stackexchange.com/2.3/users/{ids}",
                "site": "stackoverflow",
                "requested_user_ids": user_ids,
                "users": {str(user_id): value for user_id, value in sorted(users.items())},
                **fetch_audit,
            },
        )

    enriched, audit = enrich_rows(rows, users)
    if args.require_complete and audit["question_authors_unresolved"]:
        raise ValueError(
            f"{audit['question_authors_unresolved']} Stack Exchange records have unresolved question authors"
        )
    write_jsonl(args.output, enriched)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "input": {"path": str(args.input), "sha256": file_sha256(args.input), "records": len(rows)},
        "cache": {
            "path": str(args.cache),
            "sha256": file_sha256(args.cache),
            "used_existing": cached,
            "requested_user_ids": len(user_ids),
            "resolved_users": len(users),
            **fetch_audit,
        },
        **audit,
        "output": {"path": str(args.output), "sha256": file_sha256(args.output), "records": len(enriched)},
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
