"""Analyze command handler."""

from __future__ import annotations

from pathlib import Path

import typer

from kflow.cli.common import run_command
from kflow.services.analyze_service import AnalyzeService


def analyze(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Analyze repository planning artifacts and inferred adoption mode."""
    run_command(lambda: AnalyzeService(Path.cwd()).analyze(), json_output=json_output)
