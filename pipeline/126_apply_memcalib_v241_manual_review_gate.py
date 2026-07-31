#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import importlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from memcalib_v23_common import canonical_sha256, file_sha256, portable_path
from memcalib_v24_coding_common import V24_DIR
from utils import iter_jsonl, write_json, write_jsonl


finalizer = importlib.import_module("123_finalize_memcalib_v241_curated_residual")
alignment = importlib.import_module("110_audit_memcalib_v24_atom_alignment")

DEFAULT_CODING_INPUT = (
    V24_DIR / "v241" / "memcalib_v241_coding_complete_3750.jsonl"
)
DEFAULT_RELEASE_INPUT = (
    V24_DIR
    / "v241"
    / "release"
    / "memcalib_v241_multidomain_benchmark_15000.jsonl"
)
DEFAULT_RESERVE = (
    V24_DIR.parent
    / "crk2_v2_memory_benchmark_local_repaired3_attributed_complete_16195.jsonl"
)
DEFAULT_AUDIT = (
    V24_DIR / "v241" / "audit" / "memcalib_v241_manual_review_gate.audit.jsonl"
)
DEFAULT_MANIFEST = (
    V24_DIR
    / "v241"
    / "release"
    / "memcalib_v241_multidomain_benchmark_15000.manifest.json"
)

REMOVED_RECORD_ID = "crk2_v2_raw_coding_0731c5f2e7b0d174"
REPLACEMENT_RECORD_ID = "crk2_v2_raw_coding_e19cebbe74362259"


