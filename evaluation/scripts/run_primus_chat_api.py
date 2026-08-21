#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, write_json


DEFAULT_URL = "https://llm-chat-api.alibaba-inc.com/v1/api/chat"
_THREAD_LOCAL = threading.local()


def _opener() -> urllib.request.OpenerDirector:
    opener = getattr(_THREAD_LOCAL, "opener", None)
    if opener is None:
        # An empty ProxyHandler prevents urllib from inheriting HTTP(S)_PROXY.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        _THREAD_LOCAL.opener = opener
    return opener


def build_payload(
    request: dict[str, Any],
    *,
    model: str,
    seed: int,
    max_tokens: int,
    app: str,
    tag: str,
    category: str,
    user_id: str,
    access_key: str,
    quota_id: str,
) -> dict[str, Any]:
    messages = request.get("prompt")
    if not isinstance(messages, list) or not messages:
        raise ValueError("request prompt must be a non-empty message list")
    return {
        "model": model,
        "prompt": messages,
        "params": {
            "temperature": 1.0,
            "max_tokens": max_tokens,
        },
        "cache": 0,
        "tag": tag,
        "app": app,
        "category": category,
        "user_id": user_id,
        "access_key": access_key,
        "quota_id": quota_id,
    }


def _content_from_message(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts).strip()
    return ""


