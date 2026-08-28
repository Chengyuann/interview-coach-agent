"""Schema loading, validation, and artifact helpers."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_VERSION = "0.1.0"
WORKPACK_FILES = (
    "transcript.jsonl",
    "claims.json",
    "revision_graph.json",
    "evidence_map.json",
    "decisions.md",
    "action_items.csv",
    "risks.md",
    "incident_timeline.md",
    "implementation_plan.md",
    "proposed_commands.md",
    "provenance.json",
    "manifest.json",
)


class ContractError(ValueError):
    """Raised when structured data violates a project contract."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_schema(name: str) -> dict[str, Any]:
    path = project_root() / "schemas" / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def validate_document(document: Any, schema_name: str) -> None:
    validator = Draft202012Validator(
        load_schema(schema_name),
        format_checker=FormatChecker(),
    )
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        rendered = []
        for error in errors:
            path = ".".join(str(part) for part in error.path) or "<root>"
            rendered.append(f"{path}: {error.message}")
        raise ContractError(f"{schema_name} validation failed: " + "; ".join(rendered))


def load_transcript(path: Path) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            segment = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid transcript JSON on line {line_number}: {exc}") from exc
        validate_document(segment, "transcript")
        segments.append(segment)
    validate_transcript_sequence(segments)
    return segments


def validate_transcript_sequence(segments: Iterable[dict[str, Any]]) -> None:
    seen: set[str] = set()
    previous_start = -1
    previous_end = -1
    for segment in segments:
        segment_id = segment["segment_id"]
        if segment_id in seen:
            raise ContractError(f"duplicate segment_id: {segment_id}")
        seen.add(segment_id)
        start_ms = segment["start_ms"]
        end_ms = segment["end_ms"]
        if end_ms <= start_ms:
            raise ContractError(f"{segment_id}: end_ms must be greater than start_ms")
        if start_ms < previous_start or end_ms < previous_end:
            raise ContractError(f"{segment_id}: transcript timestamps must be ordered")
        previous_start = start_ms
        previous_end = end_ms


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_record(path: Path, relative_to: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def validate_workpack(output_dir: Path) -> dict[str, Any]:
    missing = [name for name in WORKPACK_FILES if not (output_dir / name).is_file()]
    if missing:
        raise ContractError(f"missing workpack files: {', '.join(missing)}")

    segments = load_transcript(output_dir / "transcript.jsonl")
    claims_doc = json.loads((output_dir / "claims.json").read_text(encoding="utf-8"))
    graph_doc = json.loads((output_dir / "revision_graph.json").read_text(encoding="utf-8"))
    evidence_doc = json.loads((output_dir / "evidence_map.json").read_text(encoding="utf-8"))
    manifest_doc = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    provenance_doc = json.loads(
        (output_dir / "provenance.json").read_text(encoding="utf-8")
    )

    validate_document(claims_doc, "claims")
    validate_document(graph_doc, "revision_graph")
    validate_document(evidence_doc, "evidence_map")
    validate_document(manifest_doc, "manifest")
    validate_document(provenance_doc, "provenance")
    validate_cross_references(segments, claims_doc, graph_doc, evidence_doc)

    return {
        "schema_valid": True,
        "workpack_file_count": len(WORKPACK_FILES),
        "segment_count": len(segments),
        "claim_count": len(claims_doc["claims"]),
        "relation_count": len(graph_doc["relations"]),
        "evidence_count": len(evidence_doc["evidence"]),
        "content_id": provenance_doc["content_id"],
        "execution_id": provenance_doc["execution_id"],
    }


def validate_cross_references(
    segments: list[dict[str, Any]],
    claims_doc: dict[str, Any],
    graph_doc: dict[str, Any],
    evidence_doc: dict[str, Any],
) -> None:
    segment_ids = {item["segment_id"] for item in segments}
    claim_ids = {item["claim_id"] for item in claims_doc["claims"]}
    relation_ids = {item["relation_id"] for item in graph_doc["relations"]}
    evidence_ids = {item["evidence_id"] for item in evidence_doc["evidence"]}

    _require_unique(claim_ids, claims_doc["claims"], "claim_id")
    _require_unique(relation_ids, graph_doc["relations"], "relation_id")
    _require_unique(evidence_ids, evidence_doc["evidence"], "evidence_id")

    for claim in claims_doc["claims"]:
        unknown_evidence = set(claim["evidence_refs"]) - evidence_ids
        unknown_relations = set(claim["relation_refs"]) - relation_ids
        unknown_workspace = set(claim["workspace_refs"]) - evidence_ids
        if unknown_evidence or unknown_relations or unknown_workspace:
            raise ContractError(
                f"{claim['claim_id']}: invalid references "
                f"evidence={sorted(unknown_evidence)} "
                f"relations={sorted(unknown_relations)} "
                f"workspace={sorted(unknown_workspace)}"
            )
        if claim["lifecycle_status"] == "active" and claim["claim_type"] in {
            "decision",
            "action",
            "risk",
            "hypothesis",
            "proposed_command",
        }:
            if not claim["evidence_refs"]:
                raise ContractError(f"{claim['claim_id']}: active claim has no evidence")
        if claim["claim_type"] == "proposed_command":
            if not claim["requires_confirmation"]:
                raise ContractError(
                    f"{claim['claim_id']}: proposed command must require confirmation"
                )
            if not claim.get("command"):
                raise ContractError(f"{claim['claim_id']}: proposed command is missing command")

    destructive_edges: dict[str, list[str]] = {}
    for relation in graph_doc["relations"]:
        if relation["from_claim_id"] not in claim_ids or relation["to_claim_id"] not in claim_ids:
            raise ContractError(f"{relation['relation_id']}: relation references unknown claim")
        if relation["from_claim_id"] == relation["to_claim_id"]:
            raise ContractError(f"{relation['relation_id']}: self-loop is not allowed")
        if set(relation["evidence_refs"]) - evidence_ids:
            raise ContractError(f"{relation['relation_id']}: unknown evidence reference")
        if relation["relation_type"] in {"supersedes", "cancels"}:
            destructive_edges.setdefault(relation["from_claim_id"], []).append(
                relation["to_claim_id"]
            )
    _reject_cycles(destructive_edges)

    for evidence in evidence_doc["evidence"]:
        for supported in evidence["supports"]:
            if supported.startswith("C") and supported not in claim_ids:
                raise ContractError(f"{evidence['evidence_id']}: supports unknown claim")
            if supported.startswith("R") and supported not in relation_ids:
                raise ContractError(f"{evidence['evidence_id']}: supports unknown relation")
        unknown_segments = set(evidence["locator"].get("segment_ids", [])) - segment_ids
        if unknown_segments:
            raise ContractError(
                f"{evidence['evidence_id']}: unknown segments {sorted(unknown_segments)}"
            )


def _require_unique(ids: set[str], rows: list[dict[str, Any]], key: str) -> None:
    if len(ids) != len(rows):
        raise ContractError(f"duplicate {key}")


def _reject_cycles(edges: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise ContractError("supersedes/cancels relation cycle detected")
        if node in visited:
            return
        visiting.add(node)
        for target in edges.get(node, []):
            visit(target)
        visiting.remove(node)
        visited.add(node)

    for node in edges:
        visit(node)
