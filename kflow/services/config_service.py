"""Config viewing and mutation services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError
from yaml import YAMLError

from kflow.config.loader import config_path, load_config, load_config_with_meta, resolve_root, serialize_config
from kflow.core.exceptions import KFlowValidationError
from kflow.core.validator import to_user_validation_error
from kflow.models.results import Message, OperationResult
from kflow.models.config import ProjectConfig
from kflow.utils.files import write_text


def _parse_scalar(raw: str) -> Any:
    """Parse a CLI value into a YAML scalar/object."""
    try:
        return yaml.safe_load(raw)
    except YAMLError:
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            return raw[1:-1]
        return raw


def _set_nested_value(payload: dict[str, Any], dotted_path: str, value: Any) -> dict[str, Any]:
    """Set a nested key by dotted path."""
    parts = dotted_path.split(".")
    current: dict[str, Any] = payload
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            raise KeyError(dotted_path)
        current = next_value
    if parts[-1] not in current:
        raise KeyError(dotted_path)
    current[parts[-1]] = value
    return payload


class ConfigService:
    """Show and update repository config."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.repo_root = resolve_root(cwd)

    def show(self) -> OperationResult:
        config, migration = load_config_with_meta(self.cwd)
        rendered = config.model_dump(mode="json", by_alias=True)
        messages = [Message(severity="info", text=config.model_dump_json(indent=2, by_alias=True))]
        if migration["migrated"]:
            messages.append(Message(severity="warning", text=f"Config migrated from version {migration['original_version']} to {migration['current_version']} during load."))
        return OperationResult(
            command="config show",
            status="ok",
            messages=messages,
            data={"config": rendered, "migration": migration},
        )

    def validate(self) -> OperationResult:
        _, migration = load_config_with_meta(self.cwd)
        messages = [Message(severity="pass", text="Config is valid.")]
        if migration["migrated"]:
            messages.append(Message(severity="warning", text=f"Config migrated from version {migration['original_version']} to {migration['current_version']} during validation."))
        return OperationResult(
            command="config validate",
            status="ok",
            messages=messages,
            data={"migration": migration},
        )

    def set_value(self, key: str, raw_value: str) -> OperationResult:
        config = load_config(self.cwd)
        payload = config.model_dump(mode="python", by_alias=True, exclude_none=False)
        try:
            updated_payload = _set_nested_value(payload, key, _parse_scalar(raw_value))
            updated_config = ProjectConfig.model_validate(updated_payload)
        except KeyError as exc:
            raise KFlowValidationError([f"{key}: Unknown config key"]) from exc
        except ValidationError as exc:
            raise to_user_validation_error(exc) from exc

        write_text(config_path(self.repo_root), serialize_config(updated_config), overwrite=True)
        return OperationResult(
            command="config set",
            status="ok",
            messages=[
                Message(severity="pass", text=f"Updated `{key}`."),
                Message(severity="info", text=f"New value: {raw_value}"),
            ],
            data={"key": key, "value": _parse_scalar(raw_value)},
        )
