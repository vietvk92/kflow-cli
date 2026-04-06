"""Init command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from kflow.cli.common import run_command
from kflow.services.init_service import InitService


def init(
    workflow: Optional[str] = typer.Option(default=None, help="Override workflow file path."),
    project_type: Optional[str] = typer.Option(default=None, help="Force project type."),
    force: bool = typer.Option(default=False, help="Overwrite existing config."),
    non_interactive: bool = typer.Option(default=False, help="Reserved for future use."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Initialize KFlow in the current repository."""
    _ = non_interactive
    run_command(
        lambda: InitService().initialize(Path.cwd(), workflow=workflow, project_type=project_type, force=force),
        json_output=json_output,
    )
