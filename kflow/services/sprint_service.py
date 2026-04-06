"""Sprint status services."""

from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Any

from kflow.config.loader import load_config
from kflow.models.results import Message, OperationResult
from kflow.models.sprint import SprintHistoryEntry, SprintRecord
from kflow.policy.evaluator import evaluate_sprint_policy
from kflow.policy.loader import load_policy
from kflow.services.phase_service import _meaningful_markdown_text, _parse_checklist_summary
from kflow.services.planning_service import discover_phase_records, inspect_phase_state
from kflow.services.task_service import TaskService
from kflow.utils.files import ensure_directory, write_text
from kflow.utils.shell import run
from kflow.utils.time import utc_now_iso
from kflow.utils.yaml_io import dump_yaml, load_yaml


class SprintService:
    """Read sprint-level status from planning artifacts when available."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.config = load_config(cwd)
        self.repo_root = self.config.repo_root_path
        self.planning_dir = self.repo_root / self.config.paths.planning_dir
        self.logs_dir = self.repo_root / ".kflow" / "logs"
        self.state_dir = self.repo_root / ".kflow" / "state"
        self.current_sprint_path = self.state_dir / "current_sprint.yaml"
        self.sprints_history_path = self.state_dir / "sprints.yaml"
        self.loaded_policy = load_policy(cwd)
        self.task_service = TaskService(cwd)

    # ------------------------------------------------------------------
    # Sprint state helpers
    # ------------------------------------------------------------------

    def _load_current_sprint(self) -> SprintRecord | None:
        """Load current_sprint.yaml if it exists and sprint is active."""
        if not self.current_sprint_path.exists():
            return None
        try:
            data = load_yaml(self.current_sprint_path)
            record = SprintRecord(**data)
            return record if record.status == "active" else None
        except Exception:
            return None

    def _write_current_sprint(self, record: SprintRecord) -> None:
        ensure_directory(self.state_dir)
        write_text(self.current_sprint_path, dump_yaml(record.model_dump()), overwrite=True)

    def _load_sprint_history(self) -> list[SprintHistoryEntry]:
        if not self.sprints_history_path.exists():
            return []
        try:
            raw = load_yaml(self.sprints_history_path)
            entries = raw.get("sprints", []) if isinstance(raw, dict) else raw
            if not isinstance(entries, list):
                return []
            return [SprintHistoryEntry(**e) for e in entries]
        except Exception:
            return []

    def _append_sprint_history(self, entry: SprintHistoryEntry) -> None:
        history = self._load_sprint_history()
        history.append(entry)
        ensure_directory(self.state_dir)
        payload = {"sprints": [e.model_dump() for e in history]}
        write_text(self.sprints_history_path, dump_yaml(payload), overwrite=True)

    @staticmethod
    def _sprint_id(name: str) -> str:
        """Convert a human name like 'Sprint 2' to 'sprint-2'."""
        return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    def status(self) -> OperationResult:
        """Return sprint-related status in normal or degraded mode."""
        messages: list[Message] = [Message(severity="info", text="Sprint Status")]
        warnings: list[str] = []
        summary_path = self.repo_root / ".kflow" / "artifacts" / "sprint-summary.json"

        # Sprint state section
        current_sprint = self._load_current_sprint()
        sprint_history = self._load_sprint_history()
        if current_sprint:
            messages.append(Message(severity="info", text=f"Active sprint: {current_sprint.name}"))
        else:
            messages.append(Message(severity="warning", text="No active sprint. Run `kflow sprint start <name>` to begin one."))
        if sprint_history:
            completed_names = ", ".join(e.name for e in sprint_history if e.status == "completed")
            if completed_names:
                messages.append(Message(severity="info", text=f"Completed sprints: {completed_names}"))


        if not self.planning_dir.exists():
            warnings.append("Planning directory missing. Sprint status is running in degraded mode.")
            messages.append(Message(severity="warning", text=warnings[0]))
            messages.append(Message(severity="info", text=f"Create `{self.planning_dir}` or configure a planning path to enable planning-aware sprint status."))
            return OperationResult(
                command="sprint status",
                status="warning",
                messages=messages,
                data={
                    "planning_dir": str(self.planning_dir),
                    "warnings": warnings,
                    "phases": [],
                    "summary_artifact": None,
                },
            )

        phase_records = discover_phase_records(self.planning_dir)
        phase_entries = []
        current_phase: str | None = None
        ready_count = 0
        readiness_totals = {"ready": 0, "not_ready": 0, "unknown": 0}
        sprint_task_total = 0
        sprint_open_task_total = 0
        sprint_evidence_totals = {
            "build": {"pass": 0, "fail": 0, "missing": 0},
            "test": {"pass": 0, "fail": 0, "missing": 0},
            "mobile": {"pass": 0, "fail": 0, "missing": 0, "not_required": 0},
        }
        for record in phase_records:
            phase_entry = self._build_phase_entry(record)
            if phase_entry["readiness"] == "ready":
                ready_count += 1
            elif current_phase is None:
                current_phase = str(phase_entry["phase"])
            readiness_totals[str(phase_entry["readiness"])] += 1
            task_count = int(phase_entry["linked_tasks"]["task_count"])
            sprint_task_total += task_count
            sprint_open_task_total += sum(
                1
                for item in phase_entry["linked_tasks"]["tasks"]
                if item["status"] != "done"
            )
            for area, counts in phase_entry["linked_tasks"]["evidence_totals"].items():
                for key, value in counts.items():
                    sprint_evidence_totals[area][key] += value
            phase_entries.append(phase_entry)
        if current_phase is None and phase_entries:
            current_phase = phase_entries[-1]["phase"]

        messages.append(Message(severity="pass", text=f"Planning directory found: {self.planning_dir}"))
        if phase_entries:
            messages.append(Message(severity="info", text=f"Detected phases: {', '.join(item['phase'] for item in phase_entries)}"))
            if current_phase:
                messages.append(Message(severity="info", text=f"Current phase: {current_phase}"))
            messages.append(Message(severity="info", text=f"Ready phases: {ready_count}/{len(phase_entries)}"))
            messages.append(Message(severity="info", text=f"Linked tasks: {sprint_task_total} total, {sprint_open_task_total} open"))
            messages.append(
                Message(
                    severity="info",
                    text=(
                        "Task evidence: "
                        f"build(pass={sprint_evidence_totals['build']['pass']}, fail={sprint_evidence_totals['build']['fail']}, missing={sprint_evidence_totals['build']['missing']}), "
                        f"test(pass={sprint_evidence_totals['test']['pass']}, fail={sprint_evidence_totals['test']['fail']}, missing={sprint_evidence_totals['test']['missing']}), "
                        f"mobile(pass={sprint_evidence_totals['mobile']['pass']}, fail={sprint_evidence_totals['mobile']['fail']}, missing={sprint_evidence_totals['mobile']['missing']}, not_required={sprint_evidence_totals['mobile']['not_required']})"
                    ),
                )
            )
            messages.append(
                Message(
                    severity="info",
                    text=f"Readiness breakdown: ready={readiness_totals['ready']}, not_ready={readiness_totals['not_ready']}, unknown={readiness_totals['unknown']}",
                )
            )
        else:
            warnings.append("No phase directories detected in planning directory.")
            messages.append(Message(severity="warning", text=warnings[0]))

        ensure_directory(summary_path.parent)
        summary_payload: dict[str, Any] = {
            "planning_dir": str(self.planning_dir),
            "current_phase": current_phase,
            "ready_phases": ready_count,
            "phase_count": len(phase_entries),
            "readiness_totals": readiness_totals,
            "task_totals": {"total": sprint_task_total, "open": sprint_open_task_total},
            "evidence_totals": sprint_evidence_totals,
            "phases": phase_entries,
            "warnings": warnings,
            "active_sprint": current_sprint.model_dump() if current_sprint else None,
            "completed_sprints": [e.model_dump() for e in sprint_history if e.status == "completed"],
        }
        write_text(summary_path, json.dumps(summary_payload, indent=2) + "\n", overwrite=True)

        return OperationResult(
            command="sprint status",
            status="warning" if warnings else "ok",
            messages=messages,
            data={
                "scope": {
                    "kind": "sprint",
                    "planning_dir": str(self.planning_dir),
                },
                "summary": {
                    "current_phase": current_phase,
                    "phase_count": len(phase_entries),
                    "ready_phases": ready_count,
                    "task_totals": {"total": sprint_task_total, "open": sprint_open_task_total},
                    "evidence_totals": sprint_evidence_totals,
                },
                "active_sprint": current_sprint.model_dump() if current_sprint else None,
                "completed_sprints": [e.model_dump() for e in sprint_history if e.status == "completed"],
                "planning_dir": str(self.planning_dir),
                "warnings": warnings,
                "phases": phase_entries,
                "current_phase": current_phase,
                "ready_phases": ready_count,
                "readiness_totals": readiness_totals,
                "task_totals": {"total": sprint_task_total, "open": sprint_open_task_total},
                "evidence_totals": sprint_evidence_totals,
                "summary_artifact": str(summary_path),
            },
        )

    def doctor(self) -> OperationResult:
        """Evaluate sprint-wide blockers and warnings for CI or operational checks."""
        status_result = self.status()
        data = status_result.data
        phases = data.get("phases", []) or []
        blockers: list[str] = []
        warnings: list[str] = []
        messages: list[Message] = [Message(severity="info", text="Sprint Doctor")]

        if not phases:
            warnings.append("no phases discovered for sprint doctor")
        if any(int(((phase.get("linked_tasks", {}).get("evidence_totals", {}).get("build", {}) or {}).get("fail", 0) or 0)) > 0 for phase in phases):
            blockers.append("sprint has failing build evidence in linked tasks")
        if any(int(((phase.get("linked_tasks", {}).get("evidence_totals", {}).get("test", {}) or {}).get("fail", 0) or 0)) > 0 for phase in phases):
            blockers.append("sprint has failing test evidence in linked tasks")
        if any(int(((phase.get("linked_tasks", {}).get("evidence_totals", {}).get("mobile", {}) or {}).get("fail", 0) or 0)) > 0 for phase in phases):
            blockers.append("sprint has failing mobile verification evidence in linked tasks")

        current_phase = data.get("current_phase")
        current_phase_entry = next((phase for phase in phases if phase.get("phase") == current_phase), None)
        if current_phase_entry and current_phase_entry.get("readiness") != "ready":
            warnings.append(f"current phase not ready: {current_phase}")
        if int((data.get("task_totals", {}) or {}).get("open", 0) or 0) > 0:
            warnings.append("sprint has open linked tasks")

        policy_eval = evaluate_sprint_policy(
            self.loaded_policy.policy,
            summary={
                "current_phase": current_phase,
                "task_totals": data.get("task_totals", {}),
                "evidence_totals": data.get("evidence_totals", {}),
            },
            context={
                "current_phase_entry": current_phase_entry or {},
                "planning_dir": str(self.planning_dir),
            },
        )
        for warning in policy_eval.warnings:
            if warning not in warnings:
                warnings.append(warning)
        for blocker in policy_eval.blockers:
            if blocker not in blockers:
                blockers.append(blocker)

        next_steps: list[str] = []
        if "sprint has failing build evidence in linked tasks" in blockers or "sprint has failing test evidence in linked tasks" in blockers or "sprint has failing mobile verification evidence in linked tasks" in blockers:
            next_steps.append("Resolve failing linked-task execution evidence before considering the sprint healthy.")
        if current_phase_entry and current_phase_entry.get("readiness") != "ready":
            next_steps.append(f"Bring phase {current_phase} to ready status under `{self.planning_dir}` before advancing sprint-level checks.")
        if "sprint has open linked tasks" in warnings:
            next_steps.append("Close, defer, or explicitly accept remaining linked sprint tasks.")
        for next_step in policy_eval.next_steps:
            if next_step not in next_steps:
                next_steps.append(next_step)

        for warning in warnings:
            messages.append(Message(severity="warning", text=warning))
        for blocker in blockers:
            messages.append(Message(severity="blocked", text=blocker))
        if not warnings and not blockers:
            messages.append(Message(severity="pass", text="Sprint-wide checks passed."))

        return OperationResult(
            command="doctor sprint",
            status="blocked" if blockers else ("warning" if warnings else "ok"),
            messages=messages,
            data={
                "scope": {
                    "kind": "sprint",
                    "planning_dir": str(self.planning_dir),
                },
                "summary": {
                    **(data.get("summary", {}) or {}),
                    "warning_count": len(warnings),
                    "blocker_count": len(blockers),
                },
                "policy_source": self.loaded_policy.source,
                "requirements": policy_eval.requirements,
                "warnings": warnings,
                "blockers": blockers,
                "next_steps": next_steps,
                "sprint_status": status_result.model_dump(mode="json"),
            },
        )

    def start(self, sprint_name: str) -> OperationResult:
        """Start a sprint via repo-local script when available."""
        script = self.repo_root / ".tools" / "start-sprint.sh"
        if not script.exists():
            sprint_record = SprintRecord(
                id=self._sprint_id(sprint_name),
                name=sprint_name,
                status="active",
                started_at=utc_now_iso(),
            )
            self._write_current_sprint(sprint_record)
            return OperationResult(
                command="sprint start",
                status="warning",
                messages=[
                    Message(severity="info", text=f"Active sprint set: {sprint_name}"),
                    Message(severity="warning", text="Sprint start script not found."),
                    Message(severity="info", text="Add `./.tools/start-sprint.sh` to enable sprint bootstrap automation."),
                ],
                data={
                    "sprint_name": sprint_name,
                    "script": str(script),
                    "started": False,
                    "active_sprint": sprint_record.model_dump(),
                },
            )

        phase_records_before = discover_phase_records(self.planning_dir)
        result = run([str(script), sprint_name], cwd=self.repo_root)
        ensure_directory(self.logs_dir)
        log_path = self.logs_dir / "sprint-start.log"
        log_sections = [
            f"command: {script} {sprint_name}",
            f"returncode: {result.returncode}",
            "",
            "[stdout]",
            result.stdout,
            "",
            "[stderr]",
            result.stderr,
            "",
        ]

        gsd_attempted = False
        gsd_ok = False
        gsd_command: str | None = None
        gsd_returncode: int | None = None
        gsd_stderr = ""

        planning_present = self.planning_dir.exists()
        phase_records_after = discover_phase_records(self.planning_dir)
        outputs_verified = planning_present and bool(phase_records_after)

        if result.ok and not outputs_verified:
            gsd_command = self._resolve_gsd_new_milestone()
            if gsd_command:
                gsd_attempted = True
                gsd_result = run([gsd_command, sprint_name], cwd=self.repo_root)
                gsd_ok = gsd_result.ok
                gsd_returncode = gsd_result.returncode
                gsd_stderr = gsd_result.stderr
                log_sections.extend(
                    [
                        f"fallback_command: {gsd_command} {sprint_name}",
                        f"fallback_returncode: {gsd_result.returncode}",
                        "",
                        "[fallback stdout]",
                        gsd_result.stdout,
                        "",
                        "[fallback stderr]",
                        gsd_result.stderr,
                        "",
                    ]
                )
                planning_present = self.planning_dir.exists()
                phase_records_after = discover_phase_records(self.planning_dir)
                outputs_verified = planning_present and bool(phase_records_after)

        write_text(log_path, "\n".join(log_sections), overwrite=True)

        sprint_record: SprintRecord | None = None
        if result.ok:
            sprint_record = SprintRecord(
                id=self._sprint_id(sprint_name),
                name=sprint_name,
                status="active",
                started_at=utc_now_iso(),
            )
            self._write_current_sprint(sprint_record)

        warnings: list[str] = []
        messages = [Message(severity="pass" if result.ok else "blocked", text=f"Sprint start {'succeeded' if result.ok else 'failed'}")]
        if sprint_record:
            messages.append(Message(severity="info", text=f"Active sprint set: {sprint_record.name}"))
        if result.ok and outputs_verified:
            messages.append(Message(severity="pass", text=f"Planning outputs verified in {self.planning_dir}"))
        elif result.ok:
            warnings.append("Sprint bootstrap completed but no planning outputs were detected.")
            messages.append(Message(severity="warning", text=warnings[-1]))
        messages.append(Message(severity="info", text=f"Log: {log_path}"))
        if planning_present:
            messages.append(Message(severity="info", text=f"Planning directory present: {self.planning_dir}"))
        if phase_records_after:
            messages.append(
                Message(
                    severity="info",
                    text=f"Detected phases after start: {', '.join(str(item['phase']) for item in phase_records_after)}",
                )
            )
        if gsd_attempted:
            if gsd_ok:
                messages.append(Message(severity="pass", text=f"GSD milestone bootstrap succeeded via `{Path(gsd_command).name}`"))
            else:
                warnings.append("GSD milestone bootstrap failed after sprint script completed.")
                messages.append(Message(severity="warning", text=warnings[-1]))
        if result.stderr:
            messages.append(Message(severity="warning" if result.ok else "blocked", text=result.stderr))
        if gsd_stderr and (not result.stderr or gsd_stderr != result.stderr):
            messages.append(Message(severity="warning", text=gsd_stderr))

        status = "blocked"
        if result.ok:
            status = "ok" if outputs_verified and (not gsd_attempted or gsd_ok) else "warning"

        return OperationResult(
            command="sprint start",
            status=status,
            messages=messages,
            data={
                "sprint_name": sprint_name,
                "script": str(script),
                "started": result.ok,
                "log": str(log_path),
                "returncode": result.returncode,
                "planning_dir": str(self.planning_dir),
                "planning_dir_present": planning_present,
                "phases_before": [str(item["phase"]) for item in phase_records_before],
                "phases_after": [str(item["phase"]) for item in phase_records_after],
                "outputs_verified": outputs_verified,
                "warnings": warnings,
                "active_sprint": sprint_record.model_dump() if sprint_record else None,
                "gsd": {
                    "attempted": gsd_attempted,
                    "command": gsd_command,
                    "ok": gsd_ok if gsd_attempted else None,
                    "returncode": gsd_returncode,
                },
            },
        )

    def close(self) -> OperationResult:
        """Mark the active sprint as completed and archive it to sprints.yaml."""
        current = self._load_current_sprint()
        if not current:
            return OperationResult(
                command="sprint close",
                status="warning",
                messages=[Message(severity="warning", text="No active sprint to close.")],
                data={"closed": False},
            )

        closed_at = utc_now_iso()
        entry = SprintHistoryEntry(
            id=current.id,
            name=current.name,
            status="completed",
            started_at=current.started_at,
            closed_at=closed_at,
        )
        self._append_sprint_history(entry)

        # Remove current_sprint.yaml (no longer active)
        if self.current_sprint_path.exists():
            self.current_sprint_path.unlink()

        return OperationResult(
            command="sprint close",
            status="ok",
            messages=[
                Message(severity="pass", text=f"Sprint '{current.name}' closed."),
                Message(severity="info", text=f"Archived to: {self.sprints_history_path}"),
            ],
            data={
                "closed": True,
                "sprint": entry.model_dump(),
            },
        )

    def _resolve_gsd_new_milestone(self) -> str | None:
        """Resolve an optional GSD bootstrap command."""
        if not self.config.adapters.gsd.enabled:
            return None
        repo_local = self.repo_root / ".tools" / "gsd-new-milestone"
        if repo_local.exists():
            return str(repo_local)
        return shutil.which("gsd-new-milestone")

    def _build_phase_entry(self, record: dict[str, object]) -> dict[str, object]:
        """Build a structured readiness snapshot for one phase directory."""
        phase_ref = str(record["phase"])
        path = Path(record["phase_dir"])
        state = inspect_phase_state(self.planning_dir, phase_ref)
        detected_documents = state.get("documents", {})
        context_path = Path(str(detected_documents["context"])) if detected_documents.get("context") else path / "CONTEXT.md"
        plan_path = Path(str(detected_documents["plan"])) if detected_documents.get("plan") else path / "PLAN.md"
        checklist_path = Path(str(detected_documents["checklist"])) if detected_documents.get("checklist") else path / "READY_CHECKLIST.md"

        context_has_content = context_path.exists() and bool(_meaningful_markdown_text(context_path.read_text(encoding="utf-8")))
        plan_has_content = plan_path.exists() and bool(_meaningful_markdown_text(plan_path.read_text(encoding="utf-8")))
        if checklist_path.exists():
            checklist_summary = _parse_checklist_summary(checklist_path.read_text(encoding="utf-8"))
            checklist_has_items = checklist_summary["total"] > 0
        else:
            checklist_summary = {"total": 0, "complete": 0, "incomplete": 0, "is_complete": False}
            checklist_has_items = False

        blockers: list[str] = []
        warnings: list[str] = []
        if not context_path.exists():
            blockers.append("context_missing")
        elif not context_has_content:
            blockers.append("context_empty")
        if not plan_path.exists():
            blockers.append("plan_missing")
        elif not plan_has_content:
            blockers.append("plan_empty")
        if not checklist_path.exists():
            blockers.append("checklist_missing")
        elif not checklist_has_items:
            warnings.append("checklist_has_no_items")
        elif not checklist_summary["is_complete"]:
            warnings.append("checklist_incomplete")

        readiness = "ready"
        if blockers:
            readiness = "unknown"
        elif warnings:
            readiness = "not_ready"

        return {
            "phase": phase_ref,
            "path": str(path),
            "readiness": readiness,
            "checklist_summary": checklist_summary,
            "documents": {
                "context": {"exists": context_path.exists(), "has_content": context_has_content},
                "plan": {"exists": plan_path.exists(), "has_content": plan_has_content},
                "checklist": {"exists": checklist_path.exists(), "has_items": checklist_has_items},
            },
            "warnings": warnings,
            "blockers": blockers,
            "linked_tasks": self.task_service.summarize_tasks_for_phase(phase_ref),
        }
