"""Centralized stop-condition evaluation for task doctor and closeout."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StopConditionEvaluation(BaseModel):
    """Structured stop-condition output."""

    model_config = ConfigDict(extra="ignore")

    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    triggered: list[str] = Field(default_factory=list)

    def add_blocker(self, code: str, message: str, next_step: str | None = None) -> None:
        if message not in self.blockers:
            self.blockers.append(message)
        if code not in self.triggered:
            self.triggered.append(code)
        if next_step and next_step not in self.next_steps:
            self.next_steps.append(next_step)

    def add_warning(self, code: str, message: str, next_step: str | None = None) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
        if code not in self.triggered:
            self.triggered.append(code)
        if next_step and next_step not in self.next_steps:
            self.next_steps.append(next_step)


def evaluate_stop_conditions(
    *,
    closeout: bool,
    brief_exists: bool,
    goal_present: bool,
    acceptance_present: bool,
    risk_present: bool,
    acceptance_has_conflict_marker: bool,
    change_plan_exists: bool,
    high_risk_missing_test_plan: bool,
    result_exists: bool,
    result_changed_files_stale: bool,
    result_build_missing: bool,
    result_test_missing: bool,
    result_known_issues_missing: bool,
    diff_available: bool,
    diff_has_code_changes: bool,
    impacted_symbols_present: bool,
    build_evidence: str,
    test_evidence: str,
    mobile_evidence: str,
    mobile_required: bool,
    verify_exists: bool,
    mobile_acknowledged: bool,
    require_change_plan: bool,
    require_result_file: bool,
    require_verify_if_flagged: bool,
) -> StopConditionEvaluation:
    """Evaluate explicit stop conditions separate from doctor orchestration."""
    result = StopConditionEvaluation()

    if not brief_exists:
        result.add_blocker("brief_missing", "TASK_BRIEF.md missing")
        return result

    if not goal_present:
        result.add_blocker("goal_missing", "task goal missing", "Fill the Goal section in TASK_BRIEF.md.")
    if not acceptance_present:
        result.add_blocker("acceptance_missing", "acceptance criteria missing", "Add acceptance criteria in TASK_BRIEF.md.")
    if not risk_present:
        result.add_blocker("risk_missing", "risk level missing", "Set the Risk Level section in TASK_BRIEF.md.")
    if acceptance_has_conflict_marker:
        result.add_blocker(
            "acceptance_conflict_marker",
            "conflicting acceptance criteria marker found",
            "Resolve the conflicting acceptance criteria markers in TASK_BRIEF.md.",
        )

    if high_risk_missing_test_plan:
        result.add_blocker(
            "high_risk_missing_test_plan",
            "high risk task missing test plan",
            "Fill the Test Plan section in CHANGE_PLAN.md for this high-risk task.",
        )

    if not change_plan_exists and require_change_plan:
        result.add_blocker("change_plan_missing", "CHANGE_PLAN.md missing", "Create CHANGE_PLAN.md for this task.")

    if mobile_required:
        if closeout and not verify_exists and require_verify_if_flagged:
            result.add_blocker(
                "verify_missing_for_required_mobile",
                "VERIFY_CHECKLIST.md missing for required verification",
                "Create VERIFY_CHECKLIST.md and capture mobile verification evidence.",
            )
        elif closeout and verify_exists and not mobile_acknowledged:
            result.add_blocker(
                "mobile_not_acknowledged",
                "mobile verification not acknowledged",
                "Check off the relevant Mobile items in VERIFY_CHECKLIST.md.",
            )

    if not result_exists and require_result_file:
        result.add_blocker("result_missing", "RESULT.md missing", "Create RESULT.md before closeout.")
    elif result_exists:
        if result_changed_files_stale:
            message = "result changed files do not reflect current code diff"
            if closeout:
                result.add_blocker(
                    "result_changed_files_stale",
                    message,
                    "Update RESULT.md Changed Files so it matches the current code diff.",
                )
            else:
                result.add_warning(
                    "result_changed_files_stale",
                    message,
                    "Update the Changed Files section in RESULT.md to include current code diff paths.",
                )
        if closeout and result_build_missing:
            result.add_blocker("result_build_missing", "RESULT.md section incomplete: Build Result", "Fill the `Build Result` section in RESULT.md.")
        if closeout and result_test_missing:
            result.add_blocker("result_test_missing", "RESULT.md section incomplete: Test Result", "Fill the `Test Result` section in RESULT.md.")
        if closeout and result_known_issues_missing:
            result.add_blocker("result_known_issues_missing", "RESULT.md section incomplete: Known Issues", "Fill the `Known Issues` section in RESULT.md.")

    if diff_available and diff_has_code_changes:
        if not impacted_symbols_present:
            result.add_warning(
                "diff_impacted_symbols_missing",
                "code changes detected but impacted symbols are not documented",
                "Update the Impacted Symbols section in CHANGE_PLAN.md to match the current diff.",
            )
        if build_evidence == "missing":
            message = "code changes detected but build evidence is missing"
            if closeout:
                result.add_blocker("diff_build_evidence_missing", message, "Run `kflow build` after code changes or capture build evidence.")
            else:
                result.add_warning("diff_build_evidence_missing", message, "Run `kflow build` after code changes or record equivalent build evidence.")
        if test_evidence == "missing":
            message = "code changes detected but test evidence is missing"
            if closeout:
                result.add_blocker("diff_test_evidence_missing", message, "Run `kflow test` after code changes or capture test evidence.")
            else:
                result.add_warning("diff_test_evidence_missing", message, "Run `kflow test` after code changes or record equivalent test evidence.")

    if build_evidence == "fail":
        result.add_blocker("build_evidence_failed", "build evidence indicates failure", "Re-run `kflow build` and fix the failing build.")
    if test_evidence == "fail":
        result.add_blocker("test_evidence_failed", "test evidence indicates failure", "Re-run `kflow test` and fix the failing tests.")
    if mobile_evidence == "fail":
        result.add_blocker(
            "mobile_evidence_failed",
            "mobile verification evidence indicates failure",
            "Re-run `kflow verify mobile` and resolve the failing flow.",
        )
    if closeout and mobile_required and mobile_evidence == "missing":
        result.add_blocker(
            "mobile_evidence_missing",
            "mobile verification evidence missing",
            "Run `kflow verify mobile` or record manual verification evidence.",
        )

    return result
