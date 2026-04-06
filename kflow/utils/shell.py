"""Shell execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shlex
import subprocess


@dataclass
class ShellResult:
    """Stable subprocess result wrapper."""

    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run(command: list[str], cwd: Path | None = None) -> ShellResult:
    """Run a subprocess without raising on missing commands."""
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
        )
        return ShellResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
    except FileNotFoundError:
        return ShellResult(command=command, returncode=127, stdout="", stderr="command not found")


def run_command_text(command: str, cwd: Path | None = None) -> ShellResult:
    """Run a shell-style command string via shlex parsing."""
    return run(shlex.split(command), cwd=cwd)
