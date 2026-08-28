from vevc.interview_coach import CoachRequest, coach_interview, list_roles
from vevc.interview_report import build_interview_report


def test_release_contains_aipc_local_skill_contract():
    root = __import__("pathlib").Path(__file__).resolve().parents[2]
    required = {
        "requirements.txt",
        "scripts/run.ps1",
        "scripts/install-env.ps1",
        "scripts/client.py",
        "scripts/server.py",
        "scripts/model_manager.py",
        "tests/test.ps1",
        "references/aipc-local-skill-standard.md",
    }
    assert all((root / relative).is_file() for relative in required)
    assert (root / "scripts" / "run.ps1").read_text(
        encoding="utf-8"
    ).splitlines()[0] == "$ErrorActionPreference = 'Stop'"


def test_release_lists_roles_and_questions():
    roles = list_roles()["roles"]
    assert {item["role"] for item in roles} == {
        "product-manager",
        "algorithm-engineer",
        "sales",
        "operations",
    }
    assert all(item["questions"] for item in roles)


def test_release_scores_and_compares_two_attempts_without_inventing():
    result = coach_interview(
        CoachRequest(
            role="product-manager",
            question_id="pm-impact",
            answer="我做过增长项目，后来效果明显变好。",
            second_answer=(
                "当时首单转化率是 18%。我负责拆解用户漏斗，"
                "推动研发做 A/B 实验，结果转化率提升到 26%。"
            ),
        )
    )
    assert result["comparison"]["verdict"] == "improved"
    assert result["comparison"]["total_delta"] > 0
    rewrite = result["first_answer"]["rewrite"]
    assert "我做过增长项目" in rewrite
    assert "[补充一个可核实结果和数字]" in rewrite
    assert "先明确目标和约束" not in rewrite

    report = build_interview_report(
        CoachRequest(
            role="product-manager",
            question_id="pm-impact",
            answer="我做过增长项目，后来效果明显变好。",
            second_answer=(
                "当时首单转化率是 18%。我负责拆解用户漏斗，"
                "推动研发做 A/B 实验，结果转化率提升到 26%。"
            ),
        )
    )
    assert report["summary"]["attempt_count"] == 2
    assert "## 六方面表现" in report["markdown"]
