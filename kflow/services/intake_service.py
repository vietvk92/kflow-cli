"""Spec intake service — bootstrap tasks from dropped spec files."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from kflow.config.loader import load_config
from kflow.models.results import Message, OperationResult
from kflow.services.task_service import TaskService
from kflow.utils.files import ensure_directory, write_text
from kflow.utils.yaml_io import dump_yaml, load_yaml


INTAKE_EXTENSIONS = {".md", ".txt"}

_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["bug", "fix", "crash", "error", "defect", "null pointer", "exception", "broken"], "bug"),
    (["refactor", "cleanup", "clean up", "restructure", "migrate", "chore", "infra"], "refactor"),
    (["spike", "research", "investigation", "explore", "proof of concept", "poc"], "spike"),
]

_RISK_HIGH = ["critical", "p0", "high risk", "high-risk", "high priority", "blocker", "blocking"]
_RISK_LOW = ["low risk", "low-risk", "trivial", "minor", "cosmetic", "p3", "nice to have"]


def _extract_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return fallback


def _infer_task_type(content: str) -> str:
    lower = content.lower()
    for keywords, task_type in _TYPE_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return task_type
    return "feat"


def _infer_risk(content: str) -> str:
    lower = content.lower()
    if any(kw in lower for kw in _RISK_HIGH):
        return "high"
    if any(kw in lower for kw in _RISK_LOW):
        return "low"
    return "medium"


def _spec_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _render_task_brief_from_spec(task_type: str, risk: str, spec_title: str, spec_content: str) -> str:
    return f"""# Task Brief

## Type
{task_type}

## Goal
{spec_title}

## In Scope

## Out of Scope

## Acceptance Criteria

## Constraints

## Risk Level
{risk}

## Tags

## Repro Steps

---

## Spec Content

{spec_content.strip()}
"""


class IntakeService:
    """Scan an intake directory for spec files and bootstrap tasks."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.config = load_config(cwd)
        self.repo_root = self.config.repo_root_path
        self.intake_dir = self.repo_root / self.config.paths.intake_dir
        self.processed_log = self.repo_root / ".kflow" / "state" / "intake_processed.yaml"

    def _load_processed(self) -> dict[str, str]:
        if not self.processed_log.exists():
            return {}
        data = load_yaml(self.processed_log)
        return data if isinstance(data, dict) else {}

    def _save_processed(self, processed: dict[str, str]) -> None:
        ensure_directory(self.processed_log.parent)
        write_text(self.processed_log, dump_yaml(processed), overwrite=True)

    def scan(self) -> OperationResult:
        """Dry-run: show what would be created without applying."""
        return self._run(apply=False, force=False)

    def run(self, force: bool = False) -> OperationResult:
        """Ingest all new specs and create tasks."""
        return self._run(apply=True, force=force)

    def _run(self, apply: bool, force: bool) -> OperationResult:
        messages: list[Message] = []

        if not self.intake_dir.exists():
            ensure_directory(self.intake_dir)
            messages.append(Message(severity="info", text=f"Created intake directory: {self.intake_dir.relative_to(self.repo_root)}"))

        spec_files = sorted(
            p for p in self.intake_dir.iterdir()
            if p.is_file() and p.suffix.lower() in INTAKE_EXTENSIONS
        )

        if not spec_files:
            messages.append(Message(severity="warning", text=f"No spec files found in {self.intake_dir.relative_to(self.repo_root)}/"))
            messages.append(Message(severity="info", text="Drop .md or .txt spec files there, then re-run `kflow intake`."))
            return OperationResult(command="intake", status="warning", messages=messages, data={"specs_found": 0})

        processed = self._load_processed()
        pending: list[dict[str, str]] = []
        skipped: list[str] = []

        for spec_path in spec_files:
            file_hash = _spec_hash(spec_path)
            rel = str(spec_path.relative_to(self.repo_root))
            if not force and processed.get(rel) == file_hash:
                skipped.append(rel)
                continue
            content = spec_path.read_text(encoding="utf-8")
            title = _extract_title(content, spec_path.stem.replace("-", " ").replace("_", " ").title())
            pending.append({
                "path": rel,
                "hash": file_hash,
                "title": title,
                "type": _infer_task_type(content),
                "risk": _infer_risk(content),
                "content": content,
            })

        if skipped:
            messages.append(Message(severity="info", text=f"Already processed (skipped): {len(skipped)} file(s). Use --force to re-ingest."))

        if not pending:
            messages.append(Message(severity="pass", text="No new specs to process."))
            return OperationResult(command="intake", status="ok", messages=messages, data={"specs_found": len(spec_files), "pending": 0, "skipped": len(skipped)})

        messages.append(Message(severity="info", text=f"Found {len(pending)} new spec(s) to ingest:"))
        for item in pending:
            messages.append(Message(severity="info", text=f"  [{item['type']} / {item['risk']}] {item['title']}"))

        if not apply:
            messages.append(Message(severity="warning", text="Dry-run mode — use `kflow intake --apply` to create tasks."))
            return OperationResult(
                command="intake",
                status="ok",
                messages=messages,
                data={"specs_found": len(spec_files), "pending": len(pending), "skipped": len(skipped)},
            )

        task_service = TaskService(self.cwd)
        created: list[dict[str, str]] = []

        for item in pending:
            try:
                result = task_service.create_task(
                    task_type=item["type"],
                    name=item["title"],
                    risk=item["risk"],
                )
                task_id: str = result.data["task_id"]
                task_dir = Path(result.data["task_dir"])

                # Overwrite TASK_BRIEF.md with spec-prefilled content
                brief_content = _render_task_brief_from_spec(
                    task_type=item["type"],
                    risk=item["risk"],
                    spec_title=item["title"],
                    spec_content=item["content"],
                )
                write_text(task_dir / "TASK_BRIEF.md", brief_content, overwrite=True)

                processed[item["path"]] = item["hash"]
                created.append({"task_id": task_id, "spec": item["path"], "title": item["title"]})
                messages.append(Message(severity="pass", text=f"Created task [{task_id}] from {item['path']}"))
            except Exception as exc:  # noqa: BLE001
                messages.append(Message(severity="warning", text=f"Failed to create task for '{item['title']}': {exc}"))

        if created:
            self._save_processed(processed)
            messages.append(Message(severity="info", text="Next: review TASK_BRIEF.md files, then run `kflow task doctor`."))

        return OperationResult(
            command="intake --apply",
            status="ok" if created else "warning",
            messages=messages,
            data={
                "specs_found": len(spec_files),
                "pending": len(pending),
                "skipped": len(skipped),
                "created": created,
            },
        )
