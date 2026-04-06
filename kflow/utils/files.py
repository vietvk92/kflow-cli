"""Filesystem helpers."""

from pathlib import Path

from kflow.core.exceptions import KFlowFilesystemError


def ensure_directory(path: Path) -> Path:
    """Create a directory if it does not exist."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise KFlowFilesystemError(f"Failed to create directory: {path}") from exc
    return path


def write_text(path: Path, content: str, overwrite: bool = True) -> None:
    """Write UTF-8 text to disk."""
    if path.exists() and not overwrite:
        raise KFlowFilesystemError(f"Refusing to overwrite existing file: {path}")
    ensure_directory(path.parent)
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise KFlowFilesystemError(f"Failed to write file: {path}") from exc
