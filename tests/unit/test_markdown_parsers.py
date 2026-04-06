from kflow.utils.markdown import parse_result_document, parse_task_brief, parse_verify_checklist


def test_parse_task_brief_extracts_lists_and_scalar_sections() -> None:
    content = """# Task Brief

## Type
bug

## Goal
Fix fallback

## In Scope
- permissions

## Out of Scope
- onboarding

## Acceptance Criteria
- fallback works

## Constraints
- no refactor

## Risk Level
high

## Tags
- permissions
- settings

## Repro Steps
- open app
"""
    parsed = parse_task_brief(content)
    assert parsed.type == "bug"
    assert parsed.goal == "Fix fallback"
    assert parsed.acceptance_criteria == ["fallback works"]
    assert parsed.tags == ["permissions", "settings"]
    assert parsed.repro_steps == ["open app"]


def test_parse_verify_checklist_extracts_checkbox_states() -> None:
    content = """# Verification Checklist

## Build
- [x] success

## Tests
- [x] targeted tests pass

## Mobile
- [x] flow verified
- [ ] UI correct
- [x] permissions correct

## Regression
- [ ] critical paths OK
"""
    parsed = parse_verify_checklist(content)
    assert parsed.build_success is True
    assert parsed.tests_passed is True
    assert parsed.mobile_flow_verified is True
    assert parsed.mobile_ui_correct is False
    assert parsed.mobile_permissions_correct is True
    assert parsed.regression_ok is False


def test_parse_result_document_extracts_sections() -> None:
    content = """# Result

## Changed Files
- RESULT.md

## Build Result
pass

## Test Result
pass

## Mobile Verification
fail

## Known Issues
- none

## Follow-ups
- Closed at now
"""
    parsed = parse_result_document(content)
    assert parsed.changed_files == ["RESULT.md"]
    assert parsed.build_result == "pass"
    assert parsed.test_result == "pass"
    assert parsed.mobile_verification == "fail"
    assert parsed.known_issues == ["none"]
    assert parsed.follow_ups == ["Closed at now"]
