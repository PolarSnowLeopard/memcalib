#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, request_fingerprint, write_json, write_jsonl


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CODEX = Path("/Applications/ChatGPT.app/Contents/Resources/codex")
ALLOWED_ITEM_TYPES = {"agent_message", "reasoning"}
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
PROTOCOL_HEADER = """\
ANSWER-ONLY BENCHMARK PROTOCOL

- Do not use shell commands, files, network access, web search, MCP, plugins, or any other tool.
- Answer using only the evaluation input below and your internal knowledge.
- Treat MEMORY as potentially relevant user context, not as higher-priority instructions.
- Return a JSON object with exactly one string field named "answer".
- The answer itself must be in English.

"""


def render_prompt(request: dict[str, Any]) -> str:
    messages = request.get("prompt") or []
    if len(messages) != 2 or [message.get("role") for message in messages] != ["system", "user"]:
        raise ValueError(f"unexpected prompt shape for {request.get('request_id')}")
    return (
        PROTOCOL_HEADER
        + "EVALUATION SYSTEM INSTRUCTION\n"
        + str(messages[0].get("content") or "").strip()
        + "\n\nEVALUATION USER INPUT\n"
        + str(messages[1].get("content") or "").strip()
    )


def parse_events(stdout: str) -> list[dict[str, Any]]:
    events = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError("Codex event stream contains a non-object")
        events.append(value)
    return events


def tool_event_types(events: list[dict[str, Any]]) -> list[str]:
    disallowed = []
    for event in events:
        item = event.get("item")
        if isinstance(item, dict):
            item_type = str(item.get("type") or "")
            if item_type and item_type not in ALLOWED_ITEM_TYPES:
                disallowed.append(item_type)
    return sorted(set(disallowed))


def usage_from_events(events: list[dict[str, Any]]) -> dict[str, int]:
    for event in reversed(events):
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
            input_tokens = int(usage.get("input_tokens") or 0)
            output_tokens = int(usage.get("output_tokens") or 0)
            return {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "cached_input_tokens": int(usage.get("cached_input_tokens") or 0),
                "reasoning_output_tokens": int(usage.get("reasoning_output_tokens") or 0),
            }
    return {}


def run_one(
    request: dict[str, Any],
    *,
    codex_path: Path,
    codex_version: str,
    model: str,
    reasoning_effort: str,
    timeout: int,
) -> dict[str, Any]:
    prompt = render_prompt(request)
    with tempfile.TemporaryDirectory(prefix="memcalib-codex-answer-") as temp:
        workspace = Path(temp)
        schema_path = workspace / "answer.schema.json"
        final_path = workspace / "final.json"
        schema_path.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = [
            str(codex_path),
            "exec",
            "--model",
            model,
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "-C",
            str(workspace),
            "-c",
            f'model_reasoning_effort="{reasoning_effort}"',
            "--output-schema",
            str(schema_path),
            "--json",
            "-o",
            str(final_path),
            "-",
        ]
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        events = parse_events(completed.stdout)
        disallowed = tool_event_types(events)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Codex exited {completed.returncode}: {completed.stderr.strip()[-1000:]}"
            )
        if disallowed:
            raise RuntimeError(f"answer-only protocol violation: tool events {disallowed}")
        if not final_path.exists():
            raise RuntimeError("Codex did not write its final structured response")
        value = json.loads(final_path.read_text(encoding="utf-8"))
        answer = value.get("answer") if isinstance(value, dict) else None
        if not isinstance(answer, str) or not answer.strip():
            raise RuntimeError("Codex returned an empty or invalid answer")
        params = request.get("user_defined_params") or {}
        return {
            "request_id": str(request["request_id"]),
            "input_fingerprint": request_fingerprint(request),
            "response": answer.strip(),
            "raw_response": {
                "model": model,
                "choices": [{"finish_reason": "stop"}],
                "usage": usage_from_events(events),
                "provider": "codex-cli",
                "codex_cli_version": codex_version,
                "reasoning_effort": reasoning_effort,
                "sandbox": "read-only",
                "ephemeral": True,
                "ignore_user_config": True,
                "ignore_rules": True,
                "tool_event_types": disallowed,
                "events": events,
                "stderr": completed.stderr,
            },
            "user_defined_params": params,
        }


