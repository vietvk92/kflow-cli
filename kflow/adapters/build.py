"""Build adapter scaffold."""

from __future__ import annotations

from pathlib import Path

from kflow.adapters.base import AdapterDetection, DetectionAdapter
from kflow.utils.shell import ShellResult, run_command_text


class BuildAdapter(DetectionAdapter):
    """Scaffold for configured build command detection."""

    name = "build"

    def __init__(self, command: str | None, enabled: bool) -> None:
        self.command = command
        self.enabled = enabled

    def detect(self, repo_root: Path) -> AdapterDetection:
        if not self.enabled:
            return AdapterDetection(status="disabled", detail=self.command or "disabled")
        return AdapterDetection(status="present" if self.command else "missing", detail=self.command or "command not configured")

    def execute(self, repo_root: Path) -> ShellResult:
        if not self.enabled:
            return ShellResult(command=["build"], returncode=1, stdout="", stderr="build adapter disabled")
        if not self.command:
            return ShellResult(command=["build"], returncode=1, stdout="", stderr="build command not configured")
        return run_command_text(self.command, cwd=repo_root)
