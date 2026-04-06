"""Configuration loading."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from kflow.config.migrator import migrate_config
from kflow.core.exceptions import KFlowConfigError
from kflow.core.validator import to_user_validation_error
from kflow.models.config import ProjectConfig
from kflow.utils.paths import find_repo_root
from kflow.utils.yaml_io import dump_yaml, load_yaml


def config_path(repo_root: Path) -> Path:
    """Return the canonical config file path."""
    return repo_root / ".kflow" / "config.yaml"


def resolve_root(start: Path) -> Path:
    """Resolve the root used for config operations."""
    return find_repo_root(start) or start.resolve()


def load_config(repo_root: Path) -> ProjectConfig:
    """Load configuration from disk."""
    return load_config_with_meta(repo_root)[0]


def load_config_with_meta(repo_root: Path) -> tuple[ProjectConfig, dict[str, object]]:
    """Load configuration from disk with migration metadata."""
    root = resolve_root(repo_root)
    path = config_path(root)
    if not path.exists():
        raise KFlowConfigError(f"Config file not found: {path}")
    payload, migration = migrate_config(load_yaml(path))
    try:
        return ProjectConfig.model_validate(payload), migration
    except ValidationError as exc:
        raise to_user_validation_error(exc) from exc


def serialize_config(config: ProjectConfig) -> str:
    """Serialize configuration for persistence."""
    return dump_yaml(config.model_dump(mode="python", exclude_none=False, by_alias=True))
