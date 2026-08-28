"""Render portable interview practice reports from local coach results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vevc.interview_coach import CoachRequest, coach_interview
from vevc.safety import prepare_output_file


DIMENSION_LABELS = {
    "structure": "STAR 结构",
    "specificity": "具体程度",
    "metrics": "数据量化",
    "role_fit": "岗位匹配",
    "clarity": "表达清晰",
    "risk_control": "真实可信",
}

PRACTICE_ACTIONS = {
    "structure": "下一次回答前，先写出背景、任务、行动和结果各一句。",
    "specificity": "补充对象、范围、周期和你实际执行的动作。",
    "metrics": "准备至少一个可核实的结果数字，并说明统计口径。",
    "role_fit": "使用目标岗位的专业方法说明判断和执行过程。",
    "clarity": "删除模糊词和填充词，让每句话只表达一个重点。",
    "risk_control": "说清本人贡献，不夸大，也不把团队成果都算在自己身上。",
}


def build_interview_report(request: CoachRequest) -> dict[str, Any]:
    result = coach_interview(request)
    return {
        "schema_version": "0.1.0",
        "product": "interview-coach-agent",
        "format": "markdown",
        "filename": report_filename(result),
        "markdown": render_interview_report(result),
        "summary": report_summary(result),
    }


def write_interview_report(
    *,
    request: CoachRequest,
    output: Path,
    output_root: Path,
    overwrite: bool,
) -> dict[str, Any]:
    report = build_interview_report(request)
    path = prepare_output_file(output, output_root, overwrite=overwrite)
    path.write_text(report["markdown"], encoding="utf-8")
    return {
        "schema_version": "0.1.0",
        "product": "interview-coach-agent",
        "status": "written",
        "output": path.relative_to(output_root.parent).as_posix(),
        "filename": path.name,
        "summary": report["summary"],
    }


def render_interview_report(result: dict[str, Any]) -> str:
    first = result["first_answer"]
    second = result.get("second_answer")
    comparison = result.get("comparison")
    attempt = second or first
    lines = [
        "# 面试练习报告",
        "",
        "> 由 interview-coach-agent 在本地生成。报告只整理本次练习内容，"
        "不补充候选人未提供的经历。",
        "",
        "## 练习信息",
        "",
        f"- 岗位：{result['role_label']}",
        f"- 问题：{result['question']}",
        f"- 练习轮次：{'两轮' if second else '一轮'}",
        "",
        "## 结果摘要",
        "",
    ]
    if second and comparison:
        lines.extend(
            [
                "| 第一次回答 | 第二次回答 | 总分变化 | 结论 |",
                "|---:|---:|---:|---|",
                (
                    f"| {first['total_score']:.1f} / 7 "
                    f"| {second['total_score']:.1f} / 7 "
                    f"| {signed(comparison['total_delta'])} "
                    f"| {verdict_label(comparison['verdict'])} |"
                ),
            ]
        )
    else:
        lines.extend(
            [
                "| 当前得分 | 建议 |",
                "|---:|---|",
                f"| {first['total_score']:.1f} / 7 | {result['recommendation']} |",
            ]
        )
    lines.extend(["", "## 六方面表现", ""])
    if second and comparison:
        lines.extend(
            [
                "| 维度 | 第一次 | 第二次 | 变化 |",
                "|---|---:|---:|---:|",
            ]
        )
        for key, label in DIMENSION_LABELS.items():
            lines.append(
                f"| {label} | {first['scores'][key]} "
                f"| {second['scores'][key]} "
                f"| {signed(comparison['dimension_delta'][key])} |"
            )
    else:
        lines.extend(["| 维度 | 得分 |", "|---|---:|"])
        for key, label in DIMENSION_LABELS.items():
            lines.append(f"| {label} | {first['scores'][key]} / 7 |")

    lines.extend(
        [
            "",
            "## 第一次回答",
            "",
            quote(first["answer"]),
            "",
            "### 主要问题",
            "",
            *issue_lines(first),
            "",
            "### 建议追问",
            "",
            *bullet_lines(first["followups"]),
        ]
    )
    if second and comparison:
        lines.extend(
            [
                "",
                "## 第二次回答",
                "",
                quote(second["answer"]),
                "",
                "### 回答变化",
                "",
                (
                    f"- 总分由 {first['total_score']:.1f} 提升到 "
                    f"{second['total_score']:.1f}，变化 "
                    f"{signed(comparison['total_delta'])}。"
                ),
                (
                    "- 提升维度："
                    + dimension_list(comparison["improved_dimensions"])
                    + "。"
                ),
                (
                    "- 下降维度："
                    + dimension_list(comparison["regressed_dimensions"], empty="无")
                    + "。"
                ),
                "",
                "### 当前仍需关注",
                "",
                *issue_lines(second),
            ]
        )

    weakest = sorted(
        attempt["scores"],
        key=lambda key: (attempt["scores"][key], list(DIMENSION_LABELS).index(key)),
    )[:2]
    lines.extend(
        [
            "",
            "## 下一次练习",
            "",
            *[
                (
                    f"- **{DIMENSION_LABELS[key]}（{attempt['scores'][key]} / 7）**："
                    f"{PRACTICE_ACTIONS[key]}"
                )
                for key in weakest
            ],
            "",
            "## 参考表达结构",
            "",
            compact_rewrite(attempt["rewrite"]),
            "",
            "## 注意事项",
            "",
            "- 本报告用于面试练习和导师复盘，不作为招聘录用结论。",
            "- 分数用于比较同一候选人的回答变化，不用于跨候选人排名。",
            "- 语音转写可能存在误差，正式使用前应核对原文。",
            "- 方括号中的内容需要候选人本人补充并确认。",
            "",
        ]
    )
    return "\n".join(lines)


def report_filename(result: dict[str, Any]) -> str:
    return (
        f"interview-practice-{result['role']}-{result['question_id']}.md"
    )


def report_summary(result: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "role": result["role"],
        "role_label": result["role_label"],
        "question_id": result["question_id"],
        "first_total": result["first_answer"]["total_score"],
        "attempt_count": 1,
    }
    if "second_answer" in result:
        summary.update(
            {
                "attempt_count": 2,
                "second_total": result["second_answer"]["total_score"],
                "total_delta": result["comparison"]["total_delta"],
                "verdict": result["comparison"]["verdict"],
            }
        )
    return summary


def issue_lines(attempt: dict[str, Any]) -> list[str]:
    if not attempt["issues"]:
        return ["- 未发现规则型问题，可继续准备更深入的追问。"]
    return [
        (
            f"- **{item['message']}** "
            f"{localize_issue_detail(item['detail'])}（`{item['code']}`）"
        )
        for item in attempt["issues"]
    ]


def bullet_lines(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


def dimension_list(keys: list[str], empty: str = "无") -> str:
    if not keys:
        return empty
    return "、".join(DIMENSION_LABELS[key] for key in keys)


def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def compact_rewrite(text: str) -> str:
    return text.split("原始回答：", 1)[0].strip()


def localize_issue_detail(text: str) -> str:
    labels = {
        "situation": "背景",
        "task": "任务",
        "action": "行动",
        "result": "结果",
    }
    localized = text
    for key, label in labels.items():
        localized = localized.replace(key, label)
    return localized


def signed(value: float | int) -> str:
    return f"+{value:g}" if value > 0 else f"{value:g}"


def verdict_label(verdict: str) -> str:
    return "有提升" if verdict == "improved" else "未提升"
