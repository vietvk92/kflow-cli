"""Verify command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from typer import Typer

from kflow.cli.common import run_command
from kflow.services.execution_service import ExecutionService

app = Typer(help="Verification commands.")


@app.command("mobile")
def mobile(task_id: Optional[str] = typer.Argument(default=None), json_output: bool = typer.Option(False, "--json")) -> None:
    """Run mobile verification for the current task."""
    run_command(lambda: ExecutionService(Path.cwd()).run_mobile_verify(task_id), json_output=json_output)