def _response_shape(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    data = data if isinstance(data, dict) else {}
    completion = data.get("completion")
    completion = completion if isinstance(completion, dict) else {}
    choices = completion.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    message = choice.get("message")
    message = message if isinstance(message, dict) else {}
    output = completion.get("output")
    output_item = output[0] if isinstance(output, list) and output and isinstance(output[0], dict) else {}
    return {
        "root_keys": sorted(payload),
        "data_keys": sorted(data),
        "completion_keys": sorted(completion),
        "choice_keys": sorted(choice),
        "message_keys": sorted(message),
        "output_item_keys": sorted(output_item),
    }


def parse_response(payload: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Primus response root is not an object")
    if payload.get("code") not in (None, 0, "0", 200, "200"):
        raise ValueError(
            f"Primus API rejected request: code={payload.get('code')} "
            f"message={str(payload.get('message') or '')[:300]}"
        )
    data = payload.get("data")
    data = data if isinstance(data, dict) else payload
    completion = data.get("completion")
    completion = completion if isinstance(completion, dict) else data

    text = ""
    finish_reason = str(data.get("finish_reason") or "")
    choices = completion.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        choice = choices[0]
        text = _content_from_message(choice.get("message"))
        finish_reason = str(choice.get("finish_reason") or finish_reason)
    if not text and isinstance(completion.get("content"), str):
        text = completion["content"].strip()
    candidates = completion.get("candidates")
    if not text and isinstance(candidates, list) and candidates:
        candidate = candidates[0] if isinstance(candidates[0], dict) else {}
        parts = (candidate.get("content") or {}).get("parts") or []
        text = "".join(
            str(part.get("text") or "")
            for part in parts
            if isinstance(part, dict)
        ).strip()
        finish_reason = str(
            candidate.get("finishReason")
            or candidate.get("finish_reason")
            or finish_reason
        )
    output = completion.get("output")
    if not text and isinstance(output, list):
        parts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, str):
                parts.append(content)
                continue
            if not isinstance(content, list):
                continue
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
        text = "".join(parts).strip()
    if not text and isinstance(completion.get("output_text"), str):
        text = completion["output_text"].strip()
    if not text:
        raise ValueError(
            "Primus response contains no assistant content; "
            f"shape={json.dumps(_response_shape(payload), ensure_ascii=False)}"
        )

    normalized_finish = finish_reason.strip().lower()
    if normalized_finish in {"", "stop", "end_turn", "finished"}:
        normalized_finish = "stop"
    elif normalized_finish in {"length", "max_tokens", "max_token"}:
        normalized_finish = "length"

    usage = completion.get("usage") or data.get("usage") or {}
    return text, normalized_finish, usage if isinstance(usage, dict) else {}


def request_one(
    request: dict[str, Any],
    *,
    url: str,
    model: str,
    seed: int,
    max_tokens: int,
    timeout: float,
    max_retries: int,
    app: str,
    tag: str,
    category: str,
    user_id: str,
    access_key: str,
    quota_id: str,
) -> dict[str, Any]:
    body = build_payload(
        request,
        model=model,
        seed=seed,
        max_tokens=max_tokens,
        app=app,
        tag=tag,
        category=category,
        user_id=user_id,
        access_key=access_key,
        quota_id=quota_id,
    )
    started = time.monotonic()
    last_error: Exception | None = None
    attempts = 0
    for attempt in range(1, max_retries + 1):
        attempts = attempt
        try:
            encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
            http_request = urllib.request.Request(
                url,
                data=encoded,
                headers={"content-type": "application/json", "token": ""},
                method="POST",
            )
            with _opener().open(http_request, timeout=timeout) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
            text, finish_reason, usage = parse_response(response_payload)
            if finish_reason == "length":
                raise ValueError("finish_reason=length")
            return {
                "request_id": str(request["request_id"]),
                "input_fingerprint": request_fingerprint(request),
                "response": text,
                "raw_response": {
                    "object": "chat.completion",
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": finish_reason,
                            "message": {"role": "assistant", "content": text},
                        }
                    ],
                    "usage": usage,
                    "attempts": attempts,
                    "latency_sec": round(time.monotonic() - started, 6),
                },
                "user_defined_params": dict(
                    request.get("user_defined_params") or {}
                ),
                "credential_role": "company-primus-chat-api",
            }
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(min(30.0, (2 ** (attempt - 1)) + random.random()))
    assert last_error is not None
    raise RuntimeError(
        f"{type(last_error).__name__}:{str(last_error)[:500]}"
    ) from last_error


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def load_existing(path: Path, requests_by_id: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows: dict[str, dict[str, Any]] = {}
    for row in iter_jsonl(path):
        request_id = str(row.get("request_id") or "")
        source = requests_by_id.get(request_id)
        if source is None or request_id in rows:
            raise ValueError("existing output contains unknown or duplicate request ID")
        if row.get("input_fingerprint") != request_fingerprint(source):
            raise ValueError(f"existing fingerprint mismatch for {request_id}")
        if not isinstance(row.get("response"), str) or not row["response"].strip():
            raise ValueError(f"existing output is empty for {request_id}")
        rows[request_id] = row
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run resumable MemCalib answers through the Primus chat API."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failed-output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()

    url = os.environ.get("PRIMUS_CHAT_URL", DEFAULT_URL).strip()
    user_id = os.environ.get("PRIMUS_USER_ID", "").strip()
    access_key = os.environ.get("PRIMUS_ACCESS_KEY", "").strip()
    quota_id = os.environ.get("PRIMUS_QUOTA_ID", "").strip()
    app = os.environ.get("PRIMUS_APP", "all_medical").strip()
    tag = os.environ.get("PRIMUS_TAG", app).strip()
    category = os.environ.get("PRIMUS_CATEGORY", "医疗").strip()
    missing_env = [
        name
        for name, value in (
            ("PRIMUS_USER_ID", user_id),
            ("PRIMUS_ACCESS_KEY", access_key),
            ("PRIMUS_QUOTA_ID", quota_id),
        )
        if not value
    ]
    if missing_env:
        raise RuntimeError("missing environment variables: " + ", ".join(missing_env))

    requests_all = list(iter_jsonl(args.input))
    if args.limit > 0:
        requests_all = requests_all[: args.limit]
    requests_by_id = {str(row.get("request_id") or ""): row for row in requests_all}
    if "" in requests_by_id or len(requests_by_id) != len(requests_all):
        raise ValueError("input contains empty or duplicate request IDs")

    existing = load_existing(args.output, requests_by_id)
    pending = [
        row for row in requests_all if str(row["request_id"]) not in existing
    ]
    failures: list[dict[str, Any]] = []
    completed = 0
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                request_one,
                row,
                url=url,
                model=args.model,
                seed=args.seed,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
                max_retries=args.max_retries,
                app=app,
                tag=tag,
                category=category,
                user_id=user_id,
                access_key=access_key,
                quota_id=quota_id,
            ): row
            for row in pending
        }
        for future in as_completed(futures):
            source = futures[future]
            request_id = str(source["request_id"])
            try:
                row = future.result()
                append_jsonl(args.output, row)
                existing[request_id] = row
            except Exception as exc:
                failure = {
                    "request_id": request_id,
                    "input_fingerprint": request_fingerprint(source),
                    "model": args.model,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
                append_jsonl(args.failed_output, failure)
                failures.append(failure)
            completed += 1
            if completed % args.progress_every == 0 or completed == len(pending):
                print(
                    "primus_chat_progress "
                    f"completed={completed}/{len(pending)} "
                    f"ok={len(existing)} failed={len(failures)}",
                    flush=True,
                )

    ordered = [existing[str(row["request_id"])] for row in requests_all if str(row["request_id"]) in existing]
    with args.output.open("w", encoding="utf-8") as handle:
        for row in ordered:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    errors = Counter(row["error_type"] for row in failures)
    report = {
        "schema_version": "memcalib-primus-chat-run-v1",
        "input": str(args.input),
        "output": str(args.output),
        "model": args.model,
        "seed": args.seed,
        "provider_seed_control": False,
        "generation_params": {
            "temperature": 1.0,
            "max_tokens": args.max_tokens,
        },
        "requested": len(requests_all),
        "resume_done": len(requests_all) - len(pending),
        "submitted": len(pending),
        "ok": len(ordered),
        "failed": len(failures),
        "errors": dict(sorted(errors.items())),
        "elapsed_sec": round(time.monotonic() - started, 3),
        "proxy_environment_disabled": True,
    }
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if len(ordered) == len(requests_all) else 1)


if __name__ == "__main__":
    main()
