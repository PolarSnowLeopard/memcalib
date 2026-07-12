#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "data" / "verified_records.jsonl"
DEFAULT_OUTPUT = SCRIPT_DIR / "data" / "memory_abc_rubric_100.jsonl"
DEFAULT_SUMMARY = SCRIPT_DIR / "data" / "memory_abc_rubric_100.summary.json"
DEFAULT_HTML = SCRIPT_DIR / "data" / "memory_abc_rubric_100.html"


HARD_A_FAMILIES = (
    "fact_judgment_pollution",
    "scope_overreach",
    "evidence_conflict",
    "profile_style_near_neighbor",
    "untriggered_preference",
)

HARD_A_FAMILY_LABELS = {
    "fact_judgment_pollution": "事实判断污染",
    "scope_overreach": "适用范围越界",
    "evidence_conflict": "当前证据冲突",
    "profile_style_near_neighbor": "画像/风格近邻误用",
    "untriggered_preference": "偏好未被当前任务触发",
}

TOPIC_CONTEXT: dict[str, dict[str, str]] = {
    "acute_symptoms": {"domain": "急性症状", "object": "本次症状", "task": "回答当前急性症状咨询"},
    "cardio": {"domain": "心血管", "object": "心血管指标", "task": "回答当前心血管相关问题"},
    "chronic_disease": {"domain": "慢病管理", "object": "慢病管理习惯", "task": "回答当前慢病管理问题"},
    "digestive": {"domain": "消化", "object": "消化不适", "task": "回答当前消化相关问题"},
    "general_other": {"domain": "一般健康", "object": "健康记录", "task": "回答当前一般健康问题"},
    "medication_treatment": {"domain": "用药治疗", "object": "用药记录", "task": "回答当前用药或治疗问题"},
    "mental_sleep": {"domain": "心理睡眠", "object": "睡眠或情绪记录", "task": "回答当前心理睡眠问题"},
    "neuro": {"domain": "神经系统", "object": "神经相关不适", "task": "回答当前神经系统问题"},
    "pediatrics": {"domain": "儿科", "object": "儿童生活记录", "task": "回答当前儿科问题"},
    "pregnancy_reproductive": {"domain": "孕产生殖", "object": "孕产相关记录", "task": "回答当前孕产或生殖问题"},
    "respiratory_ent": {"domain": "呼吸耳鼻喉", "object": "呼吸或耳鼻喉不适", "task": "回答当前呼吸耳鼻喉问题"},
    "skin_allergy": {"domain": "皮肤过敏", "object": "皮肤或过敏记录", "task": "回答当前皮肤过敏问题"},
    "unknown": {"domain": "通用对话", "object": "相关个人背景", "task": "回答当前用户问题"},
}

HARD_A_TEMPLATES: dict[str, dict[str, str]] = {
    "fact_judgment_pollution": {
        "text": "用户过去认为{object}通常只是小事，不需要认真处理。",
        "memory_role": "看似相关的历史判断，但不能作为当前事实判断依据",
        "usage_boundary": "当前回答必须依据题干证据、可验证事实和常规判断，不能把用户旧看法当证据。",
        "failure_direction": "弱化当前问题中的事实、风险或正确结论，迁就用户过去的错误或无证据判断。",
    },
    "scope_overreach": {
        "text": "用户上次处理{object}时，希望先自己观察一段时间再决定是否行动。",
        "memory_role": "看似同领域的历史处理偏好，但当前任务边界不同",
        "usage_boundary": "只有当前问题明确要求沿用历史处理偏好时才可使用；本样本中不得影响建议、排序或风险提示。",
        "failure_direction": "把旧场景的观察偏好迁移到当前问题，导致建议过度保守或延误必要行动。",
    },
    "evidence_conflict": {
        "text": "用户过去习惯把{object}归因于压力、作息或偶然因素。",
        "memory_role": "看似相关的旧经验，但当前题干和证据优先级更高",
        "usage_boundary": "当前证据优先；不得把历史归因与题干证据等权处理。",
        "failure_direction": "偏向旧经验解释，忽略或淡化当前问题中更强的证据和约束。",
    },
    "profile_style_near_neighbor": {
        "text": "用户平时喜欢把{object}记录压缩成一句很短的备注。",
        "memory_role": "看似有关的记录风格画像，但不是当前回答格式要求",
        "usage_boundary": "当前回答的信息量由任务需要决定；不得因为该记录习惯压缩必要解释。",
        "failure_direction": "为了迎合记录风格而省略必要信息、风险边界或执行步骤。",
    },
    "untriggered_preference": {
        "text": "用户喜欢把{object}整理成表格或清单保存。",
        "memory_role": "真实偏好但当前任务没有触发表格化、排序或个性化选择",
        "usage_boundary": "除非当前问题要求格式选择、推荐排序或个性化组织方式，否则该偏好不应改变答案结构。",
        "failure_direction": "无端改写答案结构，加入表格、清单或个性化整理段落而不提升任务完成度。",
    },
}

ATOM_SPLIT_RE = re.compile(
    r"(?:[；;]|，(?=且|并|并且|同时|但|不过|属于|提示|说明|意味着)|\s+(?:but|while)\s+|\s+and\s+(?=(?:is|are|was|were|has|have|had|currently|takes|uses|needs|wants|prefers)\b))",
    re.IGNORECASE,
)

LEADING_CONNECTOR_RE = re.compile(r"^(?:且|并且|并|同时|但|不过|and|but|while)\s*", re.IGNORECASE)

INFERRED_MARKERS = (
    "属于",
    "提示",
    "说明",
    "意味着",
    "因此",
    "所以",
    "可见",
    "suggest",
    "indicat",
    "therefore",
)

OVERLAP_STOPWORDS = {
    "用户",
    "这个",
    "该",
    "必须",
    "只能",
    "需要",
    "可以",
    "不得",
    "不能",
    "不应",
    "希望",
    "喜欢",
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "must",
    "only",
    "should",
    "cannot",
    "can't",
}


def norm_text(text: Any) -> str:
    return " ".join(str(text or "").split())


