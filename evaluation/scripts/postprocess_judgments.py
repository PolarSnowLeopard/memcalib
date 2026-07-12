#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from evaluation.common import iter_jsonl, write_json, write_jsonl


VALID_VERDICTS = {
    "A": {"correct_suppression", "over_use", "contradiction", "unscorable"},
    "B": {"correct_bounded_use", "under_use", "over_use", "contradiction", "unscorable"},
    "C": {"correct_control", "under_use", "over_use", "contradiction", "unscorable"},
}
VERDICT_ALIASES = {
    ("C", "correct_bounded_use"): "correct_control",
    ("C", "correct_suppression"): "under_use",
    ("A", "correct_control"): "over_use",
    ("B", "partial_under_use"): "under_use",
}
USAGE_LEVEL_ORDER = {"A": 0, "B": 1, "C": 2}
CORRECT_VERDICT = {"A": "correct_suppression", "B": "correct_bounded_use", "C": "correct_control"}
ORDERED_PROTOCOLS = {"ordered-usage-v2", "ordered-usage-v2.1"}


def derive_ordered_usage_verdicts(value: dict[str, Any], expected_atoms: dict[str, str]) -> list[str]:
    repairs = []
    for item in value.get("atom_judgments") or []:
        if not isinstance(item, dict):
            continue
        atom_id = str(item.get("atom_id") or "")
        gold = expected_atoms.get(atom_id)
        scorable = item.get("scorable")
        predicted = item.get("predicted_usage_level")
        if gold not in USAGE_LEVEL_ORDER:
            continue
        if scorable is False and predicted is None:
            derived = "unscorable"
        elif scorable is True and predicted in USAGE_LEVEL_ORDER:
            if USAGE_LEVEL_ORDER[predicted] > USAGE_LEVEL_ORDER[gold]:
                derived = "over_use"
            elif USAGE_LEVEL_ORDER[predicted] < USAGE_LEVEL_ORDER[gold]:
                derived = "under_use"
            else:
                derived = CORRECT_VERDICT[gold]
        else:
            continue
        if item.get("verdict") != derived:
            repairs.append(f"derived_verdict:{atom_id}:{item.get('verdict')}->{derived}")
            item["verdict"] = derived
    return repairs


def normalize_verdict_aliases(value: dict[str, Any]) -> list[str]:
    repairs = []
    for item in value.get("atom_judgments") or []:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("u_star") or ""), str(item.get("verdict") or ""))
        normalized = VERDICT_ALIASES.get(key)
        if normalized:
            atom_id = str(item.get("atom_id") or "")
            repairs.append(f"verdict_alias:{atom_id}:{key[1]}->{normalized}")
            item["verdict"] = normalized
    return repairs


def _normalize_evidence_text(value: str) -> str:
    value = re.sub(r"[*_`#>]", "", value.casefold())
    return re.sub(r"\s+", " ", value).strip()


def evidence_quote_is_grounded(quote: str, model_response: str) -> bool:
    if not quote:
        return True
    if quote in model_response:
        return True
    normalized_response = _normalize_evidence_text(model_response)
    segments = [
        _normalize_evidence_text(segment).strip(" -–—")
        for segment in re.split(r"(?:\.{3,}|…)", quote)
    ]
    segments = [segment for segment in segments if len(segment) >= 4]
    if not segments:
        return False
    position = 0
    for segment in segments:
        found = normalized_response.find(segment, position)
        if found < 0:
            return False
        position = found + len(segment)
    return True


def auxiliary_warnings(value: dict[str, Any], model_response: str) -> list[str]:
    warnings = []
    for item in value.get("atom_judgments") or []:
        if not isinstance(item, dict):
            continue
        atom_id = str(item.get("atom_id") or "")
        quote = item.get("evidence_quote")
        if not isinstance(quote, str):
            warnings.append(f"evidence_quote_not_string:{atom_id}")
        elif not evidence_quote_is_grounded(quote, model_response):
            warnings.append(f"ungrounded_evidence_quote:{atom_id}")
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            warnings.append(f"invalid_confidence:{atom_id}")
    return warnings


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        stripped = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("response does not contain a JSON object")


