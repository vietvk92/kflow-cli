"""Shared CLI helpers."""

from __future__ import annotations

import json
from typing import Callable, TypeVar

import typer

from kflow.core.exceptions import KFlowConfigError, KFlowError, KFlowFilesystemError, KFlowValidationError
from kflow.models.results import OperationResult
from kflow.utils.console import build_console, render_result


ResultT = TypeVar("ResultT", bound=OperationResult)


def emit_result(result: OperationResult, json_output: bool) -> None:
    """Render a service result in text or JSON mode."""
    if json_output:
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2))
        return
    render_result(build_console(), result)


def run_command(action: Callable[[], ResultT], *, json_output: bool = False) -> None:
    """Run a command and convert known application errors into clean CLI output."""
    try:
        result = action()
    except KFlowValidationError as exc:
        for message in exc.messages:
            typer.echo(f"ERROR: {message}")
        raise typer.Exit(code=1) from exc
    except (KFlowConfigError, KFlowFilesystemError, KFlowError) as exc:
        typer.echo(f"ERROR: {exc}")
        raise typer.Exit(code=1) from exc
    emit_result(result, json_output)


def run_command_with_status_exit(
    action: Callable[[], ResultT],
    *,
    json_output: bool = False,
    fail_statuses: tuple[str, ...] = ("blocked",),
) -> None:
    """Run a command and exit non-zero when the resulting status matches a CI-failing state."""
    try:
        result = action()
    except KFlowValidationError as exc:
        for message in exc.messages:
            typer.echo(f"ERROR: {message}")
        raise typer.Exit(code=1) from exc
    except (KFlowConfigError, KFlowFilesystemError, KFlowError) as exc:
        typer.echo(f"ERROR: {exc}")
        raise typer.Exit(code=1) from exc
    emit_result(result, json_output)
    if result.status in fail_statuses:
        raise typer.Exit(code=1)