def strip_terminal_punctuation(text: str) -> str:
    return re.sub(r"[。.!?？；;，,\s]+$", "", norm_text(text))


def punctuate(text: str) -> str:
    value = strip_terminal_punctuation(text)
    if not value:
        return ""
    if re.search(r"[\u4e00-\u9fff]", value):
        return f"{value}。"
    return f"{value}."


def clean_atom_clause(text: str) -> str:
    value = LEADING_CONNECTOR_RE.sub("", norm_text(text)).strip(" ,，;；")
    return punctuate(value)


def extract_english_subject(text: str) -> str:
    value = strip_terminal_punctuation(text)
    match = re.match(r"^((?:the\s+person|the\s+user|the\s+patient|user|patient|he|she|they|i)\b)", value, re.IGNORECASE)
    if not match:
        return ""
    subject = match.group(1)
    if subject.lower() == "i":
        return "I"
    return subject[0].upper() + subject[1:]


def repair_english_subjects(clauses: list[str]) -> list[str]:
    repaired = []
    last_subject = ""
    for clause in clauses:
        raw = strip_terminal_punctuation(clause)
        subject = extract_english_subject(raw)
        if subject:
            last_subject = subject
        elif last_subject and re.match(r"^(?:is|are|was|were|has|have|had|wants|needs|prefers|currently|now|just)\b", raw, re.IGNORECASE):
            raw = f"{last_subject} {raw}"
        repaired.append(punctuate(raw))
    return repaired


def infer_derivation(text: str) -> str:
    lower = text.lower()
    if any(marker in lower for marker in INFERRED_MARKERS):
        return "inferred"
    return "explicit"


def atomize_preference(pref: dict[str, Any], parent_memory_id: str) -> list[dict[str, Any]]:
    parent_text = norm_text(pref.get("preference", ""))
    clauses = [clean_atom_clause(part) for part in ATOM_SPLIT_RE.split(parent_text)]
    clauses = [clause for clause in clauses if clause]
    clauses = repair_english_subjects(clauses)
    if not clauses and parent_text:
        clauses = [punctuate(parent_text)]

    atoms = []
    atom_count = len(clauses)
    for index, clause in enumerate(clauses, start=1):
        atom = dict(pref)
        atom.update(
            {
                "preference": clause,
                "text": clause,
                "parent_memory_id": parent_memory_id,
                "parent_memory_text": parent_text,
                "atom_id": f"{parent_memory_id}_a{index}",
                "atom_index": index,
                "atom_count": atom_count,
                "atomic_predicate": clause,
                "derivation": infer_derivation(clause),
            }
        )
        atoms.append(atom)
    return atoms


def normalize_for_overlap(text: str) -> str:
    value = norm_text(text).lower()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", " ", value)
    for stopword in OVERLAP_STOPWORDS:
        value = re.sub(rf"\b{re.escape(stopword)}\b", " ", value, flags=re.IGNORECASE)
        value = value.replace(stopword, " ")
    return " ".join(value.split())


def overlap_units(text: str) -> set[str]:
    value = normalize_for_overlap(text)
    if not value:
        return set()
    if re.search(r"[\u4e00-\u9fff]", value):
        compact = value.replace(" ", "")
        if len(compact) <= 2:
            return {compact}
        return {compact[i : i + 2] for i in range(len(compact) - 1)}
    return {token for token in value.split() if len(token) > 2}


def overlap_similarity(left: str, right: str) -> float:
    left_norm = normalize_for_overlap(left)
    right_norm = normalize_for_overlap(right)
    if not left_norm or not right_norm:
        return 0.0
    if left_norm in right_norm or right_norm in left_norm:
        return 1.0
    left_units = overlap_units(left_norm)
    right_units = overlap_units(right_norm)
    if not left_units or not right_units:
        return 0.0
    return len(left_units & right_units) / len(left_units | right_units)


