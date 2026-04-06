"""Sprint command handlers."""

from __future__ import annotations

from pathlib import Path

import typer
from typer import Typer

from kflow.cli.common import run_command
from kflow.services.sprint_service import SprintService

app = Typer(help="Sprint commands.")


@app.command("status")
def status(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Show sprint-related status from planning artifacts, with shared scope/summary fields in JSON mode."""
    run_command(lambda: SprintService(Path.cwd()).status(), json_output=json_output)


@app.command("start")
def start(
    sprint_name: str = typer.Argument(..., help="Human-readable sprint name."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Start a sprint using the repo-local automation script when available."""
    run_command(lambda: SprintService(Path.cwd()).start(sprint_name), json_output=json_output)


@app.command("close")
def close(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Mark the active sprint as completed and archive it."""
    run_command(lambda: SprintService(Path.cwd()).close(), json_output=json_output)
