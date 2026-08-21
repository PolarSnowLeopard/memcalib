from __future__ import annotations

from evaluation.scripts.prepare_primus_model_request_template import convert_rows


def test_convert_rows_changes_only_model_identity() -> None:
    source = [
        {
            "request_id": "answer:claude-opus-5:full_memory:sample-1",
            "prompt": [{"role": "user", "content": "locked prompt"}],
            "user_defined_params": {
                "condition": "full_memory",
                "expected_model": "claude-opus-5",
                "model_key": "claude-opus-5",
                "sample_id": "sample-1",
                "stage": "answer",
            },
        }
    ]

    converted = convert_rows(
        source,
        source_key="claude-opus-5",
        target_key="claude-sonnet-4-6",
        target_model="claude-sonnet-4-6",
    )

    assert converted[0]["request_id"] == (
        "answer:claude-sonnet-4-6:full_memory:sample-1"
    )
    assert converted[0]["prompt"] == source[0]["prompt"]
    assert converted[0]["user_defined_params"]["sample_id"] == "sample-1"
    assert converted[0]["user_defined_params"]["expected_model"] == (
        "claude-sonnet-4-6"
    )
    assert converted[0]["user_defined_params"]["model_key"] == (
        "claude-sonnet-4-6"
    )
    assert source[0]["user_defined_params"]["expected_model"] == "claude-opus-5"
