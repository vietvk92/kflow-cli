"""Artifact listing and collection services."""

from __future__ import annotations

import json
from pathlib import Path

from kflow.models.results import Message, OperationResult
from kflow.policy.evaluator import evaluate_task_policy
from kflow.policy.loader import load_policy
from kflow.services.doctor_service import DoctorService
from kflow.services.evidence_service import EvidenceService
from kflow.services.env_service import EnvironmentService
from kflow.services.task_service import TaskService
from kflow.templates.ci_workflow import render_github_actions_ci
from kflow.utils.files import ensure_directory, write_text


class ArtifactService:
    """Inspect and collect task artifacts."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.task_service = TaskService(cwd)
        self.config = self.task_service.config

    def list_artifacts(self, task_id: str | None = None) -> OperationResult:
        task = self.task_service.get_task(task_id)
        artifact_dir = self.task_service.task_artifacts_dir(task)
        ensure_directory(artifact_dir)
        files = sorted(str(path.relative_to(Path(task.task_dir))) for path in artifact_dir.glob("**/*") if path.is_file())
        messages = [Message(severity="info", text=f"Task: {task.id}")]
        if files:
            messages.extend(Message(severity="pass", text=path) for path in files)
        else:
            messages.append(Message(severity="warning", text="No artifacts found for the current task."))
        return OperationResult(
            command="artifacts list",
            status="ok" if files else "warning",
            messages=messages,
            data={"task_id": task.id, "artifacts": files},
        )

    def collect_artifacts(self, task_id: str | None = None) -> OperationResult:
        task = self.task_service.get_task(task_id)
        artifact_dir = ensure_directory(self.task_service.task_artifacts_dir(task))
        env_result = EnvironmentService().detect(self.cwd, self.config)
        policy = load_policy(self.task_service.repo_root, self.config.policy.file)
        policy_eval = evaluate_task_policy(task, policy.policy)
        evidence = EvidenceService(task).collect(mobile_required="mobile verification required" in policy_eval.requirements)
        collected: list[str] = []

        env_path = artifact_dir / "env.txt"
        env_content = "\n".join(
            [
                f"os={env_result.environment.os_name}",
                f"python={env_result.environment.python_version}",
                f"project_type={env_result.environment.project_type}",
                f"git={env_result.environment.git.status}",
                f"workflow={env_result.environment.workflow_file.status}",
            ]
        )
        write_text(env_path, env_content, overwrite=True)
        collected.append(str(env_path.relative_to(Path(task.task_dir))))

        changed_files = [
            str(path.relative_to(Path(task.task_dir)))
            for path in sorted(Path(task.task_dir).glob("*"))
            if path.is_file()
        ]
        summary_path = artifact_dir / "changed-files.txt"
        write_text(summary_path, "\n".join(changed_files) + ("\n" if changed_files else ""), overwrite=True)
        collected.append(str(summary_path.relative_to(Path(task.task_dir))))

        evidence_path = artifact_dir / "execution-evidence.json"
        write_text(evidence_path, json.dumps(evidence.model_dump(mode="json"), indent=2) + "\n", overwrite=True)
        collected.append(str(evidence_path.relative_to(Path(task.task_dir))))

        doctor_result = DoctorService(self.cwd).inspect_task(task.id, closeout=False)
        task_status = self.task_service.status(task.id)
        ci_summary = {
            "task_id": task.id,
            "task_status": task_status.data.get("summary", {}),
            "doctor": {
                "status": doctor_result.status,
                "policy_source": doctor_result.data.get("policy_source"),
                "requirements": doctor_result.data.get("requirements", []),
                "warnings": doctor_result.data.get("warnings", []),
                "blockers": doctor_result.data.get("blockers", []),
                "next_steps": doctor_result.data.get("next_steps", []),
                "stop_conditions": doctor_result.data.get("stop_conditions", {}),
            },
            "evidence": evidence.model_dump(mode="json"),
            "environment": {
                "git": env_result.environment.git.status,
                "workflow_file": env_result.environment.workflow_file.status,
                "build": env_result.environment.build.status,
                "test": env_result.environment.test.status,
                "mobile_verify": env_result.environment.mobile_verify.status,
            },
        }
        ci_summary_path = artifact_dir / "ci-summary.json"
        write_text(ci_summary_path, json.dumps(ci_summary, indent=2) + "\n", overwrite=True)
        collected.append(str(ci_summary_path.relative_to(Path(task.task_dir))))

        messages = [Message(severity="pass", text=f"Collected {len(collected)} artifacts for {task.id}")]
        messages.extend(Message(severity="info", text=path) for path in collected)
        return OperationResult(
            command="artifacts collect",
            status="ok",
            messages=messages,
            data={
                "task_id": task.id,
                "artifacts": collected,
                "evidence": evidence.model_dump(mode="json"),
                "ci_summary": ci_summary,
            },
        )

    def scaffold_ci(self, *, provider: str = "github", force: bool = False) -> OperationResult:
        """Generate a packaged CI workflow template."""
        normalized_provider = provider.strip().lower()
        if normalized_provider != "github":
            return OperationResult(
                command="artifacts scaffold-ci",
                status="blocked",
                messages=[Message(severity="blocked", text=f"Unsupported CI provider: {provider}")],
                data={"provider": provider, "supported_providers": ["github"]},
            )

        workflow_path = self.task_service.repo_root / ".github" / "workflows" / "kflow-ci.yml"
        existed_before = workflow_path.exists()
        if existed_before and not force:
            return OperationResult(
                command="artifacts scaffold-ci",
                status="warning",
                messages=[
                    Message(severity="warning", text=f"CI workflow already exists: {workflow_path}"),
                    Message(severity="info", text="Re-run with `--force` to overwrite the existing workflow template."),
                ],
                data={
                    "provider": normalized_provider,
                    "workflow_path": str(workflow_path),
                    "written": False,
                    "existed_before": True,
                },
            )

        write_text(workflow_path, render_github_actions_ci(), overwrite=True)
        return OperationResult(
            command="artifacts scaffold-ci",
            status="ok",
            messages=[
                Message(severity="pass", text=f"Generated GitHub Actions workflow: {workflow_path}"),
                Message(severity="info", text="This workflow runs repo doctor, repo CI gates, and writes the aggregated doctor report."),
            ],
            data={
                "provider": normalized_provider,
                "workflow_path": str(workflow_path),
                "written": True,
                "existed_before": existed_before,
            },
        )
