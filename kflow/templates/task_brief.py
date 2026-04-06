"""Task brief template."""


def render_task_brief(task_type: str, risk: str) -> str:
    """Render the task brief template."""
    return f"""# Task Brief

## Type
{task_type}

## Goal

## In Scope

## Out of Scope

## Acceptance Criteria

## Constraints

## Risk Level
{risk}

## Tags

## Repro Steps
"""
