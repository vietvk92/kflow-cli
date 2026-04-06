"""Template rendering."""

from kflow.templates.change_plan import render_change_plan
from kflow.templates.result import render_result
from kflow.templates.task_brief import render_task_brief
from kflow.templates.verify_checklist import render_verify_checklist


def render_task_templates(task_type: str, risk: str) -> dict[str, str]:
    """Render all managed task artifact templates."""
    return {
        "TASK_BRIEF.md": render_task_brief(task_type, risk),
        "CHANGE_PLAN.md": render_change_plan(),
        "VERIFY_CHECKLIST.md": render_verify_checklist(),
        "RESULT.md": render_result(),
    }