REFERENCE_UPDATES = {
    "crk2_v2_raw_coding_698941cbf11a4ea7": (
        "The cloud infrastructure management system specifically targets Google "
        "Kubernetes Engine (GKE) clusters. The system requires Google Cloud Storage "
        "(GCS) buckets specifically for storing GKE cluster logs. The helper should "
        "preserve the two inputs in order and join clusterName and suffix with exactly "
        "one hyphen, yielding clusterName-suffix. The caller should validate that both "
        "components are non-empty and already satisfy the provider's bucket-name "
        "constraints; the helper itself has the narrow responsibility of deterministic "
        "formatting."
    ),
    "crk2_v2_raw_coding_041ea662e9263b06": (
        "Use a damped force-directed model. For every observed interaction edge, use "
        "a spring attraction whose magnitude is k_a times the difference between the "
        "current distance and a positive desired distance. For repulsion, use an "
        "inverse-square force at short range, with a small distance floor to avoid "
        "division by zero. Do not evaluate that repulsion for every pair: at roughly "
        "one million users, an all-pairs step is quadratic and infeasible. Approximate "
        "long-range repulsion with a quadtree or Barnes-Hut method, and process the "
        "roughly ten million observed interactions as a sparse edge list. Start with "
        "small force constants, cap each displacement, apply velocity damping, and "
        "stop when movement falls below a threshold or a maximum iteration count is "
        "reached. Avoid min/max coordinate normalization because it reproduces the "
        "observed pattern in which low-activity nodes remain at the edges while dense "
        "nodes collapse centrally. Tune attraction, repulsion, damping, and the "
        "approximation tolerance on representative subgraphs before running the full "
        "layout, and report non-convergence or non-finite coordinates as failures."
    ),
    "crk2_v2_raw_coding_9f2a5d792f26fc2a": (
        "Use a template-based separation strategy. Rename the tracked environment "
        "configuration to a template such as config.php.sample and commit that "
        "template with defaults or placeholders. Keep the production configuration "
        "as an unversioned sibling in the working copy. During deployment or startup, "
        "check whether the active configuration exists; create it from the template "
        "only when it is absent, and never overwrite an existing local copy. Apply "
        "future schema changes to the tracked template while retaining "
        "environment-specific values only in the local file. This works with the "
        "production Subversion checkout and respects the decision not to use "
        "svn:ignore. If the template disappears, existing production configuration "
        "remains intact, but new deployments must fail clearly until the template is "
        "restored."
    ),
    "crk2_v2_raw_coding_0ef9607a46af8054": (
        "Place a thin wrapper at the canonical path in the shared directory. Because "
        "the machines use the same POSIX-compatible shell, the wrapper can use uname "
        "to identify the operating system and architecture, map that result to a "
        "platform-specific executable stored beside the wrapper, verify that the "
        "selected file exists and is executable, and then replace the wrapper process "
        "with that executable. The standardized Python installation makes a Python "
        "dispatcher possible, but a shell wrapper avoids starting a larger interpreter "
        "for this small decision. Updating the shared wrapper or replacing a "
        "platform-specific executable takes effect on the next invocation without "
        "alias reloads. This avoids a package-distribution workflow, which the user "
        "considers undesirable. Publish binaries under distinct OS-and-architecture "
        "names, replace them atomically only after qualification, and return a "
        "non-zero status with a clear unsupported-platform or missing-binary message "
        "when no matching executable is available."
    ),
    "crk2_v2_raw_coding_ce439ac2342e5ac6": (
        "Keep the existing flexible data-access path: construct the SqlConnection at "
        "runtime, use the caller-supplied connection string and dynamic query, and "
        "fill a DataSet without generating a fixed typed schema. A WinForms "
        "DataGridView cannot display the DataSet container without knowing which "
        "table to expose. Either assign the desired DataTable, such as the relevant "
        "entry in DataSet.Tables, directly to DataGridView.DataSource, or assign the "
        "DataSet to a BindingSource and set BindingSource.DataMember to the exact "
        "table name before assigning that BindingSource to the grid. Leave "
        "AutoGenerateColumns enabled so the columns follow the runtime schema. Do not "
        "call DataBind, because WinForms DataGridView has no ASP.NET-style DataBind "
        "method. "
        "If the grid remains empty, verify that the selected table exists, contains "
        "rows, and that binding is performed on the UI thread; report a missing table "
        "name rather than silently binding the wrong object."
    ),
    "crk2_v2_raw_coding_b4c6fd3607809601": (
        "The function accepts no arguments. Resolve the file named 'TM27 Sample "
        "Spectral Data.spdx' inside RESOURCES_DIRECTORY and load it with the colour "
        "library's SpectralDistribution_IESTM2714 class. Read the resulting spectral "
        "samples, compute the arithmetic mean of their values, find the wavelength "
        "associated with the maximum value, and return those two results as a tuple "
        "in that order. If the resource is missing, unreadable, malformed, or contains "
        "no spectral samples, stop and surface the corresponding load or validation "
        "failure rather than returning fabricated statistics."
    ),
    "crk2_v2_raw_coding_0f25f1dbb4e56078": (
        "On Ubuntu, os.path uses POSIX path rules, so it treats backslashes as ordinary "
        "characters and does not recognize a Windows drive prefix. Use the standard "
        "library ntpath module when the data being parsed follows Windows rules, even "
        "though the host is Linux and the runtime is Python 2.5. Represent a Windows "
        "path in Python source with a raw string or escaped backslashes so sequences "
        "such as backslash-t are not converted into control characters. With the "
        "intended path c:\\ttemp\\FILEPA~1.EXE, ntpath.basename yields FILEPA~1.EXE, "
        "and ntpath.splitdrive separates c: from the remaining path. Reject or handle "
        "empty and malformed input according to the caller's policy; no external "
        "dependency or host configuration change is required."
    ),
    "crk2_v2_raw_6a85c11f9300952b": (
        "In an 11-month-old, a rash concentrated in the diaper area can be irritant "
        "or allergic contact dermatitis, and Candida is another common possibility. "
        "Because the eruption is also widespread and appears ready to blister or "
        "bleed, the earlier contact-dermatitis diagnosis should not be treated as "
        "conclusive; broken skin can also become secondarily infected, and some viral "
        "illnesses can cause a generalized rash with enlarged lymph nodes. The lump "
        "behind the ear may be a reactive lymph node, but it needs to be interpreted "
        "with the rash and the child's overall condition. Arrange prompt pediatric "
        "reassessment rather than relying only on a soothing cream. Seek urgent care "
        "now for fever in an unwell child, lethargy, rapidly spreading blisters, "
        "significant pain, pus, mucosal involvement, breathing difficulty, or reduced "
        "drinking or urination. Until reviewed, use gentle cleansing, avoid new "
        "fragranced products, and do not apply medication to open skin unless a "
        "clinician recommends it."
    ),
    "crk2_v2_raw_83d0ec64551f902a": (
        "Growing or changing dark lesions and an itchy mole warrant prompt in-person "
        "assessment by a dermatologist; they cannot be classified reliably from a "
        "text description. A family history of skin cancer increases the importance "
        "of timely evaluation, but it does not by itself establish a diagnosis. Type "
        "1 diabetes broadens the differential because infection and impaired healing "
        "can alter skin lesions, yet it should not be used to dismiss the cancer "
        "concern. The clinician may examine the lesions with dermoscopy and decide "
        "whether biopsy and histopathology are needed. Seek more urgent care if there "
        "is rapid change, bleeding, ulceration, spreading redness, drainage, fever, "
        "or significant pain."
    ),
    "crk2_v2_raw_general_12a12f3253775f4d": (
        "Well-known Istanbul options include Hamdi Restaurant for charcoal-grilled "
        "regional kebabs, Şehzade Cağ Kebap for cağ kebab, Zübeyir Ocakbaşı for an "
        "ocakbaşı experience, and Dürümzade for casual dürüm. Quality and opening "
        "status can change, so check recent local reviews and reservations before "
        "travelling. Since the user is uneasy about spicy tomato-based sauces, ask "
        "for acısız (not spicy), request sauces on the side, and confirm the heat "
        "level with the restaurant; that concern need not exclude the strongest kebab "
        "venues because many preparations are not inherently hot."
    ),
}