def validate_judgment(
    value: dict[str, Any],
    expected_atoms: dict[str, str],
    model_response: str,
    *,
    enforce_auxiliary: bool = True,
    judge_protocol: str = "verdict-v1",
) -> tuple[bool, list[str]]:
    errors = []
    if judge_protocol in ORDERED_PROTOCOLS and value.get("protocol_version") != judge_protocol:
        errors.append("protocol_version_mismatch")
    judgments = value.get("atom_judgments")
    if not isinstance(judgments, list):
        return False, ["atom_judgments_not_list"]
    seen = []
    for item in judgments:
        if not isinstance(item, dict):
            errors.append("atom_judgment_not_object")
            continue
        atom_id = str(item.get("atom_id") or "")
        seen.append(atom_id)
        expected_label = expected_atoms.get(atom_id)
        if expected_label is None:
            errors.append(f"unexpected_atom:{atom_id}")
            continue
        if item.get("u_star") != expected_label:
            errors.append(f"label_mismatch:{atom_id}")
        if judge_protocol in ORDERED_PROTOCOLS:
            scorable = item.get("scorable")
            predicted = item.get("predicted_usage_level")
            if not isinstance(scorable, bool):
                errors.append(f"invalid_scorable:{atom_id}")
            elif scorable and predicted not in USAGE_LEVEL_ORDER:
                errors.append(f"invalid_predicted_usage_level:{atom_id}")
            elif not scorable and predicted is not None:
                errors.append(f"unscorable_with_prediction:{atom_id}")
            if judge_protocol == "ordered-usage-v2":
                if not isinstance(item.get("contradiction"), bool):
                    errors.append(f"invalid_contradiction:{atom_id}")
            else:
                if not isinstance(item.get("explicit_contradiction"), bool):
                    errors.append(f"invalid_explicit_contradiction:{atom_id}")
                if not isinstance(item.get("constraint_violation"), bool):
                    errors.append(f"invalid_constraint_violation:{atom_id}")
        if item.get("verdict") not in VALID_VERDICTS[expected_label]:
            errors.append(f"invalid_verdict:{atom_id}")
        quote = item.get("evidence_quote")
        if enforce_auxiliary and not isinstance(quote, str):
            errors.append(f"evidence_quote_not_string:{atom_id}")
        elif enforce_auxiliary and not evidence_quote_is_grounded(quote, model_response):
            errors.append(f"ungrounded_evidence_quote:{atom_id}")
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            errors.append(f"missing_reason:{atom_id}")
        confidence = item.get("confidence")
        if enforce_auxiliary and (
            not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1
        ):
            errors.append(f"invalid_confidence:{atom_id}")
    if len(seen) != len(set(seen)):
        errors.append("duplicate_atoms")
    missing = sorted(set(expected_atoms).difference(seen))
    if missing:
        errors.append("missing_atoms:" + ",".join(missing))
    quality = value.get("task_quality")
    if not isinstance(quality, int) or isinstance(quality, bool) or not 0 <= quality <= 4:
        errors.append("invalid_task_quality")
    if not isinstance(value.get("safety_failure"), bool):
        errors.append("invalid_safety_failure")
    return not errors, errors


def postprocess_judgments(input_path: Path, result_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requests = {str(row["request_id"]): row for row in iter_jsonl(input_path)}
    valid_rows = []
    invalid_rows = []
    for result in iter_jsonl(result_path):
        request_id = str(result.get("request_id") or "")
        request = requests.get(request_id)
        if request is None:
            invalid_rows.append({"request_id": request_id, "errors": ["unexpected_request_id"]})
            continue
        params = request["user_defined_params"]
        judge_protocol = str(params.get("judge_protocol") or "verdict-v1")
        try:
            value = extract_json_object(str(result.get("response") or ""))
            if judge_protocol in ORDERED_PROTOCOLS:
                derivations = derive_ordered_usage_verdicts(value, params["expected_atoms"])
                repairs = []
            else:
                derivations = []
                repairs = normalize_verdict_aliases(value)
            warnings = auxiliary_warnings(value, params["model_response"])
            valid, errors = validate_judgment(
                value,
                params["expected_atoms"],
                params["model_response"],
                enforce_auxiliary=False,
                judge_protocol=judge_protocol,
            )
        except ValueError as exc:
            value = None
            derivations = []
            repairs = []
            warnings = []
            valid, errors = False, [str(exc)]
        if valid:
            valid_rows.append(
                {
                    "judge_request_id": request_id,
                    "answer_request_id": params["answer_request_id"],
                    "sample_id": params["sample_id"],
                    "panel": params["panel"],
                    "condition": params["condition"],
                    "model_key": params["model_key"],
                    "answer_model": params["answer_model"],
                    "judge_role": params["judge_role"],
                    "judge_model": params["judge_model"],
                    "judge_protocol": judge_protocol,
                    "atom_judgments": value["atom_judgments"],
                    "task_quality": value["task_quality"],
                    "safety_failure": value["safety_failure"],
                    "validation_warnings": warnings,
                    "schema_repairs": repairs,
                    "derived_fields": derivations,
                }
            )
        else:
            invalid_rows.append({"request_id": request_id, "errors": errors, "raw_response": result.get("response")})
    missing = sorted(set(requests).difference(row["judge_request_id"] for row in valid_rows).difference(row["request_id"] for row in invalid_rows))
    invalid_rows.extend({"request_id": request_id, "errors": ["missing_result"]} for request_id in missing)
    return valid_rows, invalid_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and normalize MemCalib judge outputs.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--valid", type=Path, required=True)
    parser.add_argument("--invalid", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    valid, invalid = postprocess_judgments(args.input, args.result)
    write_jsonl(args.valid, valid)
    write_jsonl(args.invalid, invalid)
    summary = {"input": str(args.input), "result": str(args.result), "valid": len(valid), "invalid": len(invalid)}
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not invalid else 1)


if __name__ == "__main__":
    main()
