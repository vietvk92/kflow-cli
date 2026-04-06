"""Service result models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from kflow.models.env import EnvironmentStatus
from kflow.utils.time import utc_now_iso


Severity = Literal["pass", "warning", "required", "blocked", "info"]


class Message(BaseModel):
    """Structured message item for CLI and JSON output."""

    model_config = ConfigDict(extra="ignore")

    severity: Severity
    text: str


class ResultMeta(BaseModel):
    """Stable metadata attached to every operation result."""

    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    generated_at: str = Field(default_factory=utc_now_iso)


class OperationResult(BaseModel):
    """Base result for commands."""

    model_config = ConfigDict(extra="ignore")

    command: str
    status: Literal["ok", "warning", "blocked", "error"] = "ok"
    messages: list[Message] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    meta: ResultMeta = Field(default_factory=ResultMeta)


class InitResult(OperationResult):
    """Initialization command result."""

    environment: EnvironmentStatus


class EnvironmentResult(OperationResult):
    """Environment detection result."""

    environment: EnvironmentStatus


class ExecutionEvidence(BaseModel):
    """Parsed evidence from task execution artifacts and result file."""

    model_config = ConfigDict(extra="ignore")

    build: Literal["pass", "fail", "missing"] = "missing"
    test: Literal["pass", "fail", "missing"] = "missing"
    mobile: Literal["pass", "fail", "missing", "not_required"] = "missing"
    build_summary: dict[str, Any] = Field(default_factory=dict)
    test_summary: dict[str, Any] = Field(default_factory=dict)
