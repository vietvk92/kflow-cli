"""Initialization service."""

from __future__ import annotations

from pathlib import Path

from kflow.config.defaults import build_default_config
from kflow.config.loader import serialize_config
from kflow.models.config import ProjectConfig
from kflow.models.results import InitResult, Message
from kflow.services.env_service import EnvironmentService
from kflow.utils.files import ensure_directory, write_text
from kflow.utils.paths import detect_project_type, find_repo_root, find_workflow_file


class InitService:
    """Initialize KFlow files and directories."""

    def __init__(self, env_service: EnvironmentService | None = None) -> None:
        self.env_service = env_service or EnvironmentService()

    def initialize(
        self,
        cwd: Path,
        *,
        workflow: str | None = None,
        project_type: str | None = None,
        force: bool = False,
    ) -> InitResult:
        repo_root = find_repo_root(cwd) or cwd.resolve()
        detected_project_type = project_type or detect_project_type(repo_root)
        workflow_path = find_workflow_file(repo_root, workflow)
        config = build_default_config(
            repo_root=repo_root,
            project_name=repo_root.name,
            project_type=detected_project_type,
            workflow_file=str(workflow_path.relative_to(repo_root)) if workflow_path and workflow_path.is_relative_to(repo_root) else (str(workflow_path) if workflow_path else None),
        )
        self._write_layout(config, force=force)
        env_result = self.env_service.detect(repo_root, config)
        messages = [
            Message(severity="pass", text=f"Initialized KFlow in {repo_root}"),
            Message(severity="info", text=f"Project type: {config.project_type}"),
        ]
        if workflow_path:
            messages.append(Message(severity="pass", text=f"Workflow: {workflow_path.name}"))
        else:
            messages.append(Message(severity="warning", text="Workflow file missing. Embedded policy fallback configured."))
        messages.append(Message(severity="info", text="Next: run `kflow env detect` and `kflow config validate`."))
        return InitResult(
            command="init",
            status="warning" if env_result.environment.warnings else "ok",
            messages=messages,
            data={"config_path": str(repo_root / ".kflow" / "config.yaml")},
            environment=env_result.environment,
        )

    def _write_layout(self, config: ProjectConfig, *, force: bool) -> None:
        repo_root = config.repo_root_path
        base = repo_root / ".kflow"
        for path in (
            base,
            base / "state",
            base / "state" / "tasks",
            base / "cache",
            base / "logs",
            base / "tasks",
            base / "artifacts",
        ):
            ensure_directory(path)
        write_text(base / "config.yaml", serialize_config(config), overwrite=force or not (base / "config.yaml").exists())
