"""Planning proposal services."""

from __future__ import annotations

from pathlib import Path

from kflow.config.loader import load_config
from kflow.models.results import Message, OperationResult
from kflow.services.analyze_service import AnalyzeService


class PlanService:
    """Propose and attach planning state from repository artifacts."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.config = load_config(cwd)
        self.repo_root = self.config.repo_root_path
        self.planning_dir = self.repo_root / self.config.paths.planning_dir

    def plan(self, apply: bool = False) -> OperationResult:
        """Propose a normalized sprint, phase, and task state."""
        analyzer = AnalyzeService(self.cwd)
        analysis = analyzer.analyze()
        analysis_data = analysis.data

        mode = analysis_data["summary"]["planning_mode"]
        if mode == "no_planning":
            sprint_stage = "intake"
        else:
            sprint_stage = "execution" if analysis_data["summary"]["phase_count"] > 0 else "planning"

        phase_mappings = analysis_data["planning"]["phases"]
        
        proposed_tasks = []
        for spec in analysis_data["repo_docs"]["specs"]:
            proposed_tasks.append({
                "name": f"Implementation for {Path(spec).with_suffix('').name}",
                "source": spec,
            })

        ambiguities: list[str] = []
        if mode == "partial_planning":
            ambiguities.append(f"Planning directory {self.planning_dir.name} exists but no valid phase documents were normalized.")

        messages = [
            Message(severity="info", text="Planning Proposal Generated"),
            Message(severity="pass", text=f"Sprint inferred stage: {sprint_stage}"),
            Message(severity="pass", text=f"Detected phase mappings: {len(phase_mappings)}"),
        ]

        if proposed_tasks:
            messages.append(Message(severity="info", text=f"Proposed task drafts from specs: {len(proposed_tasks)}"))
            
        if ambiguities:
            for ambiguity in ambiguities:
                messages.append(Message(severity="warning", text=ambiguity))

        if apply:
            messages.append(Message(severity="pass", text="Persisted planning state successfully."))
            
            import json
            from kflow.utils.files import ensure_directory, write_text
            
            manifest_path = self.repo_root / ".kflow" / "artifacts" / "planning_attach_manifest.json"
            ensure_directory(manifest_path.parent)
            payload = {
                "mode": mode,
                "sprint_stage": sprint_stage,
                "phases": phase_mappings,
                "proposed_tasks": proposed_tasks,
            }
            write_text(manifest_path, json.dumps(payload, indent=2) + "\n", overwrite=True)
            
            from kflow.services.task_service import TaskService
            task_service = TaskService(self.cwd)
            created_count: int = 0
            for task in proposed_tasks:
                try:
                    task_service.create_task(
                        task_type="feat",
                        name=task["name"],
                        risk="medium"
                    )
                    created_count = int(created_count) + 1
                except Exception as e:
                    messages.append(Message(severity="warning", text=f"Failed to bootstrap task '{task['name']}': {e}"))
            
            if created_count > 0:
                messages.append(Message(severity="pass", text=f"Bootstrapped {created_count} task drafts."))
        else:
            messages.append(Message(severity="warning", text="Action running in dry-run mode. Use --apply to attach and persist state."))

        return OperationResult(
            command="plan" + (" apply" if apply else ""),
            status="ok" if not ambiguities else "warning",
            messages=messages,
            data={
                "scope": {
                    "kind": "planning_proposal",
                    "repo_root": str(self.repo_root),
                    "planning_dir": str(self.planning_dir),
                },
                "sprint_stage": sprint_stage,
                "phase_mappings": phase_mappings,
                "proposed_tasks": proposed_tasks,
                "ambiguities": ambiguities,
                "is_dry_run": not apply,
            },
        )
