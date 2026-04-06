"""Task service."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import re

from kflow.core.state_machine import can_transition
from kflow.config.loader import load_config
from kflow.core.exceptions import KFlowValidationError
from kflow.models.results import Message, OperationResult
from kflow.models.task import TaskRecord
from kflow.policy.evaluator import evaluate_task_policy
from kflow.policy.loader import load_policy
from kflow.services.diff_service import DiffService
from kflow.services.evidence_service import EvidenceService
from kflow.services.env_service import EnvironmentService
from kflow.services.planning_service import inspect_phase_state
from kflow.templates.renderer import render_task_templates
from kflow.utils.files import ensure_directory, write_text
from kflow.utils.markdown import get_section_content, parse_bullet_lines
from kflow.utils.time import utc_now_iso
from kflow.utils.yaml_io import dump_yaml, load_yaml


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "task"


class TaskService:
    """Create and inspect task state."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.config = load_config(cwd)
        self.repo_root = self.config.repo_root_path
        self.state_dir = self.repo_root / ".kflow" / "state"
        self.tasks_state_dir = self.state_dir / "tasks"
        self.tasks_dir = self.repo_root / self.config.paths.tasks_dir

    def create_task(
        self,
        *,
        task_type: str,
        name: str,
        risk: str,
        phase: str | None = None,
        tags: list[str] | None = None,
        task_dir_override: str | None = None,
    ) -> OperationResult:
        tags = tags or []
        task_id = _slugify(name)
        task_dir = self.repo_root / task_dir_override if task_dir_override else self.tasks_dir / task_id
        ensure_directory(task_dir)
        ensure_directory(task_dir / "artifacts")
        ensure_directory(self.tasks_state_dir)
        now = utc_now_iso()
        task = TaskRecord(
            id=task_id,
            name=name,
            type=task_type,
            risk_level=risk,
            status="created",
            created_at=now,
            updated_at=now,
            tags=tags,
            task_dir=str(task_dir),
            phase_ref=phase,
        )
        for filename, content in render_task_templates(task_type, risk).items():
            write_text(task_dir / filename, content, overwrite=False)
        write_text(self.tasks_state_dir / f"{task_id}.yaml", dump_yaml(task.model_dump(mode="python")), overwrite=True)
        write_text(self.state_dir / "current_task.yaml", dump_yaml({"task_id": task_id}), overwrite=True)
        return OperationResult(
            command="task new",
            status="ok",
            messages=[
                Message(severity="pass", text=f"Task created: {task_id}"),
                Message(severity="pass", text="Templates generated"),
                Message(severity="info", text="Next: fill TASK_BRIEF.md and run `kflow task doctor`."),
            ],
            data={"task_id": task_id, "task_dir": str(task_dir)},
        )

    def get_task(self, task_id: str | None = None) -> TaskRecord:
        target_id = task_id or self.get_current_task_id()
        payload = load_yaml(self.tasks_state_dir / f"{target_id}.yaml")
        return TaskRecord.model_validate(payload)

    def list_tasks(self) -> list[TaskRecord]:
        """Return all persisted tasks sorted by id."""
        if not self.tasks_state_dir.exists():
            return []
        tasks: list[TaskRecord] = []
        for path in sorted(self.tasks_state_dir.glob("*.yaml")):
            payload = load_yaml(path)
            if payload:
                tasks.append(TaskRecord.model_validate(payload))
        return tasks

    def summarize_tasks_for_phase(self, phase_ref: str) -> dict[str, object]:
        """Summarize persisted tasks linked to a phase reference."""
        tasks = [task for task in self.list_tasks() if task.phase_ref == phase_ref]
        status_counts = dict(Counter(task.status for task in tasks))
        evidence_totals = {
            "build": {"pass": 0, "fail": 0, "missing": 0},
            "test": {"pass": 0, "fail": 0, "missing": 0},
            "mobile": {"pass": 0, "fail": 0, "missing": 0, "not_required": 0},
        }
        current_task_id: str | None = None
        try:
            current_task_id = self.get_current_task_id()
        except Exception:
            current_task_id = None
        loaded_policy = load_policy(self.repo_root, self.config.policy.file)
        task_entries = []
        for task in tasks:
            policy_eval = evaluate_task_policy(task, loaded_policy.policy)
            evidence = EvidenceService(task).collect(mobile_required="mobile verification required" in policy_eval.requirements)
            evidence_totals["build"][evidence.build] += 1
            evidence_totals["test"][evidence.test] += 1
            evidence_totals["mobile"][evidence.mobile] += 1
            task_entries.append(
                {
                    "id": task.id,
                    "name": task.name,
                    "status": task.status,
                    "type": task.type,
                    "risk_level": task.risk_level,
                    "is_current": task.id == current_task_id,
                    "evidence": evidence.model_dump(mode="json"),
                }
            )
        return {
            "phase": phase_ref,
            "task_count": len(tasks),
            "status_counts": status_counts,
            "evidence_totals": evidence_totals,
            "current_task_id": current_task_id,
            "tasks": task_entries,
        }

    def get_current_task_id(self) -> str:
        payload = load_yaml(self.state_dir / "current_task.yaml")
        return str(payload["task_id"])

    def save_task(self, task: TaskRecord) -> None:
        task.updated_at = utc_now_iso()
        write_text(
            self.tasks_state_dir / f"{task.id}.yaml",
            dump_yaml(task.model_dump(mode="python")),
            overwrite=True,
        )

    def task_artifacts_dir(self, task: TaskRecord) -> Path:
        return Path(task.task_dir) / "artifacts"

    def update_status(self, task: TaskRecord, target_status: str) -> TaskRecord:
        if task.status != target_status and not can_transition(task.status, target_status):
            raise KFlowValidationError([f"Invalid task state transition: {task.status} -> {target_status}"])
        task.status = target_status
        self.save_task(task)
        return task

    def status(self, task_id: str | None = None) -> OperationResult:
        task = self.get_task(task_id)
        task_dir = Path(task.task_dir)
        loaded_policy = load_policy(self.repo_root, self.config.policy.file)
        diff_summary = DiffService(self.repo_root).summarize()
        env = EnvironmentService().detect(self.cwd, self.config).environment
        phase_summary = self.summarize_tasks_for_phase(task.phase_ref) if task.phase_ref else None
        phase_state = (
            inspect_phase_state(self.repo_root / self.config.paths.planning_dir, task.phase_ref)
            if task.phase_ref
            else {}
        )
        phase_task_state = phase_task_state_for_policy(phase_summary, current_task_id=task.id)
        change_plan_path = task_dir / "CHANGE_PLAN.md"
        change_plan_content = change_plan_path.read_text(encoding="utf-8") if change_plan_path.exists() else ""
        initial_policy_eval = evaluate_task_policy(
            task,
            loaded_policy.policy,
            context={
                "diff_summary": diff_summary,
                "change_plan_has_test_plan": bool(get_section_content(change_plan_content, "Test Plan").strip()),
                "impacted_symbols_count": len(parse_bullet_lines(get_section_content(change_plan_content, "Impacted Symbols"))),
                "env_statuses": {
                    "git": env.git.status,
                    "workflow_file": env.workflow_file.status,
                    "config_file": env.config_file.status,
                    "xcodebuild": env.xcodebuild.status,
                    "gitnexus": env.gitnexus.status,
                    "gsd": env.gsd.status,
                    "build": env.build.status,
                    "test": env.test.status,
                    "planning_dir": env.planning_dir.status,
                    "mobile_verify": env.mobile_verify.status,
                },
                "project_type": env.project_type,
                "phase_ref": task.phase_ref,
                "phase_state": phase_state,
                "phase_task_state": phase_task_state,
            },
        )
        evidence = EvidenceService(task).collect(mobile_required=_is_mobile_required(initial_policy_eval.requirements))
        policy_eval = evaluate_task_policy(
            task,
            loaded_policy.policy,
            context={
                "diff_summary": diff_summary,
                "change_plan_has_test_plan": bool(get_section_content(change_plan_content, "Test Plan").strip()),
                "impacted_symbols_count": len(parse_bullet_lines(get_section_content(change_plan_content, "Impacted Symbols"))),
                "env_statuses": {
                    "git": env.git.status,
                    "workflow_file": env.workflow_file.status,
                    "config_file": env.config_file.status,
                    "xcodebuild": env.xcodebuild.status,
                    "gitnexus": env.gitnexus.status,
                    "gsd": env.gsd.status,
                    "build": env.build.status,
                    "test": env.test.status,
                    "planning_dir": env.planning_dir.status,
                    "mobile_verify": env.mobile_verify.status,
                },
                "project_type": env.project_type,
                "phase_ref": task.phase_ref,
                "phase_state": phase_state,
                "phase_task_state": phase_task_state,
                "evidence_statuses": {
                    "build": evidence.build,
                    "test": evidence.test,
                    "mobile": evidence.mobile,
                },
            },
        )
        requirements = list(policy_eval.requirements)
        warnings = list(policy_eval.warnings)
        blockers = list(policy_eval.blockers)
        is_current_task = False
        try:
            is_current_task = self.get_current_task_id() == task.id
        except Exception:
            is_current_task = False
        missing = [
            name
            for name in ("TASK_BRIEF.md", "CHANGE_PLAN.md", "VERIFY_CHECKLIST.md", "RESULT.md")
            if not (task_dir / name).exists()
        ]
        messages = [
            Message(severity="info", text=f"Task: {task.id}"),
            Message(severity="info", text=f"Status: {task.status}"),
            Message(severity="info", text=f"Type: {task.type}"),
            Message(severity="info", text=f"Risk: {task.risk_level}"),
        ]
        if task.phase_ref:
            messages.append(Message(severity="info", text=f"Phase: {task.phase_ref}"))
        if is_current_task:
            messages.append(Message(severity="info", text="Current task pointer is set to this task."))
        if missing:
            messages.append(Message(severity="warning", text=f"Missing artifacts: {', '.join(missing)}"))
        else:
            messages.append(Message(severity="pass", text="All required task artifacts exist."))
        messages.append(
            Message(
                severity="info",
                text=f"Evidence: build={evidence.build}, test={evidence.test}, mobile={evidence.mobile}",
            )
        )
        if evidence.build == "missing":
            warnings.append("build evidence missing")
        if evidence.test == "missing":
            warnings.append("test evidence missing")
        if "mobile verification required" in requirements and evidence.mobile == "missing":
            warnings.append("mobile verification evidence missing")
        for requirement in requirements:
            messages.append(Message(severity="required", text=requirement))
        for warning in warnings:
            messages.append(Message(severity="warning", text=warning))
        for blocker in blockers:
            messages.append(Message(severity="blocked", text=blocker))
        return OperationResult(
            command="task status",
            status="blocked" if blockers else ("warning" if missing or warnings or requirements else "ok"),
            messages=messages,
            data={
                "scope": {
                    "kind": "task",
                    "task_id": task.id,
                    "phase": task.phase_ref,
                },
                "summary": {
                    "status": task.status,
                    "missing_artifacts": len(missing),
                    "is_current_task": is_current_task,
                    "evidence": evidence.model_dump(mode="json"),
                    "diff_summary": diff_summary,
                    "requirements": requirements,
                    "warnings": warnings,
                    "blockers": blockers,
                    "gates_open": len(requirements) + len(warnings) + len(blockers),
                },
                "task": task.model_dump(mode="json"),
                "missing_artifacts": missing,
                "is_current_task": is_current_task,
                "evidence": evidence.model_dump(mode="json"),
                "diff_summary": diff_summary,
                "requirements": requirements,
                "warnings": warnings,
                "blockers": blockers,
                "phase_summary": phase_summary,
                "phase_state": phase_state,
                "phase_task_state": phase_task_state,
            },
        )


def _is_mobile_required(requirements: list[str]) -> bool:
    """Return true when any requirement string demands mobile verification."""
    return any("mobile verification required" in requirement for requirement in requirements)


def phase_task_state_for_policy(phase_summary: dict[str, object] | None, *, current_task_id: str) -> dict[str, object]:
    """Project linked-task health into a small policy-evaluator context."""
    if not phase_summary:
        return {}
    tasks = phase_summary.get("tasks", []) or []
    other_open_task_count = sum(
        1
        for item in tasks
        if item.get("id") != current_task_id and item.get("status") != "done"
    )
    evidence_totals = phase_summary.get("evidence_totals", {}) or {}
    has_failing_linked_tasks = any(
        int(((evidence_totals.get(name, {}) or {}).get("fail", 0) or 0)) > 0
        for name in ("build", "test", "mobile")
    )
    return {
        "task_count": int(phase_summary.get("task_count", 0) or 0),
        "other_open_task_count": other_open_task_count,
        "has_failing_linked_tasks": has_failing_linked_tasks,
    }
