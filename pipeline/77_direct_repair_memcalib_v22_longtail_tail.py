#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from utils import iter_jsonl, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
V22_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-longtail-blocks"
DEFAULT_BENCHMARK = V22_DIR / "memcalib_v22_longtail_benchmark_structural_pass_15000.jsonl"
DEFAULT_REJECTED = V22_DIR / "memcalib_v22_longtail_independent_qc_resolved2_15000.reject.jsonl"
DEFAULT_OUTPUT = V22_DIR / "memcalib_v22_longtail_benchmark_tail_repaired_15000.jsonl"
DEFAULT_REPAIRED = V22_DIR / "memcalib_v22_longtail_tail_repaired_2.jsonl"
DEFAULT_AUDIT = V22_DIR / "memcalib_v22_longtail_tail_repaired_2.audit.jsonl"
DEFAULT_MANIFEST = V22_DIR / "memcalib_v22_longtail_tail_repaired_2.manifest.json"
REPAIR_SCHEMA = "memcalib-v22-longtail-direct-tail-repair-v1"


REPAIRS: dict[str, dict[str, Any]] = {
    "crk2_v2_raw_general_4f4b8ac10c2c8c88": {
        "v22_noise_02": {
            "scene_spec": {
                "object_phrase": "a robin",
                "setting_phrase": "the balcony railing",
                "time_phrase": "July 2008",
            },
            "joint_reason": (
                "The two atoms form one dated bird-observation episode and provide no "
                "equipment, price, safety, or preference signal relevant to bouldering."
            ),
            "atoms": {
                "v22_noise_02_a1": (
                    "In July 2008, the user noticed a robin landing on the balcony "
                    "railing shortly after sunrise."
                ),
                "v22_noise_02_a2": (
                    "Later that morning in July 2008, the user photographed the same "
                    "robin before it flew toward a nearby maple tree."
                ),
            },
        },
        "v22_noise_03": {
            "scene_spec": {
                "object_phrase": "a commuter train",
                "setting_phrase": "a neighborhood station",
                "time_phrase": "September 2008",
            },
            "joint_reason": (
                "This isolated transit observation supplies no facts or constraints "
                "for selecting bouldering equipment or estimating its cost."
            ),
            "atoms": {
                "v22_noise_03_a1": (
                    "In September 2008, the user recorded that a commuter train arrived "
                    "twelve minutes late at a neighborhood station."
                ),
            },
        },
    },
    "crk2_v2_raw_general_19fc48c531536b97": {
        "v22_noise_02": {
            "scene_spec": {
                "object_phrase": "an ivory shell fragment",
                "setting_phrase": "a marine research enclosure",
                "time_phrase": "January 2008",
            },
            "joint_reason": (
                "The two atoms describe a dolphin-compatible object-recognition episode "
                "and add no information about combustion or current fire difficulties."
            ),
            "atoms": {
                "v22_noise_02_a1": (
                    "In January 2008, the user nudged an ivory shell fragment beside a "
                    "glass observation panel in the marine research enclosure."
                ),
                "v22_noise_02_a2": (
                    "Later in January 2008, the user returned the same ivory shell "
                    "fragment to a marked tray during an object-recognition session."
                ),
            },
        },
        "v22_noise_03": {
            "scene_spec": {
                "object_phrase": "a pale lilac floating marker",
                "setting_phrase": "the lower enclosure channel",
                "time_phrase": "August 2008",
            },
            "joint_reason": (
                "This navigation episode is coherent with the locked aquatic persona "
                "but cannot change an answer about the present fire problem."
            ),
            "atoms": {
                "v22_noise_03_a1": (
                    "In August 2008, the user followed a pale lilac floating marker "
                    "through the lower channel of the marine enclosure."
                ),
                "v22_noise_03_a2": (
                    "During the same August 2008 session, the user paused beside the "
                    "pale lilac marker before swimming back toward the open pool."
                ),
            },
        },
        "v22_noise_04": {
            "scene_spec": {
                "object_phrase": "a mustard-yellow seashell",
                "setting_phrase": "a shallow training tray",
                "time_phrase": "September 2008",
            },
            "joint_reason": (
                "The color-discrimination episode is plausible for the same user yet "
                "has no content, safety, or implementation footprint on the fire answer."
            ),
            "atoms": {
                "v22_noise_04_a1": (
                    "In September 2008, the user selected a mustard-yellow seashell "
                    "from a shallow tray during a color-discrimination session."
                ),
                "v22_noise_04_a2": (
                    "During the same session, the user released the mustard-yellow "
                    "seashell after the trainer's neutral signal."
                ),
            },
        },
        "v22_noise_05": {
            "scene_spec": {
                "object_phrase": "a terracotta waterproof marker tag",
                "setting_phrase": "the observation gate",
                "time_phrase": "July 2008",
            },
            "joint_reason": (
                "The marker-tag interaction is an unrelated past enrichment episode "
                "and supplies no evidence about the current fire."
            ),
            "atoms": {
                "v22_noise_05_a1": (
                    "In July 2008, the user touched a terracotta waterproof marker tag "
                    "suspended near the top of the observation gate."
                ),
                "v22_noise_05_a2": (
                    "Later in the July 2008 session, the user returned to the same "
                    "marker tag after circling the enclosure."
                ),
            },
        },
        "v22_noise_06": {
            "scene_spec": {
                "object_phrase": "a rust-red floating target",
                "setting_phrase": "the quiet side pool",
                "time_phrase": "May 2008",
            },
            "joint_reason": (
                "This enrichment action is compatible with the aquatic persona and "
                "does not bear on fire-making materials, conditions, or difficulties."
            ),
            "atoms": {
                "v22_noise_06_a1": (
                    "In May 2008, the user pushed a rust-red floating target across the "
                    "quiet side pool during an enrichment session."
                ),
            },
        },
        "v22_noise_07": {
            "scene_spec": {
                "object_phrase": "a terracotta puzzle float",
                "setting_phrase": "the central enclosure pool",
                "time_phrase": "July 2008",
            },
            "joint_reason": (
                "The choice of an enrichment float is unrelated to the physical and "
                "environmental constraints governing the current fire."
            ),
            "atoms": {
                "v22_noise_07_a1": (
                    "In July 2008, the user selected a terracotta puzzle float during "
                    "a choice-based enrichment session in the central enclosure pool."
                ),
            },
        },
        "v22_noise_08": {
            "scene_spec": {
                "object_phrase": "a cobalt-blue rubber ring",
                "setting_phrase": "the enclosure wall",
                "time_phrase": "April 2008",
            },
            "joint_reason": (
                "Retrieving an enrichment ring is a same-user historical detail with "
                "zero legitimate influence on the present fire response."
            ),
            "atoms": {
                "v22_noise_08_a1": (
                    "In April 2008, the user retrieved a cobalt-blue rubber ring "
                    "floating near the enclosure wall and carried it to the trainer's platform."
                ),
            },
        },
    },
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def block_text(atom_texts: list[str]) -> str:
    if len(atom_texts) == 1:
        return atom_texts[0]
    return " ".join(f"{index}. {text}" for index, text in enumerate(atom_texts, 1))


def repair_record(
    row: dict[str, Any], plan: dict[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    repaired = copy.deepcopy(row)
    before_record_sha = canonical_sha256(row)
    atom_by_id = {
        str(atom.get("atom_id") or ""): atom for atom in repaired.get("memories") or []
    }
    block_by_id = {
        str(block.get("parent_memory_id") or ""): block
        for block in repaired.get("memory_blocks") or []
    }
    expected_blocks = set(plan)
    observed_blocks = {
        parent_id
        for parent_id, block in block_by_id.items()
        if block.get("source") == "synthetic_retrieval_noise"
    }
    if observed_blocks != expected_blocks:
        raise ValueError(
            f"{row.get('id')} repair plan does not cover all auxiliary blocks"
        )

    audits: list[dict[str, Any]] = []
    changed_atom_ids: list[str] = []
    for parent_id, block_plan in plan.items():
        block = block_by_id[parent_id]
        atom_texts: list[str] = []
        planned_atoms = block_plan["atoms"]
        if set(block.get("atom_ids") or []) != set(planned_atoms):
            raise ValueError(f"{row.get('id')} {parent_id} atom coverage mismatch")
        for atom_id in block.get("atom_ids") or []:
            atom = atom_by_id.get(str(atom_id))
            if atom is None or atom.get("source") != "synthetic_retrieval_noise":
                raise ValueError(f"{row.get('id')} {atom_id} is not auxiliary noise")
            if atom.get("u_star") != "A" or atom.get("memory_action") != "ignore":
                raise ValueError(f"{row.get('id')} {atom_id} label/action changed")
            before_text = str(atom.get("text") or "")
            after_text = str(planned_atoms[str(atom_id)])
            if not before_text or not after_text or before_text == after_text:
                raise ValueError(f"{row.get('id')} {atom_id} repair is empty or a no-op")
            atom["text"] = after_text
            atom["atomic_predicate"] = after_text
            atom["label_reason"] = (
                "This dated same-user episode is unrelated to the current question and "
                "must leave no atom-specific answer footprint."
            )
            atom["surface_relevance"] = (
                "Broad identity or time-based retrieval could surface this historical "
                "detail even though it has no task authority."
            )
            atom["non_applicability_reason"] = (
                "The proposition supplies no facts, constraints, preferences, or safety "
                "information that bear on the current task."
            )
            atom["independence_reason"] = (
                "The proposition is independently observable and unrelated to the "
                "locked memories, current question, and other auxiliary scenes."
            )
            atom_texts.append(after_text)
            changed_atom_ids.append(str(atom_id))
            audits.append(
                {
                    "schema_version": REPAIR_SCHEMA,
                    "record_id": str(row.get("id") or ""),
                    "parent_memory_id": parent_id,
                    "atom_id": str(atom_id),
                    "before_text": before_text,
                    "after_text": after_text,
                    "before_text_sha256": canonical_sha256(before_text),
                    "after_text_sha256": canonical_sha256(after_text),
                    "repair_reason": (
                        "Resolve independent-QC same-user plausibility or collective "
                        "persona failure without changing labels or structure."
                    ),
                }
            )
        block["memory_text"] = block_text(atom_texts)
        scene_spec = dict(block.get("retrieval_noise_scene_spec") or {})
        scene_spec.update(block_plan["scene_spec"])
        scene_spec["manual_tail_repair"] = True
        block["retrieval_noise_scene_spec"] = scene_spec
        block["joint_no_footprint_reason"] = block_plan["joint_reason"]

    repaired["longtail_tail_repair"] = {
        "schema_version": REPAIR_SCHEMA,
        "record_fingerprint_before_repair": before_record_sha,
        "changed_atom_ids": changed_atom_ids,
        "changed_block_ids": sorted(plan),
        "structure_and_labels_preserved": True,
    }
    if len(repaired.get("memory_blocks") or []) != len(row.get("memory_blocks") or []):
        raise ValueError("repair changed visible block count")
    if len(repaired.get("memories") or []) != len(row.get("memories") or []):
        raise ValueError("repair changed memory atom count")
    return repaired, audits


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Directly repair the two semantic tail failures in MemCalib v2.2."
    )
    parser.add_argument("--benchmark", type=Path, default=DEFAULT_BENCHMARK)
    parser.add_argument("--rejected", type=Path, default=DEFAULT_REJECTED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repaired", type=Path, default=DEFAULT_REPAIRED)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.benchmark))
    rejected = list(iter_jsonl(args.rejected))
    rejected_ids = {str(row.get("id") or "") for row in rejected}
    if rejected_ids != set(REPAIRS):
        raise ValueError(
            f"rejected record IDs do not match the locked repair plan: {sorted(rejected_ids)}"
        )
    output_rows: list[dict[str, Any]] = []
    repaired_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for row in rows:
        record_id = str(row.get("id") or "")
        if record_id in REPAIRS:
            repaired, audits = repair_record(row, REPAIRS[record_id])
            output_rows.append(repaired)
            repaired_rows.append(repaired)
            audit_rows.extend(audits)
        else:
            output_rows.append(row)
    if len(repaired_rows) != len(REPAIRS):
        raise ValueError("not every planned record was found in the benchmark")
    if len(output_rows) != len(rows):
        raise ValueError("repair changed benchmark record count")

    write_jsonl(args.output, output_rows)
    write_jsonl(args.repaired, repaired_rows)
    write_jsonl(args.audit, audit_rows)
    manifest = {
        "schema_version": REPAIR_SCHEMA,
        "inputs": {
            "benchmark": {
                "path": portable_path(args.benchmark),
                "sha256": file_sha256(args.benchmark),
                "records": len(rows),
            },
            "rejected": {
                "path": portable_path(args.rejected),
                "sha256": file_sha256(args.rejected),
                "records": len(rejected),
            },
        },
        "counts": {
            "benchmark_records": len(output_rows),
            "repaired_records": len(repaired_rows),
            "repaired_atoms": len(audit_rows),
        },
        "outputs": {
            "benchmark": {
                "path": portable_path(args.output),
                "sha256": file_sha256(args.output),
            },
            "repaired_records": {
                "path": portable_path(args.repaired),
                "sha256": file_sha256(args.repaired),
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
