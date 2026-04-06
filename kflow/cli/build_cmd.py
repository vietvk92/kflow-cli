"""Build command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from kflow.cli.common import run_command
from kflow.services.execution_service import ExecutionService


def build(task_id: Optional[str] = typer.Argument(default=None), json_output: bool = typer.Option(False, "--json")) -> None:
    """Run the configured build command for the current task."""
    run_command(lambda: ExecutionService(Path.cwd()).run_build(task_id), json_output=json_output)
