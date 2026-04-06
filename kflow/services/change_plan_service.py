"""Helpers for keeping CHANGE_PLAN.md in sync with execution evidence."""

from __future__ import annotations

from pathlib import Path

from kflow.models.task import TaskRecord
from kflow.utils.files import write_text
from kflow.utils.markdown import upsert_section_bullets


class ChangePlanService:
    """Read and update managed task change plans."""

    def __init__(self, task: TaskRecord) -> None:
        self.task = task
        self.change_plan_path = Path(task.task_dir) / "CHANGE_PLAN.md"

    def update_test_plan_entry(self, key: str, value: str) -> None:
        """Upsert a managed execution-related bullet inside Test Plan."""
        content = self.change_plan_path.read_text(encoding="utf-8")
        updated = upsert_section_bullets(content, "Test Plan", {key: value})
        write_text(self.change_plan_path, updated, overwrite=True)
