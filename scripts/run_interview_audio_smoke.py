#!/usr/bin/env python3
"""Run local speech transcription and interview coaching end to end."""

from __future__ import annotations

import argparse
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vevc.contracts import write_json
from vevc.interview_coach import CoachRequest, coach_interview, normalize_text
from vevc.moonshine_runtime import MoonshineRuntime

DEFAULT_MANIFEST = ROOT / "build" / "interview-audio-fixture" / "manifest.json"
DEFAULT_OUTPUT = ROOT / "build" / "interview-audio-smoke"
MIN_REFERENCE_RECALL = 0.90


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest_path = args.manifest.expanduser().resolve()
    fixture = json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    runtime = MoonshineRuntime(ROOT)
    try:
        evidence = runtime.transcribe_file(
            audio_path=ROOT / fixture["audio"],
            language=fixture["language"],
            output_path=output_dir / "transcript.jsonl",
            evidence_path=output_dir / "asr-evidence.json",
        )
    finally:
        runtime.close()
    coach = coach_interview(
        CoachRequest(
            role=fixture["role"],
            question_id=fixture["question_id"],
            answer=evidence["text"],
        )
    )
    write_json(output_dir / "coach-result.json", coach)
    quality = reference_quality(
        reference=fixture["script_text"],
        transcript=evidence["text"],
    )
    issue_codes = [
        item["code"] for item in coach["first_answer"]["issues"]
    ]
    if quality["review_required"]:
        issue_codes.insert(0, "ASR_REVIEW_REQUIRED")
    result = {
        "schema_version": "0.1.0",
        "status": "passed",
        "audio": fixture["audio"],
        "transcript_text": evidence["text"],
        "duration_ms": evidence["audio"]["duration_ms"],
        "inference_seconds": evidence["inference_seconds"],
        "real_time_factor": evidence["real_time_factor"],
        "total_score": coach["first_answer"]["total_score"],
        "issue_codes": issue_codes,
        "asr_quality": quality,
        "artifacts": {
            "asr_evidence": "asr-evidence.json",
            "transcript": "transcript.jsonl",
            "coach_result": "coach-result.json",
        },
    }
    write_json(output_dir / "summary.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def reference_quality(*, reference: str, transcript: str) -> dict:
    expected = compact_for_comparison(reference)
    actual = compact_for_comparison(transcript)
    matcher = SequenceMatcher(None, expected, actual)
    matched = sum(block.size for block in matcher.get_matching_blocks())
    recall = matched / len(expected) if expected else 0.0
    precision = matched / len(actual) if actual else 0.0
    return {
        "method": "normalized_character_alignment",
        "reference_chars": len(expected),
        "transcript_chars": len(actual),
        "matched_chars": matched,
        "reference_recall": round(recall, 6),
        "transcript_precision": round(precision, 6),
        "minimum_reference_recall": MIN_REFERENCE_RECALL,
        "review_required": recall < MIN_REFERENCE_RECALL,
    }


def compact_for_comparison(text: str) -> str:
    normalized = normalize_text(text)
    return re.sub(r"[^0-9A-Za-z%\u3400-\u9fff]+", "", normalized)


if __name__ == "__main__":
    raise SystemExit(main())
