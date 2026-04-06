"""Path helpers."""

from __future__ import annotations

from pathlib import Path


WORKFLOW_CANDIDATES = ("WORKFLOW_v2_PRO.md", "WORKFLOW_v2.md", "WORKFLOW.md")


def find_repo_root(start: Path) -> Path | None:
    """Search upwards for a git root."""
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def find_workflow_file(repo_root: Path, forced: str | None = None) -> Path | None:
    """Find a workflow file by explicit override or standard search order."""
    if forced:
        target = (repo_root / forced).resolve() if not Path(forced).is_absolute() else Path(forced)
        return target if target.exists() else None
    for name in WORKFLOW_CANDIDATES:
        candidate = repo_root / name
        if candidate.exists():
            return candidate
    return None


def detect_project_type(repo_root: Path) -> str:
    """Infer project type from repo contents."""
    if any(repo_root.glob("*.xcodeproj")) or any(repo_root.glob("*.xcworkspace")):
        return "ios"
    return "generic"
