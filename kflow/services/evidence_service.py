"""Execution evidence parsing for doctor and closeout."""

from __future__ import annotations

from pathlib import Path
import re

from kflow.models.results import ExecutionEvidence
from kflow.models.task import TaskRecord
from kflow.services.result_service import ResultService


def _artifact_status(path: Path) -> str:
    """Parse a command artifact log into pass/fail/missing."""
    if not path.exists():
        return "missing"
    content = path.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.startswith("returncode:"):
            code = line.split(":", maxsplit=1)[1].strip()
            return "pass" if code == "0" else "fail"
    return "missing"


def _artifact_text(path: Path) -> str:
    """Read an artifact log if it exists."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _parse_build_summary(content: str) -> dict[str, int | str]:
    """Extract a lightweight build summary from log content."""
    summary: dict[str, int | str] = {}
    lowered = content.lower()
    if "build succeeded" in lowered:
        summary["outcome"] = "build_succeeded"
    elif "build failed" in lowered:
        summary["outcome"] = "build_failed"
    warning_match = re.search(r"(\d+)\s+warning", lowered)
    error_match = re.search(r"(\d+)\s+error", lowered)
    if warning_match:
        summary["warnings"] = int(warning_match.group(1))
    if error_match:
        summary["errors"] = int(error_match.group(1))
    return summary


def _parse_test_summary(content: str) -> dict[str, int]:
    """Extract a lightweight test summary from log content."""
    lowered = content.lower()
    summary: dict[str, int] = {}
    patterns = {
        "passed": r"(\d+)\s+passed",
        "failed": r"(\d+)\s+failed",
        "skipped": r"(\d+)\s+skipped",
        "errors": r"(\d+)\s+error",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, lowered)
        if match:
            summary[key] = int(match.group(1))
    return summary


class EvidenceService:
    """Compute evidence summaries for a task."""

    def __init__(self, task: TaskRecord) -> None:
        self.task = task
        self.task_dir = Path(task.task_dir)
        self.artifacts_dir = self.task_dir / "artifacts"

    def collect(self, *, mobile_required: bool) -> ExecutionEvidence:
        result_doc = ResultService(self.task).parse()
        build_log = self.artifacts_dir / "build.log"
        test_log = self.artifacts_dir / "test.log"
        build = self._merge_status(_artifact_status(build_log), result_doc.build_result)
        test = self._merge_status(_artifact_status(test_log), result_doc.test_result)
        if mobile_required:
            mobile = self._merge_status(_artifact_status(self.artifacts_dir / "verify-mobile.log"), result_doc.mobile_verification)
        else:
            mobile = "not_required"
        return ExecutionEvidence(
            build=build,
            test=test,
            mobile=mobile,
            build_summary=_parse_build_summary(_artifact_text(build_log)),
            test_summary=_parse_test_summary(_artifact_text(test_log)),
        )

    @staticmethod
    def _merge_status(artifact_status: str, result_status: str) -> str:
        normalized_result = result_status.strip().lower()
        if artifact_status == "fail" or normalized_result == "fail":
            return "fail"
        if artifact_status == "pass" or normalized_result == "pass":
            return "pass"
        return "missing"
