"""Phase command handlers."""

from __future__ import annotations

from pathlib import Path

import typer
from typer import Typer

from kflow.cli.common import run_command
from kflow.services.phase_service import PhaseService

app = Typer(help="Phase commands.")


@app.command("check")
def check(
    phase_ref: str = typer.Argument(..., help="Phase number or phase id."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Check whether a phase is ready, with shared scope/summary fields in JSON mode."""
    run_command(lambda: PhaseService(Path.cwd()).check(phase_ref), json_output=json_output)