def rows_by_id(path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows = list(iter_jsonl(path))
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError(f"record IDs must be non-empty and unique: {path}")
    return rows, dict(zip(ids, rows, strict=True))


def rebuild_block_text(
    blocks: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(atom.get("atom_id") or ""): atom for atom in atoms}
    rebuilt: list[dict[str, Any]] = []
    for block in blocks:
        atom_ids = [
            str(atom_id)
            for atom_id in block.get("atom_ids") or []
            if str(atom_id) in by_id
        ]
        if not atom_ids:
            continue
        output = copy.deepcopy(block)
        output["atom_ids"] = atom_ids
        output["memory_text"] = " ".join(
            str(by_id[atom_id].get("text") or "").strip() for atom_id in atom_ids
        )
        rebuilt.append(output)
    return rebuilt


def mark_review(
    record: dict[str, Any],
    *,
    issue: str,
    changes: list[str],
    input_fingerprint: str,
) -> None:
    record["v241_manual_review_gate"] = {
        "schema_version": "memcalib-v241-manual-review-gate-v1",
        "decision": "pass_after_manual_correction",
        "issue": issue,
        "changes": changes,
        "input_record_fingerprint": input_fingerprint,
    }


def update_reference(record: dict[str, Any], reference: str) -> dict[str, Any]:
    output = copy.deepcopy(record)
    before = canonical_sha256(record)
    output["source_answer"] = reference
    mark_review(
        output,
        issue="reference_answer_quality",
        changes=["reference_answer"],
        input_fingerprint=before,
    )
    return output


def repair_shared_shell_atom(record: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(record)
    before = canonical_sha256(record)
    rebuilt: list[dict[str, Any]] = []
    for atom in output.get("memories") or []:
        if atom.get("atom_id") != "p2_a1":
            rebuilt.append(copy.deepcopy(atom))
            continue
        updated = copy.deepcopy(atom)
        updated["text"] = (
            "All target platforms in the shared workspace use the same "
            "POSIX-compatible shell and provide standard operating-system "
            "identification utilities such as uname."
        )
        updated["atomic_predicate"] = (
            "Target platforms share a POSIX-compatible shell with uname available"
        )
        rebuilt.append(
            finalizer.scored_supervision(
                updated,
                (
                    "The wrapper can use the shared POSIX-compatible shell and uname "
                    "to detect the current operating system and architecture."
                ),
            )
        )
    output["memories"] = rebuilt
    output["memory_blocks"] = rebuild_block_text(
        list(output.get("memory_blocks") or []), rebuilt
    )
    output["source_answer"] = REFERENCE_UPDATES[str(output["id"])]
    mark_review(
        output,
        issue="atom_rubric_semantic_misalignment",
        changes=["atom_text", "same_atom_supervision", "memory_block", "reference_answer"],
        input_fingerprint=before,
    )
    return output


def remove_conflicting_hard_a(record: dict[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(record)
    before = canonical_sha256(record)
    removed = "v22_harda_01_a1"
    memories = [
        copy.deepcopy(atom)
        for atom in output.get("memories") or []
        if atom.get("atom_id") != removed
    ]
    if len(memories) + 1 != len(output.get("memories") or []):
        raise ValueError(f"expected exactly one conflicting atom in {output['id']}")
    output["memories"] = memories
    output["memory_blocks"] = rebuild_block_text(
        list(output.get("memory_blocks") or []), memories
    )
    mark_review(
        output,
        issue="query_entailed_hard_a_conflicted_with_required_failure_behavior",
        changes=["remove_conflicting_hard_a", "memory_blocks"],
        input_fingerprint=before,
    )
    return output


def build_replacement(
    reserve: dict[str, Any],
    removed: dict[str, Any],
) -> dict[str, Any]:
    if reserve.get("id") != REPLACEMENT_RECORD_ID:
        raise ValueError("unexpected reserve record")
    output = copy.deepcopy(reserve)
    reserve_memories = {
        str(atom.get("atom_id") or ""): copy.deepcopy(atom)
        for atom in reserve.get("memories") or []
    }
    if set(reserve_memories) != {"p1_a1", "p1_a2", "p3_a1"}:
        raise ValueError("replacement reserve must contain three reviewed core atoms")
    team_atom = reserve_memories["p1_a1"]
    team_atom["text"] = "The user works on a three-person development team."
    team_atom["atomic_predicate"] = "User works on a three-person team"
    team_atom["u_star"] = "C"
    team_atom["memory_action"] = "apply"
    team_atom = finalizer.scored_supervision(
        team_atom,
        "The hardware recommendation must be sized for a three-person team.",
    )
    php_atom = reserve_memories["p1_a2"]
    php_atom["text"] = "The user's primary development language is PHP."
    php_atom["atomic_predicate"] = "User develops primarily in PHP"
    php_atom["u_star"] = "B"
    php_atom["memory_action"] = "apply"
    php_atom = finalizer.scored_supervision(
        php_atom,
        (
            "The operating-environment and workload advice must account for the "
            "team's PHP stack."
        ),
    )
    hard_a_atom = finalizer.a_supervision(reserve_memories["p3_a1"])
    relevant = [team_atom, php_atom, hard_a_atom]
    retained_a = [
        copy.deepcopy(atom)
        for atom in removed.get("memories") or []
        if atom.get("u_star") == "A"
    ]
    if not retained_a:
        raise ValueError("removed record has no reusable retrieval-noise atoms")
    memories = relevant + retained_a
    core_block = {
        "parent_memory_id": "v241_manual_replacement_core",
        "raw_evidence": "manual review replacement core memories",
        "memory_text": " ".join(str(atom.get("text") or "") for atom in relevant),
        "source": "manual_review_replacement",
        "atom_ids": [str(atom.get("atom_id") or "") for atom in relevant],
        "atomization_notes": (
            "Core atoms from an attributed, deterministic-pass coding reserve record."
        ),
    }
    a_blocks = rebuild_block_text(
        list(removed.get("memory_blocks") or []), retained_a
    )
    output["schema_version"] = "crk-2-canonical-memory-v2.4.1"
    output["question"] = (
        "Recommend hardware-selection criteria for a dedicated continuous-integration "
        "machine. Address CPU, memory, storage, reliability, operating environment, "
        "and how to validate capacity for the expected workload. Respond in prose "
        "and avoid naming a particular CI product unless it is necessary."
    )
    output["source_answer"] = (
        "For a three-person PHP team, start with a modest, reliable current-generation "
        "machine rather than an enterprise server. Prioritize a fast SSD for checkout, "
        "dependency, and test I/O; enough capacity for retained build artifacts; and "
        "a modern multi-core CPU sized to the number of PHP test jobs that will run in "
        "parallel. Sixteen gigabytes of memory is a reasonable starting point for a "
        "single PHP build with its database and web stack, while 32 GB is justified "
        "when several isolated builds, containers, or database instances must run "
        "concurrently. Choose an operating system that supports the team's PHP "
        "runtime, database, and web dependencies, use wired networking and dependable "
        "storage, and arrange backup "
        "or reproducible replacement for configuration and artifacts. Measure a "
        "representative full build, peak parallel test run, and artifact-retention "
        "growth before buying more capacity. The recommendation should remain "
        "CI-product agnostic because the selected orchestration product does not by "
        "itself determine the hardware requirement."
    )
    output["memories"] = memories
    output["memory_blocks"] = [core_block, *a_blocks]
    output["longtail_block_revision"] = {
        "schema_version": "memcalib-v241-manual-review-replacement-longtail-v1",
        "target_block_count": len(output["memory_blocks"]),
        "target_atom_count": len(memories),
        "visible_block_policy": "3-20 deterministic long-tail",
        "reviewed_core_atoms_preserved": True,
        "retrieval_noise_reused_from_removed_record": True,
    }
    output["composite_block_revision"] = {
        "schema_version": "memcalib-v241-manual-review-replacement-composite-v1",
        "difficulty_level": "level_3",
        "source_atom_count": len(relevant),
        "target_atom_count": len(memories),
        "max_atoms_per_block": max(
            len(block.get("atom_ids") or []) for block in output["memory_blocks"]
        ),
        "model_facing_atom_boundaries_hidden": True,
    }
    output["coding_text_observability_revision"] = {
        "schema_version": "memcalib-v241-manual-finalization-v1",
        "task_family": "recommendation_or_evaluation",
        "question_contract": "natural_language_only_no_code_blocks",
        "input_record_fingerprint": canonical_sha256(reserve),
        "manual_override_scope": [
            "question",
            "reference_answer",
            "core_atomization_and_labels",
            "retrieval_noise_expansion",
        ],
        "labels_and_actions_preserved": False,
        "core_memory_propositions_preserved": True,
    }
    output["revision_release_admission"] = {
        "schema_version": "memcalib-v241-manual-review-replacement-admission-v1",
        "decision": "admitted_after_manual_review",
    }
    output["v241_manual_review_replacement"] = {
        "schema_version": "memcalib-v241-manual-review-replacement-v1",
        "removed_record_id": REMOVED_RECORD_ID,
        "replacement_record_id": REPLACEMENT_RECORD_ID,
        "reason": "removed record was ergonomics rather than software engineering",
        "reserve_input_fingerprint": canonical_sha256(reserve),
        "removed_input_fingerprint": canonical_sha256(removed),
    }
    return output


def apply_review_gate(
    rows: list[dict[str, Any]],
    reserve: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_id = {str(row.get("id") or ""): row for row in rows}
    all_targets = set(REFERENCE_UPDATES) | {
        REMOVED_RECORD_ID,
        "crk2_v2_raw_coding_db2be6712d26ab79",
    }
    domains = {str(row.get("domain") or "") for row in rows}
    required = (
        {
            record_id
            for record_id in all_targets
            if record_id.startswith("crk2_v2_raw_coding_")
        }
        if domains == {"coding"}
        else all_targets
    )
    missing = required - set(by_id)
    if missing:
        raise ValueError(f"review targets missing from release: {sorted(missing)}")
    if REPLACEMENT_RECORD_ID in by_id:
        raise ValueError("replacement record is already present")

    output: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for record in rows:
        record_id = str(record.get("id") or "")
        if record_id == REMOVED_RECORD_ID:
            updated = build_replacement(reserve, record)
            issue = "non_software_record_in_coding_domain"
        elif record_id == "crk2_v2_raw_coding_0ef9607a46af8054":
            updated = repair_shared_shell_atom(record)
            issue = "atom_rubric_semantic_misalignment"
        elif record_id == "crk2_v2_raw_coding_db2be6712d26ab79":
            updated = remove_conflicting_hard_a(record)
            issue = "query_entailed_hard_a_conflict"
        elif record_id in REFERENCE_UPDATES:
            updated = update_reference(record, REFERENCE_UPDATES[record_id])
            issue = "reference_answer_quality"
        else:
            output.append(copy.deepcopy(record))
            continue
        output.append(updated)
        audits.append(
            {
                "schema_version": "memcalib-v241-manual-review-gate-audit-v1",
                "input_record_id": record_id,
                "output_record_id": updated.get("id"),
                "issue": issue,
                "input_record_fingerprint": canonical_sha256(record),
                "output_record_fingerprint": canonical_sha256(updated),
            }
        )
    return output, audits


def validate_release(
    coding: list[dict[str, Any]],
    release: list[dict[str, Any]],
) -> dict[str, Any]:
    coding_ids = [str(row.get("id") or "") for row in coding]
    release_ids = [str(row.get("id") or "") for row in release]
    if len(coding) != 3750 or len(set(coding_ids)) != 3750:
        raise ValueError("coding release must contain 3750 unique IDs")
    if len(release) != 15000 or len(set(release_ids)) != 15000:
        raise ValueError("full release must contain 15000 unique IDs")
    domains = Counter(str(row.get("domain") or "") for row in release)
    expected_domains = {"coding": 3750, "general": 3750, "health_seed": 7500}
    if dict(domains) != expected_domains:
        raise ValueError(f"unexpected domain distribution: {dict(domains)}")
    if set(coding_ids) != {
        str(row.get("id") or "")
        for row in release
        if row.get("domain") == "coding"
    }:
        raise ValueError("coding file and full release coding partition differ")
    if REMOVED_RECORD_ID in release_ids or REPLACEMENT_RECORD_ID not in release_ids:
        raise ValueError("manual replacement was not applied exactly once")
    alignment_findings = [
        finding
        for row in coding
        if (finding := alignment.audit_record(row)) is not None
    ]
    if alignment_findings:
        raise ValueError(
            f"manual review gate left {len(alignment_findings)} alignment findings"
        )
    return {
        "domains": dict(sorted(domains.items())),
        "coding_alignment_findings": 0,
        "removed_record_absent": True,
        "replacement_record_present": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply the v2.4.1 pre-evaluation manual-review quality gate."
    )
    parser.add_argument("--coding-input", type=Path, default=DEFAULT_CODING_INPUT)
    parser.add_argument("--release-input", type=Path, default=DEFAULT_RELEASE_INPUT)
    parser.add_argument("--reserve", type=Path, default=DEFAULT_RESERVE)
    parser.add_argument("--coding-output", type=Path)
    parser.add_argument("--release-output", type=Path)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    coding_output = args.coding_output or args.coding_input
    release_output = args.release_output or args.release_input

    coding, _ = rows_by_id(args.coding_input)
    release, _ = rows_by_id(args.release_input)
    _, reserve_by_id = rows_by_id(args.reserve)
    reserve = reserve_by_id.get(REPLACEMENT_RECORD_ID)
    if reserve is None:
        raise ValueError("replacement reserve record is missing")
    input_hashes = {
        "coding": file_sha256(args.coding_input),
        "release": file_sha256(args.release_input),
        "reserve": file_sha256(args.reserve),
    }
    reviewed_coding, coding_audit = apply_review_gate(coding, reserve)
    reviewed_release, release_audit = apply_review_gate(release, reserve)
    coding_pairs = [
        (row["input_record_id"], row["output_record_id"]) for row in coding_audit
    ]
    release_coding_pairs = [
        (row["input_record_id"], row["output_record_id"]) for row in release_audit
        if str(row["input_record_id"]).startswith("crk2_v2_raw_coding_")
    ]
    if coding_pairs != release_coding_pairs:
        raise ValueError("coding and full-release repair sets differ")
    validation = validate_release(reviewed_coding, reviewed_release)
    write_jsonl(coding_output, reviewed_coding)
    write_jsonl(release_output, reviewed_release)
    write_jsonl(args.audit_output, release_audit)
    summary = {
        "schema_version": "memcalib-v241-manual-review-gate-summary-v1",
        "inputs": {
            "coding": {
                "path": portable_path(args.coding_input),
                "sha256_before_write": input_hashes["coding"],
                "records": len(coding),
            },
            "release": {
                "path": portable_path(args.release_input),
                "sha256_before_write": input_hashes["release"],
                "records": len(release),
            },
            "reserve": {
                "path": portable_path(args.reserve),
                "sha256": input_hashes["reserve"],
                "record_id": REPLACEMENT_RECORD_ID,
            },
        },
        "counts": {
            "reviewed_records": len(release_audit),
            "issues": dict(
                sorted(Counter(row["issue"] for row in release_audit).items())
            ),
            "coding": len(reviewed_coding),
            "release": len(reviewed_release),
        },
        "validation": validation,
        "outputs": {
            "coding": {
                "path": portable_path(coding_output),
                "sha256": file_sha256(coding_output),
            },
            "release": {
                "path": portable_path(release_output),
                "sha256": file_sha256(release_output),
            },
            "audit": {
                "path": portable_path(args.audit_output),
                "sha256": file_sha256(args.audit_output),
            },
        },
    }
    write_json(args.manifest, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
