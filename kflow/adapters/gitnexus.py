"""GitNexus adapter scaffold."""

from __future__ import annotations

from pathlib import Path

from kflow.adapters.base import AdapterDetection, DetectionAdapter
from kflow.utils.shell import ShellResult, run


class GitNexusAdapter(DetectionAdapter):
    """Detect GitNexus availability."""

    name = "gitnexus"

    def __init__(self, command: str = "gitnexus", enabled: bool = True) -> None:
        self.command = command
        self.enabled = enabled

    def detect(self, repo_root: Path) -> AdapterDetection:
        if not self.enabled:
            return AdapterDetection(status="disabled", detail=self.command)
        result = run([self.command, "--help"], cwd=repo_root)
        return AdapterDetection(
            status="present" if result.ok else "missing",
            detail=self.command,
        )

    def context(self, repo_root: Path, symbol: str) -> ShellResult:
        """Run GitNexus context lookup."""
        if not self.enabled:
            return ShellResult(command=[self.command, "context", symbol], returncode=1, stdout="", stderr="gitnexus disabled")
        return run([self.command, "context", symbol], cwd=repo_root)

    def impact(self, repo_root: Path, symbol: str) -> ShellResult:
        """Run GitNexus impact lookup."""
        if not self.enabled:
            return ShellResult(command=[self.command, "impact", symbol], returncode=1, stdout="", stderr="gitnexus disabled")
        return run([self.command, "impact", symbol], cwd=repo_root)
