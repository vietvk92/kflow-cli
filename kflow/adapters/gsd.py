"""GSD adapter scaffold."""

from __future__ import annotations

from pathlib import Path

from kflow.adapters.base import AdapterDetection, DetectionAdapter
from kflow.services.planning_service import discover_phase_dirs, inspect_phase_state, phase_ref_for_path


class GSDAdapter(DetectionAdapter):
    """Detect GSD planning availability."""

    name = "gsd"

    def __init__(self, planning_dir: str = ".planning", enabled: bool = True) -> None:
        self.planning_dir = planning_dir
        self.enabled = enabled

    def detect(self, repo_root: Path) -> AdapterDetection:
        if not self.enabled:
            return AdapterDetection(status="disabled", detail=self.planning_dir)
        path = repo_root / self.planning_dir
        return AdapterDetection(status="present" if path.exists() else "missing", detail=str(path))

    def summarize(self, repo_root: Path) -> dict[str, object]:
        """Summarize practical GSD/planning state from the planning directory."""
        planning_path = repo_root / self.planning_dir
        if not self.enabled:
            return {
                "enabled": False,
                "planning_dir": str(planning_path),
                "present": False,
                "phase_count": 0,
                "ready_phases": 0,
                "current_phase": None,
                "phases": [],
            }
        if not planning_path.exists():
            return {
                "enabled": True,
                "planning_dir": str(planning_path),
                "present": False,
                "phase_count": 0,
                "ready_phases": 0,
                "current_phase": None,
                "phases": [],
            }

        phase_dirs = discover_phase_dirs(planning_path)
        phases: list[dict[str, object]] = []
        ready_phases = 0
        current_phase: str | None = None
        for phase_dir in phase_dirs:
            phase_ref = phase_ref_for_path(phase_dir)
            state = inspect_phase_state(planning_path, phase_ref)
            if state.get("readiness") == "ready":
                ready_phases += 1
            elif current_phase is None:
                current_phase = phase_ref
            phases.append(
                {
                    "phase": phase_ref,
                    "readiness": state.get("readiness"),
                    "context_ready": bool(state.get("context_ready")),
                    "plan_ready": bool(state.get("plan_ready")),
                    "checklist_complete": bool(state.get("checklist_complete")),
                }
            )
        if current_phase is None and phases:
            current_phase = str(phases[-1]["phase"])

        return {
            "enabled": True,
            "planning_dir": str(planning_path),
            "present": True,
            "phase_count": len(phases),
            "ready_phases": ready_phases,
            "current_phase": current_phase,
            "phases": phases,
        }
