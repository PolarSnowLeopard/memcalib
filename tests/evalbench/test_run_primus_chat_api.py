from __future__ import annotations

from evaluation.scripts.run_primus_chat_api import build_payload, parse_response


def test_build_payload_preserves_messages_and_generation_contract() -> None:
    request = {
        "request_id": "answer:model:full_memory:sample",
        "prompt": [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "question"},
        ],
    }
    payload = build_payload(
        request,
        model="claude-opus-5",
        seed=42,
        max_tokens=8192,
        app="all_medical",
        tag="all_medical",
        category="医疗",
        user_id="user",
        access_key="secret",
        quota_id="quota",
    )
    assert payload["prompt"] == request["prompt"]
    assert payload["app"] == "all_medical"
    assert payload["tag"] == "all_medical"
    assert payload["category"] == "医疗"
    assert payload["params"] == {
        "temperature": 1.0,
        "max_tokens": 8192,
    }


def test_parse_response_supports_openai_completion() -> None:
    text, finish, usage = parse_response(
        {
            "code": 0,
            "data": {
                "finish_reason": "stop",
                "completion": {
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": "answer"},
                        }
                    ],
                    "usage": {"completion_tokens": 3},
                },
            },
        }
    )
    assert (text, finish) == ("answer", "stop")
    assert usage == {"completion_tokens": 3}


def test_parse_response_supports_gemini_completion() -> None:
    text, finish, _ = parse_response(
        {
            "data": {
                "completion": {
                    "candidates": [
                        {
                            "finishReason": "STOP",
                            "content": {"parts": [{"text": "gemini answer"}]},
                        }
                    ]
                }
            }
        }
    )
    assert (text, finish) == ("gemini answer", "stop")


def test_parse_response_supports_openai_responses_output() -> None:
    text, finish, _ = parse_response(
        {
            "data": {
                "finish_reason": "stop",
                "completion": {
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "GPT answer"}
                            ],
                        }
                    ]
                },
            }
        }
    )
    assert (text, finish) == ("GPT answer", "stop")
