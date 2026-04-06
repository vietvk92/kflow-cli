"""Doctor command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from typer import Typer

from kflow.cli.common import run_command, run_command_with_status_exit
from kflow.cli.env_cmd import detect
from kflow.services.doctor_service import DoctorService
from kflow.services.report_service import ReportService
from kflow.services.sprint_service import SprintService

app = Typer(help="Doctor commands.")
app.command("env")(detect)


@app.command("task")
def task(
    task_id: Optional[str] = typer.Argument(default=None),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Alias to task doctor."""
    run_command(lambda: DoctorService(Path.cwd()).inspect_task(task_id, closeout=False), json_output=json_output)


@app.command("repo")
def repo(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Run repository-level health checks."""
    run_command(lambda: DoctorService(Path.cwd()).inspect_repo(), json_output=json_output)


@app.command("sprint")
def sprint(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Run sprint-level health checks over planning and linked-task evidence."""
    run_command(lambda: SprintService(Path.cwd()).doctor(), json_output=json_output)


@app.command("ci")
def ci(
    task_id: Optional[str] = typer.Argument(default=None),
    closeout: bool = typer.Option(False, "--closeout", help="Use closeout-level gating."),
    repo: bool = typer.Option(False, "--repo", help="Run aggregated repo/sprint/task CI gating."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Run CI-oriented doctor checks and exit non-zero on blocked results."""
    if repo:
        run_command_with_status_exit(
            lambda: ReportService(Path.cwd()).doctor_report_result(closeout=closeout).model_copy(
                update={"command": "doctor ci"}
            ),
            json_output=json_output,
            fail_statuses=("blocked",),
        )
        return
    run_command_with_status_exit(
        lambda: DoctorService(Path.cwd()).inspect_task(task_id, closeout=closeout),
        json_output=json_output,
        fail_statuses=("blocked",),
    )


@app.command("report")
def report(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Generate an aggregated doctor report artifact for CI or dashboards."""
    run_command(lambda: ReportService(Path.cwd()).doctor_report_result(), json_output=json_output)
