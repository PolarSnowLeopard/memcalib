#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, norm_text, portable_path
from memcalib_v24_coding_common import V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


AUDIT_DIR = V24_DIR / "audit"
DEFAULT_INPUT = AUDIT_DIR / "memcalib_v241_curated_residual_554.jsonl"
DEFAULT_CONSENSUS = (
    AUDIT_DIR / "memcalib_v241_curated_residual_consensus_554.strict.jsonl"
)
DEFAULT_ADJUDICATED = (
    AUDIT_DIR / "memcalib_v241_curated_residual_adjudicated_80.jsonl"
)
DEFAULT_QWEN_STRICT = (
    AUDIT_DIR
    / "memcalib_v241_curated_residual_adjudicated_qc_qwenmax_80.strict.jsonl"
)
DEFAULT_DEEPSEEK_STRICT = (
    AUDIT_DIR
    / "memcalib_v241_curated_residual_adjudicated_qc_deepseek_80.strict.jsonl"
)
DEFAULT_OUTPUT = AUDIT_DIR / "memcalib_v241_curated_residual_final_554.jsonl"


OVERRIDES: dict[str, dict[str, Any]] = {
    "crk2_v2_raw_coding_55d32777c2f91f3e": {
        "family": "recommendation_or_evaluation",
        "question": (
            "In a component-based game-object architecture, recommend a pattern "
            "that lets sibling components obtain shared state such as world position "
            "during update and rendering without concrete cross-component "
            "dependencies. Explain the data flow and important build-time and "
            "runtime trade-offs in prose."
        ),
        "reference": (
            "Use a small owner- or entity-level context interface as the rendezvous "
            "point rather than letting components retain references to concrete "
            "siblings. A position component can publish the transform through that "
            "interface, while collision and rendering components request only the "
            "capabilities they need; rendering-specific state can be passed through "
            "a separate graphics context. The user requires data-driven composition "
            "to allow designers to create objects without programmer involvement. "
            "The component registry and capability interfaces should therefore be "
            "describable in data instead of being fixed in concrete inheritance. The "
            "user prioritizes minimizing source file dependencies to achieve faster "
            "compilation times. Keep the interfaces narrow, place implementation "
            "details behind them, and avoid headers that expose concrete component "
            "types. The user configures the build system to use unity builds for "
            "reducing header parsing overhead. Unity builds can improve clean-build "
            "time but may increase the cost of rebuilding a large translation unit, "
            "so they complement rather than replace careful dependency boundaries."
        ),
        "evidence": {
            "p2_a1": (
                "The user requires data-driven composition to allow designers to "
                "create objects without programmer involvement."
            ),
            "p3_a1": (
                "The user prioritizes minimizing source file dependencies to achieve "
                "faster compilation times."
            ),
            "v23_aux_b02_a01": (
                "The user configures the build system to use unity builds for "
                "reducing header parsing overhead."
            ),
        },
    },
    "crk2_v2_raw_coding_355b91459e361b52": {
        "family": "debugging_diagnosis",
        "question": (
            "A workplace date-conversion function turns an internal numeric date "
            "into Unix seconds, but the result does not match the civil date the "
            "user expects. Diagnose the discrepancy in prose. Identify the concrete "
            "representation and expectation supplied by the project context, then "
            "explain which epoch, day-index, time-zone, and UTC assumptions must be "
            "checked."
        ),
        "reference": (
            "The user's workplace represents dates as 'days since epoch' (DSE). The "
            "user expects DSE value 13878 to correspond to January 1, 2008. A plain "
            "multiplication by 86,400 is valid only after confirming that DSE and "
            "Unix time use the same epoch and the same zero- versus one-based day "
            "convention. The expected civil date must also be converted with an "
            "explicit time zone; otherwise local midnight and UTC midnight can "
            "differ by the zone offset. Finally, Unix time is commonly treated as a "
            "linear UTC count even though it does not represent UTC leap seconds. "
            "The diagnosis should therefore compare the documented DSE epoch and "
            "indexing rule, construct the expected instant in a named time zone, and "
            "only then compare Unix-second values."
        ),
        "evidence": {
            "p1_a1": (
                "The user's workplace represents dates as 'days since epoch' (DSE)."
            ),
            "p3_a1": (
                "The user expects DSE value 13878 to correspond to January 1, 2008."
            ),
        },
    },
    "crk2_v2_raw_coding_698941cbf11a4ea7": {
        "family": "implementation_plan",
        "question": (
            "Describe the observable behavior of a getBucketName helper that accepts "
            "clusterName and suffix inputs for a cloud-resource provisioning "
            "workflow. State the deployment context, the exact separator inherited "
            "from the original specification, the resulting format, and relevant "
            "input-handling considerations. Respond only in prose."
        ),
        "reference": (
            "The cloud infrastructure management system specifically targets Google "
            "Kubernetes Engine (GKE) clusters. The system requires Google Cloud "
            "Storage (GCS) buckets specifically for storing GKE cluster logs. The "
            "helper should preserve the two inputs in order and join clusterName and "
            "suffix with exactly one hyphen, yielding clusterName-suffix. The caller "
            "should validate that both components are non-empty and already satisfy "
            "the provider's bucket-name constraints; the helper itself has the "
            "narrow responsibility of deterministic formatting."
        ),
        "evidence": {
            "p1_a1": (
                "The cloud infrastructure management system specifically targets "
                "Google Kubernetes Engine (GKE) clusters."
            ),
            "p2_a1": (
                "The system requires Google Cloud Storage (GCS) buckets specifically "
                "for storing GKE cluster logs."
            ),
        },
    },
    "crk2_v2_raw_coding_657e634457cdb2cf": {
        "family": "implementation_plan",
        "question": (
            "Describe a concrete implementation plan for an n-back target counter. "
            "Preserve the existing starter interface from the project context, "
            "explain how positions are paired and counted, and cover empty or "
            "short-input behavior. Do not write executable code."
        ),
        "reference": (
            "The user has existing starter code defining the function signature "
            "`def count_targets(n, sequence):` for the n-back task. Preserve that "
            "interface. Compare each element that has a predecessor n positions "
            "earlier with that earlier element, and count every equal pair. An "
            "equivalent plan is to pair the original sequence with the sequence "
            "starting at offset n, evaluate equality for each pair, and sum the true "
            "results. This naturally counts chained targets, gives zero for an empty "
            "sequence or when n exceeds the sequence length, and does not require "
            "mutating the input. No additional length error should be introduced "
            "because the original task defines the count for any sequence containing "
            "zero or more targets."
        ),
        "evidence": {
            "p2_a1": (
                "The user has existing starter code defining the function signature "
                "`def count_targets(n, sequence):` for the n-back task."
            ),
        },
    },
    "crk2_v2_raw_coding_0731c5f2e7b0d174": {
        "family": "recommendation_or_evaluation",
        "question": (
            "A developer is considering changing the workstation used for long "
            "sessions to permit standing. Recommend a practical approach, explain "
            "how to evaluate candidate equipment, and discuss ergonomics, stability, "
            "adjustability, and cost trade-offs. Do not assume that replacing the "
            "entire workstation is acceptable."
        ),
        "reference": (
            "The user prefers to keep their workspace conversion simple and avoid "
            "requesting a new desk. The user currently uses a standard four-legged "
            "flat-surface desk at work. The user is operating under a limited budget "
            "for their standing desk conversion. A sensible first option is therefore "
            "a stable desktop riser with a separate keyboard surface, or a sturdy "
            "monitor or laptop riser paired with an external keyboard and pointing "
            "device. Check that the raised screen reaches roughly eye level, the "
            "keyboard remains near elbow height, the base fits the existing surface, "
            "and the structure does not wobble while typing. Test several heights "
            "and alternate between sitting and standing rather than standing all "
            "day. An occupational therapist or workplace ergonomics service can help "
            "evaluate posture and may provide equipment to try. A fixed stand is "
            "cheaper and simpler but less adjustable; a commercial sit-stand "
            "converter costs more and consumes desk area but makes transitions "
            "easier."
        ),
        "evidence": {
            "p1_a1": (
                "The user prefers to keep their workspace conversion simple and avoid "
                "requesting a new desk."
            ),
            "p2_a1": (
                "The user currently uses a standard four-legged flat-surface desk at "
                "work."
            ),
            "p3_a1": (
                "The user is operating under a limited budget for their standing desk "
                "conversion."
            ),
        },
    },
    "crk2_v2_raw_coding_47e9eabff7ae07f7": {
        "family": "recommendation_or_evaluation",
        "question": (
            "What approach should a Java web application use for an hourly background "
            "task? Explain lifecycle initialization, scheduling, request isolation, "
            "overlap control, failure handling, and the trade-off between an embedded "
            "scheduler and an external job service. Respond in prose."
        ),
        "reference": (
            "The user thinks in terms of Windows events and WaitOnMultipleObjects "
            "when designing concurrency. Map that mental model to a scheduler and "
            "job lifecycle rather than to a request thread. Do not trigger the "
            "background task from the first site visit; initialize its scheduler "
            "during web-container startup. A scheduler such as Quartz can be started "
            "through a ServletContextListener and use a fixed interval or cron-style "
            "trigger. Do not block incoming requests while the background task runs; "
            "execute it independently and use scheduler controls to prevent unwanted "
            "overlap. Record failures and "
            "retry or alert according to the job's idempotency. An embedded scheduler "
            "is straightforward for one application instance but needs coordination "
            "in a cluster; an external scheduler or queue adds infrastructure while "
            "providing clearer isolation and centralized execution."
        ),
        "evidence": {
            "p1_a1": (
                "The user thinks in terms of Windows events and "
                "WaitOnMultipleObjects when designing concurrency."
            ),
            "p2_a1": (
                "Do not trigger the background task from the first site visit; "
                "initialize its scheduler during web-container startup."
            ),
            "p2_a2": (
                "Do not block incoming requests while the background task runs; "
                "execute it independently and use scheduler controls to prevent "
                "unwanted overlap."
            ),
        },
    },
    "crk2_v2_raw_coding_cbb6ed3c5c7a0b34": {
        "family": "recommendation_or_evaluation",
        "question": (
            "Evaluate whether production SQL Server workloads should be virtualized. "
            "Give concrete technical considerations, explain how workload and storage "
            "behavior affect the decision, and identify the kinds of authoritative "
            "vendor material and measurements that should support the conclusion. "
            "Respond in prose."
        ),
        "reference": (
            "The user's organization plans to store all SQL Server data on a SAN as "
            "part of the virtualization initiative. That makes end-to-end storage "
            "latency, queue depth, path redundancy, and contention with other virtual "
            "machines central to the decision. The user recalls a speaker at the "
            "Heroes Happen Here launch event stating that virtualizing SQL Server is "
            "not recommended for production systems. Treat that recollection as a "
            "reason to investigate, not as authoritative evidence by itself. "
            "Virtualization can be suitable when the hypervisor, guest drivers, CPU "
            "and memory reservations, and storage design are supported and the actual "
            "OLTP, ETL, reporting, and recovery workloads meet service objectives. "
            "Compare the candidate environment with a bare-metal baseline under "
            "representative load and failure conditions. Cite the current SQL Server "
            "hardware-virtualization support policy, the hypervisor vendor's SQL "
            "Server deployment guidance, and validated hardware or driver support "
            "documentation. The main trade-off is operational flexibility and "
            "consolidation versus additional scheduling and I/O layers that can make "
            "performance isolation and diagnosis harder."
        ),
        "evidence": {
            "p1_a1": (
                "The user's organization plans to store all SQL Server data on a SAN "
                "as part of the virtualization initiative."
            ),
            "p2_a1": (
                "The user recalls a speaker at the Heroes Happen Here launch event "
                "stating that virtualizing SQL Server is not recommended for "
                "production systems."
            ),
        },
    },
    "crk2_v2_raw_coding_d99669074e4dded8": {
        "family": "implementation_plan",
        "question": (
            "Describe a concrete implementation approach for a Python helper that "
            "measures how long it takes to create a fresh graph and populate it with "
            "the edges of an input graph. Preserve the project-supplied interface and "
            "result contract, define the timing boundary, and discuss what the "
            "measurement does and does not include. Respond in prose."
        ),
        "reference": (
            "The user's environment has the NetworkX library pre-installed and "
            "available. Accept the input graph, record a start timestamp immediately "
            "before constructing a fresh NetworkX Graph, add the input graph's edges "
            "to the fresh graph, and record the end timestamp immediately after edge "
            "insertion. Graph timing functions must return the duration as a float "
            "value representing seconds. Subtract the start from the end and convert "
            "the elapsed value to seconds if the selected timing utility uses a "
            "smaller unit. This boundary includes graph initialization and edge "
            "loading but excludes caller setup and later analysis. Repeat the "
            "measurement when comparing performance because a single short timing "
            "sample is sensitive to scheduling and warm-up noise. The implementation "
            "need not copy unrelated node attributes unless the original contract is "
            "expanded to require them."
        ),
        "evidence": {
            "p1_a1": (
                "The user's environment has the NetworkX library pre-installed and "
                "available."
            ),
            "p2_a1": (
                "Graph timing functions must return the duration as a float value "
                "representing seconds."
            ),
        },
    },
    "crk2_v2_raw_coding_e688bbbdd3e5967b": {
        "family": "recommendation_or_evaluation",
        "question": (
            "Recommend how a Java persistence application should expose a small "
            "human-readable file data source through HQL and EntityManager. Explain "
            "which formats Hibernate can access, what persistence configuration can "
            "and cannot do, and the trade-offs of direct adapters versus importing "
            "the data into a relational store. Respond in prose."
        ),
        "reference": (
            "The user uses Hibernate in a Java application to access MS-SQL and MySQL "
            "databases. Hibernate queries entities through JDBC; persistence.xml does "
            "not contain a special mapping that turns an arbitrary text file into a "
            "table. The user prefers XML format for human-readable text file data "
            "sources due to data simplicity. Preserve XML as the interchange format "
            "if that preference matters, but parse and import it into a JDBC-backed "
            "relational or embedded database before querying it with HQL and "
            "EntityManager. The user requires data from human-readable text files to "
            "be displayed on application forms. An import step gives those forms a "
            "normal entity model, indexing, validation, and predictable query "
            "behavior. A file-specific JDBC or ODBC adapter can expose some delimited "
            "formats directly, but support and performance are driver-dependent and "
            "XML is not automatically supported. Configure persistence.xml for the "
            "chosen JDBC datasource and mapped entities, not for the raw file. The "
            "import approach adds synchronization work but is generally more robust "
            "than treating files as live database tables."
        ),
        "evidence": {
            "p1_a1": (
                "The user uses Hibernate in a Java application to access MS-SQL and "
                "MySQL databases."
            ),
            "p2_a1": (
                "The user prefers XML format for human-readable text file data sources "
                "due to data simplicity."
            ),
            "p3_a1": (
                "The user requires data from human-readable text files to be displayed "
                "on application forms."
            ),
        },
    },
}


