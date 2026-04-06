"""Config command handlers."""

from pathlib import Path

import typer
from typer import Typer

from kflow.cli.common import run_command
from kflow.services.config_service import ConfigService

app = Typer(help="Config commands.")


@app.command("show")
def show(json_output: bool = typer.Option(False, "--json")) -> None:
    """Show resolved project config."""
    run_command(lambda: ConfigService(Path.cwd()).show(), json_output=json_output)


@app.command("validate")
def validate(json_output: bool = typer.Option(False, "--json")) -> None:
    """Validate project config."""
    run_command(lambda: ConfigService(Path.cwd()).validate(), json_output=json_output)


@app.command("set")
def set_value(
    key: str = typer.Argument(..., help="Dotted config path."),
    value: str = typer.Argument(..., help="New value parsed as YAML scalar/object."),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Set a nested config value and persist it."""
    run_command(lambda: ConfigService(Path.cwd()).set_value(key, value), json_output=json_output)
