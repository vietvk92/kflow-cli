import json
from pathlib import Path
import subprocess

import yaml

from kflow.services.artifact_service import ArtifactService
from kflow.services.execution_service import ExecutionService
from kflow.services.init_service import InitService
from kflow.services.result_service import ResultService
from kflow.services.task_service import TaskService


def test_collect_artifacts_writes_execution_evidence_json(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"print('build-ok')\""}
    config["adapters"]["test"] = {"enabled": True, "command": "python3 -c \"print('test-ok')\""}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    TaskService(tmp_path).create_task(task_type="feat", name="Artifact evidence", risk="medium")
    ExecutionService(tmp_path).run_build()
    ExecutionService(tmp_path).run_test()

    result = ArtifactService(tmp_path).collect_artifacts()

    evidence_path = tmp_path / ".kflow" / "tasks" / "artifact-evidence" / "artifacts" / "execution-evidence.json"
    ci_summary_path = tmp_path / ".kflow" / "tasks" / "artifact-evidence" / "artifacts" / "ci-summary.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    ci_summary = json.loads(ci_summary_path.read_text(encoding="utf-8"))
    assert result.status == "ok"
    assert evidence["build"] == "pass"
    assert evidence["test"] == "pass"
    assert "artifacts/execution-evidence.json" in result.data["artifacts"]
    assert "artifacts/ci-summary.json" in result.data["artifacts"]
    assert ci_summary["doctor"]["status"] in {"ok", "warning", "blocked"}
    assert "policy_source" in ci_summary["doctor"]
    assert "stop_conditions" in ci_summary["doctor"]
    assert ci_summary["task_status"]["evidence"]["build"] == "pass"


def test_result_sync_includes_repo_diff_files_when_git_available(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("print('changed')\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    task = TaskService(tmp_path).create_task(task_type="feat", name="Result sync", risk="medium")
    record = TaskService(tmp_path).get_task("result-sync")
    ResultService(record).sync_changed_files()

    result_md = (tmp_path / ".kflow" / "tasks" / "result-sync" / "RESULT.md").read_text(encoding="utf-8")
    assert "- feature.py" in result_md


def test_scaffold_ci_writes_github_actions_workflow_and_respects_force(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    service = ArtifactService(tmp_path)
    first = service.scaffold_ci()
    workflow_path = tmp_path / ".github" / "workflows" / "kflow-ci.yml"

    assert first.status == "ok"
    assert workflow_path.exists()
    assert "doctor ci --repo --json" in workflow_path.read_text(encoding="utf-8")

    workflow_path.write_text("custom\n", encoding="utf-8")
    second = service.scaffold_ci()
    assert second.status == "warning"
    assert workflow_path.read_text(encoding="utf-8") == "custom\n"

    third = service.scaffold_ci(force=True)
    assert third.status == "ok"
    assert "doctor report --json" in workflow_path.read_text(encoding="utf-8")
