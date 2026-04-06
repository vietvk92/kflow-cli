"""Shared planning discovery helpers."""

from __future__ import annotations

from pathlib import Path
import re


PHASE_DOCS = ("CONTEXT.md", "PLAN.md", "READY_CHECKLIST.md")
DOC_TYPES = ("context", "plan", "checklist", "summary")


def analyze_planning_dir(planning_dir: Path) -> dict[str, object]:
    """Analyze a planning root and normalize detected phase structure."""
    phase_records = discover_phase_records(planning_dir)
    phases = [record_to_phase_summary(item) for item in phase_records]
    if phases:
        mode = "existing_planning"
    elif planning_dir.exists():
        mode = "partial_planning"
    else:
        mode = "no_planning"
    return {
        "planning_dir": str(planning_dir),
        "exists": planning_dir.exists(),
        "mode": mode,
        "phase_count": len(phases),
        "phases": phases,
    }


def discover_phase_dirs(planning_dir: Path) -> list[Path]:
    """Discover likely phase directories under a planning root."""
    return [record["phase_dir"] for record in discover_phase_records(planning_dir)]


def discover_phase_records(planning_dir: Path) -> list[dict[str, object]]:
    """Discover normalized phase records under a planning root."""
    if not planning_dir.exists():
        return []

    records: dict[str, dict[str, object]] = {}

    for path in sorted(planning_dir.rglob("*"), key=lambda item: str(item)):
        if not path.is_dir():
            continue
        dir_phase_ref = _extract_phase_ref(path.name)
        if not dir_phase_ref:
            continue
        record = records.setdefault(
            dir_phase_ref,
            {
                "phase": dir_phase_ref,
                "phase_dir": path,
                "documents": {},
            },
        )
        if len(str(path)) < len(str(record["phase_dir"])):
            record["phase_dir"] = path

    for path in sorted(planning_dir.rglob("*.md"), key=lambda item: str(item)):
        doc_type = _classify_doc_type(path)
        if doc_type is None:
            continue
        phase_ref = _resolve_phase_ref_for_document(path, planning_dir)
        if not phase_ref:
            continue
        record = records.setdefault(
            phase_ref,
            {
                "phase": phase_ref,
                "phase_dir": path.parent,
                "documents": {},
            },
        )
        existing = record["documents"].get(doc_type)
        if existing is None or _document_score(path, doc_type) > _document_score(existing, doc_type):
            record["documents"][doc_type] = path
        record["phase_dir"] = _prefer_phase_dir(Path(record["phase_dir"]), path.parent)

    return sorted(records.values(), key=lambda item: _phase_sort_key(str(item["phase"])))


def phase_ref_for_path(path: Path) -> str:
    """Normalize a directory name into a phase reference string."""
    return _extract_phase_ref(path.name) or path.name


def inspect_phase_state(planning_dir: Path, phase_ref: str) -> dict[str, object]:
    """Inspect planning readiness for one phase in a lightweight reusable shape."""
    phase_record = find_phase_record(planning_dir, phase_ref)
    if phase_record is None:
        return {
            "exists": False,
            "phase": phase_ref,
            "readiness": "missing",
            "context_ready": False,
            "plan_ready": False,
            "checklist_complete": False,
            "checklist_total": 0,
            "checklist_incomplete": 0,
        }

    phase_dir = Path(phase_record["phase_dir"])
    documents = phase_record.get("documents", {})
    context_path = documents.get("context")
    plan_path = documents.get("plan")
    checklist_path = documents.get("checklist")
    context_ready = bool(context_path and context_path.exists() and _meaningful_markdown_text(context_path.read_text(encoding="utf-8")))
    plan_ready = bool(plan_path and plan_path.exists() and _meaningful_markdown_text(plan_path.read_text(encoding="utf-8")))
    checklist_summary = (
        _parse_checklist_summary(checklist_path.read_text(encoding="utf-8"))
        if checklist_path and checklist_path.exists()
        else {"total": 0, "complete": 0, "incomplete": 0, "is_complete": False}
    )
    readiness = "ready" if context_ready and plan_ready and bool(checklist_summary["is_complete"]) else "not_ready"
    return {
        "exists": True,
        "phase": str(phase_record["phase"]),
        "phase_dir": str(phase_dir),
        "readiness": readiness,
        "context_ready": context_ready,
        "plan_ready": plan_ready,
        "checklist_complete": bool(checklist_summary["is_complete"]),
        "checklist_total": int(checklist_summary["total"]),
        "checklist_incomplete": int(checklist_summary["incomplete"]),
        "documents": {
            "context": str(context_path) if context_path else None,
            "plan": str(plan_path) if plan_path else None,
            "checklist": str(checklist_path) if checklist_path else None,
            "summary": str(documents.get("summary")) if documents.get("summary") else None,
        },
    }


