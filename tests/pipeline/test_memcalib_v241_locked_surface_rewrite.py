from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load_module(
    "prepare_locked_surface",
    ROOT / "pipeline" / "114_prepare_memcalib_v241_locked_surface_rewrite.py",
)
post = load_module(
    "post_locked_surface",
    ROOT / "pipeline" / "115_post_memcalib_v241_locked_surface_rewrite.py",
)


def atom(
    atom_id: str,
    label: str,
    action: str,
    text: str,
    minimal_evidence: list[str] | None = None,
) -> dict:
    return {
        "atom_id": atom_id,
        "parent_memory_id": atom_id.split("_")[0],
        "u_star": label,
        "memory_action": action,
        "text": text,
        "counterfactual_contract": {
            "without_memory_behavior": "The answer omits the requirement.",
            "with_memory_behavior": "The answer states the corrected behavior.",
            "observable_delta": "The corrected behavior is stated.",
            "minimal_evidence": minimal_evidence or [],
        },
    }


def record() -> dict:
    atoms = [
        atom(
            "p1_a1",
            "C",
            "apply",
            "The project uses FrameworkOne for request processing.",
        ),
        atom(
            "p2_a1",
            "B",
            "correct",
            "The user incorrectly believes FeatureTwo is unavailable.",
            ["FeatureTwo is available through the supported adapter"],
        ),
        atom("noise_a1", "A", "ignore", "The user owns a green notebook."),
    ]
    return {
        "id": "coding-example",
        "domain": "coding",
        "source_topic": "api_library",
        "question": "Write integration code.",
        "source_answer": "Original answer.",
        "memories": atoms,
        "memory_blocks": [
            {
                "parent_memory_id": "p1",
                "memory_text": "Project context.",
                "atom_ids": ["p1_a1", "p2_a1", "noise_a1"],
            }
        ],
    }


def test_locked_requirements_preserve_atom_attribution_and_correction() -> None:
    requirements = prepare.locked_requirements(record())
    assert requirements == [
        {
            "atom_id": "p1_a1",
            "role": "primary",
            "action": "apply",
            "required_evidence": [
                "The project uses FrameworkOne for request processing."
            ],
        },
        {
            "atom_id": "p2_a1",
            "role": "supporting",
            "action": "correct",
            "required_evidence": [
                "FeatureTwo is available through the supported adapter"
            ],
        },
    ]


def test_surface_validation_blocks_requirement_value_leakage() -> None:
    source = record()
    params = {
        "record_id": source["id"],
        "task_family": "implementation_plan",
        "locked_requirements": prepare.locked_requirements(source),
    }
    surface = {
        "schema_version": post.SURFACE_SCHEMA,
        "record_id": source["id"],
        "task_family": "implementation_plan",
        "task_stem": (
            "Prepare a natural-language integration plan for the project. "
            "The project uses FrameworkOne for request processing, so explain that "
            "exact project requirement and the bounded supporting behavior. Cover "
            "inputs, control flow, outputs, and failure handling without executable "
            "code, while keeping the response concise and suitable for a design review."
        ),
        "self_check": {key: True for key in post.SELF_CHECK_KEYS},
    }
    errors = post.validate_surface(surface, params, source)
    assert any("query_atom_value_leakage" in error for error in errors)


def test_reference_keeps_primary_and_supporting_evidence_separate() -> None:
    requirements = prepare.locked_requirements(record())
    reference = post.build_reference(requirements)
    assert "The project uses FrameworkOne for request processing." in reference
    assert "FeatureTwo is available through the supported adapter" in reference
    assert reference.index("primary requirements") < reference.index(
        "bounded supporting considerations"
    )


def test_correction_evidence_is_supported_by_locked_correction_contract() -> None:
    source = record()
    atoms = post.applicable_atoms(source)
    requirement = prepare.locked_requirements(source)[1]
    from memcalib_v24_alignment import analyze_atom_alignment

    result = analyze_atom_alignment(
        atoms[1],
        " ".join(requirement["required_evidence"]),
        atoms,
        "Explain the required supporting correction without naming its value.",
    )
    assert "rubric_introduces_unsupported_identifier" not in result["reasons"]
    assert "very_low_atom_rubric_overlap" not in result["reasons"]


def test_fallback_surface_is_long_and_keeps_requirement_values_unresolved() -> None:
    source = record()
    params = {
        "record_id": source["id"],
        "task_family": "debugging_diagnosis",
        "locked_requirements": prepare.locked_requirements(source),
    }
    surface = post.fallback_surface(source, params)
    assert len(surface["task_stem"].split()) >= 40
    assert "FrameworkOne" not in surface["task_stem"]
    assert "FeatureTwo" not in surface["task_stem"]
    assert post.validate_surface(surface, params, source) == []
