"""Task command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from typer import Typer

from kflow.cli.common import run_command
from kflow.services.closeout_service import CloseoutService
from kflow.services.doctor_service import DoctorService
from kflow.services.handoff_service import HandoffService
from kflow.services.task_service import TaskService

app = Typer(help="Task commands.")


@app.command("new")
def new(
    task_type: str = typer.Option(..., "--type", help="Task type."),
    name: str = typer.Option(..., "--name", help="Task name."),
    phase: Optional[str] = typer.Option(default=None, help="Phase reference."),
    risk: str = typer.Option(default="medium", help="Risk level."),
    tags: str = typer.Option(default="", help="Comma-separated tags."),
    task_dir: Optional[str] = typer.Option(None, "--dir", help="Custom task directory."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Create a new task."""
    parsed_tags = [item.strip() for item in tags.split(",") if item.strip()]
    run_command(
        lambda: TaskService(Path.cwd()).create_task(
            task_type=task_type,
            name=name,
            risk=risk,
            phase=phase,
            tags=parsed_tags,
            task_dir_override=task_dir,
        ),
        json_output=json_output,
    )


@app.command("status")
def status(
    task_id: Optional[str] = typer.Argument(default=None),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Show task status, with shared scope/summary fields in JSON mode."""
    run_command(lambda: TaskService(Path.cwd()).status(task_id), json_output=json_output)


@app.command("doctor")
def doctor(
    task_id: Optional[str] = typer.Argument(default=None),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Run task doctor."""
    run_command(lambda: DoctorService(Path.cwd()).inspect_task(task_id, closeout=False), json_output=json_output)


@app.command("close")
def close(
    task_id: Optional[str] = typer.Argument(default=None),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Close a task."""
    run_command(lambda: CloseoutService(Path.cwd()).close_task(task_id), json_output=json_output)


@app.command("handoff")
def handoff(
    task_id: Optional[str] = typer.Argument(default=None),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Export a task handoff artifact for agent or human continuation."""
    run_command(lambda: HandoffService(Path.cwd()).export(task_id), json_output=json_output)
