"""Validation helpers."""

from pydantic import ValidationError

from kflow.core.exceptions import KFlowValidationError


def to_user_validation_error(exc: ValidationError) -> KFlowValidationError:
    """Convert Pydantic errors to a user-facing validation error."""
    messages = []
    for issue in exc.errors():
        location = ".".join(str(part) for part in issue.get("loc", ()))
        detail = issue.get("msg", "Invalid value")
        messages.append(f"{location}: {detail}" if location else detail)
    return KFlowValidationError(messages=messages)
