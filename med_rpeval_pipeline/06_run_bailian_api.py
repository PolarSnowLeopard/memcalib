#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from utils import iter_jsonl, load_json, stable_id


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPT_DIR / "config.json"


class LengthFinishError(RuntimeError):
    pass


class RateLimiter:
    def __init__(self, rpm: int) -> None:
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self.lock = threading.Lock()
        self.next_time = 0.0

    def wait(self) -> None:
        if self.interval <= 0:
            return
        with self.lock:
            now = time.monotonic()
            if now < self.next_time:
                time.sleep(self.next_time - now)
            self.next_time = max(now, self.next_time) + self.interval


def request_id(row: dict[str, Any]) -> str:
    params = row.get("user_defined_params") or row.get("passParams") or row.get("params") or {}
    for key in ("id", "source_raw_id", "source_id"):
        value = params.get(key)
        if value:
            return str(value)
    return stable_id(json.dumps(row.get("prompt", ""), ensure_ascii=False), prefix="req")


def parse_messages(row: dict[str, Any]) -> list[dict[str, str]]:
    prompt = row.get("prompt")
    if isinstance(prompt, str):
        prompt = json.loads(prompt)
    if not isinstance(prompt, list):
        raise ValueError("prompt must be a messages list or a JSON-encoded messages list")
    messages = []
    for item in prompt:
        if not isinstance(item, dict):
            raise ValueError("message item must be object")
        messages.append({"role": str(item.get("role", "user")), "content": str(item.get("content", ""))})
    return messages


def finish_reason(row: dict[str, Any]) -> str:
    raw = row.get("raw_response")
    if not isinstance(raw, dict):
        return ""
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    return str(first.get("finish_reason", "") or "")


def is_bad_output_row(row: dict[str, Any], *, allow_length_finish: bool = False) -> tuple[bool, str]:
    if row.get("error"):
        return True, "error_field_present"
    response = row.get("response")
    if not isinstance(response, str) or not response.strip():
        return True, "empty_response"
    reason = finish_reason(row)
    if reason == "length" and not allow_length_finish:
        return True, "finish_reason_length"
    return False, ""


def load_done_ids(path: Path) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    for row in iter_jsonl(path):
        rid = row.get("request_id")
        if rid:
            done.add(str(rid))
            continue
        done.add(request_id(row))
    return done


def repair_output_for_resume(path: Path, invalid_path: Path | None, *, allow_length_finish: bool = False) -> dict[str, Any]:
    if not path.exists():
        return {"valid": 0, "invalid": 0, "invalid_reasons": {}}
    valid_rows = []
    invalid_rows = []
    invalid_reasons: dict[str, int] = {}
    for row in iter_jsonl(path):
        bad, reason = is_bad_output_row(row, allow_length_finish=allow_length_finish)
        if bad:
            row["_invalid_reason"] = reason
            invalid_rows.append(row)
            invalid_reasons[reason] = invalid_reasons.get(reason, 0) + 1
        else:
            valid_rows.append(row)

    if invalid_rows:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            for row in valid_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        tmp_path.replace(path)
        if invalid_path is not None:
            invalid_path.parent.mkdir(parents=True, exist_ok=True)
            with invalid_path.open("a", encoding="utf-8") as f:
                for row in invalid_rows:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {"valid": len(valid_rows), "invalid": len(invalid_rows), "invalid_reasons": invalid_reasons}


def call_chat_completions(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base_url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    raise ValueError("No assistant content found in API response")


def ensure_not_truncated(response: dict[str, Any]) -> None:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict) and first.get("finish_reason") == "length":
            raise LengthFinishError("finish_reason=length")


