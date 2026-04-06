"""Base adapter types."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AdapterDetection:
    """Normalized adapter availability result."""

    status: str
    detail: str


class DetectionAdapter:
    """Base class for optional tool detection."""

    name: str = "adapter"

    def detect(self, repo_root: Path) -> AdapterDetection:
        raise NotImplementedError
