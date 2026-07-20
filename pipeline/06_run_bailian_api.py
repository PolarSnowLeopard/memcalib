#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
RESERVED_EXTRA_BODY_FIELDS = {"model", "messages", "temperature", "max_tokens"}


class LengthFinishError(RuntimeError):
    pass


class ProviderCallError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


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


class ApiKeySelector:
    def __init__(self, preferred: str, fallback: str = "") -> None:
        if not preferred:
            raise ValueError("Preferred API key is required")
        self._preferred = preferred
        self._fallback = fallback if fallback and fallback != preferred else ""
        self._fallback_active = False
        self._lock = threading.Lock()

    @property
    def fallback_configured(self) -> bool:
        return bool(self._fallback)

    @property
    def fallback_activated(self) -> bool:
        with self._lock:
            return self._fallback_active

    def current(self) -> tuple[str, str]:
        with self._lock:
            if self._fallback_active:
                return self._fallback, "fallback"
            return self._preferred, "preferred"

    def activate_fallback(self) -> bool:
        with self._lock:
            if not self._fallback:
                return False
            changed = not self._fallback_active
            self._fallback_active = True
            return changed


def is_model_access_denied(error: str) -> bool:
    normalized = error.lower()
    return "model.accessdenied" in normalized or (
        "http" in normalized and "403" in normalized and "model access denied" in normalized
    )


def validate_extra_body(value: dict[str, Any]) -> dict[str, Any]:
    reserved = sorted(RESERVED_EXTRA_BODY_FIELDS.intersection(value))
    if reserved:
        raise ValueError(f"extra body contains reserved fields: {', '.join(reserved)}")
    return value


def parse_extra_body(value: str) -> dict[str, Any]:
    if not value.strip():
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("extra body must be a JSON object")
    return validate_extra_body(parsed)


def parse_streaming_chat_completions(body: bytes | str) -> dict[str, Any]:
    text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else body
    response: dict[str, Any] = {}
    choices: dict[int, dict[str, Any]] = {}
    chunks = 0
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        chunk = json.loads(payload)
        if not isinstance(chunk, dict):
            continue
        chunks += 1
        for key in ("id", "created", "model", "object", "system_fingerprint", "usage"):
            if chunk.get(key) is not None:
                response[key] = chunk[key]
        for item in chunk.get("choices") or []:
            if not isinstance(item, dict):
                continue
            index = int(item.get("index") or 0)
            choice = choices.setdefault(
                index,
                {
                    "index": index,
                    "finish_reason": None,
                    "message": {"role": "assistant", "content": "", "reasoning_content": ""},
                },
            )
            delta = item.get("delta") or item.get("message") or {}
            if isinstance(delta, dict):
                message = choice["message"]
                if delta.get("role"):
                    message["role"] = delta["role"]
                for key in ("content", "reasoning_content", "refusal"):
                    value = delta.get(key)
                    if isinstance(value, str):
                        message[key] = str(message.get(key) or "") + value
            if item.get("finish_reason") is not None:
                choice["finish_reason"] = item["finish_reason"]
    if not chunks:
        raise ValueError("Provider returned no SSE chat completion chunks")
    response["object"] = "chat.completion"
    response["choices"] = [choices[index] for index in sorted(choices)]
    if not response["choices"]:
        raise ValueError("Provider returned no SSE chat completion choices")
    return response


def request_id(row: dict[str, Any]) -> str:
    explicit_id = row.get("request_id")
    if explicit_id:
        return str(explicit_id)
    params = row.get("user_defined_params") or row.get("passParams") or row.get("params") or {}
    for key in ("id", "source_raw_id", "source_id"):
        value = params.get(key)
        if value:
            return str(value)
    return stable_id(json.dumps(row.get("prompt", ""), ensure_ascii=False), prefix="req")


def request_fingerprint(row: dict[str, Any]) -> str:
    payload = {
        "request_id": request_id(row),
        "prompt": parse_messages(row),
        "user_defined_params": row.get("user_defined_params") or row.get("passParams") or row.get("params") or {},
    }
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


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
    if not reason:
        return True, "finish_reason_missing"
    if reason != "stop" and not (allow_length_finish and reason == "length"):
        return True, f"finish_reason_{reason}"
    return False, ""


