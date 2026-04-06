import json
import os
from pathlib import Path
import stat
import subprocess

import yaml

from typer.testing import CliRunner

from kflow.cli.app import app


runner = CliRunner()


def test_init_creates_config_and_env_detect_works(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    init_result = runner.invoke(app, ["init", "--json"], catch_exceptions=False)
    assert init_result.exit_code == 0
    payload = json.loads(init_result.stdout)
    assert payload["command"] == "init"
    assert (tmp_path / ".kflow" / "config.yaml").exists()

    env_result = runner.invoke(app, ["env", "detect", "--json"], catch_exceptions=False)
    assert env_result.exit_code == 0
    env_payload = json.loads(env_result.stdout)
    assert env_payload["command"] == "env detect"
    assert env_payload["environment"]["workflow_file"]["status"] == "present"


def test_analyze_reports_existing_planning_and_detected_specs(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "product-spec.md").write_text("# Spec\nRequirements\n", encoding="utf-8")
    legacy_phase_dir = tmp_path / ".planning" / "01-feature-name"
    legacy_phase_dir.mkdir(parents=True)
    (legacy_phase_dir / "05-CONTEXT.md").write_text("# Context\nLegacy context\n", encoding="utf-8")
    (legacy_phase_dir / "01-01-PLAN.md").write_text("# Plan\nLegacy plan\n", encoding="utf-8")
    (legacy_phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    payload = json.loads(runner.invoke(app, ["analyze", "--json"], catch_exceptions=False).stdout)

    assert payload["command"] == "analyze"
    assert payload["data"]["summary"]["planning_mode"] == "existing_planning"
    assert payload["data"]["summary"]["phase_count"] == 1
    assert payload["data"]["summary"]["spec_count"] == 1


def test_plan_proposes_state_and_is_dry_run_by_default(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "product-spec.md").write_text("# Spec\nRequirements\n", encoding="utf-8")
    legacy_phase_dir = tmp_path / ".planning" / "01-feature-name"
    legacy_phase_dir.mkdir(parents=True)
    (legacy_phase_dir / "05-CONTEXT.md").write_text("# Context\nLegacy context\n", encoding="utf-8")
    (legacy_phase_dir / "01-01-PLAN.md").write_text("# Plan\nLegacy plan\n", encoding="utf-8")
    (legacy_phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    payload = json.loads(runner.invoke(app, ["plan", "--json"], catch_exceptions=False).stdout)

    assert payload["command"] == "plan"
    assert payload["data"]["sprint_stage"] == "execution"
    assert len(payload["data"]["phase_mappings"]) == 1
    assert len(payload["data"]["proposed_tasks"]) == 1
    assert payload["data"]["is_dry_run"] is True


def test_plan_apply_writes_tasks_and_manifest(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "product-spec.md").write_text("# Spec\nRequirements\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    payload = json.loads(runner.invoke(app, ["plan", "--apply", "--json"], catch_exceptions=False).stdout)

    assert payload["command"] == "plan apply"
    assert payload["data"]["is_dry_run"] is False
    assert (tmp_path / ".kflow" / "artifacts" / "planning_attach_manifest.json").exists()

    # The auto-slug functionality for task "Implementation for product-spec" evaluates to "implementation-for-product-spec"
    assert (tmp_path / ".kflow" / "state" / "tasks" / "implementation-for-product-spec.yaml").exists()


def test_doctor_repo_reports_repo_health(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    repo_result = runner.invoke(app, ["doctor", "repo", "--json"], catch_exceptions=False)
    payload = json.loads(repo_result.stdout)

    assert payload["command"] == "doctor repo"
    assert payload["data"]["scope"]["kind"] == "repo"
    assert "warning_count" in payload["data"]["summary"]
    assert "warnings" in payload["data"]
    assert "environment" in payload["data"]
    assert payload["data"]["environment"]["workflow_file"]["status"] == "present"


def test_doctor_repo_includes_gsd_summary(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_1 = tmp_path / ".planning" / "phases" / "1"
    phase_2 = tmp_path / ".planning" / "phases" / "2"
    phase_1.mkdir(parents=True)
    phase_2.mkdir(parents=True)
    (phase_1 / "CONTEXT.md").write_text("# Context\nready context\n", encoding="utf-8")
    (phase_1 / "PLAN.md").write_text("# Plan\nready plan\n", encoding="utf-8")
    (phase_1 / "READY_CHECKLIST.md").write_text("- [x] done\n", encoding="utf-8")
    (phase_2 / "CONTEXT.md").write_text("# Context\npending context\n", encoding="utf-8")
    (phase_2 / "PLAN.md").write_text("# Plan\npending plan\n", encoding="utf-8")
    (phase_2 / "READY_CHECKLIST.md").write_text("- [ ] pending\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    payload = json.loads(runner.invoke(app, ["doctor", "repo", "--json"], catch_exceptions=False).stdout)

    assert payload["data"]["gsd_summary"]["phase_count"] == 2
    assert payload["data"]["gsd_summary"]["ready_phases"] == 1
    assert payload["data"]["gsd_summary"]["current_phase"] == "2"
    assert payload["data"]["summary"]["phase_count"] == 2
    assert payload["data"]["summary"]["ready_phases"] == 1


def test_doctor_repo_warns_when_planning_dir_has_no_phases(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / ".planning").mkdir()
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    payload = json.loads(runner.invoke(app, ["doctor", "repo", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "warning"
    assert "planning directory present but no phases discovered" in payload["data"]["warnings"]
    assert payload["data"]["gsd_summary"]["phase_count"] == 0


def test_config_validate_and_show_json_expose_migration_metadata(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / ".kflow"
    config_dir.mkdir()
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (config_dir / "config.yaml").write_text(
        """
project_name: LegacyApp
project_type: generic
repo_root: REPO_ROOT_PLACEHOLDER
workflow_file: WORKFLOW_v2_PRO.md
policy: {}
output:
  json_enabled: true
""".strip().replace("REPO_ROOT_PLACEHOLDER", str(tmp_path)),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    validate_payload = json.loads(runner.invoke(app, ["config", "validate", "--json"], catch_exceptions=False).stdout)
    show_payload = json.loads(runner.invoke(app, ["config", "show", "--json"], catch_exceptions=False).stdout)

    assert validate_payload["command"] == "config validate"
    assert validate_payload["data"]["migration"]["migrated"] is True
    assert show_payload["command"] == "config show"
    assert show_payload["data"]["migration"]["migrated"] is True
    assert show_payload["data"]["config"]["output"]["json"] is True


def test_sprint_status_degraded_without_planning_dir(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    result = runner.invoke(app, ["sprint", "status"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "planning directory missing" in result.stdout.lower()


def test_sprint_status_uses_configured_planning_path(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    custom_phase_dir = tmp_path / "planning-docs" / "phase-2"
    custom_phase_dir.mkdir(parents=True)
    (custom_phase_dir / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (custom_phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (custom_phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(app, ["config", "set", "paths.planning_dir", "planning-docs"], catch_exceptions=False).exit_code == 0

    payload = json.loads(runner.invoke(app, ["sprint", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["data"]["planning_dir"].endswith("planning-docs")
    assert payload["data"]["summary"]["current_phase"] == "2"


def test_sprint_status_discovers_current_phase_and_readiness(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_1 = tmp_path / ".planning" / "phases" / "1"
    phase_2 = tmp_path / ".planning" / "phases" / "2"
    phase_1.mkdir(parents=True)
    phase_2.mkdir(parents=True)
    (phase_1 / "CONTEXT.md").write_text("# Context\nready context\n", encoding="utf-8")
    (phase_1 / "PLAN.md").write_text("# Plan\nready plan\n", encoding="utf-8")
    (phase_1 / "READY_CHECKLIST.md").write_text("- [x] done\n", encoding="utf-8")
    (phase_2 / "CONTEXT.md").write_text("# Context\npending context\n", encoding="utf-8")
    (phase_2 / "PLAN.md").write_text("# Plan\npending plan\n", encoding="utf-8")
    (phase_2 / "READY_CHECKLIST.md").write_text("- [ ] pending\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    result = runner.invoke(app, ["sprint", "status", "--help"], catch_exceptions=False)
    assert result.exit_code == 0

    json_result = runner.invoke(app, ["sprint", "status"], catch_exceptions=False)
    assert "Current phase: 2" in json_result.stdout
    assert "Ready phases: 1/2" in json_result.stdout

    payload = json.loads(runner.invoke(app, ["sprint", "status", "--json"], catch_exceptions=False).stdout)
    assert payload["data"]["readiness_totals"]["ready"] == 1
    assert payload["data"]["readiness_totals"]["not_ready"] == 1
    assert payload["data"]["scope"]["kind"] == "sprint"
    assert payload["data"]["summary"]["current_phase"] == "2"
    assert payload["data"]["summary_artifact"]
    assert (tmp_path / ".kflow" / "artifacts" / "sprint-summary.json").exists()


def test_sprint_status_reports_unknown_phase_when_docs_missing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_3 = tmp_path / ".planning" / "phases" / "3"
    phase_3.mkdir(parents=True)
    (phase_3 / "READY_CHECKLIST.md").write_text("- [x] done\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    payload = json.loads(runner.invoke(app, ["sprint", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "ok"
    assert payload["data"]["readiness_totals"]["unknown"] == 1
    assert payload["data"]["phases"][0]["blockers"] == ["context_missing", "plan_missing"]


def test_sprint_status_includes_phase_task_totals(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_4 = tmp_path / ".planning" / "phases" / "4"
    phase_4.mkdir(parents=True)
    (phase_4 / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_4 / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_4 / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Sprint linked one", "--phase", "4"],
        catch_exceptions=False,
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "Sprint linked two", "--phase", "4"],
        catch_exceptions=False,
    ).exit_code == 0

    payload = json.loads(runner.invoke(app, ["sprint", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["data"]["task_totals"]["total"] == 2
    assert payload["data"]["task_totals"]["open"] == 2
    assert payload["data"]["phases"][0]["linked_tasks"]["task_count"] == 2
    assert payload["data"]["phases"][0]["linked_tasks"]["current_task_id"] == "sprint-linked-two"
    assert payload["data"]["evidence_totals"]["build"]["missing"] == 2


def test_sprint_status_aggregates_task_execution_evidence(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_5 = tmp_path / ".planning" / "phases" / "5"
    phase_5.mkdir(parents=True)
    (phase_5 / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_5 / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_5 / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"print(1)\""}
    config["adapters"]["test"] = {"enabled": True, "command": "python3 -c \"print('2 passed in 0.10s')\""}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Evidence phase task", "--phase", "5"],
        catch_exceptions=False,
    ).exit_code == 0
    assert runner.invoke(app, ["build", "--json"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(app, ["test", "--json"], catch_exceptions=False).exit_code == 0

    payload = json.loads(runner.invoke(app, ["sprint", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["data"]["evidence_totals"]["build"]["pass"] == 1
    assert payload["data"]["evidence_totals"]["test"]["pass"] == 1
    assert payload["data"]["phases"][0]["linked_tasks"]["tasks"][0]["evidence"]["build"] == "pass"


def test_task_status_json_includes_evidence_and_phase_context(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_6 = tmp_path / ".planning" / "phases" / "6"
    phase_6.mkdir(parents=True)
    (phase_6 / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_6 / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_6 / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"print(1)\""}
    config["adapters"]["test"] = {"enabled": True, "command": "python3 -c \"print('1 passed in 0.10s')\""}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Status phase task", "--phase", "6"],
        catch_exceptions=False,
    ).exit_code == 0
    assert runner.invoke(app, ["build", "--json"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(app, ["test", "--json"], catch_exceptions=False).exit_code == 0

    payload = json.loads(runner.invoke(app, ["task", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["command"] == "task status"
    assert payload["data"]["scope"]["kind"] == "task"
    assert payload["data"]["summary"]["status"] == "verification_pending"
    assert payload["data"]["is_current_task"] is True
    assert payload["data"]["evidence"]["build"] == "pass"
    assert payload["data"]["evidence"]["test"] == "pass"
    assert payload["data"]["phase_summary"]["phase"] == "6"
    assert payload["data"]["phase_summary"]["task_count"] == 1


def test_task_status_exposes_policy_requirements_and_warnings(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "Policy status task", "--tags", "permissions"],
        catch_exceptions=False,
    ).exit_code == 0

    payload = json.loads(runner.invoke(app, ["task", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "warning"
    assert "mobile verification required" in payload["data"]["requirements"]
    assert "build evidence missing" in payload["data"]["warnings"]
    assert payload["data"]["summary"]["gates_open"] >= 2
    assert "diff_summary" in payload["data"]["summary"]


def test_task_status_json_surfaces_policy_required_adapter_blocker(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
required_adapters: [mobile_verify]
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Adapter gated task", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    payload = json.loads(runner.invoke(app, ["task", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "blocked"
    assert "required adapter unavailable: mobile_verify" in payload["data"]["blockers"]
    assert payload["data"]["summary"]["gates_open"] >= 1


def test_task_status_json_uses_project_rules_for_ios_tasks(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules:
  ios:
    require_build_evidence: true
    require_test_evidence: true
    require_mobile_verify: true
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init", "--project-type", "ios"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "iOS gated task", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    payload = json.loads(runner.invoke(app, ["task", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "warning"
    assert "build evidence required for ios project" in payload["data"]["requirements"]
    assert "test evidence required for ios project" in payload["data"]["requirements"]
    assert "mobile verification required for ios project" in payload["data"]["requirements"]


def test_task_status_json_uses_tag_rules(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
tag_rules:
  payments:
    require_manual_review: true
    require_test_plan_if_code_changes: true
    messages:
      warnings: ["payments path requires audit trail review"]
      next_steps: ["Confirm audit-trail coverage for payments flows."]
project_rules: {}
phase_rules: {}
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "payments.py").write_text("print('changed')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Payments tagged task", "--tags", "payments", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    payload = json.loads(runner.invoke(app, ["task", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "warning"
    assert "manual review required for tag: payments" in payload["data"]["warnings"]
    assert "payments path requires audit trail review" in payload["data"]["warnings"]
    assert "test plan required for tag: payments" in payload["data"]["requirements"]


def test_task_status_json_uses_phase_rules_for_phase_linked_tasks(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules: {}
phase_rules:
  11:
    require_build_evidence: true
    require_test_evidence: true
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Phase gated task", "--phase", "11", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    payload = json.loads(runner.invoke(app, ["task", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "warning"
    assert "build evidence required for phase 11" in payload["data"]["requirements"]
    assert "test evidence required for phase 11" in payload["data"]["requirements"]
    assert payload["data"]["scope"]["phase"] == "11"


def test_task_status_json_surfaces_phase_readiness_blockers(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules: {}
phase_rules:
  12:
    require_docs_ready: true
    require_checklist_complete: true
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    phase_dir = tmp_path / ".planning" / "phases" / "12"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [ ] pending\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Phase readiness gated task", "--phase", "12", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    payload = json.loads(runner.invoke(app, ["task", "status", "--json"], catch_exceptions=False).stdout)

    assert payload["status"] == "blocked"
    assert "planning docs not ready for phase 12" in payload["data"]["blockers"]
    assert "phase checklist incomplete: 12" in payload["data"]["blockers"]
    assert payload["data"]["phase_state"]["readiness"] == "not_ready"


def test_task_status_json_surfaces_phase_linked_task_health_blockers(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules: {}
phase_rules:
  15:
    require_no_failing_linked_tasks: true
    require_no_other_open_tasks: true
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    phase_dir = tmp_path / ".planning" / "phases" / "15"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Linked failing task", "--phase", "15", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Current linked gated task", "--phase", "15", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"import sys; sys.exit(1)\""}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    assert runner.invoke(app, ["build", "--json", "linked-failing-task"], catch_exceptions=False).exit_code == 0

    payload = json.loads(
        runner.invoke(app, ["task", "status", "--json", "current-linked-gated-task"], catch_exceptions=False).stdout
    )

    assert payload["status"] == "blocked"
    assert "linked task execution failing in phase 15" in payload["data"]["blockers"]
    assert "other linked tasks still open in phase 15" in payload["data"]["blockers"]
    assert payload["data"]["phase_task_state"]["has_failing_linked_tasks"] is True


def test_doctor_sprint_blocks_on_failing_linked_task_evidence(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_dir = tmp_path / ".planning" / "phases" / "16"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Sprint failing task", "--phase", "16", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"import sys; sys.exit(1)\""}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    assert runner.invoke(app, ["build", "--json"], catch_exceptions=False).exit_code == 0

    payload = json.loads(runner.invoke(app, ["doctor", "sprint", "--json"], catch_exceptions=False).stdout)

    assert payload["command"] == "doctor sprint"
    assert payload["status"] == "blocked"
    assert "sprint has failing build evidence in linked tasks" in payload["data"]["blockers"]


def test_doctor_sprint_uses_sprint_policy_for_current_phase_readiness(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules: {}
phase_rules: {}
sprint_rules:
  require_current_phase_ready: true
  messages:
    warnings: ["sprint review required before advance"]
    next_steps: ["Finish sprint readiness review before proceeding."]
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    phase_dir = tmp_path / ".planning" / "phases" / "18"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [ ] pending\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    payload = json.loads(runner.invoke(app, ["doctor", "sprint", "--json"], catch_exceptions=False).stdout)

    assert payload["command"] == "doctor sprint"
    assert payload["status"] == "blocked"
    assert str(payload["data"]["policy_source"]).endswith("WORKFLOW_v2_PRO.md")
    assert "current phase not ready for sprint policy: 18" in payload["data"]["blockers"]
    assert "sprint review required before advance" in payload["data"]["warnings"]
    assert "Finish sprint readiness review before proceeding." in payload["data"]["next_steps"]


def test_doctor_ci_repo_uses_sprint_doctor_in_overall_status(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_dir = tmp_path / ".planning" / "phases" / "17"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "feat", "--name", "Repo sprint failing task", "--phase", "17", "--risk", "medium"],
        catch_exceptions=False,
    ).exit_code == 0

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"import sys; sys.exit(1)\""}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    assert runner.invoke(app, ["build", "--json"], catch_exceptions=False).exit_code == 0

    result = runner.invoke(app, ["doctor", "ci", "--repo", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert result.exit_code == 1
    assert payload["data"]["report"]["overall_status"] == "blocked"
    assert payload["data"]["report"]["sprint_doctor"]["status"] == "blocked"


def test_doctor_ci_exits_nonzero_on_blocked_result(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "CI blocked task", "--tags", "permissions"],
        catch_exceptions=False,
    ).exit_code == 0

    result = runner.invoke(app, ["doctor", "ci", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert result.exit_code == 1
    assert payload["command"] == "task doctor"
    assert payload["status"] == "blocked"
    assert payload["data"]["scope"]["kind"] == "task"
    assert payload["data"]["summary"]["blocker_count"] >= 1


def test_doctor_ci_closeout_exits_zero_when_task_is_ready(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    tools_dir = tmp_path / ".tools"
    tools_dir.mkdir()
    verify_script = tools_dir / "verify-mobile.sh"
    verify_script.write_text("#!/bin/sh\necho mobile-ok\n", encoding="utf-8")
    verify_script.chmod(verify_script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"print('build-ok')\""}
    config["adapters"]["test"] = {"enabled": True, "command": "python3 -c \"print('3 passed in 0.10s')\""}
    config["adapters"]["mobile_verify"] = {"enabled": True, "command": "./.tools/verify-mobile.sh"}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "CI ready task", "--tags", "permissions"],
        catch_exceptions=False,
    ).exit_code == 0

    brief_path = tmp_path / ".kflow" / "tasks" / "ci-ready-task" / "TASK_BRIEF.md"
    brief = brief_path.read_text(encoding="utf-8")
    brief = brief.replace("## Goal\n", "## Goal\nFix permission fallback\n")
    brief = brief.replace("## Acceptance Criteria\n", "## Acceptance Criteria\n- fallback works\n")
    brief = brief.replace("## Repro Steps\n", "## Repro Steps\n- open app\n")
    brief = brief.replace("## Risk Level\n", "## Risk Level\nhigh\n")
    brief_path.write_text(brief, encoding="utf-8")

    change_plan_path = tmp_path / ".kflow" / "tasks" / "ci-ready-task" / "CHANGE_PLAN.md"
    change_plan = change_plan_path.read_text(encoding="utf-8")
    change_plan = change_plan.replace("## Impacted Symbols\n", "## Impacted Symbols\n- PermissionManager\n")
    change_plan = change_plan.replace("## Test Plan\n", "## Test Plan\n- targeted permission regression\n")
    change_plan_path.write_text(change_plan, encoding="utf-8")

    assert runner.invoke(app, ["build", "--json"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(app, ["test", "--json"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(app, ["verify", "mobile", "--json"], catch_exceptions=False).exit_code == 0

    result_path = tmp_path / ".kflow" / "tasks" / "ci-ready-task" / "RESULT.md"
    result_text = result_path.read_text(encoding="utf-8")
    result_text = result_text.replace("## Build Result\npass", "## Build Result\npass")
    result_text = result_text.replace("## Test Result\npass", "## Test Result\npass")
    result_path.write_text(result_text, encoding="utf-8")

    result = runner.invoke(app, ["doctor", "ci", "--closeout", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload["status"] in {"ok", "warning"}


def test_doctor_report_writes_aggregate_report(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "Report task", "--tags", "permissions"],
        catch_exceptions=False,
    ).exit_code == 0

    result = runner.invoke(app, ["doctor", "report", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert payload["command"] == "doctor report"
    assert payload["data"]["scope"]["kind"] == "repo_report"
    assert payload["data"]["summary"]["overall_status"] in {"ok", "warning", "blocked"}
    assert "task_policy_source" in payload["data"]["summary"]
    assert "task_stop_condition_count" in payload["data"]["summary"]
    assert payload["data"]["report"]["overall_status"] in {"ok", "warning", "blocked"}
    assert "policy" in payload["data"]["report"]
    assert payload["data"]["report"]["repo"]["command"] == "doctor repo"
    assert payload["data"]["report"]["task_doctor"]["command"] == "task doctor"
    assert (tmp_path / ".kflow" / "artifacts" / "doctor-report.json").exists()


def test_doctor_ci_repo_uses_aggregate_report_and_exits_nonzero_on_blocked(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "Repo CI task", "--tags", "permissions"],
        catch_exceptions=False,
    ).exit_code == 0

    result = runner.invoke(app, ["doctor", "ci", "--repo", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert result.exit_code == 1
    assert payload["command"] == "doctor ci"
    assert payload["data"]["report"]["overall_status"] == "blocked"


def test_artifacts_scaffold_ci_generates_workflow_template(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0

    first = runner.invoke(app, ["artifacts", "scaffold-ci", "--json"], catch_exceptions=False)
    payload = json.loads(first.stdout)
    workflow_path = tmp_path / ".github" / "workflows" / "kflow-ci.yml"

    assert first.exit_code == 0
    assert payload["command"] == "artifacts scaffold-ci"
    assert payload["status"] == "ok"
    assert payload["data"]["provider"] == "github"
    assert payload["data"]["written"] is True
    assert workflow_path.exists()

    workflow_path.write_text("custom\n", encoding="utf-8")
    second = runner.invoke(app, ["artifacts", "scaffold-ci", "--json"], catch_exceptions=False)
    second_payload = json.loads(second.stdout)

    assert second.exit_code == 0
    assert second_payload["status"] == "warning"
    assert second_payload["data"]["written"] is False
    assert workflow_path.read_text(encoding="utf-8") == "custom\n"


def test_task_handoff_exports_agent_context_artifact(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "Handoff task", "--tags", "permissions"],
        catch_exceptions=False,
    ).exit_code == 0

    result = runner.invoke(app, ["task", "handoff", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert payload["command"] == "task handoff"
    assert payload["data"]["task_id"] == "handoff-task"
    assert "KFlow Agent Handoff" in payload["data"]["prompt"]
    assert (tmp_path / ".kflow" / "tasks" / "handoff-task" / "artifacts" / "agent-handoff.md").exists()


def test_sprint_start_runs_repo_script_and_writes_log(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    tools_dir = tmp_path / ".tools"
    tools_dir.mkdir()
    script = tools_dir / "start-sprint.sh"
    script.write_text(
        "#!/bin/sh\n"
        "mkdir -p .planning/phases/7\n"
        "printf '%s\n' '- [ ] bootstrap' > .planning/phases/7/READY_CHECKLIST.md\n"
        "echo started:$1\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    result = runner.invoke(app, ["sprint", "start", "Sprint 7", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert payload["command"] == "sprint start"
    assert payload["status"] == "ok"
    assert payload["data"]["started"] is True
    assert payload["data"]["outputs_verified"] is True
    assert payload["data"]["phases_after"] == ["7"]
    assert (tmp_path / ".kflow" / "logs" / "sprint-start.log").exists()


def test_sprint_start_uses_gsd_fallback_when_script_creates_no_outputs(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    tools_dir = tmp_path / ".tools"
    tools_dir.mkdir()
    script = tools_dir / "start-sprint.sh"
    script.write_text("#!/bin/sh\necho started:$1\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gsd = bin_dir / "gsd-new-milestone"
    gsd.write_text(
        "#!/bin/sh\n"
        "mkdir -p .planning/phases/1\n"
        "printf '%s\n' '- [x] milestone bootstrapped' > .planning/phases/1/READY_CHECKLIST.md\n",
        encoding="utf-8",
    )
    gsd.chmod(gsd.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    result = runner.invoke(app, ["sprint", "start", "Sprint Fallback", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert payload["status"] == "ok"
    assert payload["data"]["outputs_verified"] is True
    assert payload["data"]["gsd"]["attempted"] is True
    assert payload["data"]["gsd"]["ok"] is True
    assert payload["data"]["phases_after"] == ["1"]


def test_phase_check_reads_phase_docs_and_reports_warning(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    planning_phase = tmp_path / ".planning" / "phases" / "2"
    planning_phase.mkdir(parents=True)
    (planning_phase / "CONTEXT.md").write_text("# Context\nPhase scope is captured\n", encoding="utf-8")
    (planning_phase / "PLAN.md").write_text("# Plan\nImplement and verify the flow\n", encoding="utf-8")
    (planning_phase / "READY_CHECKLIST.md").write_text("- [ ] ac mapped\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    result = runner.invoke(app, ["phase", "check", "2", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert payload["command"] == "phase check"
    assert payload["status"] == "warning"
    assert payload["data"]["scope"]["kind"] == "phase"
    assert payload["data"]["summary"]["readiness"] == "warning"
    assert "READY_CHECKLIST.md incomplete" in payload["data"]["warnings"]
    assert payload["data"]["checklist_summary"]["incomplete"] == 1


def test_phase_check_blocks_on_empty_phase_docs(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    planning_phase = tmp_path / ".planning" / "phases" / "3"
    planning_phase.mkdir(parents=True)
    (planning_phase / "CONTEXT.md").write_text("# Context\n", encoding="utf-8")
    (planning_phase / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
    (planning_phase / "READY_CHECKLIST.md").write_text("- [x] mapped\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    result = runner.invoke(app, ["phase", "check", "3", "--json"], catch_exceptions=False)
    payload = json.loads(result.stdout)

    assert payload["status"] == "blocked"
    assert "CONTEXT.md has no meaningful content" in payload["data"]["blockers"]
    assert "PLAN.md has no meaningful content" in payload["data"]["blockers"]
    assert payload["data"]["documents"]["context"]["has_content"] is False


def test_inspect_updates_change_plan_and_task_state(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    tools_dir = tmp_path / ".tools"
    tools_dir.mkdir()
    gitnexus = tools_dir / "gitnexus"
    gitnexus.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--help\" ]; then echo ok; exit 0; fi\n"
        "if [ \"$1\" = \"context\" ]; then printf '%s\n%s\n' context-for-$2 risk-for-$2; exit 0; fi\n"
        "if [ \"$1\" = \"impact\" ]; then printf '%s\n%s\n' impact-for-$2 patch-for-$2; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gitnexus.chmod(gitnexus.stat().st_mode | stat.S_IEXEC)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["gitnexus"] = {"enabled": True, "command": "./.tools/gitnexus"}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(app, ["task", "new", "--type", "feat", "--name", "Inspect flow"], catch_exceptions=False).exit_code == 0

    inspect_result = runner.invoke(app, ["inspect", "LocationPermissionManager", "--json"], catch_exceptions=False)
    inspect_payload = json.loads(inspect_result.stdout)
    assert inspect_payload["status"] == "ok"
    assert inspect_payload["data"]["task_status"] == "context_ready"
    assert inspect_payload["data"]["context_lines"] == ["context-for-LocationPermissionManager", "risk-for-LocationPermissionManager"]
    assert inspect_payload["data"]["impact_lines"] == ["impact-for-LocationPermissionManager", "patch-for-LocationPermissionManager"]

    change_plan = (tmp_path / ".kflow" / "tasks" / "inspect-flow" / "CHANGE_PLAN.md").read_text(encoding="utf-8")
    assert "- LocationPermissionManager" in change_plan
    assert "- impact-for-LocationPermissionManager" in change_plan
    assert "- patch-for-LocationPermissionManager" in change_plan
    assert "- risk-for-LocationPermissionManager" in change_plan

    rerun_result = runner.invoke(app, ["inspect", "LocationPermissionManager", "--json"], catch_exceptions=False)
    assert rerun_result.exit_code == 0
    change_plan_again = (tmp_path / ".kflow" / "tasks" / "inspect-flow" / "CHANGE_PLAN.md").read_text(encoding="utf-8")
    assert change_plan_again.count("- LocationPermissionManager") == 1
    assert change_plan_again.count("- impact-for-LocationPermissionManager") == 1


def test_inspect_emits_structured_summary_from_key_value_output(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    tools_dir = tmp_path / ".tools"
    tools_dir.mkdir()
    gitnexus = tools_dir / "gitnexus"
    gitnexus.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = \"--help\" ]; then echo ok; exit 0; fi\n"
        "if [ \"$1\" = \"context\" ]; then printf '%s\n%s\n%s\n' 'risk: permissions regression' 'files: app/permissions.py' 'symbol: PermissionGate'; exit 0; fi\n"
        "if [ \"$1\" = \"impact\" ]; then printf '%s\n%s\n' 'change: update permission fallback' 'files: app/permissions.py'; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    gitnexus.chmod(gitnexus.stat().st_mode | stat.S_IEXEC)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["gitnexus"] = {"enabled": True, "command": "./.tools/gitnexus"}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(app, ["task", "new", "--type", "feat", "--name", "Inspect structured"], catch_exceptions=False).exit_code == 0

    inspect_payload = json.loads(runner.invoke(app, ["inspect", "PermissionGate", "--json"], catch_exceptions=False).stdout)

    assert inspect_payload["status"] == "ok"
    assert inspect_payload["data"]["context_fields"]["risk"] == ["permissions regression"]
    assert inspect_payload["data"]["context_fields"]["files"] == ["app/permissions.py"]
    assert inspect_payload["data"]["impact_fields"]["change"] == ["update permission fallback"]

    summary_path = tmp_path / ".kflow" / "tasks" / "inspect-structured" / "artifacts" / "inspect-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["context"]["fields"]["risk"] == ["permissions regression"]
    assert summary["impact"]["fields"]["change"] == ["update permission fallback"]

    change_plan = (tmp_path / ".kflow" / "tasks" / "inspect-structured" / "CHANGE_PLAN.md").read_text(encoding="utf-8")
    assert "- permissions regression" in change_plan
    assert "- update permission fallback" in change_plan


def test_task_doctor_and_close_block_on_incomplete_artifacts(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    task_result = runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "Permission flow", "--tags", "permissions"],
        catch_exceptions=False,
    )
    assert task_result.exit_code == 0

    doctor_result = runner.invoke(app, ["task", "doctor", "--json"], catch_exceptions=False)
    doctor_payload = json.loads(doctor_result.stdout)
    assert doctor_payload["status"] == "blocked"
    assert "repro steps missing" in doctor_payload["data"]["blockers"]

    close_result = runner.invoke(app, ["task", "close", "--json"], catch_exceptions=False)
    close_payload = json.loads(close_result.stdout)
    assert close_payload["status"] == "blocked"
    assert any("RESULT.md section incomplete" in item for item in close_payload["data"]["blockers"])


def test_build_test_and_verify_mobile_create_artifacts_and_update_state(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    tools_dir = tmp_path / ".tools"
    tools_dir.mkdir()
    verify_script = tools_dir / "verify-mobile.sh"
    verify_script.write_text("#!/bin/sh\necho mobile-ok\n", encoding="utf-8")
    verify_script.chmod(verify_script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"print('build-ok')\""}
    config["adapters"]["test"] = {"enabled": True, "command": "python3 -c \"print('3 passed in 0.10s')\""}
    config["adapters"]["mobile_verify"] = {"enabled": True, "command": "./.tools/verify-mobile.sh"}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(app, ["task", "new", "--type", "feat", "--name", "Execution flow"], catch_exceptions=False).exit_code == 0

    build_result = runner.invoke(app, ["build", "--json"], catch_exceptions=False)
    build_payload = json.loads(build_result.stdout)
    assert build_payload["status"] == "ok"
    assert (tmp_path / ".kflow" / "tasks" / "execution-flow" / "artifacts" / "build.log").exists()

    test_result = runner.invoke(app, ["test", "--json"], catch_exceptions=False)
    test_payload = json.loads(test_result.stdout)
    assert test_payload["status"] == "ok"
    assert (tmp_path / ".kflow" / "tasks" / "execution-flow" / "artifacts" / "test.log").exists()
    assert test_payload["data"]["summary"]["passed"] == 3

    verify_result = runner.invoke(app, ["verify", "mobile", "--json"], catch_exceptions=False)
    verify_payload = json.loads(verify_result.stdout)
    assert verify_payload["status"] == "ok"
    assert (tmp_path / ".kflow" / "tasks" / "execution-flow" / "artifacts" / "verify-mobile.log").exists()

    status_result = runner.invoke(app, ["task", "status"], catch_exceptions=False)
    assert "Status: verification_pending" in status_result.stdout
    checklist = (tmp_path / ".kflow" / "tasks" / "execution-flow" / "VERIFY_CHECKLIST.md").read_text(encoding="utf-8")
    assert "- [x] flow verified" in checklist

    artifacts_list = runner.invoke(app, ["artifacts", "list", "--json"], catch_exceptions=False)
    artifacts_payload = json.loads(artifacts_list.stdout)
    assert "artifacts/build.log" in artifacts_payload["data"]["artifacts"]

    collect_result = runner.invoke(app, ["artifacts", "collect", "--json"], catch_exceptions=False)
    collect_payload = json.loads(collect_result.stdout)
    assert "artifacts/env.txt" in collect_payload["data"]["artifacts"]
    assert (tmp_path / ".kflow" / "tasks" / "execution-flow" / "artifacts" / "changed-files.txt").exists()
    assert (tmp_path / ".kflow" / "tasks" / "execution-flow" / "artifacts" / "execution-evidence.json").exists()
    assert (tmp_path / ".kflow" / "tasks" / "execution-flow" / "artifacts" / "ci-summary.json").exists()
    assert collect_payload["data"]["evidence"]["build"] == "pass"
    assert collect_payload["data"]["evidence"]["test_summary"]["passed"] == 3
    assert collect_payload["data"]["ci_summary"]["doctor"]["status"] in {"ok", "warning", "blocked"}
    change_plan = (tmp_path / ".kflow" / "tasks" / "execution-flow" / "CHANGE_PLAN.md").read_text(encoding="utf-8")
    assert "- build: pass [build.log]" in change_plan
    assert "- tests: pass (passed=3) [test.log]" in change_plan
    assert "- mobile verify: pass [verify-mobile.log]" in change_plan
    result_md = (tmp_path / ".kflow" / "tasks" / "execution-flow" / "RESULT.md").read_text(encoding="utf-8")
    assert "## Build Result" in result_md and "pass" in result_md
    assert "## Test Result" in result_md and "pass" in result_md
    assert "## Mobile Verification" in result_md and "pass" in result_md
    assert "- TASK_BRIEF.md" in result_md
    assert "- none" in result_md


def test_close_succeeds_after_required_sections_and_execution(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    tools_dir = tmp_path / ".tools"
    tools_dir.mkdir()
    verify_script = tools_dir / "verify-mobile.sh"
    verify_script.write_text("#!/bin/sh\necho mobile-ok\n", encoding="utf-8")
    verify_script.chmod(verify_script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": "python3 -c \"print('build-ok')\""}
    config["adapters"]["test"] = {"enabled": True, "command": "python3 -c \"print('3 passed in 0.10s')\""}
    config["adapters"]["mobile_verify"] = {"enabled": True, "command": "./.tools/verify-mobile.sh"}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(
        app,
        ["task", "new", "--type", "bug", "--name", "Closable task", "--tags", "permissions"],
        catch_exceptions=False,
    ).exit_code == 0

    brief_path = tmp_path / ".kflow" / "tasks" / "closable-task" / "TASK_BRIEF.md"
    brief = brief_path.read_text(encoding="utf-8")
    brief = brief.replace("## Goal\n", "## Goal\nFix permission fallback\n")
    brief = brief.replace("## Acceptance Criteria\n", "## Acceptance Criteria\n- fallback works\n")
    brief = brief.replace("## Repro Steps\n", "## Repro Steps\n- open app\n")
    brief_path.write_text(brief, encoding="utf-8")

    assert runner.invoke(app, ["build"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(app, ["test"], catch_exceptions=False).exit_code == 0
    assert runner.invoke(app, ["verify", "mobile"], catch_exceptions=False).exit_code == 0

    close_result = runner.invoke(app, ["task", "close", "--json"], catch_exceptions=False)
    close_payload = json.loads(close_result.stdout)
    assert close_payload["status"] == "ok"
    assert close_payload["data"]["status"] == "done"

    result_md = (tmp_path / ".kflow" / "tasks" / "closable-task" / "RESULT.md").read_text(encoding="utf-8")
    assert "## Follow-ups" in result_md
    assert "- Closed at " in result_md


def test_close_blocks_when_build_evidence_failed(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert runner.invoke(app, ["init"], catch_exceptions=False).exit_code == 0
    config_path = tmp_path / ".kflow" / "config.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["adapters"]["build"] = {"enabled": True, "command": 'python3 -c "import sys; sys.exit(1)"'}
    config["adapters"]["test"] = {"enabled": True, "command": "python3 -c \"print('3 passed in 0.10s')\""}
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    assert runner.invoke(app, ["task", "new", "--type", "bug", "--name", "Failing build"], catch_exceptions=False).exit_code == 0
    brief_path = tmp_path / ".kflow" / "tasks" / "failing-build" / "TASK_BRIEF.md"
    brief = brief_path.read_text(encoding="utf-8")
    brief = brief.replace("## Goal\n", "## Goal\nFix build issue\n")
    brief = brief.replace("## Acceptance Criteria\n", "## Acceptance Criteria\n- task complete\n")
    brief = brief.replace("## Repro Steps\n", "## Repro Steps\n- run command\n")
    brief_path.write_text(brief, encoding="utf-8")

    build_result = runner.invoke(app, ["build", "--json"], catch_exceptions=False)
    build_payload = json.loads(build_result.stdout)
    assert build_payload["status"] == "blocked"

    close_result = runner.invoke(app, ["task", "close", "--json"], catch_exceptions=False)
    close_payload = json.loads(close_result.stdout)
    assert close_payload["status"] == "blocked"
    assert "build evidence indicates failure" in close_payload["data"]["blockers"]
