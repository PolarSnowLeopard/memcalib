#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from importlib import import_module
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import (
    PAYLOAD_SCHEMA,
    V23_RELEASE,
    V24_DIR,
    applicable_atoms,
    locked_supervision_fingerprint,
    validate_revision_payload,
)
from utils import iter_jsonl, write_json, write_jsonl


POST = import_module("103_post_memcalib_v24_coding_rewrite")
LOCAL = import_module("107_repair_memcalib_v24_coding_residual")
DEFAULT_OUTPUT = V24_DIR / "memcalib_v24_coding_manual_adjudication_15.jsonl"
DEFAULT_AUDIT = DEFAULT_OUTPUT.with_suffix(".audit.jsonl")
DEFAULT_MANIFEST = DEFAULT_OUTPUT.with_suffix(".manifest.json")

OVERRIDES: dict[str, dict[str, str]] = {
    "crk2_v2_raw_coding_ee362d2562ac3552": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a natural-language plan for a column-value retrieval helper. "
            "Explain input validation, obtaining the available values through the "
            "provided abstraction, returning a read-only result, and surfacing "
            "invalid-input or unavailable-data failures without choosing a concrete "
            "API or container type."
        ),
        "reference": (
            "Validate that the column handle is usable, obtain the value count and "
            "value sequence through the abstraction available to the caller, expose "
            "the result without permitting unintended mutation, and report invalid "
            "input or unavailable data. The answer does not require a particular "
            "library, language feature, documentation format, or concrete container."
        ),
        "rationale": (
            "All retrieved atoms are A. The adjudicated task is answerable from the "
            "question and deliberately leaves their API, container, and style details "
            "without an answer footprint."
        ),
    },
    "crk2_v2_raw_coding_7baf18088b6bb0a2": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a natural-language implementation plan for a helper that "
            "constructs a repository-cloning operation from a supplied remote "
            "identity and branch. State the helper's inputs, returned output, and "
            "validation or failure behavior without prescribing its implementation "
            "language."
        ),
        "reference": (
            "The helper accepts the remote identity and branch, validates that both "
            "are non-empty, assembles the repository-cloning operation, returns it to "
            "the caller, and reports malformed inputs instead of producing an "
            "ambiguous operation."
        ),
        "rationale": (
            "The task exposes the operation contract but leaves the controlling "
            "implementation-language preference to the C atom."
        ),
    },
    "crk2_v2_raw_coding_890761db55ed3a17": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a natural-language design for a portable launcher that obtains "
            "its runtime path from a required configuration source, changes to a "
            "requested working directory, invokes a target entry point, and reports "
            "failures. Do not prescribe concrete file names, environment-variable "
            "names, argument conventions, or error literals."
        ),
        "reference": (
            "Validate that the configuration source exists and is readable, derive "
            "the runtime path from its contents, enter the requested working "
            "directory, invoke the target with caller-supplied options, and stop with "
            "a clear failure when a prerequisite is missing. The answer remains "
            "independent of any particular file name, variable name, shell option, "
            "or exact status literal."
        ),
        "rationale": (
            "All retrieved atoms are A. The revised launcher contract is complete "
            "without using their concrete file, option, preflight, or error details."
        ),
    },
    "crk2_v2_raw_coding_fa655c438f7b46bd": {
        "family": "debugging_diagnosis",
        "task_stem": (
            "Diagnose a data-layer anomaly and explain how to reveal the values bound "
            "to a generated update operation. Identify the applicable application "
            "stack, the observed persistence symptom, and an inspection approach "
            "without the question prescribing product versions or a logging policy."
        ),
        "reference": (
            "First reproduce the persistence symptom and capture the generated update "
            "at the application boundary. Enable parameter-binding diagnostics or an "
            "application-side JDBC inspection layer that is compatible with the "
            "actual stack, compare the bound values with the entity state and "
            "transaction lifecycle, and disable the diagnostic instrumentation after "
            "the fault is isolated."
        ),
        "rationale": (
            "The task makes the B/C environment and symptom useful while keeping the "
            "synthetic server-logging policy outside the required answer."
        ),
    },
    "crk2_v2_raw_coding_0b3787a0c8371c26": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe the user-visible plan for switching between two audio-output "
            "modes through an existing keyboard-triggered helper. Cover the requested "
            "interaction, state transition, success feedback, and failure behavior "
            "without selecting a helper implementation language or wrapper style."
        ),
        "reference": (
            "The existing helper should invoke an audio-switching operation from one "
            "keystroke, determine the current output mode, select the other supported "
            "mode, apply the change, and report whether the switch succeeded. If the "
            "audio service or requested output is unavailable, leave the current mode "
            "unchanged and report the failure."
        ),
        "rationale": (
            "The answer is scoped to user-visible behavior, so auxiliary Swift/HotKey "
            "and Objective-C wrapper preferences remain legitimately ignorable."
        ),
    },
    "crk2_v2_raw_coding_dde2ebe77fa58804": {
        "family": "implementation_plan",
        "task_stem": (
            "Provide a natural-language code-review plan for the target generator "
            "function. Explain how to assess its behavior and edge cases, then state "
            "how the review should be framed and ranked for the requesting developer "
            "without writing replacement code."
        ),
        "reference": (
            "Trace the generator's inputs, yielded values, termination condition, and "
            "edge cases; identify correctness and clarity issues; and rank findings by "
            "their effect on behavior before discussing style. Present the result as "
            "constructive kata feedback rather than as an unexplained replacement."
        ),
        "rationale": (
            "The review framing makes the two locked B context atoms observably useful "
            "without turning them into implementation constraints."
        ),
    },
    "crk2_v2_raw_coding_20079bbee3daf2eb": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a natural-language plan for adding a message-retrieval endpoint "
            "to an existing messaging REST API. Identify the project-compatible web "
            "stack, endpoint registration, retrieval component, response path, and "
            "failure handling without naming the stack in the question."
        ),
        "reference": (
            "Add a retrieval component for the message resource, connect its queryset "
            "and serializer, register it with the existing API router under the "
            "versioned route, and return normal validation, not-found, and server "
            "errors through the framework's response mechanism."
        ),
        "rationale": (
            "The task preserves the endpoint integration objective while leaving the "
            "framework identity to the controlling C atom."
        ),
    },
    "crk2_v2_raw_coding_4f784878d48ef697": {
        "family": "implementation_plan",
        "task_stem": (
            "Recommend built-in or integrated coding-assistance options for a "
            "developer moving to the target IDE. Compare completion, templates, and "
            "refactoring support, and calibrate the explanation to the developer's "
            "prior tooling experience without naming that experience in the question."
        ),
        "reference": (
            "Explain the target IDE's completion controls, built-in text macros and "
            "templates, shortcut configuration, and available refactoring commands. "
            "Set expectations that its refactoring coverage is narrower than advanced "
            "third-party tooling, and give a beginner enough navigation detail to try "
            "the built-in features first."
        ),
        "rationale": (
            "The recommendations answer the source task and make the two B persona "
            "facts useful for comparison depth and onboarding detail."
        ),
    },
    "crk2_v2_raw_coding_c41505b6a8a69549": {
        "family": "debugging_diagnosis",
        "task_stem": (
            "Diagnose a server-side page-resolution parser failure in a deployed web "
            "application. Explain which hosting configuration and runtime-version "
            "checks should be made, why relative application-root resolution can "
            "differ, and how to correct the deployment without the question naming "
            "the platform versions."
        ),
        "reference": (
            "Verify that the deployed folder is configured as an application in the "
            "web server rather than inheriting a parent application root. Create the "
            "application mapping if it is missing, select the compatible runtime "
            "version, confirm the application-pool identity, and then recheck how the "
            "application-root-relative path resolves."
        ),
        "rationale": (
            "The diagnosis preserves the parser-error task while the B/C atoms supply "
            "the environment and the local-versus-server observation."
        ),
    },
    "crk2_v2_raw_coding_dae99fe4ce884a4c": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a distribution plan that lets a non-developer run the target "
            "web application as a bundled standalone package. Explain dependency "
            "bundling, startup, persistence, updates, and failure reporting without "
            "the question naming the framework or a preferred deployment technology."
        ),
        "reference": (
            "Bundle the application, its language runtime, required libraries, web "
            "server, configuration, and data migration into an installer or portable "
            "package with one startup entry point. Keep writable data outside the "
            "immutable application bundle, validate prerequisites during installation, "
            "and provide clear startup and update failures for non-developer users."
        ),
        "rationale": (
            "The plan answers the packaging task, uses the B learning/dependency "
            "context, and leaves the server-oriented container preference irrelevant."
        ),
    },
    "crk2_v2_raw_coding_dca54ffdb0d5f142": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a natural-language plan for providing serial-console access to "
            "virtualized systems hosted in the target environment. Cover host and "
            "guest configuration, connection setup, boot and login behavior, and "
            "failure checks without naming versions or prescribing document style."
        ),
        "reference": (
            "Enable the guest's serial console, configure boot output when required, "
            "start a login service on the serial device, expose the virtual serial "
            "endpoint through the host, and connect from the client with compatible "
            "line settings. Validate permissions, device ownership, baud settings, "
            "and the distinction between boot messages and an interactive login."
        ),
        "rationale": (
            "The step-plan format is an explicit task instruction; the synthetic prose "
            "format preference is therefore A and has no answer footprint."
        ),
    },
    "crk2_v2_raw_coding_df65e7c3402d8f6c": {
        "family": "implementation_plan",
        "task_stem": (
            "Write a natural-language decision memo on whether and how to adopt "
            "test-driven development within an established personal workflow. Address "
            "maintenance value, API design value, adoption cost, and a bounded trial "
            "without the question stating the developer's current experience."
        ),
        "reference": (
            "Treat regression protection during refactoring and early API design as "
            "the main potential benefits. Compare those benefits with the cost of "
            "rewriting tests when designs change, retain effective iterative design "
            "practices, and run a bounded trial rather than adopting the method "
            "ideologically or rejecting it categorically."
        ),
        "rationale": (
            "The memo directly uses the two B workflow observations while leaving the "
            "synthetic categorical anti-TDD conclusion ignorable."
        ),
    },
    "crk2_v2_raw_coding_992efee0558d32ac": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a relational schema plan for flexible many-to-many tagging while "
            "retaining the system's existing organizational model. Cover entities, "
            "links, uniqueness, indexing, metadata, migration, and query tradeoffs "
            "without prescribing a storage representation."
        ),
        "reference": (
            "Use a normalized tag entity and a link relation between tags and items, "
            "enforce uniqueness at the appropriate scope, and index both lookup "
            "directions. Keep the existing organizational relation alongside tagging, "
            "migrate incrementally, and add denormalized counts only when measured read "
            "patterns justify their maintenance cost."
        ),
        "rationale": (
            "The task makes category overlap and preservation of the existing grouping "
            "observable while leaving the synthetic comma-separated representation A."
        ),
    },
    "crk2_v2_raw_coding_8025df8782ca0074": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe the natural-language implementation structure for a typed button "
            "story and its primary variant. Identify the required component interface, "
            "story construction pattern, arguments, interaction behavior, and failure "
            "checks without supplying their project-specific names or values."
        ),
        "reference": (
            "Define the component's typed properties for variant, label, and click "
            "handling; create a reusable story template; bind the primary story from "
            "that template; provide its arguments; and verify that the interaction "
            "delegates to the supplied handler. Type mismatches or missing required "
            "arguments should be surfaced before the story is used."
        ),
        "rationale": (
            "The task is scoped to the component story, so the global-decorator "
            "placement preference remains outside the answer."
        ),
    },
    "crk2_v2_raw_coding_dd17057b2b7f9f8b": {
        "family": "implementation_plan",
        "task_stem": (
            "Describe a natural-language plan for filtering a supplied collection of "
            "movie titles by a supplied keyword. Explain the comparison, iteration, "
            "result construction, empty-input behavior, and ordering guarantees "
            "without prescribing the comparison mode or implementation syntax."
        ),
        "reference": (
            "Normalize each title and the keyword to a common case for comparison, "
            "select titles containing the normalized keyword, construct the result "
            "with a list comprehension, preserve the input order, and return an empty "
            "list when there are no matches."
        ),
        "rationale": (
            "The B implementation preference and C comparison rule are observable; "
            "alphabetical sorting is neither requested nor used, so the Hard-A has no "
            "footprint."
        ),
    },
}


