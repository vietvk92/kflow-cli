"""Intake command — bootstrap tasks from dropped spec files."""

from __future__ import annotations

from pathlib import Path

import typer

from kflow.cli.common import run_command
from kflow.services.intake_service import IntakeService


def intake(
    apply: bool = typer.Option(False, "--apply", help="Create tasks (omit for dry-run preview)."),
    force: bool = typer.Option(False, "--force", help="Re-ingest already-processed specs."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Ingest spec files from the intake directory and bootstrap tasks.

    Drop .md or .txt spec files into the configured intake directory
    (default: specs/) then run this command to auto-create tasks with
    TASK_BRIEF.md pre-filled from the spec content.

    Examples:

      kflow intake            # preview what would be created
      kflow intake --apply    # create tasks
      kflow intake --apply --force  # re-ingest already-processed specs
    """
    svc = IntakeService(Path.cwd())
    if apply:
        run_command(lambda: svc.run(force=force), json_output=json_output)
    else:
        run_command(lambda: svc.scan(), json_output=json_output)
