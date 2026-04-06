"""Markdown helpers."""

from __future__ import annotations

from kflow.models.task import ParsedResultDocument, ParsedTaskBrief, ParsedVerifyChecklist


def _split_sections(content: str) -> tuple[str, list[tuple[str, str]]]:
    """Split markdown into a title block and ordered H2 sections."""
    lines = content.splitlines()
    prefix: list[str] = []
    sections: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_heading is None and not sections:
                pass
            if current_heading is None:
                current_heading = line[3:]
                current_lines = []
                continue
            sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line[3:]
            current_lines = []
            continue
        if current_heading is None:
            prefix.append(line)
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return "\n".join(prefix).rstrip(), sections


def _render_sections(prefix: str, sections: list[tuple[str, str]]) -> str:
    """Render an ordered set of H2 sections back to markdown."""
    parts: list[str] = [prefix.strip()]
    for heading, body in sections:
        parts.append(f"## {heading}")
        parts.append(body.strip())
    return "\n\n".join(part for part in parts if part is not None).rstrip() + "\n"


def section_has_content(content: str, heading: str) -> bool:
    """Check whether a markdown section contains non-empty content."""
    marker = f"## {heading}"
    if marker not in content:
        return False
    section = content.split(marker, maxsplit=1)[1]
    lines = []
    for line in section.splitlines()[1:]:
        if line.startswith("## "):
            break
        if line.strip():
            lines.append(line.strip())
    return bool(lines)


def get_section_content(content: str, heading: str) -> str:
    """Return the raw content of a markdown H2 section."""
    _, sections = _split_sections(content)
    for name, body in sections:
        if name == heading:
            return body
    return ""


def set_section_content(content: str, heading: str, body: str) -> str:
    """Replace or add an H2 section body."""
    prefix, sections = _split_sections(content)
    updated = False
    rendered_sections: list[tuple[str, str]] = []
    for name, existing_body in sections:
        if name == heading:
            rendered_sections.append((name, body.strip()))
            updated = True
        else:
            rendered_sections.append((name, existing_body))
    if not updated:
        rendered_sections.append((heading, body.strip()))
    return _render_sections(prefix, rendered_sections)


def parse_bullet_lines(body: str) -> list[str]:
    """Parse markdown bullet-like content into cleaned items."""
    items: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- ["):
            items.append(stripped)
        elif stripped.startswith("- "):
            items.append(stripped[2:].strip())
        else:
            items.append(stripped)
    return items


def merge_section_bullets(content: str, heading: str, entries: list[str]) -> str:
    """Merge normalized bullet entries into an H2 section without duplicates."""
    existing = get_section_content(content, heading)
    items: list[str] = []
    seen: set[str] = set()
    for raw in parse_bullet_lines(existing) + [entry.strip() for entry in entries if entry.strip()]:
        normalized = raw[2:].strip() if raw.startswith("- ") else raw.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        items.append(f"- {normalized}")
    return set_section_content(content, heading, "\n".join(items))


def upsert_section_bullets(content: str, heading: str, entries: dict[str, str]) -> str:
    """Upsert keyed bullet entries in an H2 section while preserving unrelated bullets."""
    existing = get_section_content(content, heading)
    keyed_items = {key.strip(): value.strip() for key, value in entries.items() if key.strip() and value.strip()}
    lines: list[str] = []
    seen_keys: set[str] = set()

    for raw_line in existing.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = line[2:].strip() if line.startswith("- ") else line
        replaced = False
        for key, value in keyed_items.items():
            prefix = f"{key}:"
            if normalized.startswith(prefix):
                if key not in seen_keys:
                    lines.append(f"- {key}: {value}")
                    seen_keys.add(key)
                replaced = True
                break
        if not replaced:
            lines.append(f"- {normalized}" if not normalized.startswith("- ") else normalized)

    for key, value in keyed_items.items():
        if key not in seen_keys:
            lines.append(f"- {key}: {value}")
    return set_section_content(content, heading, "\n".join(lines))


def parse_task_brief(content: str) -> ParsedTaskBrief:
    """Parse TASK_BRIEF.md into structured fields."""
    return ParsedTaskBrief(
        type=get_section_content(content, "Type").strip(),
        goal=get_section_content(content, "Goal").strip(),
        in_scope=parse_bullet_lines(get_section_content(content, "In Scope")),
        out_of_scope=parse_bullet_lines(get_section_content(content, "Out of Scope")),
        acceptance_criteria=parse_bullet_lines(get_section_content(content, "Acceptance Criteria")),
        constraints=parse_bullet_lines(get_section_content(content, "Constraints")),
        risk_level=get_section_content(content, "Risk Level").strip(),
        tags=parse_bullet_lines(get_section_content(content, "Tags")),
        repro_steps=parse_bullet_lines(get_section_content(content, "Repro Steps")),
    )


def parse_verify_checklist(content: str) -> ParsedVerifyChecklist:
    """Parse VERIFY_CHECKLIST.md checkbox state."""
    build = get_section_content(content, "Build")
    tests = get_section_content(content, "Tests")
    mobile = get_section_content(content, "Mobile")
    regression = get_section_content(content, "Regression")
    return ParsedVerifyChecklist(
        build_success="- [x] success" in build.lower(),
        tests_passed="- [x] targeted tests pass" in tests.lower(),
        mobile_flow_verified="- [x] flow verified" in mobile.lower(),
        mobile_ui_correct="- [x] ui correct" in mobile.lower(),
        mobile_permissions_correct="- [x] permissions correct" in mobile.lower(),
        regression_ok="- [x] critical paths ok" in regression.lower(),
    )


def parse_result_document(content: str) -> ParsedResultDocument:
    """Parse RESULT.md into structured fields."""
    return ParsedResultDocument(
        changed_files=parse_bullet_lines(get_section_content(content, "Changed Files")),
        build_result=get_section_content(content, "Build Result").strip(),
        test_result=get_section_content(content, "Test Result").strip(),
        mobile_verification=get_section_content(content, "Mobile Verification").strip(),
        known_issues=parse_bullet_lines(get_section_content(content, "Known Issues")),
        follow_ups=parse_bullet_lines(get_section_content(content, "Follow-ups")),
    )