def record_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("record_id") or "")


def selection_rows(paths: list[Path]) -> tuple[list[str], dict[str, list[str]]]:
    ids: list[str] = []
    seen: set[str] = set()
    failures: dict[str, list[str]] = {}
    for path in paths:
        for row in iter_jsonl(path):
            item_id = record_id(row)
            if not item_id:
                raise ValueError(f"empty record ID in {path}")
            if item_id not in seen:
                seen.add(item_id)
                ids.append(item_id)
            details = [str(item) for item in row.get("errors") or []]
            details.extend(
                str(item)
                for item in row.get("v24_coding_independent_qc", {}).get(
                    "decision_reasons", []
                )
            )
            failures.setdefault(item_id, []).extend(details)
    return ids, failures


def payload_for(source: dict[str, Any], override: dict[str, str]) -> dict[str, Any]:
    footprints: list[dict[str, Any]] = []
    evidence_sentences: list[str] = []
    for atom in applicable_atoms(source):
        evidence = LOCAL.contract_evidence(atom)
        evidence_sentences.extend(evidence)
        footprints.append(
            {
                "atom_id": str(atom.get("atom_id") or ""),
                "u_star": atom.get("u_star"),
                "memory_action": atom.get("memory_action"),
                "required_answer_elements": evidence,
                "overuse_signals": [
                    str(atom.get("usage_rubric", {}).get("over_use") or "").strip()
                    or "The answer extends this requirement beyond its stated scope."
                ],
                "label_justification": str(atom.get("label_reason") or "").strip()
                or (
                    "The locked label reflects this requirement's bounded influence "
                    "on the natural-language answer."
                ),
            }
        )
    reference = " ".join(
        [override["reference"].strip(), *evidence_sentences]
    ).strip()
    return {
        "schema_version": PAYLOAD_SCHEMA,
        "record_id": str(source.get("id") or ""),
        "task_family": override["family"],
        "task_stem": override["task_stem"],
        "reference_answer": reference,
        "applicable_atom_footprints": footprints,
        "query_isolation_audit": [
            {
                "atom_id": item["atom_id"],
                "query_supplies_atom_value": False,
                "reason": (
                    "The question asks for the category of project-specific "
                    "information without supplying the atom's concrete value."
                ),
            }
            for item in footprints
        ],
        "self_check": {
            "all_applicable_atom_ids_exact": True,
            "locked_labels_actions_preserved": True,
            "query_does_not_restate_scored_memories": True,
            "answer_is_natural_language_only": True,
            "all_required_evidence_visible_in_reference_answer": True,
            "no_runtime_execution_needed_to_judge": True,
        },
    }


