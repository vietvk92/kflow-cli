"""Application exceptions."""


class KFlowError(Exception):
    """Base application error."""


class KFlowValidationError(KFlowError):
    """Raised for user-facing validation errors."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages


class KFlowConfigError(KFlowError):
    """Raised when configuration cannot be loaded."""


class KFlowFilesystemError(KFlowError):
    """Raised when file operations fail."""


class KFlowShellError(KFlowError):
    """Raised when a shell command fails unexpectedly."""
