"""Console helpers."""

from rich.panel import Panel
from rich.console import Console
from rich.text import Text

from kflow.models.results import OperationResult


def build_console(color: bool = True) -> Console:
    """Create a Rich console instance."""
    return Console(no_color=not color)


def render_result(console: Console, result: OperationResult) -> None:
    """Render a command result using simple Rich sections."""
    severity_styles = {
        "pass": "green",
        "warning": "yellow",
        "required": "cyan",
        "blocked": "red",
        "info": "blue",
    }
    lines: list[Text] = []
    for message in result.messages:
        prefix = message.severity.upper().ljust(8)
        text = Text()
        text.append(prefix, style=f"bold {severity_styles.get(message.severity, 'white')}")
        text.append(message.text)
        lines.append(text)
    body = Text("\n")
    for index, line in enumerate(lines):
        if index:
            body.append("\n")
        body.append(line)
    title = result.command
    border_style = {
        "ok": "green",
        "warning": "yellow",
        "blocked": "red",
        "error": "red",
    }.get(result.status, "white")
    console.print(Panel(body, title=title, border_style=border_style))
