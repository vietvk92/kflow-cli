"""Helpers for keeping RESULT.md in sync with execution outputs."""

from __future__ import annotations

from pathlib import Path

from kflow.models.task import TaskRecord
from kflow.services.diff_service import DiffService
from kflow.utils.files import write_text
from kflow.utils.markdown import get_section_content, parse_result_document, set_section_content


class ResultService:
    """Read and update managed task result files."""

    def __init__(self, task: TaskRecord) -> None:
        self.task = task
        self.result_path = Path(task.task_dir) / "RESULT.md"

    def update_section(self, heading: str, body: str) -> None:
        content = self.result_path.read_text(encoding="utf-8")
        write_text(self.result_path, set_section_content(content, heading, body), overwrite=True)

    def append_known_issue(self, issue: str) -> None:
        content = self.result_path.read_text(encoding="utf-8")
        existing = get_section_content(content, "Known Issues")
        lines = [line for line in existing.splitlines() if line.strip()]
        if issue not in lines:
            lines.append(f"- {issue}" if not issue.startswith("- ") else issue)
        write_text(self.result_path, set_section_content(content, "Known Issues", "\n".join(lines)), overwrite=True)

    def set_known_issues_none(self) -> None:
        """Ensure Known Issues has a minimal non-empty value for closeout."""
        content = self.result_path.read_text(encoding="utf-8")
        existing = get_section_content(content, "Known Issues")
        if existing.strip():
            return
        write_text(self.result_path, set_section_content(content, "Known Issues", "- none"), overwrite=True)

    def sync_changed_files(self) -> None:
        task_path = Path(self.task.task_dir)
        changed = {path.name for path in task_path.glob("*.md") if path.is_file()}
        diff_summary = DiffService(task_path.parent.parent.parent).summarize()
        if diff_summary["available"]:
            changed.update(str(path) for path in diff_summary["changed_files"])
        changed = sorted(changed)
        body = "\n".join(f"- {name}" for name in changed)
        self.update_section("Changed Files", body)

    def parse(self):
        """Return structured RESULT.md content."""
        return parse_result_document(self.result_path.read_text(encoding="utf-8"))