def params_for(source: dict[str, Any], family: str) -> dict[str, Any]:
    return {
        "record_id": source["id"],
        "source_record_fingerprint": canonical_sha256(source),
        "locked_supervision_fingerprint": locked_supervision_fingerprint(source),
        "memory_blocks_fingerprint": canonical_sha256(source.get("memory_blocks") or []),
        "task_family": family,
        "retry_round": "manual_adjudication",
        "retry_feedback_fingerprint": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize the manually adjudicated MemCalib v2.4 coding residual."
    )
    parser.add_argument("--benchmark", type=Path, default=V23_RELEASE)
    parser.add_argument(
        "--selection-jsonl", type=Path, action="append", default=[], required=True
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    sources = {
        str(record.get("id") or ""): record for record in iter_jsonl(args.benchmark)
    }
    ids, prior_failures = selection_rows(args.selection_jsonl)
    if set(ids) != set(OVERRIDES):
        raise ValueError(
            "manual override coverage mismatch: "
            f"missing={sorted(set(ids) - set(OVERRIDES))}, "
            f"extra={sorted(set(OVERRIDES) - set(ids))}"
        )

    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for item_id in ids:
        source = sources[item_id]
        override = OVERRIDES[item_id]
        params = params_for(source, override["family"])
        payload = payload_for(source, override)
        errors = validate_revision_payload(payload, source, params)
        if errors:
            raise ValueError(f"{item_id} payload invalid: {errors}")
        record, _ = POST.build_record(
            source,
            payload,
            params,
            f"v24_coding_manual_adjudication:{item_id}",
            deterministic_repairs=["manual_record_level_adjudication"],
        )
        errors = POST.validate_built_record(record, source, params)
        if errors:
            raise ValueError(f"{item_id} record invalid: {errors}")
        record["v24_manual_adjudication"] = {
            "schema_version": "memcalib-v24-coding-manual-adjudication-v1",
            "decision": "manual_adjudicated_strict",
            "rationale": override["rationale"],
            "prior_failure_reasons": list(
                dict.fromkeys(prior_failures.get(item_id, []))
            ),
            "labels_and_actions_changed": False,
            "deterministic_validators_passed": True,
        }
        output.append(record)
        audits.append(
            {
                "schema_version": "memcalib-v24-coding-manual-adjudication-audit-v1",
                "record_id": item_id,
                "source_record_fingerprint": canonical_sha256(source),
                "output_record_fingerprint": canonical_sha256(record),
                "rationale": override["rationale"],
                "prior_failure_reasons": list(
                    dict.fromkeys(prior_failures.get(item_id, []))
                ),
            }
        )

    write_jsonl(args.output, output)
    write_jsonl(args.audit, audits)
    manifest = {
        "schema_version": "memcalib-v24-coding-manual-adjudication-manifest-v1",
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
            },
            "selection": [
                {"path": portable_path(path), "sha256": file_sha256(path)}
                for path in args.selection_jsonl
            ],
        },
        "policy": {
            "generation_api_calls": 0,
            "judge_api_calls": 0,
            "labels_and_actions_changed": False,
            "deterministic_validators_required": True,
        },
        "counts": {
            "selected": len(ids),
            "manual_adjudicated_strict": len(output),
            "audit": len(audits),
        },
        "outputs": {
            "records": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "audit": {
                "path": portable_path(args.audit),
                "sha256": file_sha256(args.audit),
            },
        },
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