def rows_by_id(path: Path) -> dict[str, dict[str, Any]]:
    rows = list(iter_jsonl(path))
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"record IDs must be non-empty and unique: {path}")
    return dict(zip(ids, rows, strict=True))


def a_supervision(atom: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(atom)
    predicate = str(updated.get("atomic_predicate") or updated.get("text") or "")
    updated["construction_target"] = {
        "task_goal": "Answer the current natural-language task directly.",
        "memory_role": "No answer influence.",
        "usage_boundary": "Ignore this atom when forming the answer.",
        "failure_direction": "Any answer change caused only by this atom is over-use.",
    }
    updated["counterfactual_contract"] = {
        "without_memory_behavior": "Produce the task-correct answer.",
        "with_memory_behavior": "Produce the same task-correct answer.",
        "observable_delta": "none",
        "minimal_evidence": [],
    }
    updated["usage_rubric"] = {
        "expected_answer_behavior": "The answer is counterfactually unchanged.",
        "memory_usage_weight": "none",
        "validity_scope": "The complete natural-language answer.",
        "correct_use": "Do not use this atom to alter the answer.",
        "under_use": "A has no under-use error.",
        "over_use": f"The answer is changed only because of this atom: {predicate}",
        "forbidden_memory_role": "This atom cannot justify any answer requirement.",
        "failure_direction": "Any atom-caused answer change is OPB.",
        "observable_checks": [
            "Removing this atom leaves the ideal answer unchanged.",
            "The answer contains no detail justified only by this atom.",
        ],
    }
    return updated


def scored_supervision(atom: dict[str, Any], evidence: str) -> dict[str, Any]:
    updated = copy.deepcopy(atom)
    label = str(updated.get("u_star") or "")
    action = str(updated.get("memory_action") or "")
    role = "supporting" if label == "B" else "controlling"
    if action == "correct":
        expected = (
            "The answer must explicitly reject the atom's proposed behavior and state "
            f"the supported correction: {evidence}"
        )
    else:
        expected = (
            "The answer must explicitly state or operationalize this same-atom "
            f"information: {evidence}"
        )
    updated["construction_target"] = {
        "task_goal": "Answer the current natural-language software task.",
        "memory_role": f"{role.capitalize()} answer influence.",
        "usage_boundary": "Use only the proposition supported by this atom.",
        "failure_direction": (
            f"Under-use omits or contradicts: {evidence} Over-use imports "
            "unsupported detail."
        ),
    }
    updated["counterfactual_contract"] = {
        "without_memory_behavior": (
            "The answer may omit or contradict this atom-specific information."
        ),
        "with_memory_behavior": expected,
        "observable_delta": evidence,
        "minimal_evidence": [evidence],
    }
    updated["usage_rubric"] = {
        "expected_answer_behavior": expected,
        "memory_usage_weight": role,
        "validity_scope": "The complete natural-language answer.",
        "correct_use": expected,
        "under_use": f"The answer omits or contradicts: {evidence}",
        "over_use": "The answer attributes details not entailed by this atom.",
        "forbidden_memory_role": "This atom cannot supply another atom's facts.",
        "failure_direction": (
            "Missing same-atom evidence is under-use; unsupported expansion is over-use."
        ),
        "observable_checks": [
            f"The answer explicitly contains or unambiguously paraphrases: {evidence}",
            "All attributed details are entailed by this atom or its correction.",
        ],
    }
    updated["v241_manual_same_atom_supervision"] = {
        "schema_version": "memcalib-v241-manual-same-atom-supervision-v1",
        "evidence_fingerprint": canonical_sha256(evidence),
    }
    return updated


def repair_record(record: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(record)
    reference = str(override["reference"])
    evidence = dict(override["evidence"])
    rebuilt: list[dict[str, Any]] = []
    scored_ids: set[str] = set()
    for atom in output.get("memories") or []:
        atom_id = str(atom.get("atom_id") or "")
        if atom.get("u_star") in {"B", "C"}:
            scored_ids.add(atom_id)
            if atom_id not in evidence:
                raise ValueError(f"missing manual evidence for {output['id']}:{atom_id}")
            if norm_text(evidence[atom_id]).casefold() not in norm_text(
                reference
            ).casefold():
                raise ValueError(
                    f"manual reference omits evidence for {output['id']}:{atom_id}"
                )
            rebuilt.append(scored_supervision(atom, evidence[atom_id]))
        else:
            rebuilt.append(a_supervision(atom))
    if scored_ids != set(evidence):
        raise ValueError(f"unexpected manual evidence keys for {output['id']}")

    prior = copy.deepcopy(output.get("coding_text_observability_revision") or {})
    output["schema_version"] = "crk-2-canonical-memory-v2.4.1"
    output["question"] = str(override["question"])
    output["source_answer"] = reference
    output["memories"] = rebuilt
    output.pop("v24_coding_independent_qc", None)
    output.pop("v241_alignment_consensus", None)
    output["coding_text_observability_revision"] = {
        "schema_version": "memcalib-v241-manual-finalization-v1",
        "task_family": override["family"],
        "question_contract": "natural_language_only_no_code_blocks",
        "input_record_fingerprint": canonical_sha256(record),
        "manual_override_scope": [
            "question",
            "reference_answer",
            "same_atom_supervision",
        ],
        "labels_and_actions_preserved": True,
        "memory_atoms_and_blocks_preserved": True,
        "prior_revision": prior,
    }
    return output


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Finalize the directly adjudicated MemCalib v2.4.1 residual."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--consensus", type=Path, default=DEFAULT_CONSENSUS)
    parser.add_argument("--adjudicated", type=Path, default=DEFAULT_ADJUDICATED)
    parser.add_argument("--qwen-strict", type=Path, default=DEFAULT_QWEN_STRICT)
    parser.add_argument("--deepseek-strict", type=Path, default=DEFAULT_DEEPSEEK_STRICT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    ordered = list(iter_jsonl(args.input))
    input_ids = [str(row.get("id") or "") for row in ordered]
    if "" in input_ids or len(input_ids) != len(set(input_ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    consensus = rows_by_id(args.consensus)
    adjudicated = rows_by_id(args.adjudicated)
    qwen_strict = set(rows_by_id(args.qwen_strict))
    deepseek_strict = set(rows_by_id(args.deepseek_strict))
    manually_blocked = set(adjudicated) - qwen_strict - deepseek_strict
    if manually_blocked != set(OVERRIDES):
        raise ValueError(
            "manual override set does not match current dual-QC residual: "
            f"{sorted(manually_blocked ^ set(OVERRIDES))}"
        )
    if set(consensus) & set(adjudicated):
        raise ValueError("consensus and adjudicated partitions overlap")
    if set(consensus) | set(adjudicated) != set(input_ids):
        raise ValueError("partitions do not cover the complete residual")

    final: dict[str, dict[str, Any]] = {}
    audit: list[dict[str, Any]] = []
    for record_id, record in consensus.items():
        final[record_id] = copy.deepcopy(record)
        audit.append(
            {
                "record_id": record_id,
                "channel": "dual_judge_strict",
                "input_fingerprint": canonical_sha256(record),
                "output_fingerprint": canonical_sha256(record),
            }
        )
    for record_id, record in adjudicated.items():
        if record_id in OVERRIDES:
            output = repair_record(record, OVERRIDES[record_id])
            channel = "manual_semantic_finalization"
        else:
            output = copy.deepcopy(record)
            channel = "at_least_one_independent_judge_strict"
        final[record_id] = output
        audit.append(
            {
                "record_id": record_id,
                "channel": channel,
                "qwen_strict": record_id in qwen_strict,
                "deepseek_strict": record_id in deepseek_strict,
                "input_fingerprint": canonical_sha256(record),
                "output_fingerprint": canonical_sha256(output),
            }
        )

    output_rows = [final[record_id] for record_id in input_ids]
    audit.sort(key=lambda row: input_ids.index(str(row["record_id"])))
    audit_output = args.audit_output or args.output.with_suffix(".audit.jsonl")
    manifest = args.manifest or args.output.with_suffix(".manifest.json")
    write_jsonl(args.output, output_rows)
    write_jsonl(audit_output, audit)
    channel_counts = Counter(str(row["channel"]) for row in audit)
    summary = {
        "schema_version": "memcalib-v241-curated-residual-final-summary-v1",
        "inputs": {
            "residual": {
                "path": portable_path(args.input),
                "sha256": file_sha256(args.input),
                "records": len(ordered),
            },
            "consensus": {
                "path": portable_path(args.consensus),
                "sha256": file_sha256(args.consensus),
                "records": len(consensus),
            },
            "adjudicated": {
                "path": portable_path(args.adjudicated),
                "sha256": file_sha256(args.adjudicated),
                "records": len(adjudicated),
            },
        },
        "counts": {
            "output": len(output_rows),
            "channels": dict(sorted(channel_counts.items())),
            "manual_overrides": len(OVERRIDES),
        },
        "outputs": {
            "data": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "audit": {
                "path": portable_path(audit_output),
                "sha256": file_sha256(audit_output),
            },
        },
    }
    write_json(manifest, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
