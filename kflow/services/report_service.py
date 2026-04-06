"""Aggregate reporting service for CI and dashboards."""

from __future__ import annotations

import json
from pathlib import Path

from kflow.models.results import Message, OperationResult
from kflow.services.doctor_service import DoctorService
from kflow.services.sprint_service import SprintService
from kflow.services.task_service import TaskService
from kflow.utils.files import ensure_directory, write_text


class ReportService:
    """Generate aggregated KFlow reports for machine consumption."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.task_service = TaskService(cwd)
        self.repo_root = self.task_service.repo_root

    def doctor_report(self, *, closeout: bool = False) -> dict[str, object]:
        """Build and persist a combined doctor report."""
        doctor_service = DoctorService(self.cwd)
        repo_result = doctor_service.inspect_repo()
        sprint_result = SprintService(self.cwd).status()
        sprint_doctor_result = SprintService(self.cwd).doctor()

        task_status: dict[str, object] | None = None
        task_doctor: dict[str, object] | None = None
        try:
            task_status_result = self.task_service.status()
            task_doctor_result = doctor_service.inspect_task(closeout=closeout)
            task_status = task_status_result.model_dump(mode="json")
            task_doctor = task_doctor_result.model_dump(mode="json")
        except Exception:
            task_status = None
            task_doctor = None

        overall_status = "ok"
        statuses = [repo_result.status, sprint_doctor_result.status]
        if task_doctor:
            statuses.append(str(task_doctor["status"]))
        if "blocked" in statuses:
            overall_status = "blocked"
        elif "warning" in statuses:
            overall_status = "warning"

        task_policy_source = None
        task_stop_condition_count = 0
        task_stop_conditions_triggered: list[str] = []
        if task_doctor:
            task_policy_source = task_doctor.get("data", {}).get("policy_source")
            task_stop_conditions = task_doctor.get("data", {}).get("stop_conditions", {}) or {}
            task_stop_conditions_triggered = list(task_stop_conditions.get("triggered", []) or [])
            task_stop_condition_count = len(task_stop_conditions_triggered)

        report = {
            "overall_status": overall_status,
            "policy": {
                "task_policy_source": task_policy_source,
                "task_stop_condition_count": task_stop_condition_count,
                "task_stop_conditions_triggered": task_stop_conditions_triggered,
            },
            "repo": repo_result.model_dump(mode="json"),
            "sprint": sprint_result.model_dump(mode="json"),
            "sprint_doctor": sprint_doctor_result.model_dump(mode="json"),
            "task_status": task_status,
            "task_doctor": task_doctor,
        }

        report_path = self.repo_root / ".kflow" / "artifacts" / "doctor-report.json"
        ensure_directory(report_path.parent)
        write_text(report_path, json.dumps(report, indent=2) + "\n", overwrite=True)
        return {"report": report, "path": str(report_path)}

    def doctor_report_result(self, *, closeout: bool = False) -> OperationResult:
        """Return an OperationResult wrapper around the aggregated report."""
        payload = self.doctor_report(closeout=closeout)
        report = payload["report"]
        overall_status = str(report["overall_status"])
        messages = [
            Message(severity="info", text="Doctor Report"),
            Message(severity="info", text=f"Overall status: {overall_status}"),
            Message(severity="info", text=f"Artifact: {payload['path']}"),
        ]
        if report.get("task_doctor"):
            messages.append(
                Message(
                    severity="info",
                    text=f"Task doctor status: {report['task_doctor']['status']}",
                )
            )
        if report.get("sprint_doctor"):
            messages.append(
                Message(
                    severity="info",
                    text=f"Sprint doctor status: {report['sprint_doctor']['status']}",
                )
            )
        return OperationResult(
            command="doctor report",
            status=overall_status if overall_status in {"ok", "warning", "blocked"} else "warning",
            messages=messages,
            data={
                "scope": {
                    "kind": "repo_report",
                    "repo_root": str(self.repo_root),
                },
                "summary": {
                    "overall_status": overall_status,
                    "repo_status": report["repo"]["status"],
                    "sprint_status": report["sprint"]["status"],
                    "sprint_doctor_status": report["sprint_doctor"]["status"],
                    "task_doctor_status": report["task_doctor"]["status"] if report.get("task_doctor") else None,
                    "task_policy_source": report["policy"]["task_policy_source"],
                    "task_stop_condition_count": report["policy"]["task_stop_condition_count"],
                },
                **payload,
            },
        )