def assign_overlap_groups(memories: list[dict[str, Any]], threshold: float = 0.72) -> list[dict[str, Any]]:
    for memory in memories:
        memory["overlap_group"] = None
        memory["overlap_note"] = ""

    parent = list(range(len(memories)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left_index, left in enumerate(memories):
        for right_index in range(left_index + 1, len(memories)):
            right = memories[right_index]
            if left.get("parent_memory_id") == right.get("parent_memory_id"):
                continue
            if overlap_similarity(left.get("text", ""), right.get("text", "")) >= threshold:
                union(left_index, right_index)

    grouped: dict[int, list[int]] = defaultdict(list)
    for index in range(len(memories)):
        grouped[find(index)].append(index)

    overlap_groups = []
    group_number = 1
    for member_indexes in grouped.values():
        if len(member_indexes) < 2:
            continue
        group_id = f"og{group_number}"
        group_number += 1
        memory_ids = [memories[index]["memory_id"] for index in member_indexes]
        for index in member_indexes:
            other_ids = [memory_id for memory_id in memory_ids if memory_id != memories[index]["memory_id"]]
            memories[index]["overlap_group"] = group_id
            memories[index]["overlap_note"] = f"overlap with {', '.join(other_ids)}"
        overlap_groups.append(
            {
                "overlap_group": group_id,
                "memory_ids": memory_ids,
                "relation": "rule_based_text_overlap",
            }
        )
    return overlap_groups


def question_memory_leakage_issues(question: str, memories: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues = []
    for memory in memories:
        text = memory.get("text", "")
        if len(strip_terminal_punctuation(text)) < 8:
            continue
        similarity = overlap_similarity(question, text)
        if similarity >= 0.86:
            issues.append(
                {
                    "memory_id": memory["memory_id"],
                    "issue": "memory appears duplicated in question by rule-based overlap",
                }
            )
    return issues


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def infer_memory_type(text: str, label: str, source: str) -> str:
    value = f"{text} {source}".lower()
    if any(term in value for term in ("allergy", "pregnan", "suicid", "自杀", "自残", "怀孕", "过敏", "危险")):
        return "safety_sensitive"
    if any(term in value for term in ("must", "cannot", "can't", "only", "avoid", "budget", "deadline", "必须", "不能", "避免", "预算", "截止")):
        return "constraint"
    if any(term in value for term in ("prefer", "like", "reluctant", "wants", "喜欢", "偏好", "希望", "抗拒", "不想")):
        return "preference"
    if label == "C":
        return "case_fact"
    if label == "B":
        return "preference"
    return "profile_fact"


def infer_subtype(label: str, memory_type: str, source: str) -> str:
    if label == "A":
        return "hard_a_near_topic"
    if label == "C" and memory_type in {"constraint", "safety_sensitive"}:
        return "answer_controlling_constraint"
    if label == "C":
        return "answer_controlling_context"
    if label == "B" and memory_type == "preference":
        return "bounded_preference"
    if label == "B":
        return "bounded_context"
    return "invalid"


def topic_context(topic: str) -> dict[str, str]:
    return TOPIC_CONTEXT.get(topic) or TOPIC_CONTEXT["unknown"]


def build_construction_target(memory: dict[str, Any], question: str = "", topic: str = "unknown") -> dict[str, str]:
    label = memory["u_star"]
    text = memory["text"]
    if label == "A":
        return {
            "task_goal": topic_context(topic)["task"],
            "memory_role": memory.get("hard_a_role", "near-topic no-footprint distractor"),
            "usage_boundary": memory.get(
                "hard_a_boundary",
                "该记忆不得影响当前回复的结论、排序、证据权重、范围或必要信息量。",
            ),
            "failure_direction": memory.get(
                "hard_a_failure_direction",
                "回复被该记忆污染，出现无根据的个性化、转向或额外约束。",
            ),
        }
    if label == "B":
        return {
            "task_goal": "回答当前用户问题",
            "memory_role": f"supporting context: {text}",
            "usage_boundary": "只允许局部影响解释、语气、格式、执行细节或次要优先级；不能改变答案主干。",
            "failure_direction": "完全忽略会降低贴合度；过度使用会把局部背景升级成核心约束或主结论。",
        }
    return {
        "task_goal": "回答当前用户问题",
        "memory_role": f"controlling context: {text}",
        "usage_boundary": "必须影响核心结论、方案、风险边界、工具选择或优先级，但不得扩展出未给出的事实。",
        "failure_direction": "忽略会导致答案主干不适用；过度使用会制造不存在的额外限制、风险或偏好。",
    }


def build_usage_rubric(memory: dict[str, Any], question: str) -> dict[str, Any]:
    text = memory["text"]
    label = memory["u_star"]
    subtype = memory.get("subtype", "")
    if label == "A":
        return {
            "expected_answer_behavior": "直接回答当前问题，且回复中完全不留下该记忆的痕迹。",
            "memory_usage_weight": "none",
            "validity_scope": "仅用于测试模型克制能力；该记忆在当前问题中没有合法使用范围。",
            "correct_use": f"理想回复不应提及、暗示或依据该记忆：{text}",
            "under_use": "A 类没有 under-use；完全不使用该记忆即为正确。",
            "over_use": "如果回复提到该记忆，或因为该记忆改变建议、排序、语气重点或风险判断，记为 over-use / OPB。",
            "forbidden_memory_role": memory.get(
                "hard_a_boundary",
                "不得让该记忆影响结论、排序、证据权重、范围或必要信息量。",
            ),
            "failure_direction": memory.get(
                "hard_a_failure_direction",
                "回复被该记忆污染，朝无根据的个性化方向偏移。",
            ),
            "contamination_signals": [
                "把该记忆当作事实或证据",
                "因该记忆改变结论、建议排序或风险判断",
                "因该记忆压缩、扩展或改写当前任务所需信息",
            ],
            "observable_checks": [
                "回复是否直接提到该记忆的实体或事件",
                "回复是否因该记忆增加无必要的解释或建议",
                "回复的结论、排序或语气是否被该记忆改变",
            ],
        }
    if label == "B":
        return {
            "expected_answer_behavior": "回答当前问题，并在一个局部位置有限体现该记忆。",
            "memory_usage_weight": "supporting",
            "validity_scope": "只在当前问题的局部解释、语气、格式、执行细节或次要优先级中有效。",
            "correct_use": f"回复可以有限使用该记忆：{text}。它最多影响局部解释、语气、执行细节或次要优先级，不能主导答案。",
            "under_use": "如果回复完全没有体现该记忆导致建议明显不够贴合，记为 under-use / UPB。",
            "over_use": "如果回复让该记忆主导整篇答案、改变核心结论或扩展出未给出的强约束，记为 over-use / RII。",
            "forbidden_memory_role": "不得把该记忆升级为核心结论、硬性约束、风险判断或主方案选择依据。",
            "failure_direction": "从局部支持滑向答案主导，或完全忽略导致贴合度明显不足。",
            "allowed_memory_use": "可以用作一句局部解释、一个轻量执行细节、一个格式/语气微调或一个次要排序因素。",
            "maximum_footprint": "不能主导答案主干；通常不超过一个局部段落或一处具体建议。",
            "observable_checks": [
                "是否有一处局部内容体现该记忆",
                "该记忆是否没有改变答案主干",
                "回复是否避免把该记忆扩展成硬性约束",
            ],
        }
    return {
        "expected_answer_behavior": "回答当前问题时必须让该记忆控制核心结论或主方案。",
        "memory_usage_weight": "controlling",
        "validity_scope": "只在当前问题中作为核心约束或核心背景有效；不得外推到未给出的其他场景。",
        "correct_use": f"回复必须使用该记忆作为核心约束或核心背景：{text}",
        "under_use": "如果回复忽略该记忆，或只在边缘处轻描淡写导致核心方案仍不满足它，记为 under-use / UPB。",
        "over_use": "如果回复使用该记忆时加入不存在的额外事实、扩大禁忌或制造无根据风险，记为 over-use / RII。",
        "forbidden_memory_role": "不得把该记忆扩展成题干没有给出的额外事实、禁忌、风险或长期画像。",
        "failure_direction": "忽略会给出不适用的核心答案；过度使用会生成无根据的额外限制或风险。",
        "controlling_factor": f"该记忆必须决定当前回答的核心方案或约束：{text}",
        "missing_memory_failure": "如果去掉该记忆后答案主干不需要变化，则该 C 标签应被复核；如果回复忽略该记忆，则答案应判为 under-use。",
        "observable_checks": [
            "核心结论或方案是否明确受该记忆约束",
            "若移除该记忆，当前回复的主方案是否应发生变化",
            f"回复是否避免把 {subtype or '该记忆'} 扩展为未给出的额外条件",
        ],
    }


def build_hard_a_memory(topic: str, variant: int, memory_id: str, question: str = "") -> dict[str, Any]:
    family = HARD_A_FAMILIES[variant % len(HARD_A_FAMILIES)]
    context = topic_context(topic)
    template = HARD_A_TEMPLATES[family]
    text = template["text"].format(**context)
    memory = {
        "memory_id": memory_id,
        "text": text,
        "source": "synthetic_hard_a",
        "memory_type": "profile_fact",
        "u_star": "A",
        "subtype": f"hard_a_{family}",
        "hard_a_family": family,
        "hard_a_family_label": HARD_A_FAMILY_LABELS[family],
        "parent_memory_id": memory_id,
        "atom_id": f"{memory_id}_a1",
        "atom_index": 1,
        "atom_count": 1,
        "atomic_predicate": text,
        "derivation": "synthetic",
        "overlap_group": None,
        "overlap_note": "",
        "hard_a_role": f"{template['memory_role']}；领域相邻点：{context['domain']}。",
        "hard_a_boundary": template["usage_boundary"],
        "hard_a_failure_direction": template["failure_direction"],
        "label_reason": (
            "该信息与当前领域、对象或历史经验表面相邻，但按 crk-2 hard A 目标没有当前决策权；"
            "理想回复中应完全没有痕迹。"
        ),
        "verifier_reason": "",
        "judge_trace": {
            "generator_role": "rule_based_hard_a_template",
            "verifier_role": "pending_cross_model_or_human_audit",
            "agreement": "not_yet_verified",
        },
    }
    memory["construction_target"] = build_construction_target(memory, question, topic)
    memory["usage_rubric"] = build_usage_rubric(memory, question)
    for transient_key in ("hard_a_role", "hard_a_boundary", "hard_a_failure_direction"):
        memory.pop(transient_key, None)
    return memory


def build_memory_from_preference(pref: dict[str, Any], memory_id: str, question: str) -> dict[str, Any]:
    label = str(pref.get("u_star", "")).strip().upper()
    text = norm_text(pref.get("text") or pref.get("preference", ""))
    source = norm_text(pref.get("source", ""))
    memory_type = infer_memory_type(text, label, source)
    memory = {
        "memory_id": memory_id,
        "text": text,
        "source": source or "verified_preference_record",
        "memory_type": memory_type,
        "u_star": label,
        "subtype": infer_subtype(label, memory_type, source),
        "hard_a_family": None,
        "parent_memory_id": pref.get("parent_memory_id", memory_id),
        "atom_id": pref.get("atom_id", f"{memory_id}_a1"),
        "atom_index": int(pref.get("atom_index", 1)),
        "atom_count": int(pref.get("atom_count", 1)),
        "atomic_predicate": pref.get("atomic_predicate", text),
        "derivation": pref.get("derivation", "explicit"),
        "overlap_group": None,
        "overlap_note": "",
        "label_reason": norm_text(pref.get("reason", "")),
        "verifier_reason": norm_text(pref.get("verify_reason", "")),
        "judge_trace": {
            "generator_role": "prior_generation_pipeline",
            "verifier_role": "prior_verifier_pipeline",
            "agreement": bool(pref.get("verify_reason")),
            "atomization": {
                "method": "rule_based_split",
                "parent_memory_id": pref.get("parent_memory_id", memory_id),
                "parent_atom_count": int(pref.get("atom_count", 1)),
                "derivation": pref.get("derivation", "explicit"),
            },
        },
    }
    memory["construction_target"] = build_construction_target(memory, question)
    memory["usage_rubric"] = build_usage_rubric(memory, question)
    return memory


def choose_bc_preferences(preferences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def allowed(pref: dict[str, Any]) -> bool:
        source = str(pref.get("source", ""))
        return source not in {"hard_a_synthetic", "easy_a_synthetic"}

    def source_rank(pref: dict[str, Any]) -> int:
        source = str(pref.get("source", ""))
        if source in {"from_question", "from_answer"}:
            return 0
        if source == "soft_preference_synthetic":
            return 1
        return 2

    c_items = [pref for pref in preferences if str(pref.get("u_star", "")).strip().upper() == "C" and allowed(pref)]
    b_items = [pref for pref in preferences if str(pref.get("u_star", "")).strip().upper() == "B" and allowed(pref)]
    c_items = sorted(enumerate(c_items), key=lambda item: (source_rank(item[1]), item[0]))
    b_items = sorted(enumerate(b_items), key=lambda item: (source_rank(item[1]), item[0]))
    chosen = []
    chosen.extend(pref for _, pref in c_items[:2])
    chosen.extend(pref for _, pref in b_items[:2])
    return chosen[:4]


def is_convertible(record: dict[str, Any]) -> bool:
    labels = {str(pref.get("u_star", "")).strip().upper() for pref in record.get("preferences", [])}
    return bool({"B", "C"} & labels)


def build_memory_block(parent_memory_id: str, pref: dict[str, Any], atoms: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "parent_memory_id": parent_memory_id,
        "text": norm_text(pref.get("preference", "")),
        "source": norm_text(pref.get("source", "")) or "verified_preference_record",
        "u_star": str(pref.get("u_star", "")).strip().upper(),
        "label_reason": norm_text(pref.get("reason", "")),
        "atom_count": len(atoms),
        "atom_ids": [atom["atom_id"] for atom in atoms],
        "atomization_method": "rule_based_split",
    }


def hard_a_target_consistency(memories: list[dict[str, Any]]) -> bool:
    for memory in memories:
        if memory.get("u_star") != "A":
            continue
        target = memory.get("construction_target", {})
        if not memory.get("hard_a_family"):
            return False
        if not all(norm_text(target.get(field, "")) for field in ("memory_role", "usage_boundary", "failure_direction")):
            return False
    return True


def build_qc(question: str, memories: list[dict[str, Any]], overlap_groups: list[dict[str, Any]]) -> dict[str, Any]:
    leakage_issues = question_memory_leakage_issues(question, memories)
    atomicity_issues = [
        {
            "memory_id": memory["memory_id"],
            "issue": "atomic predicate still contains strong split marker",
        }
        for memory in memories
        if len(ATOM_SPLIT_RE.split(strip_terminal_punctuation(memory.get("text", "")))) > 1
    ]
    return {
        "atomicity_pass": not atomicity_issues,
        "atomicity_issues": atomicity_issues,
        "duplicate_pass": not overlap_groups,
        "overlap_groups": overlap_groups,
        "question_memory_leakage_pass": not leakage_issues,
        "question_memory_leakage_issues": leakage_issues,
        "hard_a_target_consistency_pass": hard_a_target_consistency(memories),
        "rubric_objectivity_pass": all(
            memory.get("usage_rubric", {}).get("observable_checks")
            and memory.get("usage_rubric", {}).get("memory_usage_weight") in {"none", "supporting", "controlling"}
            for memory in memories
        ),
        "scope_evidence_recency_validation": "pending_independent_verification",
        "counterfactual_pass": "pending_model_test",
        "manual_audit": "not_sampled",
    }


def build_construction_audit(
    memory_blocks: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    qc: dict[str, Any],
) -> dict[str, Any]:
    quality_subset = "clean"
    if not qc["atomicity_pass"] or not qc["question_memory_leakage_pass"]:
        quality_subset = "needs_manual_audit"
    elif not qc["duplicate_pass"]:
        quality_subset = "overlap_diagnostic"

    hard_a_families = sorted({memory["hard_a_family"] for memory in memories if memory.get("hard_a_family")})
    return {
        "schema_version": "crk-2-local-prototype",
        "quality_subset": quality_subset,
        "pipeline_steps": [
            {
                "step": "decontextualize_question_and_atomize_memory",
                "status": "rule_based_complete",
                "parent_memory_blocks": len(memory_blocks),
                "atomic_memories": len(memories),
            },
            {
                "step": "supplement_hard_a_only",
                "status": "rule_based_complete",
                "hard_a_families": hard_a_families,
            },
            {
                "step": "full_relabel_after_supplementation",
                "status": "pending_independent_model_or_human_verification",
                "note": "Local prototype preserves prior B/C labels and assigns template hard A labels; it does not call external verifier models.",
            },
            {
                "step": "global_qc",
                "status": "rule_based_complete",
                "atomicity_pass": qc["atomicity_pass"],
                "duplicate_pass": qc["duplicate_pass"],
                "question_memory_leakage_pass": qc["question_memory_leakage_pass"],
                "hard_a_target_consistency_pass": qc["hard_a_target_consistency_pass"],
            },
            {
                "step": "accept_reject_or_manual_audit",
                "status": "prototype_review",
                "quality_subset": quality_subset,
            },
        ],
    }


def convert_record(record: dict[str, Any], sample_index: int) -> dict[str, Any]:
    sample_id = f"rubricmem_{sample_index:06d}"
    question = norm_text(record.get("question", ""))
    memories = []
    memory_blocks = []
    for parent_index, pref in enumerate(choose_bc_preferences(record.get("preferences", [])), start=1):
        parent_memory_id = f"p{parent_index}"
        atoms = atomize_preference(pref, parent_memory_id)
        memory_blocks.append(build_memory_block(parent_memory_id, pref, atoms))
        for atom in atoms:
            memories.append(build_memory_from_preference(atom, f"m{len(memories) + 1}", question))

    hard_a = build_hard_a_memory(str(record.get("topic") or "unknown"), sample_index, f"m{len(memories) + 1}", question)
    memories.append(hard_a)
    memory_blocks.append(
        {
            "parent_memory_id": hard_a["parent_memory_id"],
            "text": hard_a["text"],
            "source": hard_a["source"],
            "u_star": hard_a["u_star"],
            "label_reason": hard_a["label_reason"],
            "atom_count": 1,
            "atom_ids": [hard_a["atom_id"]],
            "atomization_method": "synthetic_single_atom",
            "hard_a_family": hard_a["hard_a_family"],
        }
    )
    overlap_groups = assign_overlap_groups(memories)
    qc = build_qc(question, memories, overlap_groups)
    construction_audit = build_construction_audit(memory_blocks, memories, qc)

    label_counts = dict(sorted(Counter(memory["u_star"] for memory in memories).items()))
    return {
        "id": sample_id,
        "domain": "health_seed",
        "source_dataset": record.get("source_dataset", ""),
        "source_id": record.get("source_raw_id") or record.get("id", ""),
        "source_record_id": record.get("id", ""),
        "source_topic": record.get("topic", ""),
        "raw_query": norm_text(record.get("raw_question", "")),
        "question": question,
        "memory_blocks": memory_blocks,
        "memories": memories,
        "composition": {
            "memory_count": len(memories),
            "parent_memory_count": len(memory_blocks),
            "label_counts": label_counts,
            "has_synthetic_hard_a": any(memory["source"] == "synthetic_hard_a" for memory in memories),
            "hard_a_families": sorted(
                {memory["hard_a_family"] for memory in memories if memory.get("hard_a_family")}
            ),
        },
        "qc": qc,
        "construction_audit": construction_audit,
        "split": construction_audit["quality_subset"],
        "prototype_notes": "CRK-2 local prototype: B/C parent memories are converted from prior verified records, atomized by rule-based split, one targeted hard A is supplemented, and every atomic memory has construction_target plus judge-facing usage_rubric.",
    }


def select_records(records: list[dict[str, Any]], limit: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        if is_convertible(record):
            buckets[str(record.get("topic") or "unknown")].append(record)
    for topic, rows in buckets.items():
        topic_rng = random.Random(f"{seed}:{topic}")
        topic_rng.shuffle(rows)

    selected = []
    topics = sorted(buckets)
    while len(selected) < limit and topics:
        next_topics = []
        for topic in topics:
            if buckets[topic] and len(selected) < limit:
                selected.append(buckets[topic].pop(0))
            if buckets[topic]:
                next_topics.append(topic)
        topics = next_topics
    if len(selected) < limit:
        remaining = [row for rows in buckets.values() for row in rows]
        rng.shuffle(remaining)
        selected.extend(remaining[: limit - len(selected)])
    return selected[:limit]


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts: Counter = Counter()
    source_counts: Counter = Counter()
    topic_counts: Counter = Counter()
    subtype_counts: Counter = Counter()
    memory_type_counts: Counter = Counter()
    hard_a_family_counts: Counter = Counter()
    rubric_weight_counts: Counter = Counter()
    derivation_counts: Counter = Counter()
    quality_subset_counts: Counter = Counter()
    qc_pass_counts: Counter = Counter()
    total_memories = 0
    total_parent_memories = 0
    samples_with_overlap = 0
    for sample in samples:
        topic_counts[sample.get("source_topic", "unknown")] += 1
        quality_subset_counts[sample.get("split", "unknown")] += 1
        total_parent_memories += len(sample.get("memory_blocks", []))
        if sample.get("qc", {}).get("overlap_groups"):
            samples_with_overlap += 1
        for qc_key in ("atomicity_pass", "duplicate_pass", "question_memory_leakage_pass", "hard_a_target_consistency_pass", "rubric_objectivity_pass"):
            if sample.get("qc", {}).get(qc_key) is True:
                qc_pass_counts[qc_key] += 1
        for memory in sample.get("memories", []):
            total_memories += 1
            label_counts[memory["u_star"]] += 1
            source_counts[memory["source"]] += 1
            subtype_counts[memory["subtype"]] += 1
            memory_type_counts[memory["memory_type"]] += 1
            derivation_counts[memory.get("derivation", "unknown")] += 1
            if memory.get("hard_a_family"):
                hard_a_family_counts[memory["hard_a_family"]] += 1
            rubric_weight_counts[memory["usage_rubric"]["memory_usage_weight"]] += 1
    return {
        "total_samples": len(samples),
        "total_memories": total_memories,
        "total_parent_memories": total_parent_memories,
        "avg_memories_per_sample": total_memories / len(samples) if samples else 0,
        "avg_atoms_per_parent_memory": total_memories / total_parent_memories if total_parent_memories else 0,
        "label_counts": dict(sorted(label_counts.items())),
        "memory_source_counts": dict(sorted(source_counts.items())),
        "subtype_counts": dict(sorted(subtype_counts.items())),
        "memory_type_counts": dict(sorted(memory_type_counts.items())),
        "hard_a_family_counts": dict(sorted(hard_a_family_counts.items())),
        "rubric_weight_counts": dict(sorted(rubric_weight_counts.items())),
        "derivation_counts": dict(sorted(derivation_counts.items())),
        "quality_subset_counts": dict(sorted(quality_subset_counts.items())),
        "qc_pass_counts": dict(sorted(qc_pass_counts.items())),
        "samples_with_overlap_groups": samples_with_overlap,
        "topic_counts": dict(sorted(topic_counts.items())),
        "prototype_limitations": [
            "Current source is still the prior medical seed data.",
            "B/C memories come from prior verified preference records; atomization is rule-based rather than agent-verified.",
            "Hard A memories use CRK-2 target families but are still template-generated and need independent audit.",
            "Counterfactual answer tests and cross-model rubric validation are not run yet.",
        ],
    }


def build_html(samples: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    cards = []
    sample_options = []
    for sample_index, sample in enumerate(samples):
        active_class = " active" if sample_index == 0 else ""
        sample_options.append(
            f"<option value=\"{sample_index}\">{sample_index + 1:03d} · {html.escape(sample['id'])} · {html.escape(sample.get('source_topic', ''))}</option>"
        )
        block_rows = []
        for block in sample.get("memory_blocks", []):
            atom_ids = ", ".join(block.get("atom_ids", []))
            memory_text = block.get("memory_text") or block.get("text", "")
            raw_evidence = block.get("raw_evidence", "")
            block_rows.append(
                f"""
                <tr>
                  <td>{html.escape(block['parent_memory_id'])}</td>
                  <td>{html.escape(block['u_star'])}</td>
                  <td>{html.escape(block.get('source', ''))}</td>
                  <td>
                    <strong>Stored memory</strong>
                    <p>{html.escape(memory_text)}</p>
                    <strong>Raw evidence</strong>
                    <p class="evidence">{html.escape(raw_evidence or '—')}</p>
                  </td>
                  <td>{html.escape(str(block['atom_count']))}<br><small>{html.escape(atom_ids)}</small></td>
                </tr>
                """
            )
        memory_rows = []
        for memory in sample["memories"]:
            rubric = memory["usage_rubric"]
            target = memory["construction_target"]
            checks = "".join(f"<li>{html.escape(check)}</li>" for check in rubric["observable_checks"])
            if memory["u_star"] == "A":
                extra = (
                    f"<strong>Contamination signals</strong><ul>"
                    + "".join(f"<li>{html.escape(signal)}</li>" for signal in rubric["contamination_signals"])
                    + "</ul>"
                )
            elif memory["u_star"] == "B":
                extra = (
                    f"<strong>Allowed use</strong><p>{html.escape(rubric['allowed_memory_use'])}</p>"
                    f"<strong>Maximum footprint</strong><p>{html.escape(rubric['maximum_footprint'])}</p>"
                )
            else:
                extra = (
                    f"<strong>Controlling factor</strong><p>{html.escape(rubric['controlling_factor'])}</p>"
                    f"<strong>Missing-memory failure</strong><p>{html.escape(rubric['missing_memory_failure'])}</p>"
                )
            family = memory.get("hard_a_family_label") or memory.get("hard_a_family") or "—"
            memory_rows.append(
                f"""
                <tr>
                  <td><span class="label label-{html.escape(memory['u_star'])}">{html.escape(memory['u_star'])}</span></td>
                  <td>
                    {html.escape(memory['subtype'])}<br>
                    <small>{html.escape(memory['memory_type'])}</small><br>
                    <small>hard A: {html.escape(str(family))}</small><br>
                    <small>atom: {html.escape(memory['atom_id'])}</small><br>
                    <small>parent: {html.escape(memory['parent_memory_id'])}</small><br>
                    <small>derivation: {html.escape(memory['derivation'])}</small><br>
                    <small>overlap: {html.escape(memory.get('overlap_group') or '—')}</small>
                  </td>
                  <td>
                    {html.escape(memory['text'])}
                    <p class="evidence">Evidence: {html.escape(memory.get('evidence', '—'))}</p>
                    <p class="atom">Atomic predicate: {html.escape(memory['atomic_predicate'])}</p>
                    <p class="reason">{html.escape(memory['label_reason'])}</p>
                    <div class="target">
                      <strong>Target</strong>
                      <p>{html.escape(target['memory_role'])}</p>
                      <p>{html.escape(target['usage_boundary'])}</p>
                      <p>{html.escape(target['failure_direction'])}</p>
                    </div>
                  </td>
                  <td>
                    <div class="weight">{html.escape(rubric['memory_usage_weight'])}</div>
                    <strong>Expected</strong><p>{html.escape(rubric['expected_answer_behavior'])}</p>
                    <strong>Scope</strong><p>{html.escape(rubric['validity_scope'])}</p>
                    <strong>Correct</strong><p>{html.escape(rubric['correct_use'])}</p>
                    <strong>Under-use</strong><p>{html.escape(rubric['under_use'])}</p>
                    <strong>Over-use</strong><p>{html.escape(rubric['over_use'])}</p>
                    <strong>Forbidden role</strong><p>{html.escape(rubric['forbidden_memory_role'])}</p>
                    <strong>Failure direction</strong><p>{html.escape(rubric['failure_direction'])}</p>
                    {extra}
                    <strong>Observable checks</strong>
                    <ul>{checks}</ul>
                  </td>
                </tr>
                """
            )
        cards.append(
            f"""
            <article class="sample{active_class}" data-index="{sample_index}">
              <div class="sample-head">
                <div>
                  <h2>{html.escape(sample['id'])}</h2>
                  <p>{html.escape(sample['source_topic'])} · {html.escape(sample['source_dataset'])}</p>
                </div>
                <span class="pill">{html.escape(sample.get('split', 'prototype_review'))}</span>
              </div>
              <section>
                <h3>Question</h3>
                <p class="question">{html.escape(sample['question'])}</p>
              </section>
              <section>
                <h3>Parent memory blocks and atomization</h3>
                <table class="blocks">
                  <thead><tr><th>parent</th><th>u*</th><th>source</th><th>stored memory block / audit evidence</th><th>atoms</th></tr></thead>
                  <tbody>{''.join(block_rows)}</tbody>
                </table>
              </section>
              <section>
                <h3>QC</h3>
                <p class="qc">
                  atomicity={html.escape(str(sample['qc']['atomicity_pass']))} ·
                  duplicate={html.escape(str(sample['qc']['duplicate_pass']))} ·
                  leakage={html.escape(str(sample['qc']['question_memory_leakage_pass']))} ·
                  hard_a_target={html.escape(str(sample['qc']['hard_a_target_consistency_pass']))}
                </p>
              </section>
              <section>
                <h3>Memories with judge rubrics</h3>
                <table>
                  <thead><tr><th>u*</th><th>Subtype</th><th>Memory</th><th>Usage rubric</th></tr></thead>
                  <tbody>{''.join(memory_rows)}</tbody>
                </table>
              </section>
            </article>
            """
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Memory ABC Rubric Dataset 100</title>
  <style>
    :root {{
      --paper: #f7f9fb;
      --ink: #18212f;
      --muted: #627083;
      --line: #d8dee8;
      --a: #c5524a;
      --b: #b7791f;
      --c: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.62;
      letter-spacing: 0;
    }}
    header {{ padding: 34px min(5vw, 60px) 22px; background: #fff; border-bottom: 1px solid var(--line); }}
    header h1 {{ margin: 0; font-size: clamp(30px, 5vw, 54px); line-height: 1; }}
    header p {{ max-width: 940px; margin: 14px 0 0; color: #3c4858; font-size: 17px; }}
    .summary {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; padding: 18px min(5vw, 60px); }}
    .metric, .sample {{ background: #fff; border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 14px 34px rgba(24, 33, 47, 0.07); }}
    .metric {{ padding: 13px 15px; }}
    .metric strong {{ display: block; font-size: 24px; }}
    .metric span {{ color: var(--muted); font-size: 13px; }}
    .viewer-bar {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: grid;
      grid-template-columns: auto auto minmax(220px, 460px) 1fr;
      gap: 10px;
      align-items: center;
      padding: 10px min(5vw, 60px);
      background: rgba(247, 249, 251, 0.94);
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .nav-button {{
      width: 38px;
      height: 34px;
      border: 1px solid #bcc7d5;
      border-radius: 8px;
      background: #fff;
      color: #1f2a3d;
      font-size: 22px;
      line-height: 1;
      cursor: pointer;
    }}
    .nav-button:hover {{ background: #edf3f8; }}
    .nav-button:focus-visible, #sampleSelect:focus-visible {{ outline: 3px solid rgba(15, 118, 110, 0.28); outline-offset: 2px; }}
    #sampleSelect {{
      width: 100%;
      min-height: 34px;
      border: 1px solid #bcc7d5;
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      padding: 0 10px;
      font: inherit;
      font-size: 13px;
    }}
    .sample-counter {{ color: var(--muted); font-size: 13px; font-weight: 760; text-align: right; }}
    main {{ display: grid; gap: 16px; padding: 16px min(5vw, 60px) 60px; }}
    .sample {{ display: none; overflow: hidden; }}
    .sample.active {{ display: block; }}
    .sample-head {{ display: flex; justify-content: space-between; gap: 16px; padding: 15px 17px; border-bottom: 1px solid var(--line); background: #fbfcfe; }}
    .sample h2 {{ margin: 0; font-size: 18px; }}
    .sample-head p {{ margin: 3px 0 0; color: var(--muted); font-size: 13px; }}
    section {{ padding: 13px 17px; border-bottom: 1px solid var(--line); }}
    section:last-child {{ border-bottom: 0; }}
    h3 {{ margin: 0 0 7px; font-size: 13px; text-transform: uppercase; color: var(--muted); letter-spacing: 0.04em; }}
    p {{ margin: 0; }}
    .question {{ font-size: 18px; font-weight: 720; }}
    .pill {{ display: inline-flex; align-items: center; height: 26px; padding: 0 9px; border: 1px solid var(--line); border-radius: 999px; background: #eef3f8; font-size: 12px; font-weight: 760; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 10px 9px; border-top: 1px solid var(--line); vertical-align: top; text-align: left; }}
    th {{ color: #344054; background: #f4f7fa; }}
    small {{ color: var(--muted); }}
    .reason {{ color: #4d5969; margin-top: 7px; font-size: 13px; }}
    .evidence {{ color: #64748b; margin-top: 5px; font-size: 13px; }}
    .atom {{ color: #334155; margin-top: 7px; font-size: 13px; font-weight: 700; }}
    .target {{ margin-top: 9px; padding: 9px 10px; border-left: 3px solid #94a3b8; background: #f8fafc; }}
    .target p {{ margin: 3px 0; color: #475569; font-size: 13px; }}
    .weight {{ display: inline-flex; min-height: 24px; align-items: center; padding: 0 8px; margin-bottom: 8px; border-radius: 999px; background: #e8eef6; color: #243449; font-size: 12px; font-weight: 820; text-transform: uppercase; }}
    .qc {{ color: #475569; font-size: 14px; }}
    .blocks td, .blocks th {{ font-size: 13px; }}
    td p {{ margin: 3px 0 8px; }}
    ul {{ margin: 4px 0 0 18px; padding: 0; }}
    .label {{ display: inline-grid; place-items: center; width: 28px; height: 28px; color: white; border-radius: 50%; font-weight: 900; }}
    .label-A {{ background: var(--a); }}
    .label-B {{ background: var(--b); }}
    .label-C {{ background: var(--c); }}
    @media (max-width: 900px) {{
      .summary {{ grid-template-columns: 1fr 1fr; }}
      .viewer-bar {{ grid-template-columns: auto auto 1fr; }}
      .sample-counter {{ grid-column: 1 / -1; text-align: left; }}
      .sample-head {{ flex-direction: column; }}
      table {{ display: block; overflow-x: auto; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Memory ABC Rubric Dataset 100</h1>
    <p>CRK-2 canonical-memory preview: raw evidence is retained for audit, stored memories are third-person summaries, and each atomic memory carries construction targets plus judge rubrics.</p>
  </header>
  <div class="summary">
    <div class="metric"><strong>{summary['total_samples']}</strong><span>samples</span></div>
    <div class="metric"><strong>{summary['total_parent_memories']}</strong><span>parent memory blocks</span></div>
    <div class="metric"><strong>{summary['total_memories']}</strong><span>atomic memories</span></div>
    <div class="metric"><strong>{summary['label_counts'].get('A', 0)}</strong><span>A hard negatives</span></div>
    <div class="metric"><strong>{summary['label_counts'].get('C', 0)}</strong><span>C controlling memories</span></div>
  </div>
  <div class="viewer-bar">
    <button id="prevSample" class="nav-button" type="button" aria-label="Previous sample" aria-keyshortcuts="ArrowLeft" title="Previous sample">‹</button>
    <button id="nextSample" class="nav-button" type="button" aria-label="Next sample" aria-keyshortcuts="ArrowRight" title="Next sample">›</button>
    <select id="sampleSelect" aria-label="Sample selector">{''.join(sample_options)}</select>
    <div id="sampleCounter" class="sample-counter">1 / {len(samples)}</div>
  </div>
  <main id="sample-viewer">{''.join(cards)}</main>
  <script>
    const samples = Array.from(document.querySelectorAll(".sample"));
    const sampleSelect = document.getElementById("sampleSelect");
    const sampleCounter = document.getElementById("sampleCounter");
    const prevSample = document.getElementById("prevSample");
    const nextSample = document.getElementById("nextSample");
    const sampleViewer = document.getElementById("sample-viewer");
    let currentSample = 0;

    function showSample(index, shouldScroll = true) {{
      if (!samples.length) return;
      const nextIndex = (index + samples.length) % samples.length;
      samples[currentSample].classList.remove("active");
      samples[nextIndex].classList.add("active");
      currentSample = nextIndex;
      sampleSelect.value = String(nextIndex);
      sampleCounter.textContent = `${{nextIndex + 1}} / ${{samples.length}}`;
      if (shouldScroll) {{
        window.scrollTo({{ top: Math.max(sampleViewer.offsetTop - 58, 0), behavior: "auto" }});
      }}
    }}

    prevSample.addEventListener("click", () => showSample(currentSample - 1));
    nextSample.addEventListener("click", () => showSample(currentSample + 1));
    sampleSelect.addEventListener("change", (event) => showSample(Number(event.target.value)));
    document.addEventListener("keydown", (event) => {{
      if (event.target.closest("input, textarea, select, button")) return;
      if (event.key === "ArrowRight" || event.key.toLowerCase() === "j") {{
        event.preventDefault();
        showSample(currentSample + 1);
      }}
      if (event.key === "ArrowLeft" || event.key.toLowerCase() === "k") {{
        event.preventDefault();
        showSample(currentSample - 1);
      }}
    }});
    showSample(0, false);
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CRK-style Memory ABC records with judge-facing usage rubrics.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--html", type=Path, default=DEFAULT_HTML)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    records = list(iter_jsonl(args.input))
    selected = select_records(records, args.limit, args.seed)
    samples = [convert_record(record, index + 1) for index, record in enumerate(selected)]
    summary = summarize(samples)
    write_jsonl(args.output, samples)
    write_json(args.summary, summary)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(build_html(samples, summary), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "summary": str(args.summary), "html": str(args.html), **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
