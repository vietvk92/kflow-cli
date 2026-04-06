"""Embedded policy defaults."""

DEFAULT_POLICY = {
    "requires_mobile_verify_if": {
        "tags": [
            "permissions",
            "navigation",
            "onboarding",
            "settings",
            "ui_interaction",
        ]
    },
    "task_rules": {
        "bug": {"require_repro_steps": True},
        "refactor": {"forbid_behavior_change": True},
    },
    "risk_rules": {
        "high": {"require_manual_review": True},
    },
    "tag_rules": {},
    "project_rules": {},
    "phase_rules": {},
    "sprint_rules": {},
    "diff_rules": {
        "require_impacted_symbols_for_code_changes": True,
        "require_test_plan_for_high_risk_code_changes": True,
        "require_behavior_review_for_refactor_changes": True,
    },
    "closeout_rules": {
        "require_result_file": True,
        "require_change_plan": True,
        "require_verify_if_flagged": True,
    },
}
