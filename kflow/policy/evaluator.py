"""Policy evaluation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kflow.models.policy import PolicyModel, RuleMessages
from kflow.models.task import TaskRecord


class PolicyEvaluation(BaseModel):
    """Policy evaluation output."""

    model_config = ConfigDict(extra="ignore")

    requirements: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)

    def add_next_step(self, text: str) -> None:
        if text not in self.next_steps:
            self.next_steps.append(text)

    def add_requirement(self, text: str) -> None:
        if text not in self.requirements:
            self.requirements.append(text)

    def add_warning(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    def add_blocker(self, text: str) -> None:
        if text not in self.blockers:
            self.blockers.append(text)


def evaluate_task_policy(
    task: TaskRecord,
    policy: PolicyModel,
    *,
    context: dict[str, Any] | None = None,
) -> PolicyEvaluation:
    """Evaluate policy-derived requirements for a task."""
    result = PolicyEvaluation()
    context = context or {}
    diff_summary = context.get("diff_summary", {}) or {}
    env_statuses = context.get("env_statuses", {}) or {}
    evidence_statuses = context.get("evidence_statuses", {}) or {}
    phase_state = context.get("phase_state", {}) or {}
    phase_task_state = context.get("phase_task_state", {}) or {}
    project_type = str(context.get("project_type", "generic") or "generic")
    phase_ref = str(context.get("phase_ref", task.phase_ref or "") or "")
    has_code_changes = bool(diff_summary.get("has_code_changes"))
    change_plan_has_test_plan = bool(context.get("change_plan_has_test_plan"))
    impacted_symbols_count = int(context.get("impacted_symbols_count", 0) or 0)
    diff_rule = policy.diff_rules
    _apply_rule_messages(result, diff_rule.messages)

    for adapter_name in policy.required_adapters:
        adapter_status = str(env_statuses.get(adapter_name, "missing"))
        if adapter_status != "present":
            result.add_blocker(f"required adapter unavailable: {adapter_name}")
            result.add_next_step(f"Enable or configure the {adapter_name} adapter in .kflow/config.yaml.")

    project_rule = _lookup_rule(policy.project_rules, project_type)
    if project_rule:
        _apply_rule_messages(result, project_rule.messages)
        _apply_evidence_rules(
            result,
            label=f"{project_type} project",
            require_build_evidence=project_rule.require_build_evidence,
            require_test_evidence=project_rule.require_test_evidence,
            require_mobile_verify=project_rule.require_mobile_verify,
            evidence_statuses=evidence_statuses,
        )
    phase_rule = _lookup_rule(policy.phase_rules, phase_ref) if phase_ref else None
    if phase_rule:
        _apply_rule_messages(result, phase_rule.messages)
        _apply_evidence_rules(
            result,
            label=f"phase {phase_ref}",
            require_build_evidence=phase_rule.require_build_evidence,
            require_test_evidence=phase_rule.require_test_evidence,
            require_mobile_verify=phase_rule.require_mobile_verify,
            evidence_statuses=evidence_statuses,
        )
        if phase_rule.require_docs_ready:
            if not bool(phase_state.get("context_ready")) or not bool(phase_state.get("plan_ready")):
                result.add_blocker(f"planning docs not ready for phase {phase_ref}")
                result.add_next_step(f"Complete CONTEXT.md and PLAN.md for phase {phase_ref} before proceeding.")
        if phase_rule.require_checklist_complete and not bool(phase_state.get("checklist_complete")):
            result.add_blocker(f"phase checklist incomplete: {phase_ref}")
            result.add_next_step(f"Complete READY_CHECKLIST.md for phase {phase_ref} before proceeding.")
        if phase_rule.require_no_failing_linked_tasks and bool(phase_task_state.get("has_failing_linked_tasks")):
            result.add_blocker(f"linked task execution failing in phase {phase_ref}")
            result.add_next_step(f"Resolve failing build, test, or mobile verification evidence on linked tasks in phase {phase_ref}.")
        if phase_rule.require_no_other_open_tasks and int(phase_task_state.get("other_open_task_count", 0) or 0) > 0:
            result.add_blocker(f"other linked tasks still open in phase {phase_ref}")
            result.add_next_step(f"Close or explicitly defer other open tasks in phase {phase_ref} before proceeding.")

    for tag in task.tags:
        tag_rule = _lookup_rule(policy.tag_rules, tag)
        if not tag_rule:
            continue
        _apply_rule_messages(result, tag_rule.messages)
        if tag_rule.require_manual_review:
            result.add_warning(f"manual review required for tag: {tag}")
            result.add_next_step(f"Record manual review outcome for `{tag}`-tagged work in RESULT.md or review notes.")
        if tag_rule.require_mobile_verify:
            result.add_requirement(f"mobile verification required for tag: {tag}")
            result.add_next_step("Run `kflow verify mobile` and update VERIFY_CHECKLIST.md for the active task.")
        if tag_rule.require_build_evidence:
            _apply_evidence_rules(
                result,
                label=f"tag {tag}",
                require_build_evidence=True,
                require_test_evidence=False,
                require_mobile_verify=False,
                evidence_statuses=evidence_statuses,
            )
        if tag_rule.require_test_evidence:
            _apply_evidence_rules(
                result,
                label=f"tag {tag}",
                require_build_evidence=False,
                require_test_evidence=True,
                require_mobile_verify=False,
                evidence_statuses=evidence_statuses,
            )
        if tag_rule.require_test_plan_if_code_changes and has_code_changes and not change_plan_has_test_plan:
            result.add_requirement(f"test plan required for tag: {tag}")
            result.add_next_step(f"Fill the Test Plan section in CHANGE_PLAN.md for `{tag}`-tagged code changes.")

    trigger_tags = set(policy.requires_mobile_verify_if.tags)
    if trigger_tags.intersection(task.tags):
        result.add_requirement("mobile verification required")
        result.add_next_step("Update VERIFY_CHECKLIST.md after manual or scripted verification.")
    task_rule = policy.task_rules.get(task.type)
    if task_rule and task_rule.require_repro_steps:
        _apply_rule_messages(result, task_rule.messages)
        result.add_requirement("repro steps required for bug tasks")
        result.add_next_step("Fill the Repro Steps section in TASK_BRIEF.md.")
    elif task_rule:
        _apply_rule_messages(result, task_rule.messages)
    risk_rule = policy.risk_rules.get(task.risk_level)
    if risk_rule and risk_rule.require_manual_review:
        _apply_rule_messages(result, risk_rule.messages)
        result.add_warning("manual review required for high-risk task")
        result.add_next_step("Record manual review outcome in RESULT.md or review notes.")
        if (
            diff_rule.require_test_plan_for_high_risk_code_changes
            and has_code_changes
            and not change_plan_has_test_plan
        ):
            result.add_requirement("test plan required for high-risk code changes")
            result.add_next_step("Fill the Test Plan section in CHANGE_PLAN.md before proceeding with high-risk code changes.")
    elif risk_rule:
        _apply_rule_messages(result, risk_rule.messages)
    if (
        task_rule
        and task_rule.forbid_behavior_change
        and diff_rule.require_behavior_review_for_refactor_changes
        and has_code_changes
    ):
        result.add_warning("behavior change review required for refactor task")
        result.add_next_step("Review the current diff and confirm there is no unintended behavior change.")
    if diff_rule.require_impacted_symbols_for_code_changes and has_code_changes and impacted_symbols_count == 0:
        result.add_warning("impacted symbols should be documented for code changes")
        result.add_next_step("Document impacted symbols in CHANGE_PLAN.md for the current code diff.")
    return result


def evaluate_sprint_policy(
    policy: PolicyModel,
    *,
    summary: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> PolicyEvaluation:
    """Evaluate policy-derived requirements for sprint-wide status."""
    result = PolicyEvaluation()
    summary = summary or {}
    context = context or {}
    sprint_rule = policy.sprint_rules
    _apply_rule_messages(result, sprint_rule.messages)

    current_phase = str(summary.get("current_phase", "") or "")
    current_phase_entry = context.get("current_phase_entry") or {}
    task_totals = summary.get("task_totals", {}) or {}
    evidence_totals = summary.get("evidence_totals", {}) or {}
    planning_dir = str(context.get("planning_dir", ".planning"))

    if sprint_rule.require_current_phase_ready and current_phase and str(current_phase_entry.get("readiness", "unknown")) != "ready":
        result.add_blocker(f"current phase not ready for sprint policy: {current_phase}")
        result.add_next_step(f"Bring phase {current_phase} to ready status under `{planning_dir}` before advancing sprint-level gates.")
    if sprint_rule.require_no_open_tasks and int(task_totals.get("open", 0) or 0) > 0:
        result.add_blocker("open sprint tasks violate sprint policy")
        result.add_next_step("Close, defer, or explicitly accept remaining linked sprint tasks.")
    if sprint_rule.require_no_failing_build and int(((evidence_totals.get("build", {}) or {}).get("fail", 0) or 0)) > 0:
        result.add_blocker("failing build evidence violates sprint policy")
        result.add_next_step("Resolve failing build evidence on linked sprint tasks.")
    if sprint_rule.require_no_failing_test and int(((evidence_totals.get("test", {}) or {}).get("fail", 0) or 0)) > 0:
        result.add_blocker("failing test evidence violates sprint policy")
        result.add_next_step("Resolve failing test evidence on linked sprint tasks.")
    if sprint_rule.require_no_failing_mobile and int(((evidence_totals.get("mobile", {}) or {}).get("fail", 0) or 0)) > 0:
        result.add_blocker("failing mobile verification violates sprint policy")
        result.add_next_step("Resolve failing mobile verification evidence on linked sprint tasks.")
    return result


def _apply_rule_messages(result: PolicyEvaluation, messages: RuleMessages) -> None:
    """Project declarative rule messages into the evaluation result."""
    for requirement in messages.requirements:
        result.add_requirement(requirement)
    for warning in messages.warnings:
        result.add_warning(warning)
    for blocker in messages.blockers:
        result.add_blocker(blocker)
    for next_step in messages.next_steps:
        result.add_next_step(next_step)


def _apply_evidence_rules(
    result: PolicyEvaluation,
    *,
    label: str,
    require_build_evidence: bool,
    require_test_evidence: bool,
    require_mobile_verify: bool,
    evidence_statuses: dict[str, Any],
) -> None:
    """Apply build/test/mobile evidence requirements for a project or phase scope."""
    if require_mobile_verify:
        result.add_requirement(f"mobile verification required for {label}")
        result.add_next_step("Run `kflow verify mobile` and update VERIFY_CHECKLIST.md for the active task.")
    if require_build_evidence:
        build_status = str(evidence_statuses.get("build", "missing"))
        if build_status == "fail":
            result.add_blocker(f"build evidence failed for {label}")
            result.add_next_step("Re-run `kflow build`, fix failures, and refresh RESULT.md before proceeding.")
        elif build_status == "missing":
            result.add_requirement(f"build evidence required for {label}")
            result.add_next_step("Run `kflow build` to capture build evidence for the active task.")
    if require_test_evidence:
        test_status = str(evidence_statuses.get("test", "missing"))
        if test_status == "fail":
            result.add_blocker(f"test evidence failed for {label}")
            result.add_next_step("Re-run `kflow test`, fix failures, and refresh RESULT.md before proceeding.")
        elif test_status == "missing":
            result.add_requirement(f"test evidence required for {label}")
            result.add_next_step("Run `kflow test` to capture test evidence for the active task.")


def _lookup_rule(rule_map: dict[Any, Any], key: str) -> Any | None:
    """Look up a rule by stringified key to tolerate YAML numeric keys."""
    if key in rule_map:
        return rule_map[key]
    for candidate, rule in rule_map.items():
        if str(candidate) == key:
            return rule
    return None
