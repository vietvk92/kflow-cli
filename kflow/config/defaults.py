"""Configuration defaults."""

from __future__ import annotations

from pathlib import Path

from kflow.models.config import ProjectConfig


def build_default_config(
    *,
    repo_root: Path,
    project_name: str,
    project_type: str,
    workflow_file: str | None,
) -> ProjectConfig:
    """Build the runtime default configuration."""
    return ProjectConfig(
        project_name=project_name,
        project_type=project_type,
        repo_root=str(repo_root),
        workflow_file=workflow_file,
        paths={
            "planning_dir": ".planning",
        },
        policy={
            "source": "file" if workflow_file else "embedded",
            "file": workflow_file,
            "fallback_to_embedded": True,
        },
        adapters={
            "gsd": {"enabled": True, "planning_dir": ".planning"},
            "gitnexus": {"enabled": True, "command": "gitnexus"},
            "build": {"enabled": project_type == "ios", "command": None},
            "test": {"enabled": project_type == "ios", "command": None},
            "mobile_verify": {"enabled": False, "command": "./.tools/verify-mobile.sh"},
        },
    )
