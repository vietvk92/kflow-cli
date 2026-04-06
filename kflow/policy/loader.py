"""Policy loading."""

from __future__ import annotations

from pathlib import Path
import re

from pydantic import ValidationError
import yaml

from kflow.models.policy import LoadedPolicy, PolicyModel
from kflow.policy.defaults import DEFAULT_POLICY
from kflow.utils.paths import find_workflow_file
from kflow.utils.yaml_io import load_yaml


def _embedded(source: str, warnings: list[str] | None = None) -> LoadedPolicy:
    return LoadedPolicy(
        source=source,
        warnings=warnings or [],
        policy=PolicyModel.model_validate(DEFAULT_POLICY),
    )


def _extract_workflow_policy_block(workflow_path: Path) -> dict | None:
    """Extract a machine-readable policy block from a workflow markdown file."""
    content = workflow_path.read_text(encoding="utf-8")
    patterns = [
        r"```kflow-policy\s*\n(.*?)\n```",
        r"```yaml\s*\n#\s*kflow-policy\s*\n(.*?)\n```",
        r"```yml\s*\n#\s*kflow-policy\s*\n(.*?)\n```",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.DOTALL | re.IGNORECASE)
        if not match:
            continue
        payload = yaml.safe_load(match.group(1))
        return payload or {}
    return None


def load_policy(
    repo_root: Path,
    configured_file: str | None = None,
    workflow_file: str | None = None,
) -> LoadedPolicy:
    """Load policy from file or embedded defaults."""
    local_policy = repo_root / ".kflow" / "policy.yaml"
    if local_policy.exists():
        try:
            return LoadedPolicy(
                source=str(local_policy),
                policy=PolicyModel.model_validate(load_yaml(local_policy)),
            )
        except ValidationError:
            return _embedded("embedded", [f"Invalid policy file ignored: {local_policy}"])
    if configured_file:
        path = repo_root / configured_file if not Path(configured_file).is_absolute() else Path(configured_file)
        if path.exists() and path.suffix in {".yaml", ".yml"}:
            try:
                return LoadedPolicy(
                    source=str(path),
                    policy=PolicyModel.model_validate(load_yaml(path)),
                )
            except ValidationError:
                return _embedded("embedded", [f"Invalid configured policy ignored: {path}"])
    workflow_path = find_workflow_file(repo_root, workflow_file)
    if workflow_path and workflow_path.exists():
        try:
            extracted = _extract_workflow_policy_block(workflow_path)
            if extracted is not None:
                return LoadedPolicy(
                    source=str(workflow_path),
                    policy=PolicyModel.model_validate(extracted),
                )
        except (yaml.YAMLError, ValidationError):
            return _embedded("embedded", [f"Invalid workflow policy block ignored: {workflow_path}"])
    return _embedded("embedded")
