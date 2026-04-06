import json
from pathlib import Path

from typer.testing import CliRunner

from kflow.cli.app import app


runner = CliRunner()


def test_json_result_contract_includes_meta(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    init_payload = json.loads(runner.invoke(app, ["init", "--json"], catch_exceptions=False).stdout)
    env_payload = json.loads(runner.invoke(app, ["env", "detect", "--json"], catch_exceptions=False).stdout)

    for payload in (init_payload, env_payload):
        assert payload["meta"]["schema_version"] == 1
        assert payload["meta"]["generated_at"]
