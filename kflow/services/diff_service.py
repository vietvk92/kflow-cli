"""Git diff awareness for Phase 3 checks."""

from __future__ import annotations

from pathlib import Path

from kflow.utils.shell import run


CODE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".m",
    ".mm",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".swift",
    ".ts",
    ".tsx",
}


class DiffService:
    """Read lightweight repository diff state without failing hard."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def summarize(self) -> dict[str, object]:
        """Return a normalized diff summary for the current repo."""
        result = run(["git", "status", "--porcelain"], cwd=self.repo_root)
        if not result.ok:
            return {
                "available": False,
                "repo_root": str(self.repo_root),
                "changed_files": [],
                "code_files": [],
                "task_files": [],
                "planning_files": [],
                "other_files": [],
                "has_code_changes": False,
                "has_repo_changes": False,
            }

        changed_files: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", maxsplit=1)[1].strip()
            changed_files.append(path)

        code_files: list[str] = []
        task_files: list[str] = []
        planning_files: list[str] = []
        other_files: list[str] = []
        for rel_path in changed_files:
            normalized = rel_path.replace("\\", "/")
            suffix = Path(normalized).suffix.lower()
            if normalized.startswith(".kflow/tasks/"):
                task_files.append(normalized)
            elif normalized.startswith(".planning/"):
                planning_files.append(normalized)
            elif suffix in CODE_EXTENSIONS:
                code_files.append(normalized)
            else:
                other_files.append(normalized)

        return {
            "available": True,
            "repo_root": str(self.repo_root),
            "changed_files": changed_files,
            "code_files": code_files,
            "task_files": task_files,
            "planning_files": planning_files,
            "other_files": other_files,
            "has_code_changes": bool(code_files),
            "has_repo_changes": bool(changed_files),
        }
