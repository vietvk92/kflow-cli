"""Task state transitions."""

from __future__ import annotations

from collections.abc import Mapping


TASK_STATE_TRANSITIONS: dict[str, set[str]] = {
    "created": {"brief_ready", "context_ready", "build_pending", "verification_pending", "blocked"},
    "brief_ready": {"context_ready", "editing", "build_pending", "verification_pending", "blocked"},
    "context_ready": {"editing", "build_pending", "verification_pending", "blocked"},
    "editing": {"build_pending", "verification_pending", "blocked"},
    "build_pending": {"verification_pending", "blocked"},
    "verification_pending": {"done", "blocked"},
    "blocked": {"editing", "build_pending", "verification_pending"},
    "done": set(),
}


def can_transition(current: str, target: str, transitions: Mapping[str, set[str]] | None = None) -> bool:
    """Return whether a task can move to a target status."""
    graph = transitions or TASK_STATE_TRANSITIONS
    return target in graph.get(current, set())
