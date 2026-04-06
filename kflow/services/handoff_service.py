"""AI-assist handoff export service."""

from __future__ import annotations

from pathlib import Path

from kflow.models.results import Message, OperationResult
from kflow.services.doctor_service import DoctorService
from kflow.services.task_service import TaskService
from kflow.utils.files import write_text


class HandoffService:
    """Export a normalized task handoff for agent or human continuation."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.task_service = TaskService(cwd)

    def export(self, task_id: str | None = None) -> OperationResult:
        """Generate a task handoff artifact and machine-readable payload."""
        task = self.task_service.get_task(task_id)
        task_status = self.task_service.status(task.id)
        task_doctor = DoctorService(self.cwd).inspect_task(task.id, closeout=False)

        prompt = self._render_prompt(task_status.data, task_doctor.data)
        artifact_path = Path(task.task_dir) / "artifacts" / "agent-handoff.md"
        write_text(artifact_path, prompt, overwrite=True)

        messages = [
            Message(severity="pass", text=f"Handoff exported for {task.id}"),
            Message(severity="info", text=f"Artifact: {artifact_path}"),
        ]
        return OperationResult(
            command="task handoff",
            status="ok",
            messages=messages,
            data={
                "task_id": task.id,
                "artifact": str(artifact_path),
                "prompt": prompt,
                "task_status": task_status.data,
                "task_doctor": task_doctor.data,
            },
        )

    def _render_prompt(self, task_status: dict[str, object], task_doctor: dict[str, object]) -> str:
        """Render a concise handoff prompt for downstream agents."""
        task = task_status["task"]
        evidence = task_status["evidence"]
        summary = task_status["summary"]
        phase_summary = task_status.get("phase_summary")
        lines = [
            "# KFlow Agent Handoff",
            "",
            "## Task",
            f"- id: {task['id']}",
            f"- name: {task['name']}",
            f"- type: {task['type']}",
            f"- status: {task['status']}",
            f"- risk: {task['risk_level']}",
        ]
        if task.get("phase_ref"):
            lines.append(f"- phase: {task['phase_ref']}")
        lines.extend(
            [
                "",
                "## Execution Evidence",
                f"- build: {evidence['build']}",
                f"- test: {evidence['test']}",
                f"- mobile: {evidence['mobile']}",
                "",
                "## Open Gates",
            ]
        )
        requirements = summary.get("requirements", [])
        warnings = summary.get("warnings", [])
        blockers = task_doctor.get("blockers", [])
        if not requirements and not warnings and not blockers:
            lines.append("- none")
        else:
            lines.extend(f"- requirement: {item}" for item in requirements)
            lines.extend(f"- warning: {item}" for item in warnings)
            lines.extend(f"- blocker: {item}" for item in blockers)
        lines.extend(["", "## Next Steps"])
        next_steps = task_doctor.get("next_steps", [])
        if next_steps:
            lines.extend(f"- {item}" for item in next_steps)
        else:
            lines.append("- none")
        if phase_summary:
            lines.extend(
                [
                    "",
                    "## Phase Context",
                    f"- phase: {phase_summary['phase']}",
                    f"- linked task count: {phase_summary['task_count']}",
                    f"- current task id: {phase_summary['current_task_id']}",
                ]
            )
        lines.extend(
            [
                "",
                "## Instructions",
                "- Use this handoff together with TASK_BRIEF.md, CHANGE_PLAN.md, VERIFY_CHECKLIST.md, and RESULT.md.",
                "- Resolve blockers first, then warnings, then complete the listed next steps.",
            ]
        )
        return "\n".join(lines) + "\n"
