"""Phase readiness services."""

from __future__ import annotations

from pathlib import Path

from kflow.config.loader import load_config
from kflow.models.results import Message, OperationResult
from kflow.services.planning_service import (
    _meaningful_markdown_text,
    _parse_checklist_summary,
    find_phase_record,
    inspect_phase_state,
)
from kflow.services.task_service import TaskService


class PhaseService:
    """Inspect phase planning readiness."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.config = load_config(cwd)
        self.repo_root = self.config.repo_root_path
        self.planning_dir = self.repo_root / self.config.paths.planning_dir
        self.task_service = TaskService(cwd)

    def check(self, phase_ref: str) -> OperationResult:
        """Check whether a phase has the required planning docs."""
        phase_state = inspect_phase_state(self.planning_dir, phase_ref)
        phase_dir = Path(str(phase_state["phase_dir"])) if phase_state.get("phase_dir") else None
        messages: list[Message] = [Message(severity="info", text=f"Phase {phase_ref} Readiness")]
        blockers: list[str] = []
        warnings: list[str] = []

        if phase_dir is None or not bool(phase_state["exists"]):
            blockers.append(f"Phase `{phase_ref}` not found under {self.planning_dir}")
            messages.append(Message(severity="blocked", text=blockers[0]))
            return OperationResult(
                command="phase check",
                status="blocked",
                messages=messages,
                data={"phase": phase_ref, "blockers": blockers, "warnings": warnings},
            )

        detected_documents = phase_state.get("documents", {})
        context = Path(str(detected_documents["context"])) if detected_documents.get("context") else phase_dir / "CONTEXT.md"
        plan = Path(str(detected_documents["plan"])) if detected_documents.get("plan") else phase_dir / "PLAN.md"
        checklist = Path(str(detected_documents["checklist"])) if detected_documents.get("checklist") else phase_dir / "READY_CHECKLIST.md"
        context_state = self._inspect_doc(context, "CONTEXT.md")
        plan_state = self._inspect_doc(plan, "PLAN.md")

        if context_state["exists"]:
            messages.append(Message(severity="pass", text="CONTEXT.md found"))
            if not context_state["has_content"]:
                blockers.append("CONTEXT.md has no meaningful content")
        else:
            blockers.append("CONTEXT.md missing")

        if plan_state["exists"]:
            messages.append(Message(severity="pass", text="PLAN.md found"))
            if not plan_state["has_content"]:
                blockers.append("PLAN.md has no meaningful content")
        else:
            blockers.append("PLAN.md missing")

        if checklist.exists():
            checklist_summary = _parse_checklist_summary(checklist.read_text(encoding="utf-8"))
            if checklist_summary["is_complete"]:
                messages.append(Message(severity="pass", text="READY_CHECKLIST.md complete"))
            else:
                warnings.append("READY_CHECKLIST.md incomplete")
                messages.append(
                    Message(
                        severity="info",
                        text=f"Checklist: {checklist_summary['complete']}/{checklist_summary['total']} complete",
                    )
                )
            if checklist_summary["total"] == 0:
                warnings.append("READY_CHECKLIST.md has no checklist items")
        else:
            checklist_summary = {"total": 0, "complete": 0, "incomplete": 0, "is_complete": False}
            blockers.append("READY_CHECKLIST.md missing")

        for warning in warnings:
            messages.append(Message(severity="warning", text=warning))
        for blocker in blockers:
            messages.append(Message(severity="blocked", text=blocker))

        next_steps: list[str] = []
        if "CONTEXT.md missing" in blockers:
            next_steps.append("Add CONTEXT.md to the phase directory.")
        if "CONTEXT.md has no meaningful content" in blockers:
            next_steps.append("Add phase context, constraints, and scope details to CONTEXT.md.")
        if "PLAN.md missing" in blockers:
            next_steps.append("Add PLAN.md to the phase directory.")
        if "PLAN.md has no meaningful content" in blockers:
            next_steps.append("Add execution steps or implementation plan details to PLAN.md.")
        if "READY_CHECKLIST.md missing" in blockers or "READY_CHECKLIST.md incomplete" in warnings:
            next_steps.append("Complete READY_CHECKLIST.md before marking the phase ready.")
        if "READY_CHECKLIST.md has no checklist items" in warnings:
            next_steps.append("Add concrete readiness checklist items to READY_CHECKLIST.md.")

        resolved_phase_ref = str(phase_state["phase"])
        linked_tasks = self.task_service.summarize_tasks_for_phase(resolved_phase_ref)
        if linked_tasks["task_count"]:
            messages.append(Message(severity="info", text=f"Linked tasks: {linked_tasks['task_count']}"))
            active_tasks = [item["id"] for item in linked_tasks["tasks"] if item["status"] != "done"]
            if active_tasks:
                warnings.append(f"phase has open tasks: {', '.join(active_tasks)}")
                next_steps.append("Close or unblock linked phase tasks before marking the phase fully ready.")
            evidence_totals = linked_tasks["evidence_totals"]
            if evidence_totals["build"]["fail"] or evidence_totals["test"]["fail"] or evidence_totals["mobile"]["fail"]:
                warnings.append("phase has failing task execution evidence")
                next_steps.append("Resolve failing build/test/mobile evidence on linked tasks.")

        return OperationResult(
            command="phase check",
            status="blocked" if blockers else ("warning" if warnings else "ok"),
            messages=messages,
            data={
                "scope": {
                    "kind": "phase",
                    "phase": resolved_phase_ref,
                },
                "summary": {
                    "readiness": "blocked" if blockers else ("warning" if warnings else "ready"),
                    "task_count": linked_tasks["task_count"],
                    "open_task_count": sum(1 for item in linked_tasks["tasks"] if item["status"] != "done"),
                    "checklist_complete": checklist_summary["is_complete"],
                    "evidence_totals": linked_tasks["evidence_totals"],
                },
                "phase": resolved_phase_ref,
                "phase_dir": str(phase_dir),
                "warnings": warnings,
                "blockers": blockers,
                "next_steps": next_steps,
                "checklist_summary": checklist_summary,
                "documents": {
                    "context": context_state,
                    "plan": plan_state,
                    "checklist": {
                        "exists": checklist.exists(),
                        "has_items": checklist_summary["total"] > 0,
                    },
                },
                "linked_tasks": linked_tasks,
            },
        )

    def _locate_phase_dir(self, phase_ref: str) -> Path | None:
        record = find_phase_record(self.planning_dir, phase_ref)
        return Path(record["phase_dir"]) if record else None

    def _inspect_doc(self, path: Path, name: str) -> dict[str, str | bool]:
        """Inspect basic readiness of a markdown planning doc."""
        if not path.exists():
            return {"name": name, "exists": False, "has_content": False}
        content = path.read_text(encoding="utf-8")
        return {
            "name": name,
            "exists": True,
            "has_content": bool(_meaningful_markdown_text(content)),
        }
