"""Environment models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ToolStatusValue = Literal["present", "missing", "disabled", "not_applicable"]


class ToolStatus(BaseModel):
    """Status for one detected tool or capability."""

    model_config = ConfigDict(extra="ignore")

    status: ToolStatusValue
    detail: str | None = None


class EnvironmentStatus(BaseModel):
    """Structured environment detection result."""

    model_config = ConfigDict(extra="ignore")

    os_name: str
    python_version: str
    repo_root: str | None = None
    project_type: Literal["ios", "generic"] = "generic"
    git: ToolStatus
    workflow_file: ToolStatus
    config_file: ToolStatus
    xcodebuild: ToolStatus
    gitnexus: ToolStatus
    gsd: ToolStatus
    build: ToolStatus
    test: ToolStatus
    planning_dir: ToolStatus
    mobile_verify: ToolStatus
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
