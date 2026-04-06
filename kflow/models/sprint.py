"""Sprint models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


SprintStatus = Literal["active", "completed"]


class SprintRecord(BaseModel):
    """Current active sprint state persisted in current_sprint.yaml."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    status: SprintStatus
    started_at: str


class SprintHistoryEntry(BaseModel):
    """A completed sprint entry persisted in sprints.yaml."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    status: SprintStatus
    started_at: str
    closed_at: str
