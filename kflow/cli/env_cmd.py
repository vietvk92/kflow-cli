"""Environment command handlers."""

from __future__ import annotations

from pathlib import Path

import typer
from typer import Typer

from kflow.cli.common import run_command
from kflow.config.loader import load_config
from kflow.core.exceptions import KFlowConfigError
from kflow.services.env_service import EnvironmentService

app = Typer(help="Environment commands.")


@app.command("detect")
def detect(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Detect local environment capabilities."""
    def _action():
        cwd = Path.cwd()
        try:
            config = load_config(cwd)
        except KFlowConfigError:
            config = None
        return EnvironmentService().detect(cwd, config)

    run_command(_action, json_output=json_output)
