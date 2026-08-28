"""Deterministic interview coaching engine.

The first migrated product path is intentionally local and auditable.  It does
not invent experience details; rewrites keep the candidate's stated facts and
mark missing facts as placeholders.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vevc.contracts import SCHEMA_VERSION, validate_document, write_json
from vevc.safety import prepare_output_file


ROLE_LIBRARY: dict[str, dict[str, Any]] = {
    "product-manager": {
        "label": "产品经理",
        "default_question_id": "pm-impact",
        "keywords": [
            "用户",
            "需求",
            "指标",
            "转化",
            "留存",
            "实验",
            "数据",
            "优先级",
            "上线",
        ],
        "questions": {
            "pm-impact": "讲一个你推动产品指标提升的项目。",
            "pm-conflict": "讲一次你和研发或业务方发生分歧时如何推进。",
        },
    },
    "algorithm-engineer": {
        "label": "算法工程师",
        "default_question_id": "algo-tradeoff",
        "keywords": [
            "模型",
            "特征",
            "训练",
            "评估",
            "召回",
            "精排",
            "延迟",
            "准确率",
            "实验",
        ],
        "questions": {
            "algo-tradeoff": "讲一次你在模型效果和线上性能之间做权衡的经历。",
            "algo-debug": "讲一次你定位模型效果下降的经历。",
        },
    },
    "sales": {
        "label": "销售",
        "default_question_id": "sales-objection",
        "keywords": [
            "客户",
            "线索",
            "成交",
            "异议",
            "预算",
            "决策人",
            "续约",
            "客单价",
            "回款",
        ],
        "questions": {
            "sales-objection": "讲一次你处理关键客户异议并推动成交的经历。",
            "sales-pipeline": "讲一次你如何管理销售漏斗并提升转化。",
        },
    },
    "operations": {
        "label": "运营",
        "default_question_id": "ops-growth",
        "keywords": [
            "活动",
            "用户",
            "渠道",
            "转化",
            "留存",
            "内容",
            "社群",
            "复盘",
            "成本",
        ],
        "questions": {
            "ops-growth": "讲一次你用运营动作带来增长的经历。",
            "ops-crisis": "讲一次你处理线上运营事故或舆情的经历。",
        },
    },
}


DIMENSIONS = (
    "structure",
    "specificity",
    "metrics",
    "role_fit",
    "clarity",
    "risk_control",
)

STAR_KEYWORDS = {
    "situation": ("背景", "当时", "问题", "场景", "目标"),
    "task": ("负责", "目标", "我需要", "任务", "指标"),
    "action": ("我", "推动", "设计", "协调", "分析", "落地", "执行"),
    "result": ("结果", "提升", "下降", "完成", "上线", "成交", "通过"),
}
VAGUE_WORDS = ("一些", "很多", "比较", "挺", "大概", "明显", "还可以", "负责了一下")
FILLER_WORDS = ("然后", "就是", "这个", "那个", "其实", "可能", "应该")
RISK_WORDS = ("夸大", "编", "猜", "不知道", "随便", "大概是我")
CHINESE_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


@dataclass(frozen=True)
class CoachRequest:
    role: str
    answer: str
    question_id: str | None = None
    second_answer: str | None = None


def coach_interview(request: CoachRequest) -> dict[str, Any]:
    role = normalize_role(request.role)
    role_spec = ROLE_LIBRARY[role]
    question_id = request.question_id or role_spec["default_question_id"]
    question = role_spec["questions"].get(question_id)
    if question is None:
        raise ValueError(f"unknown question_id for {role}: {question_id}")

    first = evaluate_answer(
        answer=request.answer,
        role=role,
        question_id=question_id,
        question=question,
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "product": "interview-coach-agent",
        "role": role,
        "role_label": role_spec["label"],
        "question_id": question_id,
        "question": question,
        "first_answer": first,
        "recommendation": recommendation(first),
    }
    if request.second_answer is not None:
        second = evaluate_answer(
            answer=request.second_answer,
            role=role,
            question_id=question_id,
            question=question,
        )
        result["second_answer"] = second
        result["comparison"] = compare_attempts(first, second)
    validate_document(result, "interview_coach_result")
    return result


def write_coach_result(
    *,
    request: CoachRequest,
    output: Path,
    output_root: Path,
    overwrite: bool,
) -> dict[str, Any]:
    result = coach_interview(request)
    path = prepare_output_file(output, output_root, overwrite=overwrite)
    write_json(path, result)
    return result


def list_roles() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "roles": [
            {
                "role": key,
                "label": value["label"],
                "default_question_id": value["default_question_id"],
                "questions": value["questions"],
            }
            for key, value in ROLE_LIBRARY.items()
        ],
    }


def evaluate_answer(
    *,
    answer: str,
    role: str,
    question_id: str,
    question: str,
) -> dict[str, Any]:
    text = normalize_text(answer)
    if not text:
        raise ValueError("answer is empty")
    features = extract_features(text, role)
    scores = score_features(features)
    total = round(sum(scores.values()) / len(scores), 1)
    issues = detect_issues(features)
    followups = build_followups(features)
    rewrite = build_rewrite(text, features, role, question)
    return {
        "answer": text,
        "question_id": question_id,
        "scores": scores,
        "total_score": total,
        "features": features,
        "issues": issues,
        "followups": followups,
        "rewrite": rewrite,
    }


def extract_features(text: str, role: str) -> dict[str, Any]:
    star_hits = {
        name: [word for word in words if word in text]
        for name, words in STAR_KEYWORDS.items()
    }
    role_keywords = [word for word in ROLE_LIBRARY[role]["keywords"] if word in text]
    number_matches = re.findall(
        r"\d+(?:\.\d+)?\s*(?:%|个|人|天|周|月|年|万|千|小时|分钟|次|元|单|家)?",
        text,
    )
    sentences = split_sentences(text)
    vague_hits = [word for word in VAGUE_WORDS if word in text]
    filler_hits = [word for word in FILLER_WORDS if word in text]
    risk_hits = [word for word in RISK_WORDS if word in text]
    first_person = bool(re.search(r"我|本人|自己|由我|我负责", text))
    result_claims = [
        sentence
        for sentence in sentences
        if any(word in sentence for word in STAR_KEYWORDS["result"])
    ]
    return {
        "char_count": len(text),
        "sentence_count": len(sentences),
        "star_hits": star_hits,
        "star_coverage": sum(bool(value) for value in star_hits.values()),
        "role_keyword_hits": role_keywords,
        "role_keyword_count": len(role_keywords),
        "number_matches": number_matches,
        "number_count": len(number_matches),
        "vague_hits": vague_hits,
        "vague_count": len(vague_hits),
        "filler_hits": filler_hits,
        "filler_count": len(filler_hits),
        "risk_hits": risk_hits,
        "first_person": first_person,
        "result_claims": result_claims,
    }


def score_features(features: dict[str, Any]) -> dict[str, int]:
    length = features["char_count"]
    structure = clamp_score(1 + features["star_coverage"] * 1.5)
    if length >= 120:
        structure += 1
    specificity = clamp_score(2 + min(3, features["sentence_count"]) + min(2, features["number_count"]))
    metrics = clamp_score(1 + features["number_count"] * 2)
    role_fit = clamp_score(2 + min(5, features["role_keyword_count"]))
    clarity = clamp_score(6 - min(3, features["filler_count"] // 2) - min(2, features["vague_count"]))
    risk_control = clamp_score(5 + int(features["first_person"]) - len(features["risk_hits"]))
    if not features["result_claims"]:
        risk_control = max(1, risk_control - 1)
    return {
        "structure": clamp_score(structure),
        "specificity": specificity,
        "metrics": metrics,
        "role_fit": role_fit,
        "clarity": clarity,
        "risk_control": risk_control,
    }


def detect_issues(features: dict[str, Any]) -> list[dict[str, str]]:
    issues = []
    if features["star_coverage"] < 4:
        missing = [
            name
            for name, hits in features["star_hits"].items()
            if not hits
        ]
        issues.append(
            {
                "code": "STAR_INCOMPLETE",
                "message": "回答没有覆盖完整 STAR 结构。",
                "detail": "缺少：" + "、".join(missing),
            }
        )
    if features["number_count"] == 0:
        issues.append(
            {
                "code": "NO_METRIC",
                "message": "没有量化结果或规模。",
                "detail": "至少补充一个转化、成本、周期、人数或收入数字。",
            }
        )
    if features["role_keyword_count"] < 2:
        issues.append(
            {
                "code": "LOW_ROLE_FIT",
                "message": "岗位关键词不足。",
                "detail": "回答听起来像通用经历，缺少岗位相关动作。",
            }
        )
    if features["vague_hits"]:
        issues.append(
            {
                "code": "VAGUE_LANGUAGE",
                "message": "存在模糊表达。",
                "detail": "、".join(features["vague_hits"]),
            }
        )
    if not features["first_person"]:
        issues.append(
            {
                "code": "NO_OWNERSHIP",
                "message": "个人贡献不清楚。",
                "detail": "需要说明你本人做了什么，而不是团队整体做了什么。",
            }
        )
    return issues


def build_followups(features: dict[str, Any]) -> list[str]:
    followups = []
    if features["number_count"] == 0:
        followups.append("你说效果变好了，具体提升了多少？用一个数字说明。")
    if not features["first_person"]:
        followups.append("这件事里你本人负责哪一部分？哪些不是团队泛泛完成的？")
    if not features["result_claims"]:
        followups.append("最后结果是什么？上线、成交、通过或指标变化分别是多少？")
    if features["star_coverage"] < 4:
        followups.append("请按背景、任务、行动、结果四段重新讲一遍。")
    if not followups:
        followups.append("如果面试官继续追问，你会如何证明这个结果主要由你的动作带来？")
    return followups[:3]


def build_rewrite(
    text: str,
    features: dict[str, Any],
    role: str,
    question: str,
) -> str:
    sentences = split_sentences(text)
    stated = "；".join(sentences) if sentences else text
    situation = sentence_for_star(sentences, "situation") or "[补充背景和问题]"
    task = sentence_for_star(sentences, "task") or "[补充你的任务或目标]"
    action = sentence_for_star(sentences, "action") or "[补充你本人采取的动作]"
    result = best_result_claim(features)
    return (
        f"针对“{question}”，可按 STAR 重组。"
        f"背景：{ensure_sentence(situation)}"
        f"任务：{ensure_sentence(task)}"
        f"行动：{ensure_sentence(action)}"
        f"结果：{result}"
        f"原始回答：{ensure_sentence(text)}"
        f"已提供事实：{ensure_sentence(stated)}"
        "以上只使用你已经提供的信息；方括号处需要你本人补充。"
    )


def recommendation(first: dict[str, Any]) -> str:
    score = first["total_score"]
    if score >= 5.6:
        return "可以进入模拟追问，重点补充证据和个人贡献边界。"
    if score >= 4.2:
        return "先补量化结果和 STAR 结构，再进行第二次回答。"
    return "先不要背答案，先把背景、本人动作和结果数字补齐。"


def best_result_claim(features: dict[str, Any]) -> str:
    if not features["result_claims"]:
        return "[补充一个可核实结果和数字]。"
    suffix = (
        " [补充一个可核实结果和数字]。"
        if features["number_count"] == 0
        else ""
    )
    for claim in features["result_claims"]:
        if "结果" in claim:
            return ensure_sentence(claim) + suffix
    return ensure_sentence(features["result_claims"][-1]) + suffix


def sentence_for_star(sentences: list[str], dimension: str) -> str | None:
    keywords = STAR_KEYWORDS[dimension]
    return next(
        (
            sentence
            for sentence in sentences
            if any(keyword in sentence for keyword in keywords)
        ),
        None,
    )


def compare_attempts(
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    dimension_delta = {
        key: second["scores"][key] - first["scores"][key]
        for key in DIMENSIONS
    }
    total_delta = round(second["total_score"] - first["total_score"], 1)
    improved = [key for key, value in dimension_delta.items() if value > 0]
    regressed = [key for key, value in dimension_delta.items() if value < 0]
    return {
        "total_delta": total_delta,
        "dimension_delta": dimension_delta,
        "improved_dimensions": improved,
        "regressed_dimensions": regressed,
        "verdict": "improved" if total_delta > 0 else "not_improved",
    }


def normalize_role(role: str) -> str:
    normalized = role.strip().lower().replace("_", "-")
    aliases = {
        "pm": "product-manager",
        "product": "product-manager",
        "产品经理": "product-manager",
        "算法": "algorithm-engineer",
        "算法工程师": "algorithm-engineer",
        "销售": "sales",
        "运营": "operations",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized not in ROLE_LIBRARY:
        raise ValueError(f"unknown role: {role}")
    return normalized


def normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip())
    normalized = re.sub(
        r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])",
        "",
        normalized,
    )
    normalized = re.sub(
        r"(?<=[\u3400-\u9fff])\s+(?=\d)",
        "",
        normalized,
    )
    normalized = re.sub(
        r"(?<=\d)\s+(?=[\u3400-\u9fff])",
        "",
        normalized,
    )
    normalized = re.sub(r"(?<=\d)\s+(?=\d)", "", normalized)
    normalized = re.sub(r"\s+(?=%)", "", normalized)
    normalized = re.sub(
        r"百分之([零一二两三四五六七八九十百]+)",
        lambda match: f"{chinese_number(match.group(1))}%",
        normalized,
    )
    return normalized


def chinese_number(text: str) -> int:
    if not text:
        raise ValueError("Chinese number is empty")
    if all(char in CHINESE_DIGITS for char in text):
        return int("".join(str(CHINESE_DIGITS[char]) for char in text))
    total = 0
    current = 0
    for char in text:
        if char in CHINESE_DIGITS:
            current = CHINESE_DIGITS[char]
        elif char == "十":
            total += (current or 1) * 10
            current = 0
        elif char == "百":
            total += (current or 1) * 100
            current = 0
        else:
            raise ValueError(f"unsupported Chinese number: {text}")
    return total + current


def ensure_sentence(text: str) -> str:
    stripped = text.strip()
    if stripped.endswith(("。", "！", "？", ".", "!", "?")):
        return stripped
    return stripped + "。"


def split_sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"[。！？!?；;\n]+", text)
        if item.strip()
    ]


def clamp_score(value: float | int) -> int:
    return max(1, min(7, int(round(value))))


def load_request(path: Path) -> CoachRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CoachRequest(
        role=payload["role"],
        question_id=payload.get("question_id"),
        answer=payload["answer"],
        second_answer=payload.get("second_answer"),
    )
