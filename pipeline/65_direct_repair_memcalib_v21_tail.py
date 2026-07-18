#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any

from utils import iter_jsonl, norm_text, write_json, write_jsonl


SCRIPT_DIR = Path(__file__).resolve().parent
REVISION_DIR = SCRIPT_DIR / "data" / "multidomain" / "full-v2" / "revision-composite-harda"
DEFAULT_INPUT = (
    REVISION_DIR
    / "dispute-qc1"
    / "memcalib_v21_qc_15000.merged2.adjudicated.jsonl"
)
DEFAULT_OUTPUT = REVISION_DIR / "direct-tail-repair" / "memcalib_v21_benchmark_15000.direct1.jsonl"
DEFAULT_REPAIRED = REVISION_DIR / "direct-tail-repair" / "memcalib_v21_tail_repaired_93.jsonl"
DEFAULT_AUDIT = REVISION_DIR / "direct-tail-repair" / "memcalib_v21_tail_repair_93.audit.jsonl"
DEFAULT_SUMMARY = REVISION_DIR / "direct-tail-repair" / "memcalib_v21_tail_repair_93.summary.json"

SCHEMA_VERSION = "memcalib-v21-direct-tail-repair-v1"
COMPOSITE_PARENT_ID = "v21_real_composite"
HARD_A_PARENT_ID = "v21_hard_a"
HARD_A_ATOM_ID = "v21_hard_a_a1"
HARD_A_FAMILIES = {
    "factual_judgment_pollution",
    "scope_overreach",
    "current_evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
}
LABEL_ACTIONS = {
    "A": {"ignore"},
    "B": {"apply", "correct"},
    "C": {"apply", "correct"},
}
DEFAULT_ACTION = {
    "A": "ignore",
    "B": "apply",
    "C": "apply",
}

HARD_A_TEXT_OVERRIDES = {
    "crk2_v2_raw_general_d15736b6b84a90b3": (
        "The user previously saved a tentative Zimbabwe itinerary note saying that "
        "the next country-specific question would concern museum opening hours rather "
        "than emergency services."
    ),
    "crk2_v2_raw_4b402ebddfc9fbd0": (
        "The user previously saved a draft task note saying that the next question "
        "in this case would be answered by choosing one of four supplied options."
    ),
    "crk2_v2_raw_7ef5d75d9a979e6e": (
        "The user previously saved a draft appointment note saying that the urgent "
        "care visit would concern paperwork only and would not involve an active "
        "injury, mobility problem, or imaging question."
    ),
    "crk2_v2_raw_general_51129f1fab4d3cd0": (
        "When choosing an audiobook edition, the user prefers narrator sample links "
        "and chapter-level playback timestamps."
    ),
    "crk2_v2_raw_general_311e46b25317c0ef": (
        "For corporate travel reimbursement forms, the user requires internal "
        "cost-center codes beside every tour operator."
    ),
}


# These records were judged non-strict even though the judge's own prose or the
# deterministic composite proof establishes that the flagged item passes. They
# still receive fresh independent QC after this audit; this list is not a release
# allow-list.
MANUAL_PROOF_IDS = {
    "crk2_v2_raw_69d27d969d6c83d0",
    "crk2_v2_raw_general_98df38879e9f2bb3",
    "crk2_v2_raw_general_784f167c25478fea",
    "crk2_v2_raw_general_51129f1fab4d3cd0",
    "crk2_v2_raw_coding_dc8ea6de2d6e09fb",
    "crk2_v2_raw_coding_ee362d2562ac3552",
    "crk2_v2_raw_general_df2039a55ab78111",
    "crk2_v2_raw_coding_981fa5600979dcf0",
    "crk2_v2_raw_bb847900cd8291ed",
    "crk2_v2_raw_f94fd0bd75bd7f38",
    "crk2_v2_raw_general_8a326d9de341b5c3",
    "crk2_v2_raw_general_dbba5c5157b5402d",
    "crk2_v2_raw_883971c4bbade41b",
    "crk2_v2_raw_general_311e46b25317c0ef",
    "crk2_v2_raw_f3962667a4967e4a",
    "crk2_v2_raw_62dbf5873c860e45",
}


