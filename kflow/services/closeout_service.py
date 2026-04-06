"""Closeout service."""

from __future__ import annotations

from pathlib import Path

from kflow.models.results import Message, OperationResult
from kflow.services.doctor_service import DoctorService
from kflow.services.result_service import ResultService
from kflow.services.task_service import TaskService
from kflow.utils.files import write_text
from kflow.utils.markdown import get_section_content, set_section_content
from kflow.utils.time import utc_now_iso
from kflow.utils.yaml_io import dump_yaml


class CloseoutService:
    """Close a task if all required checks pass."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd

    def close_task(self, task_id: str | None = None) -> OperationResult:
        doctor_result = DoctorService(self.cwd).inspect_task(task_id, closeout=True)
        if doctor_result.data["blockers"]:
            return doctor_result

        task_service = TaskService(self.cwd)
        task = task_service.get_task(task_id)
        self._finalize_result(task)
        task.status = "done"
        task.updated_at = utc_now_iso()
        state_file = task_service.tasks_state_dir / f"{task.id}.yaml"
        write_text(state_file, dump_yaml(task.model_dump(mode="python")), overwrite=True)
        messages = list(doctor_result.messages)
        messages.append(Message(severity="pass", text=f"Task closed: {task.id}"))
        return OperationResult(
            command="task close",
            status="ok",
            messages=messages,
            data={"task_id": task.id, "status": task.status},
        )

    def _finalize_result(self, task) -> None:
        result_service = ResultService(task)
        result_service.sync_changed_files()
        result_path = Path(task.task_dir) / "RESULT.md"
        content = result_path.read_text(encoding="utf-8")
        follow_ups = get_section_content(content, "Follow-ups")
        lines = [line for line in follow_ups.splitlines() if line.strip()]
        note = f"- Closed at {utc_now_iso()}"
        if note not in lines:
            lines.append(note)
        write_text(result_path, set_section_content(content, "Follow-ups", "\n".join(lines)), overwrite=True)
