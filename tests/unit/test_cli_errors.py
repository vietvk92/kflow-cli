from pathlib import Path

from typer.testing import CliRunner

from kflow.cli.app import app


runner = CliRunner()


def test_config_validate_without_init_returns_clean_error(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["config", "validate"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "ERROR: Config file not found:" in result.stdout
    assert "Traceback" not in result.stdout


def test_task_doctor_without_current_task_returns_clean_error(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0

    result = runner.invoke(app, ["task", "doctor"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "ERROR:" in result.stdout
    assert "current_task.yaml" in result.stdout
    assert "Traceback" not in result.stdout


def test_config_set_with_unknown_key_returns_clean_error(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0

    result = runner.invoke(app, ["config", "set", "adapters.unknown.enabled", "true"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "ERROR:" in result.stdout
    assert "Unknown config key" in result.stdout
