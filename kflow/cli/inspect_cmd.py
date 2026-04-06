"""Inspect command handler."""

from __future__ import annotations

from pathlib import Path

import typer

from kflow.cli.common import run_command
from kflow.services.inspect_service import InspectService


def inspect(
    symbol: str = typer.Argument(..., help="Symbol or concept to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Run GitNexus-assisted inspection for the current task."""
    run_command(lambda: InspectService(Path.cwd()).inspect(symbol), json_output=json_output)