def load_done_ids(path: Path, expected_fingerprints: dict[str, str] | None = None) -> set[str]:
    done: set[str] = set()
    if not path.exists():
        return done
    for row in iter_jsonl(path):
        rid = str(row.get("request_id") or request_id(row))
        if expected_fingerprints is not None and row.get("input_fingerprint") != expected_fingerprints.get(rid):
            continue
        done.add(rid)
    return done


def repair_output_for_resume(
    path: Path,
    invalid_path: Path | None,
    *,
    allow_length_finish: bool = False,
    expected_fingerprints: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not path.exists():
        return {"valid": 0, "invalid": 0, "invalid_reasons": {}}
    valid_rows = []
    invalid_rows = []
    invalid_reasons: dict[str, int] = {}
    for row in iter_jsonl(path):
        bad, reason = is_bad_output_row(row, allow_length_finish=allow_length_finish)
        if not bad and expected_fingerprints is not None:
            rid = str(row.get("request_id") or request_id(row))
            expected = expected_fingerprints.get(rid)
            if expected is None:
                bad, reason = True, "request_not_in_current_input"
            elif row.get("input_fingerprint") != expected:
                bad, reason = True, "input_fingerprint_mismatch"
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
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra = validate_extra_body(extra_body or {})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    payload.update(extra)
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
        body = resp.read()
        if extra.get("stream"):
            return parse_streaming_chat_completions(body)
        return json.loads(body.decode("utf-8"))


def call_chat_completions_with_hard_timeout(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: int,
    hard_timeout: int,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    curl_path = shutil.which("curl")
    if curl_path:
        return call_chat_completions_with_curl(
            curl_path=curl_path,
            base_url=base_url,
            api_key=api_key,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            hard_timeout=hard_timeout,
            extra_body=extra_body,
        )

    return call_chat_completions_with_python_worker(
        base_url=base_url,
        api_key=api_key,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        hard_timeout=hard_timeout,
        extra_body=extra_body,
    )


def call_chat_completions_with_curl(
    *,
    curl_path: str,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    hard_timeout: int,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra = validate_extra_body(extra_body or {})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    payload.update(extra)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    with tempfile.TemporaryFile(mode="w+b") as header_file:
        header_file.write(f"Authorization: Bearer {api_key}\nContent-Type: application/json\n".encode("utf-8"))
        header_file.flush()
        header_file.seek(0)
        try:
            completed = subprocess.run(
                [
                    curl_path,
                    "--silent",
                    "--show-error",
                    "--http1.1",
                    "--max-time",
                    str(hard_timeout),
                    "--request",
                    "POST",
                    "--header",
                    f"@/dev/fd/{header_file.fileno()}",
                    "--data-binary",
                    "@-",
                    "--write-out",
                    "\n%{http_code}",
                    base_url,
                ],
                input=data,
                capture_output=True,
                timeout=hard_timeout + 5,
                pass_fds=(header_file.fileno(),),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderCallError(
                f"HardTimeoutError: request exceeded {hard_timeout}s total deadline",
                retryable=True,
            ) from exc

    body, separator, status_text = completed.stdout.rpartition(b"\n")
    try:
        status_code = int(status_text) if separator else 0
    except ValueError:
        status_code = 0
    if completed.returncode == 28:
        raise ProviderCallError(
            f"HardTimeoutError: request exceeded {hard_timeout}s total deadline",
            retryable=True,
        )
    if status_code >= 400:
        excerpt = body.decode("utf-8", errors="replace")[:1000]
        raise ProviderCallError(
            f"HTTPError {status_code}: {excerpt}",
            retryable=status_code in {408, 409, 429, 500, 502, 503, 504},
        )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", errors="replace")[:500]
        raise ProviderCallError(
            f"CurlError {completed.returncode}: {stderr}",
            retryable=True,
        )
    if extra.get("stream"):
        try:
            return parse_streaming_chat_completions(body)
        except (ValueError, json.JSONDecodeError) as exc:
            raise ProviderCallError("Provider returned invalid SSE JSON", retryable=True) from exc
    try:
        response = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ProviderCallError("Provider returned invalid JSON", retryable=True) from exc
    if not isinstance(response, dict):
        raise ProviderCallError("Provider returned no response object", retryable=True)
    return response


def call_chat_completions_with_python_worker(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    timeout: int,
    hard_timeout: int,
    extra_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = {
        "base_url": base_url,
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        "extra_body": extra_body or {},
    }
    child_env = os.environ.copy()
    child_env["CRK2_CHILD_API_KEY"] = api_key
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--single-request-worker"],
            input=json.dumps(envelope, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=hard_timeout,
            env=child_env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProviderCallError(
            f"HardTimeoutError: request exceeded {hard_timeout}s total deadline",
            retryable=True,
        ) from exc

    if completed.returncode != 0:
        raise ProviderCallError(
            f"Provider worker exited with code {completed.returncode}",
            retryable=True,
        )
    try:
        worker_result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ProviderCallError("Provider worker returned invalid JSON", retryable=True) from exc
    if not worker_result.get("ok"):
        raise ProviderCallError(
            str(worker_result.get("error") or "Provider worker failed"),
            retryable=bool(worker_result.get("retryable")),
        )
    response = worker_result.get("response")
    if not isinstance(response, dict):
        raise ProviderCallError("Provider worker returned no response object", retryable=True)
    return response


def single_request_worker_main() -> int:
    try:
        envelope = json.loads(sys.stdin.read())
        api_key = os.environ.get("CRK2_CHILD_API_KEY", "")
        if not api_key:
            raise ValueError("Missing child API key")
        response = call_chat_completions(
            base_url=str(envelope["base_url"]),
            api_key=api_key,
            model=str(envelope["model"]),
            messages=envelope["messages"],
            temperature=float(envelope["temperature"]),
            max_tokens=int(envelope["max_tokens"]),
            timeout=int(envelope["timeout"]),
            extra_body=envelope.get("extra_body") or {},
        )
        result = {"ok": True, "response": response}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        result = {
            "ok": False,
            "error": f"HTTPError {exc.code}: {body[:1000]}",
            "retryable": exc.code in {408, 409, 429, 500, 502, 503, 504},
        }
    except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        result = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "retryable": True,
        }
    except Exception as exc:
        result = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "retryable": False,
        }
    sys.stdout.write(json.dumps(result, ensure_ascii=False))
    return 0


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    raise ValueError("No assistant content found in API response")


def ensure_not_truncated(response: dict[str, Any]) -> None:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("No completion choice found in API response")
    reason = str(choices[0].get("finish_reason") or "")
    if reason == "length":
        raise LengthFinishError("finish_reason=length")
    if not reason:
        raise ValueError("finish_reason is missing from API response")
    if reason != "stop":
        raise ValueError(f"unexpected finish_reason={reason}")


def run_one(
    row: dict[str, Any],
    args: argparse.Namespace,
    api_key_selector: ApiKeySelector | str,
    limiter: RateLimiter,
) -> dict[str, Any]:
    rid = request_id(row)
    fingerprint = request_fingerprint(row)
    messages = parse_messages(row)
    selector = (
        api_key_selector
        if isinstance(api_key_selector, ApiKeySelector)
        else ApiKeySelector(api_key_selector)
    )
    last_error = ""
    credential_role = "preferred"
    attempt = 0
    while attempt <= args.max_retries:
        api_key, credential_role = selector.current()
        try:
            limiter.wait()
            call_args = {
                "base_url": args.base_url,
                "api_key": api_key,
                "model": args.model,
                "messages": messages,
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
                "timeout": args.timeout,
                "extra_body": getattr(args, "extra_body", {}),
            }
            hard_timeout = int(getattr(args, "hard_timeout", 0) or 0)
            if hard_timeout > 0:
                response = call_chat_completions_with_hard_timeout(
                    **call_args,
                    hard_timeout=hard_timeout,
                )
            else:
                response = call_chat_completions(**call_args)
            ensure_not_truncated(response)
            return {
                "ok": True,
                "request_id": rid,
                "input_fingerprint": fingerprint,
                "response": extract_content(response),
                "raw_response": response,
                "credential_role": credential_role,
                "user_defined_params": row.get("user_defined_params") or row.get("passParams") or row.get("params") or {},
            }
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = f"HTTPError {exc.code}: {body[:1000]}"
            retryable = exc.code in {408, 409, 429, 500, 502, 503, 504}
        except LengthFinishError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            retryable = False
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            retryable = True
        except ProviderCallError as exc:
            last_error = str(exc)
            retryable = exc.retryable
        if (
            credential_role == "preferred"
            and selector.fallback_configured
            and is_model_access_denied(last_error)
        ):
            selector.activate_fallback()
            continue
        if attempt >= args.max_retries or not retryable:
            break
        sleep_s = min(args.retry_max_sleep, args.retry_base_sleep * (2**attempt))
        time.sleep(sleep_s)
        attempt += 1
    return {
        "ok": False,
        "request_id": rid,
        "input_fingerprint": fingerprint,
        "error": last_error,
        "credential_role": credential_role,
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
    parser.add_argument(
        "--fallback-api-key-env",
        default="",
        help="Optional fallback key environment variable, used only after Model.AccessDenied.",
    )
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--rpm", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--timeout", type=int, default=None)
    parser.add_argument(
        "--hard-timeout",
        type=int,
        default=None,
        help="Total per-attempt deadline in seconds. Defaults to --timeout; use 0 to disable subprocess isolation.",
    )
    parser.add_argument("--extra-body-json", default="", help="JSON object merged into the provider request payload.")
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
    args.timeout = args.timeout if args.timeout is not None else int(cfg.get("timeout", 300))
    args.hard_timeout = args.hard_timeout if args.hard_timeout is not None else int(cfg.get("hard_timeout", args.timeout))
    args.extra_body = parse_extra_body(args.extra_body_json)
    args.failed = args.failed or args.output.with_suffix(".failed.jsonl")

    env_names = [args.api_key_env] if args.api_key_env else ["BAILIAN_API_KEY", "DASHSCOPE_API_KEY"]
    api_key = next((os.environ.get(name) for name in env_names if os.environ.get(name)), "")
    if not api_key:
        raise SystemExit(f"Missing API key. Set one of: {', '.join(env_names)}")
    fallback_env_names = (
        [args.fallback_api_key_env]
        if args.fallback_api_key_env
        else ["BAILIAN_API_KEY_FALLBACK", "DASHSCOPE_API_KEY_FALLBACK"]
    )
    fallback_api_key = next(
        (os.environ.get(name) for name in fallback_env_names if os.environ.get(name)),
        "",
    )
    api_key_selector = ApiKeySelector(api_key, fallback_api_key)

    input_rows = list(iter_jsonl(args.input))
    expected_fingerprints = {request_id(row): request_fingerprint(row) for row in input_rows}

    repair_report = {"valid": 0, "invalid": 0, "invalid_reasons": {}}
    if not args.no_resume and not args.no_repair_output:
        repair_report = repair_output_for_resume(
            args.output,
            args.invalid_output,
            allow_length_finish=args.allow_length_finish,
            expected_fingerprints=expected_fingerprints,
        )
        if repair_report["invalid"]:
            print(json.dumps({"repair_output": str(args.output), **repair_report}, ensure_ascii=False))

    done = set() if args.no_resume else load_done_ids(args.output, expected_fingerprints=expected_fingerprints)
    rows = []
    for idx, row in enumerate(input_rows):
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
        futures = [pool.submit(run_one, row, args, api_key_selector, limiter) for row in rows]
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

    print(
        json.dumps(
            {
                "input": str(args.input),
                "output": str(args.output),
                "failed": str(args.failed),
                "invalid_output": str(args.invalid_output) if args.invalid_output else None,
                "submitted": len(rows),
                "ok": ok_count,
                "failed_count": fail_count,
                "resume_done": len(done),
                "repair": repair_report,
                "credential_policy": {
                    "fallback_configured": api_key_selector.fallback_configured,
                    "fallback_activated": api_key_selector.fallback_activated,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    if sys.argv[1:] == ["--single-request-worker"]:
        raise SystemExit(single_request_worker_main())
    main()
