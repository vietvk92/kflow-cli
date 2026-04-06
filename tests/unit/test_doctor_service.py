from pathlib import Path
import subprocess

from kflow.services.doctor_service import DoctorService
from kflow.services.execution_service import ExecutionService
from kflow.services.init_service import InitService
from kflow.services.task_service import TaskService


def test_doctor_exposes_policy_source_and_actionable_next_steps(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="bug", name="Permission flow", risk="high", tags=["permissions"])

    result = DoctorService(tmp_path).inspect_task(closeout=True)

    assert result.data["policy_source"] == "embedded"
    assert "repro steps missing" in result.data["blockers"]
    assert "Document repro steps in TASK_BRIEF.md." in result.data["next_steps"]
    assert "manual review required for high-risk task" in result.data["warnings"]


def test_doctor_includes_execution_evidence_summary(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    service = TaskService(tmp_path)
    service.create_task(task_type="feat", name="Execution evidence", risk="medium")

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = config_path.read_text(encoding="utf-8")
    config = config.replace("enabled: false\n    command: null", 'enabled: true\n    command: "python3 -c \\"print(1)\\""', 1)
    config = config.replace("enabled: false\n    command: null", 'enabled: true\n    command: "python3 -c \\"print(1)\\""', 1)
    config_path.write_text(config, encoding="utf-8")

    ExecutionService(tmp_path).run_build()
    ExecutionService(tmp_path).run_test()

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert result.data["evidence"]["build"] == "pass"
    assert result.data["evidence"]["test"] == "pass"


def test_doctor_blocks_high_risk_task_without_test_plan(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="bug", name="High risk task", risk="high")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "high risk task missing test plan" in result.data["blockers"]
    assert "Fill the Test Plan section in CHANGE_PLAN.md for this high-risk task." in result.data["next_steps"]


def test_doctor_reports_diff_summary_and_conflict_marker(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "module.py").write_text("print('hello')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Conflict task", risk="medium")

    brief_path = tmp_path / ".kflow" / "tasks" / "conflict-task" / "TASK_BRIEF.md"
    brief = brief_path.read_text(encoding="utf-8")
    brief = brief.replace("## Goal\n", "## Goal\nShip the change\n")
    brief = brief.replace("## Acceptance Criteria\n", "## Acceptance Criteria\n- <<<<<<< conflict marker\n")
    brief = brief.replace("## Risk Level\n", "## Risk Level\nmedium\n")
    brief_path.write_text(brief, encoding="utf-8")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert result.data["diff_summary"]["available"] is True
    assert "module.py" in result.data["diff_summary"]["code_files"]
    assert "conflicting acceptance criteria marker found" in result.data["blockers"]
    assert "acceptance_conflict_marker" in result.data["stop_conditions"]["triggered"]


def test_doctor_warns_when_code_diff_is_not_reflected_in_change_plan_or_evidence(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("print('changed')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Diff plan task", risk="medium")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "code changes detected but impacted symbols are not documented" in result.data["warnings"]
    assert "code changes detected but build evidence is missing" in result.data["warnings"]
    assert "code changes detected but test evidence is missing" in result.data["warnings"]


def test_doctor_blocks_closeout_when_code_diff_lacks_build_and_test_evidence(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("print('changed')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Diff closeout task", risk="medium")

    result = DoctorService(tmp_path).inspect_task(closeout=True)

    assert "code changes detected but build evidence is missing" in result.data["blockers"]
    assert "code changes detected but test evidence is missing" in result.data["blockers"]


def test_doctor_uses_context_aware_policy_for_refactor_and_high_risk_diff(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "refactor.py").write_text("print('changed')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="refactor", name="Refactor diff task", risk="high")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "behavior change review required for refactor task" in result.data["warnings"]
    assert "test plan required for high-risk code changes" in result.data["requirements"]
    assert "impacted symbols should be documented for code changes" in result.data["warnings"]


def test_doctor_uses_diff_rules_from_workflow_policy(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules:
  refactor:
    forbid_behavior_change: true
risk_rules:
  high:
    require_manual_review: true
tag_rules: {}
project_rules: {}
phase_rules: {}
sprint_rules: {}
diff_rules:
  require_impacted_symbols_for_code_changes: true
  require_test_plan_for_high_risk_code_changes: true
  require_behavior_review_for_refactor_changes: true
  messages:
    warnings: ["diff-aware policy active"]
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    (tmp_path / "refactor.py").write_text("print('changed')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="refactor", name="Diff rules task", risk="high")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "diff-aware policy active" in result.data["warnings"]
    assert "behavior change review required for refactor task" in result.data["warnings"]
    assert "test plan required for high-risk code changes" in result.data["requirements"]
    assert "impacted symbols should be documented for code changes" in result.data["warnings"]


def test_doctor_warns_when_result_changed_files_are_stale_for_diff(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    (tmp_path / "feature.py").write_text("print('changed')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Result drift task", risk="medium")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "result changed files do not reflect current code diff" in result.data["warnings"]


def test_doctor_blocks_when_policy_requires_missing_adapter(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

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
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Adapter policy task", risk="medium")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "required adapter unavailable: mobile_verify" in result.data["blockers"]
    assert "Enable or configure the mobile_verify adapter in .kflow/config.yaml." in result.data["next_steps"]


def test_doctor_uses_project_rules_for_ios_evidence_requirements(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

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
    InitService().initialize(tmp_path, project_type="ios")
    TaskService(tmp_path).create_task(task_type="feat", name="iOS policy task", risk="medium")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "build evidence required for ios project" in result.data["requirements"]
    assert "test evidence required for ios project" in result.data["requirements"]
    assert "mobile verification required for ios project" in result.data["requirements"]


def test_doctor_uses_tag_rules_for_manual_review_and_test_plan(tmp_path: Path, monkeypatch) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

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
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Payments tag task", risk="medium", tags=["payments"])

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "manual review required for tag: payments" in result.data["warnings"]
    assert "payments path requires audit trail review" in result.data["warnings"]
    assert "test plan required for tag: payments" in result.data["requirements"]
    assert "Confirm audit-trail coverage for payments flows." in result.data["next_steps"]


def test_doctor_uses_phase_rules_for_phase_specific_evidence_requirements(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules: {}
phase_rules:
  7:
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
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Phase policy task", risk="medium", phase="7")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "test evidence required for phase 7" in result.data["requirements"]
    assert "mobile verification required for phase 7" in result.data["requirements"]


def test_doctor_blocks_when_phase_rule_requires_ready_docs_and_checklist(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

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
    InitService().initialize(tmp_path)
    TaskService(tmp_path).create_task(task_type="feat", name="Phase readiness task", risk="medium", phase="12")

    result = DoctorService(tmp_path).inspect_task(closeout=False)

    assert "planning docs not ready for phase 12" in result.data["blockers"]
    assert "phase checklist incomplete: 12" in result.data["blockers"]
    assert result.data["phase_state"]["checklist_complete"] is False


def test_doctor_blocks_when_phase_rule_requires_no_failing_linked_tasks(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules: {}
phase_rules:
  13:
    require_no_failing_linked_tasks: true
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    phase_dir = tmp_path / ".planning" / "phases" / "13"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    service = TaskService(tmp_path)
    service.create_task(task_type="feat", name="Failing linked task", risk="medium", phase="13")
    service.create_task(task_type="feat", name="Current gated task", risk="medium", phase="13")

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = config_path.read_text(encoding="utf-8")
    config = config.replace("enabled: false\n    command: null", 'enabled: true\n    command: "python3 -c \\"import sys; sys.exit(1)\\""', 1)
    config_path.write_text(config, encoding="utf-8")
    ExecutionService(tmp_path).run_build(task_id="failing-linked-task")

    result = DoctorService(tmp_path).inspect_task(task_id="current-gated-task", closeout=False)

    assert "linked task execution failing in phase 13" in result.data["blockers"]
    assert result.data["phase_task_state"]["has_failing_linked_tasks"] is True


def test_doctor_blocks_when_phase_rule_requires_no_other_open_tasks(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# workflow

```kflow-policy
requires_mobile_verify_if:
  tags: []
task_rules: {}
risk_rules: {}
project_rules: {}
phase_rules:
  14:
    require_no_other_open_tasks: true
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )
    phase_dir = tmp_path / ".planning" / "phases" / "14"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nscope\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nsteps\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    InitService().initialize(tmp_path)
    service = TaskService(tmp_path)
    service.create_task(task_type="feat", name="Open peer task", risk="medium", phase="14")
    service.create_task(task_type="feat", name="Current gated peer task", risk="medium", phase="14")

    result = DoctorService(tmp_path).inspect_task(task_id="current-gated-peer-task", closeout=False)

    assert "other linked tasks still open in phase 14" in result.data["blockers"]
    assert result.data["phase_task_state"]["other_open_task_count"] == 1
