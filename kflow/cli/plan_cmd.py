"""Plan command handler."""

from __future__ import annotations

from pathlib import Path

import typer

from kflow.cli.common import run_command
from kflow.services.plan_service import PlanService


def plan(json_output: bool = typer.Option(False, "--json", help="Emit JSON output."), apply: bool = typer.Option(False, "--apply", help="Apply the plan.")) -> None:
    """Propose a normalized sprint, phase, and task state from detected artifacts."""
    run_command(lambda: PlanService(Path.cwd()).plan(apply=apply), json_output=json_output)
