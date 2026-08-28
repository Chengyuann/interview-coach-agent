#!/usr/bin/env python3
"""Evaluate the deterministic interview coach across supported roles."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vevc.contracts import write_json
from vevc.interview_coach import CoachRequest, coach_interview

DEFAULT_CASES = ROOT / "eval" / "interview_coach_cases.json"
DEFAULT_OUTPUT = ROOT / "build" / "interview-coach-evaluation.json"


def evaluate(cases_path: Path) -> dict[str, Any]:
    document = json.loads(cases_path.read_text(encoding="utf-8"))
    rows = []
    for case in document["cases"]:
        result = coach_interview(
            CoachRequest(
                role=case["role"],
                question_id=case["question_id"],
                answer=case["first_answer"],
                second_answer=case["second_answer"],
            )
        )
        comparison = result["comparison"]
        rewrite = result["first_answer"]["rewrite"]
        checks = {
            "score_improved": comparison["total_delta"]
            >= case["minimum_total_delta"],
            "all_dimensions_non_regressing": not comparison[
                "regressed_dimensions"
            ],
            "first_answer_grounded": case["first_answer"] in rewrite,
            "missing_result_is_explicit": (
                "NO_METRIC"
                not in {
                    item["code"]
                    for item in result["first_answer"]["issues"]
                }
                or "[补充一个可核实结果和数字]" in rewrite
            ),
            "no_synthetic_action_template": "先明确目标和约束" not in rewrite,
        }
        rows.append(
            {
                "case_id": case["case_id"],
                "role": result["role"],
                "question_id": result["question_id"],
                "first_total": result["first_answer"]["total_score"],
                "second_total": result["second_answer"]["total_score"],
                "total_delta": comparison["total_delta"],
                "checks": checks,
                "passed": all(checks.values()),
            }
        )
    roles = {item["role"] for item in rows}
    questions = {item["question_id"] for item in rows}
    cases_per_role = {
        role: sum(item["role"] == role for item in rows)
        for role in sorted(roles)
    }
    return {
        "schema_version": "0.1.0",
        "status": (
            "passed"
            if (
                len(roles) == 4
                and len(questions) >= 8
                and min(cases_per_role.values(), default=0) >= 2
                and all(item["passed"] for item in rows)
            )
            else "failed"
        ),
        "case_count": len(rows),
        "role_count": len(roles),
        "question_count": len(questions),
        "cases_per_role": cases_per_role,
        "average_total_delta": round(
            sum(item["total_delta"] for item in rows) / len(rows),
            2,
        ),
        "cases": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = evaluate(args.cases.expanduser().resolve())
    write_json(args.output.expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
