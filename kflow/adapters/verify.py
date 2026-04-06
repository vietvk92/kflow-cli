"""Verify adapter scaffold."""

from __future__ import annotations

from pathlib import Path

from kflow.adapters.base import AdapterDetection, DetectionAdapter
from kflow.utils.shell import ShellResult, run_command_text


class VerifyAdapter(DetectionAdapter):
    """Detect mobile verify script presence."""

    name = "verify"

    def __init__(self, command: str | None, enabled: bool) -> None:
        self.command = command
        self.enabled = enabled

    def detect(self, repo_root: Path) -> AdapterDetection:
        if not self.enabled:
            return AdapterDetection(status="disabled", detail=self.command or "disabled")
        if not self.command:
            return AdapterDetection(status="missing", detail="command not configured")
        path = repo_root / self.command if not Path(self.command).is_absolute() else Path(self.command)
        return AdapterDetection(status="present" if path.exists() else "missing", detail=str(path))

    def execute(self, repo_root: Path) -> ShellResult:
        if not self.enabled:
            return ShellResult(command=["verify"], returncode=1, stdout="", stderr="verify adapter disabled")
        if not self.command:
            return ShellResult(command=["verify"], returncode=1, stdout="", stderr="verify command not configured")
        return run_command_text(self.command, cwd=repo_root)
