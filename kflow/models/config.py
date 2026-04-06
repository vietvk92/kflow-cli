"""Configuration models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProjectType = Literal["ios", "generic"]
OutputFormat = Literal["text", "json"]


class PathsConfig(BaseModel):
    """Filesystem paths used by KFlow."""

    model_config = ConfigDict(extra="ignore")

    tasks_dir: str = ".kflow/tasks"
    artifacts_dir: str = ".kflow/artifacts"
    planning_dir: str = ".planning"
    intake_dir: str = "specs"


class DefaultsConfig(BaseModel):
    """Runtime defaults for commands."""

    model_config = ConfigDict(extra="ignore")

    simulator: str = "iPhone 16 Pro"
    output_format: OutputFormat = "text"


class PolicyConfig(BaseModel):
    """Policy source configuration."""

    model_config = ConfigDict(extra="ignore")

    source: Literal["file", "embedded"] = "embedded"
    file: str | None = None
    fallback_to_embedded: bool = True


class GSDAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = True
    planning_dir: str = ".planning"


class CommandAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    command: str | None = None


class GitNexusAdapterConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    enabled: bool = False
    command: str = "gitnexus"


class AdaptersConfig(BaseModel):
    """Optional integration settings."""

    model_config = ConfigDict(extra="ignore")

    gsd: GSDAdapterConfig = Field(default_factory=GSDAdapterConfig)
    gitnexus: GitNexusAdapterConfig = Field(default_factory=GitNexusAdapterConfig)
    build: CommandAdapterConfig = Field(default_factory=CommandAdapterConfig)
    test: CommandAdapterConfig = Field(default_factory=CommandAdapterConfig)
    mobile_verify: CommandAdapterConfig = Field(default_factory=CommandAdapterConfig)


class OutputConfig(BaseModel):
    """Output-related CLI options."""

    model_config = ConfigDict(extra="ignore")

    color: bool = True
    json_enabled: bool = Field(default=False, alias="json")
    verbose: bool = False


class ProjectConfig(BaseModel):
    """Full project configuration model."""

    model_config = ConfigDict(extra="ignore")

    version: int = 1
    project_name: str
    project_type: ProjectType = "generic"
    repo_root: str
    workflow_file: str | None = None
    paths: PathsConfig = Field(default_factory=PathsConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    @property
    def repo_root_path(self) -> Path:
        return Path(self.repo_root)
