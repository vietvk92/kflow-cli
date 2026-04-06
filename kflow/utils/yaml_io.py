"""YAML helpers."""

from pathlib import Path
from typing import Any

import yaml

from kflow.core.exceptions import KFlowFilesystemError


def load_yaml(path: Path) -> dict[str, Any]:
    """Load YAML content from disk."""
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise KFlowFilesystemError(f"Failed to read YAML file: {path}") from exc
    return content or {}


def dump_yaml(data: dict[str, Any]) -> str:
    """Serialize data to stable YAML."""
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=False)
