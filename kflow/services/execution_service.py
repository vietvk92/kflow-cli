"""Build, test, and verify execution services."""

from __future__ import annotations

from pathlib import Path

from kflow.adapters.build import BuildAdapter
from kflow.adapters.test import TestAdapter
from kflow.adapters.verify import VerifyAdapter
from kflow.models.results import Message, OperationResult
from kflow.services.change_plan_service import ChangePlanService
from kflow.services.evidence_service import _parse_build_summary, _parse_test_summary
from kflow.services.result_service import ResultService
from kflow.services.task_service import TaskService
from kflow.utils.files import ensure_directory, write_text
from kflow.utils.shell import ShellResult


class ExecutionService:
    """Run configured commands and persist task artifacts."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.task_service = TaskService(cwd)
        self.config = self.task_service.config
        self.repo_root = self.task_service.repo_root

    def run_build(self, task_id: str | None = None) -> OperationResult:
        adapter = BuildAdapter(self.config.adapters.build.command, self.config.adapters.build.enabled)
        task = self.task_service.get_task(task_id)
        result_service = ResultService(task)
        change_plan_service = ChangePlanService(task)
        result = adapter.execute(self.repo_root)
        artifact_path = self._write_log(task.task_dir, "build.log", result)
        result_service.sync_changed_files()
        result_service.update_section("Build Result", "pass" if result.ok else "fail")
        change_plan_service.update_test_plan_entry("build", self._format_test_plan_entry(result.ok, artifact_path))
        if not result.ok:
            result_service.append_known_issue("build failed")
        else:
            result_service.set_known_issues_none()
        status = "build_pending" if result.ok else "blocked"
        self.task_service.update_status(task, status)
        return self._to_result("build", result, artifact_path, task.id, status)

    def run_test(self, task_id: str | None = None) -> OperationResult:
        adapter = TestAdapter(self.config.adapters.test.command, self.config.adapters.test.enabled)
        task = self.task_service.get_task(task_id)
        result_service = ResultService(task)
        change_plan_service = ChangePlanService(task)
        result = adapter.execute(self.repo_root)
        artifact_path = self._write_log(task.task_dir, "test.log", result)
        result_service.sync_changed_files()
        result_service.update_section("Test Result", "pass" if result.ok else "fail")
        summary = _parse_test_summary("\n".join(part for part in (result.stdout, result.stderr) if part))
        change_plan_service.update_test_plan_entry("tests", self._format_test_plan_entry(result.ok, artifact_path, summary))
        if not result.ok:
            result_service.append_known_issue("tests failed")
        else:
            result_service.set_known_issues_none()
        status = "verification_pending" if result.ok else "blocked"
        self.task_service.update_status(task, status)
        return self._to_result("test", result, artifact_path, task.id, status)

    def run_mobile_verify(self, task_id: str | None = None) -> OperationResult:
        adapter = VerifyAdapter(self.config.adapters.mobile_verify.command, self.config.adapters.mobile_verify.enabled)
        task = self.task_service.get_task(task_id)
        result_service = ResultService(task)
        change_plan_service = ChangePlanService(task)
        result = adapter.execute(self.repo_root)
        artifact_path = self._write_log(task.task_dir, "verify-mobile.log", result)
        result_service.sync_changed_files()
        result_service.update_section("Mobile Verification", "pass" if result.ok else "fail")
        change_plan_service.update_test_plan_entry("mobile verify", self._format_test_plan_entry(result.ok, artifact_path))
        if result.ok:
            self._mark_verify_checklist(task)
            result_service.set_known_issues_none()
        else:
            result_service.append_known_issue("mobile verification failed")
        status = "verification_pending" if result.ok else "blocked"
        self.task_service.update_status(task, status)
        return self._to_result("verify mobile", result, artifact_path, task.id, status)

    def _write_log(self, task_dir: str, filename: str, result: ShellResult) -> str:
        artifact_dir = ensure_directory(Path(task_dir) / "artifacts")
        content = "\n".join(
            [
                f"command: {' '.join(result.command)}",
                f"returncode: {result.returncode}",
                "",
                "[stdout]",
                result.stdout,
                "",
                "[stderr]",
                result.stderr,
                "",
            ]
        )
        path = artifact_dir / filename
        write_text(path, content, overwrite=True)
        return str(path)

    def _mark_verify_checklist(self, task) -> None:
        checklist_path = Path(task.task_dir) / "VERIFY_CHECKLIST.md"
        content = checklist_path.read_text(encoding="utf-8")
        updated = content.replace("- [ ] flow verified", "- [x] flow verified")
        updated = updated.replace("- [ ] UI correct", "- [x] UI correct")
        updated = updated.replace("- [ ] permissions correct", "- [x] permissions correct")
        write_text(checklist_path, updated, overwrite=True)

    def _to_result(
        self,
        command_name: str,
        result: ShellResult,
        artifact_path: str,
        task_id: str,
        task_status: str,
    ) -> OperationResult:
        status = "ok" if result.ok else "blocked"
        summary: dict[str, object] = {}
        combined_output = "\n".join(part for part in (result.stdout, result.stderr) if part)
        if command_name == "build":
            summary = _parse_build_summary(combined_output)
        elif command_name == "test":
            summary = _parse_test_summary(combined_output)
        messages = [
            Message(severity="pass" if result.ok else "blocked", text=f"{command_name} {'passed' if result.ok else 'failed'}"),
            Message(severity="info", text=f"Artifact: {artifact_path}"),
            Message(severity="info", text=f"Task status: {task_status}"),
        ]
        if summary:
            messages.append(Message(severity="info", text=f"Summary: {summary}"))
        if result.stderr:
            messages.append(Message(severity="warning" if result.ok else "blocked", text=result.stderr))
        return OperationResult(
            command=command_name,
            status=status,
            messages=messages,
            data={
                "task_id": task_id,
                "artifact": artifact_path,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "task_status": task_status,
                "summary": summary,
            },
        )

    def _format_test_plan_entry(
        self,
        ok: bool,
        artifact_path: str,
        summary: dict[str, object] | None = None,
    ) -> str:
        """Render a stable Test Plan bullet value from execution evidence."""
        detail = "pass" if ok else "fail"
        if summary:
            summary_parts = [f"{key}={value}" for key, value in summary.items() if value not in (None, "", 0, False)]
            if summary_parts:
                detail = f"{detail} ({', '.join(summary_parts)})"
        return f"{detail} [{Path(artifact_path).name}]"
