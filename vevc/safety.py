"""Read-only path and command-preview safety policy."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


SENSITIVE_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "cookies",
    "cookies.sqlite",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password)\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)


class SafetyError(PermissionError):
    """Raised when a request violates the Phase 0 policy."""


def resolve_input(path: Path, allowed_roots: Iterable[Path]) -> Path:
    resolved = path.expanduser().resolve()
    roots = [root.expanduser().resolve() for root in allowed_roots]
    if not any(_is_relative_to(resolved, root) for root in roots):
        raise SafetyError(f"input path is outside allowed roots: {resolved}")
    if resolved.name.lower() in SENSITIVE_NAMES:
        raise SafetyError(f"sensitive file is not allowed: {resolved.name}")
    return resolved


def prepare_output(path: Path, allowed_root: Path, overwrite: bool = False) -> Path:
    resolved = path.expanduser().resolve()
    root = allowed_root.expanduser().resolve()
    if not _is_relative_to(resolved, root):
        raise SafetyError(f"output path escapes allowed root: {resolved}")
    if resolved.exists():
        existing = [item for item in resolved.iterdir()]
        if existing and not overwrite:
            raise SafetyError(f"output directory already exists and is not empty: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def prepare_output_file(
    path: Path,
    allowed_root: Path,
    overwrite: bool = False,
) -> Path:
    resolved = path.expanduser().resolve()
    root = allowed_root.expanduser().resolve()
    if not _is_relative_to(resolved, root):
        raise SafetyError(f"output path escapes allowed root: {resolved}")
    if resolved.name.lower() in SENSITIVE_NAMES:
        raise SafetyError(f"sensitive output file is not allowed: {resolved.name}")
    if resolved.exists() and not overwrite:
        raise SafetyError(f"output file already exists: {resolved}")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def command_preview(command: str) -> dict[str, object]:
    return {
        "command": command,
        "execution": "not_run",
        "requires_confirmation": True,
    }


def redact_text(text: str) -> str:
    redacted = text
    for pattern in SECRET_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
