"""Typer application wiring."""

from kflow.cli.analyze_cmd import analyze
from kflow.cli.build_cmd import build
from kflow.cli.inspect_cmd import inspect
from kflow.cli.intake_cmd import intake
from kflow.cli.plan_cmd import plan
from typer import Typer

from kflow.cli.artifact_cmd import app as artifact_app
from kflow.cli.config_cmd import app as config_app
from kflow.cli.doctor_cmd import app as doctor_app
from kflow.cli.env_cmd import app as env_app
from kflow.cli.init_cmd import init
from kflow.cli.task_cmd import app as task_app
from kflow.cli.phase_cmd import app as phase_app
from kflow.cli.sprint_cmd import app as sprint_app
from kflow.cli.test_cmd import test
from kflow.cli.verify_cmd import app as verify_app

app = Typer(help="KFlow workflow enforcement CLI.")
app.command()(init)
app.command()(analyze)
app.command()(intake)
app.command()(plan)
app.command()(build)
app.command()(inspect)
app.command()(test)
app.add_typer(env_app, name="env")
app.add_typer(config_app, name="config")
app.add_typer(sprint_app, name="sprint")
app.add_typer(phase_app, name="phase")
app.add_typer(task_app, name="task")
app.add_typer(doctor_app, name="doctor")
app.add_typer(artifact_app, name="artifacts")
app.add_typer(verify_app, name="verify")