# Direct real-atom corrections. A missing field means "preserve the existing
# value". Text changes are deliberately anchored to the cited evidence rather
# than inferred from model prose.
REAL_ATOM_REPAIRS: dict[str, dict[str, Any]] = {
    "crk2_v2_raw_general_1b967fd23f03fa3a": {
        "p3_a1": {
            "text": "The user said they do not understand special relativity well.",
            "evidence": "I don't really get special relativity.",
            "label": "B",
            "memory_type": "profile_fact",
        },
    },
    "crk2_v2_raw_coding_3e4cb4e775ad6b4b": {
        "p2_a1": {
            "text": (
                "The clicked row view contains child views tagged 'name', 'hp', "
                "'attack', and 'speed'."
            ),
            "label": "C",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_coding_b55dc17c424b1c05": {
        "p1_a1": {
            "text": "The codebase contains a named animated-layer instance `_ringAnimatedLayer`.",
            "label": "B",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_4b402ebddfc9fbd0": {
        "p2_a1": {"label": "B"},
        "p3_a1": {
            "text": "Recent EEG and brain MRI results were normal, while the CT scan was not normal.",
            "evidence": "in the last 30 days an EEG, Brain MRI & CT Scan. All are normal except CT scan.",
            "label": "B",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_coding_1c64db8fb9b1de7b": {
        "p1_a1": {"label": "A"},
    },
    "crk2_v2_raw_coding_78aeecfd114d0c67": {
        "p3_a1": {
            "text": (
                "The user wants heap analysis to identify references that keep "
                "otherwise collectable objects alive."
            ),
            "evidence": (
                "work out what's keeping references to objects which should be able "
                "to be garbage collected"
            ),
            "label": "A",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_0bc510e68e201688": {
        "p2_a1": {
            "text": "The user has high cholesterol and triglycerides.",
            "evidence": "high cholestrol and triglycerides",
            "label": "B",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_coding_140406e5bcbfdb27": {
        "p4_a1": {
            "text": (
                "The compound query must match platform, synchronization interval, "
                "and user-ID criteria together."
            ),
            "evidence": (
                "The compound query should retrieve data that matches all the "
                "provided criteria (platform, interval, and user IDs)."
            ),
            "label": "C",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_general_2ac096760f5cdcf8": {
        "p1_a1": {"label": "B"},
        "p2_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_f27a28ec6821c513": {
        "p2_a1": {"label": "A"},
        "p3_a1": {"label": "A"},
    },
    "crk2_v2_raw_coding_10cd04124ae4f3b0": {
        "m1": {"label": "A"},
    },
    "crk2_v2_raw_89bc0c06ea95d73c": {
        "p3_a1": {
            "text": "The user reports tingling in the arms, legs, and face.",
            "evidence": "I have feelings of tingling sensation in my arms and legs and face .",
            "label": "C",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_general_55c8defc504c752f": {
        "p1_a1": {"label": "A"},
        "p2_a1": {"label": "A"},
    },
    "crk2_v2_raw_cc6dc9209c16a98a": {
        "p3_a1": {
            "text": "The patient is the user's daughter.",
            "evidence": "My daughter",
            "label": "A",
            "memory_type": "profile_fact",
        },
        "__remove__": ["p4_a1"],
    },
    "crk2_v2_raw_coding_656ace216d5fccfa": {
        "p2_a1": {
            "text": "The subscriber callback must perform custom processing on received sensor data.",
            "evidence": "perform some custom processing (e.g., filtering, transformation, or analysis)",
            "label": "C",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_coding_0dfe9d620d786280": {
        "p3_a1": {
            "text": "The setup script must handle errors gracefully and provide useful feedback.",
            "evidence": (
                "Ensure that the script handles potential errors gracefully and "
                "provides appropriate feedback to the user."
            ),
            "label": "A",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_coding_890761db55ed3a17": {
        "p1_a1": {
            "text": "The shell script must handle errors gracefully.",
            "evidence": (
                "Your script should handle errors gracefully and ensure that the Java "
                "program is executed with the correct classpath and options."
            ),
            "label": "A",
            "memory_type": "constraint",
        },
        "p2_a1": {
            "text": (
                "The script must run the Java main class using `$JAVA_OPTS` and pass "
                "through additional command-line arguments."
            ),
            "evidence": (
                "Run a Java program using the constructed classpath, Java options "
                "specified by `$JAVA_OPTS`, and the main class specified by `$CLASS`, "
                "passing any additional command-line arguments."
            ),
            "label": "A",
            "memory_type": "constraint",
        },
        "p4_a1": {
            "text": (
                "If `classpath.txt` is missing, the script must print an error and exit "
                "with status 1."
            ),
            "evidence": (
                "1. Check for the existence of a file named `classpath.txt`. If it does "
                "not exist, print an error message and exit with a status code of 1."
            ),
            "label": "A",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_general_37173eda7a00cdb3": {
        "p3_a1": {
            "text": (
                "The user's content plan must cover both video-game streaming and "
                "wrestling content."
            ),
            "evidence": (
                "I am a streamer who also wrestles, and I need to create content both "
                "for streaming video games and also for wrestling"
            ),
            "label": "B",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_general_3247f459bb213231": {
        "p1_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_450fa29c444e0b05": {
        "p1_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_ec9947e412db9388": {
        "p3_a1": {
            "text": "The recipe is served with cranberry sauce.",
            "evidence": "serve immediately with some cranberry sauce.",
            "label": "A",
            "memory_type": "case_fact",
        },
        "p4_a1": {
            "text": "The recipe includes mushrooms, parsley, and chives.",
            "evidence": "stir in the mushrooms, parsley and chives.",
            "label": "A",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_coding_450b4d7db987ff10": {
        "p3_a1": {"label": "B"},
    },
    "crk2_v2_raw_coding_e1804fd35a81de25": {
        "p3_a1": {
            "text": (
                "The specified input and output Excel filenames use snake_case names."
            ),
            "evidence": (
                'Assume that the input Excel file is named "sales_data.xlsx" and the '
                'output Excel file should be named "revenue_summary.xlsx".'
            ),
            "label": "A",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_general_e8cc7a4920e35d2e": {
        "p3_a1": {"label": "A"},
    },
    "crk2_v2_raw_7ef5d75d9a979e6e": {
        "p2_a1": {
            "text": (
                "The user iced the leg, minimized walking, and used a walking stick for "
                "assistance."
            ),
            "evidence": (
                "I iced my leg and minimized my walking about. Fortunately I had a "
                "walking stick to assist my walking about."
            ),
            "label": "B",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_coding_df65e7c3402d8f6c": {
        "p2_a1": {"label": "B"},
    },
    "crk2_v2_raw_276ccb4c9dc49d4a": {
        "p3_a1": {"label": "A"},
    },
    "crk2_v2_raw_coding_8025df8782ca0074": {
        "p3_a1": {"label": "C"},
    },
    "crk2_v2_raw_coding_2f32ebb7443b1569": {
        "p2_a1": {"label": "C"},
    },
    "crk2_v2_raw_coding_a70c81b9a0161150": {
        "p2_a1": {
            "text": (
                "The `getbusdata` function takes a city string and a list of search "
                "keywords."
            ),
            "evidence": (
                "The function `getbusdata` takes two parameters: `city`, a string "
                "representing the city name, and `keywords`, a list of strings "
                "representing keywords to search for in the bus data."
            ),
            "label": "C",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_general_db0e7133769e08bc": {
        "p1_a1": {"label": "A"},
        "p3_a1": {"label": "A"},
    },
    "crk2_v2_raw_coding_6387857e02107d67": {
        "p3_a1": {
            "text": (
                "The deployment script must provide clear feedback to the user during "
                "both deployment and rollback."
            ),
            "evidence": (
                "provides clear feedback to the user during both deployment and "
                "rollback processes"
            ),
            "label": "C",
            "memory_type": "constraint",
        },
        "p4_a1": {
            "text": "The deployment backup must be stored in a timestamped directory.",
            "evidence": (
                "create a backup of the current production version by copying it to a "
                "timestamped directory within the production server's file system"
            ),
            "label": "C",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_87c1591ec86168dd": {
        "p3_a1": {
            "text": "The user checked the IUD strings and found them longer than expected.",
            "evidence": (
                "I decided to check my strings today and noticed that they are much "
                "longer than what its supposed to be"
            ),
            "label": "A",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_coding_84d1afacbf4804b4": {
        "p3_a1": {
            "text": "The movement function receives the current grid position as integer coordinates.",
            "evidence": (
                "Write a Python function called `simulate_movement` that takes the "
                "current position of the player as a tuple of integers `(x, y)` "
                "representing the coordinates on the grid."
            ),
            "label": "A",
            "memory_type": "constraint",
        },
    },
    "crk2_v2_raw_general_4e8e0fe3e70d1559": {
        "p1_a1": {"label": "A"},
    },
    "crk2_v2_raw_62dbf5873c860e45": {
        "__remove__": ["p3_a1"],
    },
    "crk2_v2_raw_coding_dc8ea6de2d6e09fb": {
        "p1_a1": {"label": "B"},
        "p2_a1": {"label": "B"},
        "p4_a1": {"label": "A"},
    },
    "crk2_v2_raw_coding_ee362d2562ac3552": {
        "p1_a1": {"label": "A"},
        "p3_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_51129f1fab4d3cd0": {
        "p1_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_784f167c25478fea": {
        "p2_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_98df38879e9f2bb3": {
        "p1_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_d15736b6b84a90b3": {
        "p1_a1": {"label": "A"},
        "p3_a1": {"label": "A"},
    },
    "crk2_v2_raw_general_f9285eed18ce9032": {
        "p1_a1": {
            "text": (
                "This soup uses about 8 ounces of lentils; adding more previously "
                "left the lentils undercooked."
            ),
            "evidence": (
                "lentils (only around that 8 ounce mark - I tried adding more and it "
                "was bleeeech! They didn't cook.)"
            ),
            "label": "B",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_general_311e46b25317c0ef": {
        "p2_a1": {
            "text": "The user plans to book a tour with one of the previously suggested companies.",
            "evidence": "I'm definitely going to book a tour with one of those companies you suggested.",
            "label": "A",
            "memory_type": "case_fact",
        },
    },
    "crk2_v2_raw_general_8a326d9de341b5c3": {
        "p1_a1": {"label": "A"},
    },
    "crk2_v2_raw_66a047421d148d71": {
        "p3_a1": {"label": "A"},
    },
    "crk2_v2_raw_883971c4bbade41b": {
        "p1_a1": {"label": "A"},
    },
}


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(SCRIPT_DIR.parent))
    except ValueError:
        return str(resolved)


def normalized_contains(haystack: str, needle: str) -> bool:
    normalized_haystack = re.sub(r"\s+", " ", haystack).strip().casefold()
    normalized_needle = re.sub(r"\s+", " ", needle).strip().casefold()
    return bool(normalized_needle) and normalized_needle in normalized_haystack


def real_atoms(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") != "synthetic_hard_a"
    ]


def hard_atom(record: dict[str, Any]) -> dict[str, Any]:
    atoms = [
        atom
        for atom in record.get("memories") or []
        if isinstance(atom, dict) and atom.get("source") == "synthetic_hard_a"
    ]
    if len(atoms) != 1:
        raise ValueError(f"{record.get('id')}: expected exactly one Hard A")
    return atoms[0]


def composite_memory_text(atoms: list[dict[str, Any]]) -> str:
    return " ".join(
        f"{index}. {norm_text(str(atom.get('text') or ''))}"
        for index, atom in enumerate(atoms, 1)
    )


def set_atom_semantics(atom: dict[str, Any], label: str) -> None:
    text = norm_text(str(atom.get("text") or ""))
    if label not in LABEL_ACTIONS:
        raise ValueError(f"unsupported label: {label}")
    atom["u_star"] = label
    atom["memory_action"] = DEFAULT_ACTION[label]
    atom["query_relation"] = "absent"
    atom["atomic_predicate"] = text
    if label == "A":
        atom["label_reason"] = (
            "The proposition is grounded but has no legitimate answer influence for "
            "the current model-facing task and must leave no observable footprint."
        )
        atom["construction_target"] = {
            "task_goal": "Answer the current model-facing task accurately.",
            "memory_role": "none",
            "usage_boundary": "Do not mention, implement, or infer any requirement from this atom.",
            "failure_direction": "Any answer change caused by this atom is over-use.",
        }
        atom["counterfactual_contract"] = {
            "without_memory_behavior": "Produce the best answer from the current question and applicable memories.",
            "with_memory_behavior": "Produce the best answer from the current question and applicable memories.",
            "observable_delta": "none",
            "minimal_evidence": [],
        }
        atom["usage_rubric"] = {
            "expected_answer_behavior": "No answer content is attributable to this atom.",
            "memory_usage_weight": "none",
            "validity_scope": "The atom is grounded context but outside the current answer boundary.",
            "correct_use": "The answer remains unchanged when this atom is present.",
            "under_use": "not_applicable_for_A",
            "over_use": "Any claim, choice, or wording introduced because of this atom.",
            "forbidden_memory_role": "The atom must not alter content, structure, tone, or recommendations.",
            "failure_direction": "Over-use creates an unsupported observable answer change.",
            "observable_checks": [
                "No answer statement is attributable to this atom.",
                "Removing this atom leaves the answer unchanged.",
            ],
        }
        return

    weight = "supporting" if label == "B" else "controlling"
    strength = "bounded supporting context" if label == "B" else "a required constraint"
    atom["label_reason"] = (
        f"The grounded proposition has {strength} with an independently observable "
        "answer effect limited to its explicit scope."
    )
    atom["construction_target"] = {
        "task_goal": "Answer the current model-facing task accurately.",
        "memory_role": f"Use this atom as {strength}.",
        "usage_boundary": "Use only the explicit proposition; do not infer broader preferences or facts.",
        "failure_direction": f"The answer omits or contradicts the grounded proposition: {text}",
    }
    atom["counterfactual_contract"] = {
        "without_memory_behavior": "Answer without access to this grounded proposition.",
        "with_memory_behavior": f"Answer while correctly reflecting this proposition: {text}",
        "observable_delta": f"The answer observably and only reflects: {text}",
        "minimal_evidence": [f"The answer visibly reflects the proposition: {text}"],
    }
    atom["usage_rubric"] = {
        "expected_answer_behavior": f"Correctly reflect the proposition within its explicit scope: {text}",
        "memory_usage_weight": weight,
        "validity_scope": "Only the current task and only the proposition stated by this atom.",
        "correct_use": "Use the proposition once and only where it changes the answer legitimately.",
        "under_use": f"Omit or contradict the proposition: {text}",
        "over_use": "Generalize the proposition beyond its evidence or let it control unrelated content.",
        "forbidden_memory_role": "Do not invent a preference, diagnosis, requirement, or causal claim not in the evidence.",
        "failure_direction": "The answer either omits the legitimate effect or extends it beyond the evidence.",
        "observable_checks": [
            f"The answer visibly reflects the proposition: {text}",
            "No broader unsupported inference is introduced.",
        ],
    }


def factual_pollution_text(record: dict[str, Any]) -> str:
    selector = int(hashlib.sha256(str(record["id"]).encode()).hexdigest()[:8], 16) % 5
    number = 3 + selector
    domain = str(record.get("domain") or "general")
    if domain == "coding":
        return (
            "The user believes that code solutions are automatically more correct "
            f"when every local variable name contains at least {number} words."
        )
    if domain == "health_seed":
        variants = [
            "every paragraph contains a bolded technical term",
            f"the response contains exactly {number} section headings",
            "each paragraph includes one parenthetical medical abbreviation",
            "the introduction is longer than the practical guidance",
            f"the response contains at least {number} italicized phrases",
        ]
        return (
            "The user believes that a medical explanation is automatically more "
            f"accurate when {variants[selector]}."
        )
    variants = [
        f"it contains exactly {number} section headings",
        "each paragraph contains a semicolon",
        "the introduction is longer than the answer itself",
        f"it uses at least {number} numbered paragraphs",
        "every claim is written in the passive voice",
    ]
    return (
        "The user believes that an informational answer is automatically more "
        f"authoritative when {variants[selector]}."
    )


def replacement_hard_text(record: dict[str, Any], family: str) -> str:
    override = HARD_A_TEXT_OVERRIDES.get(str(record.get("id") or ""))
    if override:
        return override
    domain = str(record.get("domain") or "general")
    if family == "factual_judgment_pollution":
        return factual_pollution_text(record)
    if family == "current_evidence_conflict":
        if domain == "health_seed":
            return (
                "The user previously saved a draft intake placeholder saying that the "
                "next health follow-up would contain no active symptom, new lesion, "
                "injury, or treatment question."
            )
        if domain == "coding":
            return (
                "The user previously saved a draft implementation brief saying that "
                "the next task would require conceptual pseudocode only, with no "
                "executable artifact or concrete tool recommendation."
            )
        return (
            "The user previously saved a draft response brief saying that the next "
            "request would ask only for broad background and would not request concrete "
            "examples, links, instructions, or recommendations."
        )
    if family == "profile_style_near_neighbor":
        if "imaging" in str(record.get("question") or "").casefold():
            return (
                "For formal radiology cases submitted to a specialist archive, the "
                "user prefers accession metadata and imaging-sequence labels before "
                "the findings."
            )
        return (
            "For entries exported from a personal symptom-tracking archive, the user "
            "prefers timestamped bullet logs with device-compatible field labels."
        )
    if family == "untriggered_preference":
        return (
            "When comparing browser-telemetry dashboards, the user prefers comparison "
            "tables sorted by monthly active-user counts."
        )
    if family == "scope_overreach":
        return (
            "For restaurant inventory sheets, the user requires batch cost and storage "
            "bin identifiers beside every soup entry."
        )
    raise ValueError(f"unsupported Hard A family: {family}")


def hard_family_explanation(family: str) -> tuple[str, str, str]:
    if family == "factual_judgment_pollution":
        return (
            "The memory is an unsupported presentation heuristic framed as a factual accuracy rule.",
            "Using the heuristic would alter presentation without improving factual correctness.",
            "The current task asks for substantive content, not validation of the user's accuracy heuristic.",
        )
    if family == "current_evidence_conflict":
        return (
            "The memory is an obsolete draft expectation superseded by the explicit current request.",
            "Following the obsolete brief would omit the concrete task now requested.",
            "The current question itself is the stronger and more recent task anchor.",
        )
    if family == "profile_style_near_neighbor":
        return (
            "The memory is a style preference for a neighboring archival artifact and audience.",
            "Applying the archive style would distort the current direct answer.",
            "The current task is not the specialist archive or export workflow named by the memory.",
        )
    if family == "untriggered_preference":
        return (
            "The memory is a preference for a comparison decision not requested here.",
            "Using it would add an unsolicited ranking or comparison dimension.",
            "The current task requests no dashboard comparison or ranking along that dimension.",
        )
    if family == "scope_overreach":
        return (
            "The memory applies to restaurant inventory records, a different object and workflow.",
            "Using it would add inventory metadata to a content-retrieval answer.",
            "The current task concerns recipe content rather than inventory administration.",
        )
    raise ValueError(f"unsupported Hard A family: {family}")


def replace_hard_a(record: dict[str, Any]) -> dict[str, Any]:
    prior = hard_atom(record)
    family = str(prior.get("hard_a_family") or "")
    if family not in HARD_A_FAMILIES:
        raise ValueError(f"{record.get('id')}: invalid Hard A family")
    text = replacement_hard_text(record, family)
    mechanism, temptation, boundary = hard_family_explanation(family)
    replacement = copy.deepcopy(prior)
    replacement.update(
        {
            "text": text,
            "atomic_predicate": text,
            "evidence": "",
            "derivation": "synthetic",
            "source": "synthetic_hard_a",
            "memory_type": "profile_fact",
            "u_star": "A",
            "memory_action": "ignore",
            "query_relation": "absent",
            "subtype": f"direct_tail_repair_{family}",
            "label_reason": (
                "The memory is superficially adjacent but has no legitimate decision "
                "authority, requires no correction, and must leave no answer footprint."
            ),
            "surface_relevance": (
                "The memory concerns how a nearby task or answer might be framed, so it "
                "is plausible retrieved context without constraining this task."
            ),
            "non_applicability_reason": boundary,
            "family_audit": {
                "task_boundary_anchor": boundary,
                "family_specific_mechanism": mechanism,
                "tempting_incorrect_use": temptation,
                "no_valid_bounded_use": (
                    "Any use would change content, structure, or prioritization without "
                    "serving the current task; therefore even a bounded mention is invalid."
                ),
                "explicit_correction_test": "not_required",
            },
            "construction_target": {
                "task_goal": "Answer the current request using its explicit specification and grounded real atoms.",
                "memory_role": "none",
                "usage_boundary": "The memory must leave no observable answer footprint.",
                "failure_direction": temptation,
            },
            "counterfactual_contract": {
                "without_memory_behavior": "Answer the current request directly and accurately.",
                "with_memory_behavior": "Answer the current request directly and accurately.",
                "observable_delta": "none",
                "minimal_evidence": [],
            },
            "usage_rubric": {
                "expected_answer_behavior": "Answer the current request without using or mentioning this memory.",
                "memory_usage_weight": "none",
                "validity_scope": boundary,
                "correct_use": "Ignore the memory completely.",
                "under_use": "not_applicable_for_A",
                "over_use": temptation,
                "forbidden_memory_role": "The memory cannot affect facts, choices, warnings, tone, format, or recommendations.",
                "failure_direction": temptation,
                "observable_checks": [
                    "No answer content is attributable to this memory.",
                    "Removing this memory leaves the ideal answer unchanged.",
                ],
            },
        }
    )
    return replacement


def relation_reason(relation: str) -> str:
    if relation == "independent":
        return "The two atomic propositions are separately grounded and can be evaluated independently."
    if relation == "overlap":
        return "The propositions share context but retain distinct, separately judgeable claims."
    if relation == "entails":
        return "One proposition supplies a narrower consequence of the other while remaining separately represented."
    if relation == "contradicts":
        return "The propositions are explicitly opposed and must remain separately visible for adjudication."
    return "The propositions retain their original audited relation and are separately judgeable."


def rebuild_composite_and_relations(record: dict[str, Any]) -> None:
    real = real_atoms(record)
    hard = hard_atom(record)
    atom_count = len(real)
    for index, atom in enumerate(real, 1):
        atom["parent_memory_id"] = COMPOSITE_PARENT_ID
        atom["atom_index"] = index
        atom["atom_count"] = atom_count
        atom["memory_id"] = atom["atom_id"]
    hard.update(
        {
            "memory_id": HARD_A_ATOM_ID,
            "parent_memory_id": HARD_A_PARENT_ID,
            "atom_id": HARD_A_ATOM_ID,
            "atom_index": 1,
            "atom_count": 1,
        }
    )

    old_blocks = {
        str(block.get("parent_memory_id") or ""): block
        for block in record.get("memory_blocks") or []
        if isinstance(block, dict)
    }
    old_composite = old_blocks.get(COMPOSITE_PARENT_ID, {})
    source_spans = []
    for atom in real:
        atom_id = str(atom["atom_id"])
        prior_span = next(
            (
                item
                for item in old_composite.get("source_spans") or []
                if str(item.get("atom_id") or "") == atom_id
            ),
            {},
        )
        source_spans.append(
            {
                "atom_id": atom_id,
                "source": atom.get("source"),
                "evidence": norm_text(str(atom.get("evidence") or "")),
                "original_parent_memory_id": prior_span.get("original_parent_memory_id", ""),
                "original_memory_text": norm_text(str(atom.get("text") or "")),
            }
        )
    composite = {
        "parent_memory_id": COMPOSITE_PARENT_ID,
        "raw_evidence": "\n".join(
            norm_text(str(atom.get("evidence") or ""))
            for atom in real
            if norm_text(str(atom.get("evidence") or ""))
        ),
        "memory_text": composite_memory_text(real),
        "source": "composite_grounded",
        "atom_ids": [str(atom["atom_id"]) for atom in real],
        "atomization_notes": (
            "Deterministic visible composite of the grounded atoms. Numbered clauses "
            "map one-to-one to atom_ids and introduce no proposition beyond those atoms."
        ),
        "component_parent_ids": [
            str(item.get("original_parent_memory_id") or "") for item in source_spans
        ],
        "source_spans": source_spans,
    }
    hard_block = {
        "parent_memory_id": HARD_A_PARENT_ID,
        "raw_evidence": "",
        "memory_text": hard["text"],
        "source": "synthetic_hard_a",
        "atom_ids": [HARD_A_ATOM_ID],
        "atomization_notes": (
            f"Directly audited five-family synthetic Hard A ({hard['hard_a_family']}); A + ignore."
        ),
    }
    record["memory_blocks"] = [composite, hard_block]
    record["memories"] = real + [hard]

    old_relations = {
        tuple(sorted((str(item.get("left_atom_id") or ""), str(item.get("right_atom_id") or "")))): item
        for item in record.get("atom_pair_relations") or []
        if isinstance(item, dict)
    }
    ids = [str(atom["atom_id"]) for atom in record["memories"]]
    relations = []
    for left, right in combinations(ids, 2):
        pair = tuple(sorted((left, right)))
        old = old_relations.get(pair, {})
        relation = "independent" if HARD_A_ATOM_ID in pair else str(old.get("relation") or "independent")
        relations.append(
            {
                "left_atom_id": left,
                "right_atom_id": right,
                "relation": relation,
                "reason": (
                    "The synthetic Hard A has no semantic or decision dependence on this grounded atom."
                    if HARD_A_ATOM_ID in pair
                    else relation_reason(relation)
                ),
            }
        )
    record["atom_pair_relations"] = relations


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    blocks = record.get("memory_blocks") or []
    atoms = record.get("memories") or []
    real = real_atoms(record)
    hard = [atom for atom in atoms if atom.get("source") == "synthetic_hard_a"]
    if len(blocks) != 2:
        errors.append("visible_block_count_not_two")
    if len(real) < 2 or len(hard) != 1:
        errors.append("real_or_hard_atom_count_invalid")
    ids = [str(atom.get("atom_id") or "") for atom in atoms]
    if "" in ids or len(ids) != len(set(ids)):
        errors.append("atom_ids_not_unique")
    if blocks:
        if blocks[0].get("source") != "composite_grounded":
            errors.append("first_block_not_composite")
        if blocks[0].get("memory_text") != composite_memory_text(real):
            errors.append("composite_text_not_exact")
        if list(blocks[0].get("atom_ids") or []) != [str(atom.get("atom_id") or "") for atom in real]:
            errors.append("composite_atom_ids_not_exact")
        if blocks[1].get("source") != "synthetic_hard_a":
            errors.append("second_block_not_hard_a")
        if blocks[1].get("memory_text") != (hard[0].get("text") if hard else None):
            errors.append("hard_block_text_mismatch")
    corpus = "\n".join(
        str(record.get(key) or "") for key in ("raw_query", "source_context", "source_answer")
    )
    for atom in real:
        atom_id = str(atom.get("atom_id") or "")
        label = str(atom.get("u_star") or "")
        if atom.get("memory_action") not in LABEL_ACTIONS.get(label, set()):
            errors.append(f"{atom_id}_label_action_mismatch")
        if not normalized_contains(corpus, str(atom.get("evidence") or "")):
            errors.append(f"{atom_id}_evidence_not_source_contiguous")
        contract = atom.get("counterfactual_contract") or {}
        rubric = atom.get("usage_rubric") or {}
        if label == "A":
            if contract.get("observable_delta") != "none" or contract.get("minimal_evidence") != []:
                errors.append(f"{atom_id}_a_contract_has_footprint")
            if rubric.get("memory_usage_weight") != "none":
                errors.append(f"{atom_id}_a_rubric_weight_not_none")
        elif label in {"B", "C"}:
            expected = "supporting" if label == "B" else "controlling"
            if norm_text(str(contract.get("observable_delta") or "")).casefold() == "none":
                errors.append(f"{atom_id}_bc_contract_missing_delta")
            if not contract.get("minimal_evidence"):
                errors.append(f"{atom_id}_bc_contract_missing_evidence")
            if rubric.get("memory_usage_weight") != expected:
                errors.append(f"{atom_id}_bc_rubric_weight_mismatch")
        else:
            errors.append(f"{atom_id}_invalid_label")
    if hard:
        atom = hard[0]
        if atom.get("hard_a_family") not in HARD_A_FAMILIES:
            errors.append("hard_a_bad_family")
        if atom.get("u_star") != "A" or atom.get("memory_action") != "ignore":
            errors.append("hard_a_bad_label_action")
        contract = atom.get("counterfactual_contract") or {}
        if contract.get("observable_delta") != "none" or contract.get("minimal_evidence") != []:
            errors.append("hard_a_contract_has_footprint")
        if (atom.get("family_audit") or {}).get("explicit_correction_test") != "not_required":
            errors.append("hard_a_requires_correction")
    expected_pairs = len(atoms) * (len(atoms) - 1) // 2
    pairs = {
        tuple(sorted((str(item.get("left_atom_id") or ""), str(item.get("right_atom_id") or ""))))
        for item in record.get("atom_pair_relations") or []
        if isinstance(item, dict)
    }
    if len(pairs) != expected_pairs:
        errors.append("pairwise_relation_coverage_mismatch")
    return sorted(set(errors))


def repair_record(record: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    repaired = copy.deepcopy(record)
    record_id = str(record.get("id") or "")
    prior_qc = copy.deepcopy(record.get("revision_independent_qc") or {})
    prior_fingerprint = canonical_sha256(record)
    reasons = [str(value) for value in prior_qc.get("computed_reasons") or []]
    actions: list[dict[str, Any]] = []

    atom_spec = REAL_ATOM_REPAIRS.get(record_id)
    if atom_spec:
        remove_ids = set(atom_spec.get("__remove__") or [])
        if remove_ids:
            repaired["memories"] = [
                atom
                for atom in repaired.get("memories") or []
                if str(atom.get("atom_id") or "") not in remove_ids
            ]
            actions.append({"kind": "remove_unsupported_atoms", "atom_ids": sorted(remove_ids)})
        by_id = {
            str(atom.get("atom_id") or ""): atom
            for atom in repaired.get("memories") or []
            if isinstance(atom, dict)
        }
        for atom_id, patch in atom_spec.items():
            if atom_id == "__remove__":
                continue
            atom = by_id.get(atom_id)
            if atom is None:
                raise ValueError(f"{record_id}: missing atom for direct repair: {atom_id}")
            before = canonical_sha256(atom)
            for key in ("text", "evidence", "memory_type"):
                if key in patch:
                    atom[key] = patch[key]
            atom["text"] = norm_text(str(atom.get("text") or ""))
            atom["evidence"] = norm_text(str(atom.get("evidence") or ""))
            set_atom_semantics(atom, str(patch["label"]))
            actions.append(
                {
                    "kind": "repair_real_atom",
                    "atom_id": atom_id,
                    "prior_fingerprint": before,
                    "new_fingerprint": canonical_sha256(atom),
                    "label": patch["label"],
                    "text_changed": "text" in patch,
                    "evidence_changed": "evidence" in patch,
                }
            )

    if record_id in HARD_A_TEXT_OVERRIDES or any(
        reason.startswith("hard_a:") for reason in reasons
    ):
        previous = hard_atom(repaired)
        replacement = replace_hard_a(repaired)
        repaired["memories"] = [
            replacement if atom.get("source") == "synthetic_hard_a" else atom
            for atom in repaired.get("memories") or []
        ]
        actions.append(
            {
                "kind": "replace_hard_a_same_family",
                "hard_a_family": replacement["hard_a_family"],
                "prior_text": previous.get("text"),
                "replacement_text": replacement.get("text"),
                "prior_fingerprint": canonical_sha256(previous),
                "new_fingerprint": canonical_sha256(replacement),
            }
        )

    if record_id in MANUAL_PROOF_IDS:
        actions.append(
            {
                "kind": "record_formal_manual_proof",
                "basis": (
                    "The composite visible text is a deterministic numbered concatenation "
                    "of the real atom texts with exact atom-id coverage; source evidence is "
                    "audited against raw_query/source_context/source_answer. Judge prose was "
                    "also checked for contradictions with its emitted enum."
                ),
            }
        )

    if not actions:
        raise ValueError(f"{record_id}: no direct repair or proof action")
    rebuild_composite_and_relations(repaired)
    repaired["deterministic_qc"] = {
        "schema_version": SCHEMA_VERSION,
        "decision": "pass",
        "checks": {
            "question_and_source_identity_preserved": True,
            "real_atom_evidence_source_contiguous": True,
            "label_action_contract_consistent": True,
            "composite_exact_atom_coverage": True,
            "composite_introduces_no_new_proposition_beyond_atoms": True,
            "hard_a_same_family_and_zero_footprint": True,
            "pairwise_relation_coverage": True,
        },
    }
    repaired.pop("revision_independent_qc", None)
    repaired.pop("release_admission", None)
    errors = validate_record(repaired)
    audit = {
        "schema_version": SCHEMA_VERSION,
        "record_id": record_id,
        "domain": repaired.get("domain"),
        "hard_a_family": hard_atom(repaired).get("hard_a_family"),
        "prior_record_fingerprint": prior_fingerprint,
        "repaired_record_fingerprint": canonical_sha256(repaired),
        "prior_qc_decision": prior_qc.get("computed_decision"),
        "prior_qc_reasons": reasons,
        "actions": actions,
        "validation_errors": errors,
        "decision": "pass" if not errors else "reject",
        "fresh_independent_qc_required": True,
    }
    repaired["direct_tail_repair"] = {
        key: value
        for key, value in audit.items()
        if key not in {"actions", "validation_errors"}
    }
    repaired["direct_tail_repair"]["actions"] = copy.deepcopy(actions)
    return repaired, audit


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Directly repair and formally audit the final non-strict MemCalib v2.1 tail."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--repaired", type=Path, default=DEFAULT_REPAIRED)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args()

    rows = list(iter_jsonl(args.input))
    ids = [str(row.get("id") or "") for row in rows]
    if "" in ids or len(ids) != len(set(ids)):
        raise ValueError("input record IDs must be non-empty and unique")
    non_strict_ids = {
        str(row["id"])
        for row in rows
        if (row.get("revision_independent_qc") or {}).get("computed_decision") != "strict_pass"
    }
    expected_covered = set(REAL_ATOM_REPAIRS) | MANUAL_PROOF_IDS
    expected_covered |= {
        str(row["id"])
        for row in rows
        if any(
            str(reason).startswith("hard_a:")
            for reason in (row.get("revision_independent_qc") or {}).get("computed_reasons") or []
        )
    }
    if non_strict_ids != expected_covered:
        raise ValueError(
            f"tail coverage mismatch: missing={sorted(non_strict_ids - expected_covered)} "
            f"extra={sorted(expected_covered - non_strict_ids)}"
        )

    repaired_by_id: dict[str, dict[str, Any]] = {}
    audits: list[dict[str, Any]] = []
    for row in rows:
        record_id = str(row["id"])
        if record_id not in non_strict_ids:
            continue
        repaired, audit = repair_record(row)
        repaired_by_id[record_id] = repaired
        audits.append(audit)
    failures = [audit for audit in audits if audit["validation_errors"]]
    if failures:
        details = [
            {
                "record_id": audit["record_id"],
                "validation_errors": audit["validation_errors"],
            }
            for audit in failures
        ]
        raise ValueError(
            f"direct repair validation failed for {len(failures)} records: "
            f"{json.dumps(details, ensure_ascii=False)}"
        )

    output = [repaired_by_id.get(str(row["id"]), row) for row in rows]
    repaired_rows = [repaired_by_id[str(row["id"])] for row in rows if str(row["id"]) in repaired_by_id]
    all_errors = [
        (str(row["id"]), validate_record(row))
        for row in output
        if validate_record(row)
    ]
    if all_errors:
        raise ValueError(f"full output validation failed for {len(all_errors)} records: {all_errors[:3]}")

    blocks = [block for row in output for block in row.get("memory_blocks") or []]
    multi_blocks = [block for block in blocks if len(block.get("atom_ids") or []) >= 2]
    family_by_domain: dict[str, Counter[str]] = defaultdict(Counter)
    for row in output:
        family_by_domain[str(row.get("domain") or "")][str(hard_atom(row).get("hard_a_family") or "")] += 1
    action_counts = Counter(
        action["kind"]
        for audit in audits
        for action in audit["actions"]
    )
    label_changes = Counter(
        action["label"]
        for audit in audits
        for action in audit["actions"]
        if action["kind"] == "repair_real_atom"
    )

    write_jsonl(args.output, output)
    write_jsonl(args.repaired, repaired_rows)
    write_jsonl(args.audit, audits)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "input": {
            "path": portable_path(args.input),
            "sha256": file_sha256(args.input),
            "records": len(rows),
        },
        "counts": {
            "output_records": len(output),
            "unique_record_ids": len({str(row["id"]) for row in output}),
            "tail_records": len(repaired_rows),
            "tail_validation_failures": len(failures),
            "visible_blocks": len(blocks),
            "multi_atom_visible_blocks": len(multi_blocks),
            "multi_atom_visible_block_share": len(multi_blocks) / len(blocks),
            "samples_with_multi_atom_block": sum(
                any(len(block.get("atom_ids") or []) >= 2 for block in row.get("memory_blocks") or [])
                for row in output
            ),
        },
        "actions": dict(sorted(action_counts.items())),
        "repaired_real_atom_labels": dict(sorted(label_changes.items())),
        "distribution": {
            "domain": dict(sorted(Counter(str(row.get("domain") or "") for row in output).items())),
            "hard_a_family": dict(
                sorted(Counter(str(hard_atom(row).get("hard_a_family") or "") for row in output).items())
            ),
            "hard_a_family_by_domain": {
                domain: dict(sorted(counts.items()))
                for domain, counts in sorted(family_by_domain.items())
            },
        },
        "outputs": {
            "benchmark": {"path": portable_path(args.output), "sha256": file_sha256(args.output)},
            "repaired_tail": {
                "path": portable_path(args.repaired),
                "sha256": file_sha256(args.repaired),
            },
            "audit": {"path": portable_path(args.audit), "sha256": file_sha256(args.audit)},
        },
        "next_step": "fresh independent QC on exactly the 93 repaired/audited records",
    }
    write_json(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
