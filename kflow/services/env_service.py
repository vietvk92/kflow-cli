"""Environment service."""

from __future__ import annotations

from pathlib import Path
import platform

from kflow.adapters.build import BuildAdapter
from kflow.adapters.gitnexus import GitNexusAdapter
from kflow.adapters.gsd import GSDAdapter
from kflow.adapters.test import TestAdapter
from kflow.adapters.verify import VerifyAdapter
from kflow.models.config import ProjectConfig
from kflow.models.env import EnvironmentStatus, ToolStatus
from kflow.models.results import EnvironmentResult, Message
from kflow.utils.paths import detect_project_type, find_repo_root, find_workflow_file
from kflow.utils.shell import run


class EnvironmentService:
    """Detect local environment capabilities."""

    def detect(self, cwd: Path, config: ProjectConfig | None = None) -> EnvironmentResult:
        repo_root = find_repo_root(cwd) or cwd.resolve()
        workflow_path = find_workflow_file(repo_root, config.workflow_file if config else None)
        project_type = config.project_type if config else detect_project_type(repo_root)
        warnings: list[str] = []
        errors: list[str] = []

        git_result = run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root)
        if git_result.ok:
            git = ToolStatus(status="present", detail=git_result.stdout)
        else:
            git = ToolStatus(status="missing", detail="git repo not detected")
            warnings.append("Git repository not detected. KFlow will run in degraded mode.")

        config_file = repo_root / ".kflow" / "config.yaml"
        xcodebuild_result = run(["xcodebuild", "-version"], cwd=repo_root) if project_type == "ios" else None
        planning_dir = repo_root / (config.paths.planning_dir if config else ".planning")
        gitnexus_detection = GitNexusAdapter(
            command=config.adapters.gitnexus.command if config else "gitnexus",
            enabled=config.adapters.gitnexus.enabled if config else True,
        ).detect(repo_root)
        gsd_detection = GSDAdapter(
            planning_dir=config.paths.planning_dir if config else ".planning",
            enabled=config.adapters.gsd.enabled if config else True,
        ).detect(repo_root)
        verify_detection = VerifyAdapter(
            command=config.adapters.mobile_verify.command if config else "./.tools/verify-mobile.sh",
            enabled=config.adapters.mobile_verify.enabled if config else False,
        ).detect(repo_root)
        build_detection = BuildAdapter(
            command=config.adapters.build.command if config else None,
            enabled=config.adapters.build.enabled if config else False,
        ).detect(repo_root)
        test_detection = TestAdapter(
            command=config.adapters.test.command if config else None,
            enabled=config.adapters.test.enabled if config else False,
        ).detect(repo_root)

        environment = EnvironmentStatus(
            os_name=platform.system(),
            python_version=platform.python_version(),
            repo_root=str(repo_root) if git_result.ok else None,
            project_type=project_type,
            git=git,
            workflow_file=ToolStatus(
                status="present" if workflow_path else "missing",
                detail=str(workflow_path) if workflow_path else "workflow file not found",
            ),
            config_file=ToolStatus(
                status="present" if config_file.exists() else "missing",
                detail=str(config_file),
            ),
            xcodebuild=ToolStatus(
                status="present" if xcodebuild_result and xcodebuild_result.ok else ("not_applicable" if project_type != "ios" else "missing"),
                detail=(xcodebuild_result.stdout or xcodebuild_result.stderr) if xcodebuild_result else "not applicable",
            ),
            gitnexus=ToolStatus(
                status=gitnexus_detection.status,
                detail=gitnexus_detection.detail,
            ),
            gsd=ToolStatus(
                status=gsd_detection.status,
                detail=gsd_detection.detail,
            ),
            build=ToolStatus(status=build_detection.status, detail=build_detection.detail),
            test=ToolStatus(status=test_detection.status, detail=test_detection.detail),
            planning_dir=ToolStatus(
                status="present" if planning_dir.exists() else "missing",
                detail=str(planning_dir),
            ),
            mobile_verify=ToolStatus(
                status=verify_detection.status,
                detail=verify_detection.detail,
            ),
            warnings=warnings,
            errors=errors,
        )
        messages = [
            Message(severity="info", text=f"OS: {environment.os_name}"),
            Message(severity="info", text=f"Python: {environment.python_version}"),
        ]
        if workflow_path:
            messages.append(Message(severity="pass", text=f"Workflow file found: {workflow_path.name}"))
        else:
            messages.append(Message(severity="warning", text="No workflow file found, embedded policy will be used."))
        if environment.build.status == "missing":
            messages.append(Message(severity="warning", text="Build adapter enabled but command not configured."))
        if environment.test.status == "missing":
            messages.append(Message(severity="warning", text="Test adapter enabled but command not configured."))
        return EnvironmentResult(
            command="env detect",
            status="warning" if warnings else "ok",
            messages=messages,
            data={},
            environment=environment,
        )