def run_one(row: dict[str, Any], args: argparse.Namespace, api_key: str, limiter: RateLimiter) -> dict[str, Any]:
    rid = request_id(row)
    messages = parse_messages(row)
    last_error = ""
    for attempt in range(args.max_retries + 1):
        try:
            limiter.wait()
            response = call_chat_completions(
                base_url=args.base_url,
                api_key=api_key,
                model=args.model,
                messages=messages,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                timeout=args.timeout,
            )
            ensure_not_truncated(response)
            return {
                "ok": True,
                "request_id": rid,
                "response": extract_content(response),
                "raw_response": response,
                "user_defined_params": row.get("user_defined_params") or row.get("passParams") or row.get("params") or {},
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTPError {exc.code}: {body[:1000]}"
            retryable = exc.code in {408, 409, 429, 500, 502, 503, 504}
        except LengthFinishError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            retryable = False
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            retryable = True
        if attempt >= args.max_retries or not retryable:
            break
        sleep_s = min(args.retry_max_sleep, args.retry_base_sleep * (2**attempt))
        time.sleep(sleep_s)
    return {
        "ok": False,
        "request_id": rid,
        "error": last_error,
        "user_defined_params": row.get("user_defined_params") or row.get("passParams") or row.get("params") or {},
        "prompt": row.get("prompt"),
    }


def append_jsonl(path: Path, row: dict[str, Any], lock: threading.Lock) -> None:
    with lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def should_report_progress(done: int, total: int, every: int) -> bool:
    if every <= 0:
        return False
    return done % every == 0 or done == total


def progress_payload(
    *,
    done: int,
    total: int,
    ok_count: int,
    fail_count: int,
    started: float,
    now: float | None = None,
) -> dict[str, Any]:
    current = time.time() if now is None else now
    elapsed = max(current - started, 1.0)
    return {
        "done": done,
        "total": total,
        "ok": ok_count,
        "failed": fail_count,
        "remaining": max(total - done, 0),
        "elapsed_s": round(elapsed, 1),
        "rpm_actual": round(done / elapsed * 60, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Bailian/DashScope OpenAI-compatible chat completions over prepared JSONL requests.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--failed", type=Path)
    parser.add_argument("--api-key-env", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--rpm", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument("--retry-base-sleep", type=float, default=2.0)
    parser.add_argument("--retry-max-sleep", type=float, default=60.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--no-repair-output", action="store_true", help="Do not remove bad/truncated rows from an existing output before resume.")
    parser.add_argument("--invalid-output", type=Path, help="Optional audit path for removed bad/truncated output rows. By default they are discarded.")
    parser.add_argument("--allow-length-finish", action="store_true", help="Treat finish_reason=length rows as completed. Not recommended for JSON tasks.")
    parser.add_argument("--progress-every", type=int, default=1, help="Print one progress JSON line every N completed requests. Use 0 to disable.")
    args = parser.parse_args()

    cfg = load_json(args.config).get("api", {})
    args.base_url = args.base_url or cfg.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions")
    args.model = args.model or cfg.get("model", "qwen3.7-max")
    args.temperature = args.temperature if args.temperature is not None else float(cfg.get("temperature", 0.2))
    args.max_tokens = args.max_tokens if args.max_tokens is not None else int(cfg.get("max_tokens", 2048))
    args.rpm = args.rpm if args.rpm is not None else int(cfg.get("rpm", 60))
    args.max_workers = args.max_workers if args.max_workers is not None else int(cfg.get("max_workers", 4))
    args.max_retries = args.max_retries if args.max_retries is not None else int(cfg.get("max_retries", 5))
    args.timeout = args.timeout if args.timeout is not None else int(cfg.get("timeout", 120))
    args.failed = args.failed or args.output.with_suffix(".failed.jsonl")

    env_names = [args.api_key_env] if args.api_key_env else ["BAILIAN_API_KEY", "DASHSCOPE_API_KEY"]
    api_key = next((os.environ.get(name) for name in env_names if os.environ.get(name)), "")
    if not api_key:
        raise SystemExit(f"Missing API key. Set one of: {', '.join(env_names)}")

    repair_report = {"valid": 0, "invalid": 0, "invalid_reasons": {}}
    if not args.no_resume and not args.no_repair_output:
        repair_report = repair_output_for_resume(args.output, args.invalid_output, allow_length_finish=args.allow_length_finish)
        if repair_report["invalid"]:
            print(json.dumps({"repair_output": str(args.output), **repair_report}, ensure_ascii=False))

    done = set() if args.no_resume else load_done_ids(args.output)
    rows = []
    for idx, row in enumerate(iter_jsonl(args.input)):
        if args.limit and len(rows) >= args.limit:
            break
        rid = request_id(row)
        if rid in done:
            continue
        rows.append(row)

    limiter = RateLimiter(args.rpm)
    write_lock = threading.Lock()
    ok_count = 0
    fail_count = 0
    started = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as pool:
        futures = [pool.submit(run_one, row, args, api_key, limiter) for row in rows]
        for idx, fut in enumerate(as_completed(futures), start=1):
            result = fut.result()
            if result.get("ok"):
                append_jsonl(args.output, {k: v for k, v in result.items() if k != "ok"}, write_lock)
                ok_count += 1
            else:
                append_jsonl(args.failed, {k: v for k, v in result.items() if k != "ok"}, write_lock)
                fail_count += 1
            if should_report_progress(idx, len(rows), args.progress_every):
                print(
                    json.dumps(
                        progress_payload(
                            done=idx,
                            total=len(rows),
                            ok_count=ok_count,
                            fail_count=fail_count,
                            started=started,
                        ),
                        ensure_ascii=False,
                    ),
                    flush=True,
                )

    print(json.dumps({"input": str(args.input), "output": str(args.output), "failed": str(args.failed), "invalid_output": str(args.invalid_output) if args.invalid_output else None, "submitted": len(rows), "ok": ok_count, "failed_count": fail_count, "resume_done": len(done), "repair": repair_report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
