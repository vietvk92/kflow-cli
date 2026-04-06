"""Policy models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MobileVerifyRule(BaseModel):
    """Tags that require mobile verification."""

    model_config = ConfigDict(extra="ignore")

    tags: list[str] = Field(default_factory=list)


class RuleMessages(BaseModel):
    """Reusable declarative messages attached to a policy rule."""

    model_config = ConfigDict(extra="ignore")

    requirements: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class TaskRule(BaseModel):
    """Task-type-specific rule set."""

    model_config = ConfigDict(extra="ignore")

    require_repro_steps: bool = False
    forbid_behavior_change: bool = False
    messages: RuleMessages = Field(default_factory=RuleMessages)


class RiskRule(BaseModel):
    """Risk-specific rule set."""

    model_config = ConfigDict(extra="ignore")

    require_manual_review: bool = False
    messages: RuleMessages = Field(default_factory=RuleMessages)


class TagRule(BaseModel):
    """Tag-specific rule set."""

    model_config = ConfigDict(extra="ignore")

    require_manual_review: bool = False
    require_test_plan_if_code_changes: bool = False
    require_build_evidence: bool = False
    require_test_evidence: bool = False
    require_mobile_verify: bool = False
    messages: RuleMessages = Field(default_factory=RuleMessages)


class ProjectRule(BaseModel):
    """Project-type-specific rule set."""

    model_config = ConfigDict(extra="ignore")

    require_build_evidence: bool = False
    require_test_evidence: bool = False
    require_mobile_verify: bool = False
    messages: RuleMessages = Field(default_factory=RuleMessages)


class PhaseRule(BaseModel):
    """Phase-specific rule set."""

    model_config = ConfigDict(extra="ignore")

    require_build_evidence: bool = False
    require_test_evidence: bool = False
    require_mobile_verify: bool = False
    require_docs_ready: bool = False
    require_checklist_complete: bool = False
    require_no_failing_linked_tasks: bool = False
    require_no_other_open_tasks: bool = False
    messages: RuleMessages = Field(default_factory=RuleMessages)


class SprintRule(BaseModel):
    """Sprint-level rule set."""

    model_config = ConfigDict(extra="ignore")

    require_current_phase_ready: bool = False
    require_no_open_tasks: bool = False
    require_no_failing_build: bool = False
    require_no_failing_test: bool = False
    require_no_failing_mobile: bool = False
    messages: RuleMessages = Field(default_factory=RuleMessages)


class DiffRule(BaseModel):
    """Diff-aware rule set."""

    model_config = ConfigDict(extra="ignore")

    require_impacted_symbols_for_code_changes: bool = False
    require_test_plan_for_high_risk_code_changes: bool = False
    require_behavior_review_for_refactor_changes: bool = False
    messages: RuleMessages = Field(default_factory=RuleMessages)


class CloseoutRules(BaseModel):
    """Rules applied during task closeout."""

    model_config = ConfigDict(extra="ignore")

    require_result_file: bool = True
    require_change_plan: bool = True
    require_verify_if_flagged: bool = True


class PolicyModel(BaseModel):
    """Complete policy model."""

    model_config = ConfigDict(extra="ignore")

    required_adapters: list[str] = Field(default_factory=list)
    requires_mobile_verify_if: MobileVerifyRule = Field(default_factory=MobileVerifyRule)
    task_rules: dict[str, TaskRule] = Field(default_factory=dict)
    risk_rules: dict[str, RiskRule] = Field(default_factory=dict)
    tag_rules: dict[str, TagRule] = Field(default_factory=dict)
    project_rules: dict[str, ProjectRule] = Field(default_factory=dict)
    phase_rules: dict[str | int, PhaseRule] = Field(default_factory=dict)
    sprint_rules: SprintRule = Field(default_factory=SprintRule)
    diff_rules: DiffRule = Field(default_factory=DiffRule)
    closeout_rules: CloseoutRules = Field(default_factory=CloseoutRules)

    @field_validator("phase_rules", mode="before")
    @classmethod
    def _normalize_phase_rule_keys(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        return {str(key): rule for key, rule in value.items()}


class LoadedPolicy(BaseModel):
    """Policy plus load metadata."""

    model_config = ConfigDict(extra="ignore")

    source: str
    warnings: list[str] = Field(default_factory=list)
    policy: PolicyModel
