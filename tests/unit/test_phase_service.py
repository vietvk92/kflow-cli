from pathlib import Path
from datetime import datetime

from kflow.services.init_service import InitService
from kflow.services.phase_service import PhaseService
from kflow.services.task_service import TaskService
from kflow.models.task import TaskRecord


def test_phase_check_summary_counts_incomplete_items(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_dir = tmp_path / ".planning" / "phases" / "5"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nPhase scope is captured\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nImplement and verify the flow\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] mapped\n- [ ] tested\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    result = PhaseService(tmp_path).check("5")

    assert result.status == "warning"
    assert result.data["checklist_summary"]["total"] == 2
    assert result.data["checklist_summary"]["complete"] == 1
    assert result.data["checklist_summary"]["incomplete"] == 1


def test_phase_check_blocks_on_empty_context_and_plan_docs(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_dir = tmp_path / ".planning" / "phases" / "6"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] mapped\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    result = PhaseService(tmp_path).check("6")

    assert result.status == "blocked"
    assert "CONTEXT.md has no meaningful content" in result.data["blockers"]
    assert "PLAN.md has no meaningful content" in result.data["blockers"]
    assert result.data["documents"]["context"]["has_content"] is False
    assert result.data["documents"]["plan"]["has_content"] is False


def test_phase_check_warns_when_checklist_has_no_items(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_dir = tmp_path / ".planning" / "phases" / "7"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nScope is defined\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nImplement the flow\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("# Ready\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    result = PhaseService(tmp_path).check("7")

    assert result.status == "warning"
    assert "READY_CHECKLIST.md has no checklist items" in result.data["warnings"]
    assert result.data["documents"]["checklist"]["has_items"] is False


def test_phase_check_reports_linked_phase_tasks(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_dir = tmp_path / ".planning" / "phases" / "8"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nPhase scope is captured\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nImplement the flow\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    task_service = TaskService(tmp_path)
    task_service.create_task(task_type="feat", name="Phase task one", risk="medium", phase="8")
    task_service.create_task(task_type="bug", name="Phase task two", risk="medium", phase="8")

    result = PhaseService(tmp_path).check("8")

    assert result.status == "warning"
    assert result.data["linked_tasks"]["task_count"] == 2
    assert result.data["linked_tasks"]["status_counts"]["created"] == 2
    assert result.data["linked_tasks"]["evidence_totals"]["build"]["missing"] == 2
    assert "phase has open tasks" in " ".join(result.data["warnings"])


def test_phase_check_warns_on_failing_linked_task_evidence(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    phase_dir = tmp_path / ".planning" / "phases" / "9"
    phase_dir.mkdir(parents=True)
    (phase_dir / "CONTEXT.md").write_text("# Context\nPhase scope is captured\n", encoding="utf-8")
    (phase_dir / "PLAN.md").write_text("# Plan\nImplement the flow\n", encoding="utf-8")
    (phase_dir / "READY_CHECKLIST.md").write_text("- [x] ready\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    task_service = TaskService(tmp_path)
    task_service.create_task(task_type="feat", name="Failing phase task", risk="medium", phase="9")

    config_path = tmp_path / ".kflow" / "config.yaml"
    config = config_path.read_text(encoding="utf-8")
    config = config.replace("enabled: false\n    command: null", 'enabled: true\n    command: "python3 -c \\"import sys; sys.exit(1)\\""', 1)
    config_path.write_text(config, encoding="utf-8")
    from kflow.services.execution_service import ExecutionService

    ExecutionService(tmp_path).run_build()

    result = PhaseService(tmp_path).check("9")

    assert "phase has failing task execution evidence" in result.data["warnings"]
    assert result.data["linked_tasks"]["evidence_totals"]["build"]["fail"] == 1


def test_phase_check_blocks_when_phase_missing(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    result = PhaseService(tmp_path).check("42")

    assert result.status == "blocked"
    assert result.data["blockers"]


def test_phase_check_detects_legacy_phase_docs_by_filename(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text("# workflow\n", encoding="utf-8")
    legacy_phase_dir = tmp_path / ".planning" / "01-feature-name"
    legacy_phase_dir.mkdir(parents=True)
    (legacy_phase_dir / "05-CONTEXT.md").write_text("# Context\nLegacy context content\n", encoding="utf-8")
    (legacy_phase_dir / "01-01-PLAN.md").write_text("# Plan\nLegacy phase plan\n", encoding="utf-8")
    (legacy_phase_dir / "01-01-SUMMARY.md").write_text("# Summary\nLegacy summary\n", encoding="utf-8")
    (legacy_phase_dir / "READY_CHECKLIST.md").write_text("- [x] scoped\n", encoding="utf-8")
    InitService().initialize(tmp_path)

    result = PhaseService(tmp_path).check("1")

    assert result.status == "ok"
    assert result.data["phase"] == "1"
    assert result.data["documents"]["context"]["exists"] is True
    assert result.data["documents"]["plan"]["exists"] is True


def test_task_record_accepts_datetime_timestamps() -> None:
    task = TaskRecord.model_validate(
        {
            "id": "demo",
            "name": "Demo",
            "type": "feat",
            "status": "created",
            "risk_level": "medium",
            "created_at": datetime(2026, 4, 6, 10, 0, 0),
            "updated_at": datetime(2026, 4, 6, 11, 0, 0),
            "tags": [],
            "task_dir": "/tmp/demo",
        }
    )

    assert isinstance(task.created_at, str)
    assert task.created_at.startswith("2026-04-06T10:00:00")
