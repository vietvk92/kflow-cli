"""Artifact command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from typer import Typer

from kflow.cli.common import run_command
from kflow.services.artifact_service import ArtifactService

app = Typer(help="Artifact commands.")


@app.command("list")
def list_artifacts(
    task_id: Optional[str] = typer.Argument(default=None),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List artifact files for the current task."""
    run_command(lambda: ArtifactService(Path.cwd()).list_artifacts(task_id), json_output=json_output)


@app.command("collect")
def collect(
    task_id: Optional[str] = typer.Argument(default=None),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Collect standard artifacts for the current task."""
    run_command(lambda: ArtifactService(Path.cwd()).collect_artifacts(task_id), json_output=json_output)


@app.command("scaffold-ci")
def scaffold_ci(
    provider: str = typer.Option("github", "--provider", help="CI provider template to generate."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing workflow template."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Generate a packaged CI workflow template."""
    run_command(lambda: ArtifactService(Path.cwd()).scaffold_ci(provider=provider, force=force), json_output=json_output)