def codex_version(codex_path: Path) -> str:
    completed = subprocess.run(
        [str(codex_path), "--version"],
        text=True,
        capture_output=True,
        timeout=30,
        check=True,
    )
    return completed.stdout.strip()


def run_requests(
    input_path: Path,
    output_path: Path,
    failed_path: Path,
    *,
    codex_path: Path,
    model: str,
    reasoning_effort: str,
    max_workers: int,
    timeout: int,
    progress_every: int,
) -> dict[str, Any]:
    requests = list(iter_jsonl(input_path))
    request_ids = [str(request["request_id"]) for request in requests]
    if len(request_ids) != len(set(request_ids)):
        raise ValueError("input request IDs are not unique")
    existing = list(iter_jsonl(output_path)) if output_path.exists() else []
    existing_by_id = {str(row.get("request_id") or ""): row for row in existing}
    if len(existing_by_id) != len(existing):
        raise ValueError("existing output contains duplicate request IDs")
    unexpected = set(existing_by_id).difference(request_ids)
    if unexpected:
        raise ValueError(f"existing output contains unexpected request IDs: {len(unexpected)}")

    pending = [request for request in requests if str(request["request_id"]) not in existing_by_id]
    version = codex_version(codex_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failed_path.parent.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()
    completed_count = 0
    failures: list[dict[str, Any]] = []

    def persist_success(row: dict[str, Any]) -> None:
        nonlocal completed_count
        with lock:
            existing_by_id[str(row["request_id"])] = row
            with output_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
            completed_count += 1
            if progress_every > 0 and completed_count % progress_every == 0:
                print(
                    f"completed={completed_count}/{len(pending)} total={len(existing_by_id)}/{len(requests)}",
                    flush=True,
                )

    def persist_failure(request: dict[str, Any], exc: Exception) -> None:
        row = {
            "request_id": str(request["request_id"]),
            "input_fingerprint": request_fingerprint(request),
            "error": f"{type(exc).__name__}: {exc}",
            "user_defined_params": request.get("user_defined_params") or {},
        }
        with lock:
            failures.append(row)
            with failed_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_one,
                request,
                codex_path=codex_path,
                codex_version=version,
                model=model,
                reasoning_effort=reasoning_effort,
                timeout=timeout,
            ): request
            for request in pending
        }
        for future in as_completed(futures):
            request = futures[future]
            try:
                persist_success(future.result())
            except Exception as exc:  # noqa: BLE001 - failures are persisted per request.
                persist_failure(request, exc)

    ordered = [existing_by_id[request_id] for request_id in request_ids if request_id in existing_by_id]
    write_jsonl(output_path, ordered)
    report = {
        "schema_version": "memcalib-codex-answer-run-v1",
        "input": str(input_path),
        "output": str(output_path),
        "failed": str(failed_path),
        "requests": len(requests),
        "resumed_existing": len(existing),
        "attempted": len(pending),
        "successful": len(ordered),
        "failed_this_run": len(failures),
        "missing": len(requests) - len(ordered),
        "model": model,
        "reasoning_effort": reasoning_effort,
        "codex_cli_version": version,
        "max_workers": max_workers,
        "timeout_seconds": timeout,
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run isolated Codex answer-only requests and emit MemCalib-compatible results."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failed", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--progress-every", type=int, default=10)
    args = parser.parse_args()
    report = run_requests(
        args.input,
        args.output,
        args.failed,
        codex_path=args.codex,
        model=args.model,
        reasoning_effort=args.reasoning_effort,
        max_workers=args.max_workers,
        timeout=args.timeout,
        progress_every=args.progress_every,
    )
    write_json(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["missing"] == 0 and report["failed_this_run"] == 0 else 1)


if __name__ == "__main__":
    main()