def record_to_phase_summary(record: dict[str, object]) -> dict[str, object]:
    """Render a phase record into a JSON-friendly summary."""
    documents = record.get("documents", {})
    return {
        "phase": str(record["phase"]),
        "phase_dir": str(record["phase_dir"]),
        "documents": {
            name: str(documents[name])
            for name in DOC_TYPES
            if documents.get(name) is not None
        },
    }


def find_phase_record(planning_dir: Path, phase_ref: str) -> dict[str, object] | None:
    target_key = _normalize_phase_ref(phase_ref)
    for record in discover_phase_records(planning_dir):
        if _normalize_phase_ref(str(record["phase"])) == target_key:
            return record
    return None


def _parse_checklist_summary(content: str) -> dict[str, int | bool]:
    """Summarize checklist completion from markdown or yaml-like content."""
    checkbox_total = len(re.findall(r"- \[[ xX]\]", content))
    checkbox_incomplete = len(re.findall(r"- \[ \]", content))
    bool_total = len(re.findall(r":\s*(true|false)\b", content, flags=re.IGNORECASE))
    bool_incomplete = len(re.findall(r":\s*false\b", content, flags=re.IGNORECASE))
    total = checkbox_total + bool_total
    incomplete = checkbox_incomplete + bool_incomplete
    complete = total - incomplete
    return {
        "total": total,
        "complete": max(complete, 0),
        "incomplete": incomplete,
        "is_complete": bool(content.strip()) and incomplete == 0,
    }


def _meaningful_markdown_text(content: str) -> str:
    """Strip headings and bullet markers to estimate useful doc content."""
    text = re.sub(r"^#+\s+.*$", "", content, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    return text.strip()


def _classify_doc_type(path: Path) -> str | None:
    name = path.name.upper()
    if name == "CONTEXT.MD" or name.endswith("-CONTEXT.MD") or name.endswith("_CONTEXT.MD"):
        return "context"
    if name == "PLAN.MD" or name.endswith("-PLAN.MD") or name.endswith("_PLAN.MD"):
        return "plan"
    if name == "READY_CHECKLIST.MD" or "CHECKLIST" in name:
        return "checklist"
    if name.endswith("-SUMMARY.MD") or name.endswith("_SUMMARY.MD") or name == "SUMMARY.MD":
        return "summary"
    return None


def _resolve_phase_ref_for_document(path: Path, planning_dir: Path) -> str | None:
    for candidate in [path.parent.name, path.stem]:
        phase_ref = _extract_phase_ref(candidate)
        if phase_ref:
            return phase_ref
    for parent in path.relative_to(planning_dir).parents:
        if str(parent) == ".":
            continue
        part = parent.name
        phase_ref = _extract_phase_ref(part)
        if phase_ref:
            return phase_ref
    return None


def _extract_phase_ref(raw: str) -> str | None:
    lowered = raw.lower()
    if lowered.startswith("phase-") or lowered.startswith("phase_"):
        raw = raw.split("-", 1)[1] if "-" in raw else raw.split("_", 1)[1]
    match = re.match(r"^(\d+(?:[._-]\d+)*)\b", raw)
    if not match:
        match = re.match(r"^(\d+)\b", raw)
    if not match:
        return None
    return _normalize_phase_ref(match.group(1))


def _normalize_phase_ref(raw: str) -> str:
    normalized = re.sub(r"[_-]+", ".", raw.strip())
    segments = [segment for segment in normalized.split(".") if segment]
    if not segments:
        return raw.strip()
    return ".".join(str(int(segment)) if segment.isdigit() else segment for segment in segments)


def _document_score(path: Path, doc_type: str) -> int:
    name = path.name.upper()
    exact_names = {
        "context": "CONTEXT.MD",
        "plan": "PLAN.MD",
        "checklist": "READY_CHECKLIST.MD",
        "summary": "SUMMARY.MD",
    }
    score = 0
    if name == exact_names[doc_type]:
        score += 100
    if doc_type == "context" and "CONTEXT" in name:
        score += 20
    if doc_type == "plan" and "PLAN" in name:
        score += 20
    if doc_type == "checklist" and "CHECKLIST" in name:
        score += 20
    if doc_type == "summary" and "SUMMARY" in name:
        score += 20
    score -= len(path.parts)
    return score


def _prefer_phase_dir(current: Path, candidate: Path) -> Path:
    return candidate if len(candidate.parts) < len(current.parts) else current


def _phase_sort_key(phase_ref: str) -> tuple[object, ...]:
    parts = []
    for segment in phase_ref.split("."):
        parts.append((0, int(segment)) if segment.isdigit() else (1, segment))
    return tuple(parts)
