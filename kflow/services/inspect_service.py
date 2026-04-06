"""Inspect command service."""

from __future__ import annotations

import json
from pathlib import Path

from kflow.adapters.gitnexus import GitNexusAdapter
from kflow.models.results import Message, OperationResult
from kflow.services.task_service import TaskService
from kflow.utils.files import write_text
from kflow.utils.markdown import merge_section_bullets


class InspectService:
    """Run GitNexus-assisted inspection for the current task."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.task_service = TaskService(cwd)
        self.config = self.task_service.config
        self.repo_root = self.task_service.repo_root
        self.adapter = GitNexusAdapter(
            command=self.config.adapters.gitnexus.command,
            enabled=self.config.adapters.gitnexus.enabled,
        )

    def inspect(self, symbol: str) -> OperationResult:
        detection = self.adapter.detect(self.repo_root)
        task = self.task_service.get_task()
        change_plan_path = Path(task.task_dir) / "CHANGE_PLAN.md"
        artifact_dir = self.task_service.task_artifacts_dir(task)

        if detection.status != "present":
            return OperationResult(
                command="inspect",
                status="warning",
                messages=[
                    Message(severity="warning", text="GitNexus unavailable for inspect."),
                    Message(severity="info", text="Update CHANGE_PLAN.md manually."),
                ],
                data={"symbol": symbol, "task_id": task.id, "gitnexus_status": detection.status},
            )

        context_result = self.adapter.context(self.repo_root, symbol)
        impact_result = self.adapter.impact(self.repo_root, symbol)

        context_path = artifact_dir / "inspect-context.txt"
        impact_path = artifact_dir / "inspect-impact.txt"
        write_text(context_path, context_result.stdout or context_result.stderr, overwrite=True)
        write_text(impact_path, impact_result.stdout or impact_result.stderr, overwrite=True)

        context_lines = self._parse_output_lines(context_result.stdout) if context_result.ok else []
        impact_lines = self._parse_output_lines(impact_result.stdout) if impact_result.ok else []
        context_fields = self._parse_structured_output(context_lines)
        impact_fields = self._parse_structured_output(impact_lines)

        if context_result.ok:
            self._merge_plan_entries(
                change_plan_path,
                "Impacted Symbols",
                [symbol],
            )
            self._merge_plan_entries(
                change_plan_path,
                "Risk Notes",
                self._merge_structured_entries(context_lines, context_fields),
            )
        if impact_result.ok:
            self._merge_plan_entries(
                change_plan_path,
                "Intended Changes",
                self._merge_structured_entries(impact_lines, impact_fields) or [f"Review impact for {symbol}"],
            )

        summary_path = artifact_dir / "inspect-summary.json"
        summary_payload = {
            "symbol": symbol,
            "task_id": task.id,
            "gitnexus_status": detection.status,
            "context": {
                "ok": context_result.ok,
                "lines": context_lines,
                "fields": context_fields,
            },
            "impact": {
                "ok": impact_result.ok,
                "lines": impact_lines,
                "fields": impact_fields,
            },
        }
        write_text(summary_path, json.dumps(summary_payload, indent=2) + "\n", overwrite=True)

        if context_result.ok and impact_result.ok:
            self.task_service.update_status(task, "context_ready")

        status = "ok" if context_result.ok and impact_result.ok else "warning"
        messages = [
            Message(severity="pass" if context_result.ok else "warning", text=f"GitNexus context {'captured' if context_result.ok else 'failed'}"),
            Message(severity="pass" if impact_result.ok else "warning", text=f"GitNexus impact {'captured' if impact_result.ok else 'failed'}"),
            Message(severity="info", text=f"Artifacts: {context_path.name}, {impact_path.name}"),
        ]
        if context_result.stderr and not context_result.ok:
            messages.append(Message(severity="warning", text=context_result.stderr))
        if impact_result.stderr and not impact_result.ok:
            messages.append(Message(severity="warning", text=impact_result.stderr))

        return OperationResult(
            command="inspect",
            status=status,
            messages=messages,
            data={
                "symbol": symbol,
                "task_id": task.id,
                "context_artifact": str(context_path),
                "impact_artifact": str(impact_path),
                "summary_artifact": str(summary_path),
                "context_lines": context_lines,
                "impact_lines": impact_lines,
                "context_fields": context_fields,
                "impact_fields": impact_fields,
                "task_status": self.task_service.get_task(task.id).status,
            },
        )

    def _merge_plan_entries(self, path: Path, heading: str, entries: list[str]) -> None:
        content = path.read_text(encoding="utf-8")
        write_text(path, merge_section_bullets(content, heading, entries), overwrite=True)

    def _parse_output_lines(self, content: str) -> list[str]:
        """Normalize multiline adapter output into deduplicated bullet content."""
        lines: list[str] = []
        seen: set[str] = set()
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("- "):
                line = line[2:].strip()
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
        return lines

    def _parse_structured_output(self, lines: list[str]) -> dict[str, list[str]]:
        """Parse simple `key: value` output into grouped fields."""
        fields: dict[str, list[str]] = {}
        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", maxsplit=1)
            normalized_key = key.strip().lower().replace(" ", "_")
            normalized_value = value.strip()
            if not normalized_key or not normalized_value:
                continue
            bucket = fields.setdefault(normalized_key, [])
            if normalized_value not in bucket:
                bucket.append(normalized_value)
        return fields

    def _merge_structured_entries(self, lines: list[str], fields: dict[str, list[str]]) -> list[str]:
        """Prefer parsed values from structured output but preserve raw lines when needed."""
        preferred_keys = ("risk", "risks", "change", "changes", "impact", "impacts", "file", "files", "symbol", "symbols")
        entries: list[str] = []
        seen: set[str] = set()
        for key in preferred_keys:
            for value in fields.get(key, []):
                if value not in seen:
                    seen.add(value)
                    entries.append(value)
        for line in lines:
            if line not in seen:
                seen.add(line)
                entries.append(line)
        return entries
