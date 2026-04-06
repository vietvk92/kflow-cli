"""Task models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


TaskType = Literal["feat", "bug", "refactor", "spike"]
TaskStatusValue = Literal[
    "created",
    "brief_ready",
    "context_ready",
    "editing",
    "build_pending",
    "verification_pending",
    "blocked",
    "done",
]
RiskLevel = Literal["low", "medium", "high"]


class TaskRecord(BaseModel):
    """Persisted task state."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    type: TaskType
    status: TaskStatusValue = "created"
    risk_level: RiskLevel = "medium"
    created_at: str
    updated_at: str
    tags: list[str] = Field(default_factory=list)
    task_dir: str
    phase_ref: str | None = None

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def _normalize_timestamp(cls, value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()).isoformat()
        return value


class ParsedTaskBrief(BaseModel):
    """Structured values parsed from TASK_BRIEF.md."""

    model_config = ConfigDict(extra="ignore")

    type: str = ""
    goal: str = ""
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    risk_level: str = ""
    tags: list[str] = Field(default_factory=list)
    repro_steps: list[str] = Field(default_factory=list)


class ParsedVerifyChecklist(BaseModel):
    """Structured values parsed from VERIFY_CHECKLIST.md."""

    model_config = ConfigDict(extra="ignore")

    build_success: bool = False
    tests_passed: bool = False
    mobile_flow_verified: bool = False
    mobile_ui_correct: bool = False
    mobile_permissions_correct: bool = False
    regression_ok: bool = False


class ParsedResultDocument(BaseModel):
    """Structured values parsed from RESULT.md."""

    model_config = ConfigDict(extra="ignore")

    changed_files: list[str] = Field(default_factory=list)
    build_result: str = ""
    test_result: str = ""
    mobile_verification: str = ""
    known_issues: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
