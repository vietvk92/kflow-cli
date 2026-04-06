"""Configuration migration helpers."""

from __future__ import annotations

from typing import Any


CURRENT_CONFIG_VERSION = 1


def migrate_config(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Migrate a config payload to the current schema version."""
    source = dict(payload) if isinstance(payload, dict) else {}
    migrated = dict(source)
    warnings: list[str] = []
    changes: list[str] = []

    raw_version = migrated.get("version")
    try:
        original_version = int(raw_version) if raw_version is not None else 0
    except (TypeError, ValueError):
        original_version = 0
        warnings.append(f"invalid config version {raw_version!r}; assuming legacy schema")

    if original_version <= 0:
        migrated["version"] = CURRENT_CONFIG_VERSION
        changes.append(f"set version={CURRENT_CONFIG_VERSION}")

    output = migrated.get("output")
    if isinstance(output, dict) and "json_enabled" in output and "json" not in output:
        output["json"] = output.pop("json_enabled")
        changes.append("migrated output.json_enabled to output.json")

    policy = migrated.get("policy")
    workflow_file = migrated.get("workflow_file")
    if isinstance(policy, dict):
        if "fallback_to_embedded" not in policy:
            policy["fallback_to_embedded"] = True
            changes.append("set policy.fallback_to_embedded=true")
        if workflow_file and "file" not in policy:
            policy["file"] = workflow_file
            changes.append("set policy.file from workflow_file")
        if "source" not in policy:
            policy["source"] = "file" if workflow_file else "embedded"
            changes.append("set policy.source from workflow presence")

    migrated_flag = bool(changes or warnings or original_version != CURRENT_CONFIG_VERSION)
    report = {
        "original_version": original_version,
        "current_version": CURRENT_CONFIG_VERSION,
        "migrated": migrated_flag,
        "changes": changes,
        "warnings": warnings,
    }
    return migrated, report
