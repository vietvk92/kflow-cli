from pathlib import Path

from kflow.policy.loader import load_policy


def test_load_policy_prefers_local_policy_file(tmp_path: Path) -> None:
    policy_dir = tmp_path / ".kflow"
    policy_dir.mkdir()
    (policy_dir / "policy.yaml").write_text(
        """
requires_mobile_verify_if:
  tags: [custom]
task_rules: {}
risk_rules: {}
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
""".strip(),
        encoding="utf-8",
    )

    loaded = load_policy(tmp_path)

    assert loaded.source.endswith(".kflow/policy.yaml")
    assert loaded.policy.requires_mobile_verify_if.tags == ["custom"]
    assert loaded.warnings == []


def test_load_policy_falls_back_to_embedded_on_invalid_file(tmp_path: Path) -> None:
    policy_dir = tmp_path / ".kflow"
    policy_dir.mkdir()
    (policy_dir / "policy.yaml").write_text("requires_mobile_verify_if: not-a-mapping", encoding="utf-8")

    loaded = load_policy(tmp_path)

    assert loaded.source == "embedded"
    assert loaded.policy.requires_mobile_verify_if.tags
    assert loaded.warnings


def test_load_policy_uses_workflow_embedded_block_when_no_policy_file(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
required_adapters: [mobile_verify]
requires_mobile_verify_if:
  tags: [workflow]
task_rules: {}
risk_rules: {}
tag_rules:
  payments:
    require_test_plan_if_code_changes: true
    require_manual_review: true
    messages:
      warnings: ["payments path requires audit trail review"]
      next_steps: ["Confirm audit-trail coverage for payments flows."]
project_rules:
  ios:
    require_build_evidence: true
phase_rules:
  7:
    require_test_evidence: true
    require_docs_ready: true
    require_no_failing_linked_tasks: true
sprint_rules:
  require_current_phase_ready: true
  messages:
    warnings: ["sprint review required before advance"]
diff_rules:
  require_impacted_symbols_for_code_changes: true
  require_test_plan_for_high_risk_code_changes: true
  require_behavior_review_for_refactor_changes: true
  messages:
    warnings: ["diff review policy active"]
closeout_rules:
  require_result_file: true
  require_change_plan: true
  require_verify_if_flagged: true
```
""".strip(),
        encoding="utf-8",
    )

    loaded = load_policy(tmp_path)

    assert loaded.source.endswith("WORKFLOW_v2_PRO.md")
    assert loaded.policy.required_adapters == ["mobile_verify"]
    assert loaded.policy.requires_mobile_verify_if.tags == ["workflow"]
    assert loaded.policy.tag_rules["payments"].require_test_plan_if_code_changes is True
    assert loaded.policy.tag_rules["payments"].require_manual_review is True
    assert loaded.policy.tag_rules["payments"].messages.warnings == ["payments path requires audit trail review"]
    assert loaded.policy.project_rules["ios"].require_build_evidence is True
    assert loaded.policy.phase_rules["7"].require_test_evidence is True
    assert loaded.policy.phase_rules["7"].require_docs_ready is True
    assert loaded.policy.phase_rules["7"].require_no_failing_linked_tasks is True
    assert loaded.policy.sprint_rules.require_current_phase_ready is True
    assert loaded.policy.sprint_rules.messages.warnings == ["sprint review required before advance"]
    assert loaded.policy.diff_rules.require_impacted_symbols_for_code_changes is True
    assert loaded.policy.diff_rules.require_test_plan_for_high_risk_code_changes is True
    assert loaded.policy.diff_rules.require_behavior_review_for_refactor_changes is True
    assert loaded.policy.diff_rules.messages.warnings == ["diff review policy active"]


def test_load_policy_falls_back_when_workflow_policy_block_is_invalid(tmp_path: Path) -> None:
    (tmp_path / "WORKFLOW_v2_PRO.md").write_text(
        """
# Workflow

```kflow-policy
requires_mobile_verify_if: nope
```
""".strip(),
        encoding="utf-8",
    )

    loaded = load_policy(tmp_path)

    assert loaded.source == "embedded"
    assert loaded.warnings
