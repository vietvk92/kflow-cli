"""Repository analysis services."""

from __future__ import annotations

from pathlib import Path

from kflow.config.loader import load_config
from kflow.models.results import Message, OperationResult
from kflow.services.planning_service import analyze_planning_dir, discover_phase_records


class AnalyzeService:
    """Analyze repository planning signals before any apply step."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.config = load_config(cwd)
        self.repo_root = self.config.repo_root_path
        self.planning_dir = self.repo_root / self.config.paths.planning_dir

    def analyze(self) -> OperationResult:
        """Scan the repository and report detected planning shape."""
        planning_summary = analyze_planning_dir(self.planning_dir)
        repo_docs = self._scan_repo_docs()
        detected_phases = discover_phase_records(self.planning_dir)

        messages = [Message(severity="info", text="Repository Analysis")]
        if planning_summary["mode"] == "existing_planning":
            messages.append(Message(severity="pass", text=f"Planning artifacts detected under {self.planning_dir}"))
        elif planning_summary["mode"] == "partial_planning":
            messages.append(Message(severity="warning", text=f"Planning path exists but no phases were normalized from {self.planning_dir}"))
        else:
            messages.append(Message(severity="warning", text="No planning directory detected. Repository likely needs bootstrap mode."))

        if repo_docs["spec_count"]:
            messages.append(Message(severity="info", text=f"Detected spec-like docs: {repo_docs['spec_count']}"))
        if detected_phases:
            messages.append(Message(severity="info", text=f"Detected phases: {', '.join(str(item['phase']) for item in detected_phases)}"))
        else:
            messages.append(Message(severity="warning", text="No phases detected from the configured planning path."))

        next_steps = ["Run `kflow plan` after reviewing detected planning artifacts."]
        if planning_summary["mode"] == "no_planning":
            next_steps.append("Bootstrap planning from sprint intake or product specs.")

        return OperationResult(
            command="analyze",
            status="warning" if planning_summary["mode"] != "existing_planning" else "ok",
            messages=messages,
            data={
                "scope": {
                    "kind": "repo_analysis",
                    "repo_root": str(self.repo_root),
                    "planning_dir": str(self.planning_dir),
                },
                "summary": {
                    "planning_mode": planning_summary["mode"],
                    "phase_count": planning_summary["phase_count"],
                    "spec_count": repo_docs["spec_count"],
                },
                "planning": planning_summary,
                "repo_docs": repo_docs,
                "next_steps": next_steps,
            },
        )

    def _scan_repo_docs(self) -> dict[str, object]:
        """Find likely planning and spec documents outside managed runtime state."""
        matches = {
            "specs": [],
            "planning_notes": [],
        }
        for path in sorted(self.repo_root.rglob("*.md"), key=lambda item: str(item)):
            relative = path.relative_to(self.repo_root)
            if relative.parts and relative.parts[0] in {".git", ".kflow", ".venv", "venv", "__pycache__"}:
                continue
            name = path.name.lower()
            if any(token in name for token in ("spec", "prd", "requirements")):
                matches["specs"].append(str(relative))
            elif any(token in name for token in ("plan", "context", "summary", "checklist", "roadmap")):
                matches["planning_notes"].append(str(relative))
        return {
            "spec_count": len(matches["specs"]),
            "planning_note_count": len(matches["planning_notes"]),
            "specs": matches["specs"][:20],
            "planning_notes": matches["planning_notes"][:20],
        }
