"""Doctor service."""

from __future__ import annotations

from pathlib import Path

from kflow.config.loader import load_config
from kflow.adapters.gsd import GSDAdapter
from kflow.core.stop_conditions import evaluate_stop_conditions
from kflow.models.results import ExecutionEvidence
from kflow.models.results import Message, OperationResult
from kflow.policy.evaluator import evaluate_task_policy
from kflow.policy.loader import load_policy
from kflow.services.diff_service import DiffService
from kflow.services.evidence_service import EvidenceService
from kflow.services.result_service import ResultService
from kflow.services.env_service import EnvironmentService
from kflow.services.planning_service import inspect_phase_state
from kflow.services.task_service import TaskService, phase_task_state_for_policy
from kflow.utils.markdown import get_section_content, parse_bullet_lines, parse_task_brief, parse_verify_checklist


class DoctorService:
    """Evaluate task readiness and blockers."""

    def __init__(self, cwd: Path) -> None:
        self.cwd = cwd
        self.config = load_config(cwd)
        self.repo_root = self.config.repo_root_path

    def inspect_task(self, task_id: str | None = None, closeout: bool = False) -> OperationResult:
        task_service = TaskService(self.cwd)
        task = task_service.get_task(task_id)
        task_dir = Path(task.task_dir)
        env = EnvironmentService().detect(self.cwd, self.config).environment
        loaded_policy = load_policy(self.repo_root, self.config.policy.file)
        diff_summary = DiffService(self.repo_root).summarize()
        phase_summary = task_service.summarize_tasks_for_phase(task.phase_ref) if task.phase_ref else None
        phase_state = (
            inspect_phase_state(self.repo_root / self.config.paths.planning_dir, task.phase_ref)
            if task.phase_ref
            else {}
        )
        phase_task_state = phase_task_state_for_policy(phase_summary, current_task_id=task.id)

        requirements: list[str] = []
        warnings: list[str] = list(loaded_policy.warnings)
        blockers: list[str] = []
        next_steps: list[str] = []
        messages: list[Message] = [
            Message(severity="info", text=f"Task Doctor: {task.id}"),
            Message(severity="info", text=f"Policy source: {loaded_policy.source}"),
        ]

        brief = task_dir / "TASK_BRIEF.md"
        change_plan = task_dir / "CHANGE_PLAN.md"
        result = task_dir / "RESULT.md"
        verify = task_dir / "VERIFY_CHECKLIST.md"
        parsed_brief = None

        if brief.exists():
            messages.append(Message(severity="pass", text="TASK_BRIEF.md exists"))
        else:
            blockers.append("TASK_BRIEF.md missing")

        if brief.exists():
            parsed_brief = parse_task_brief(brief.read_text(encoding="utf-8"))
        if change_plan.exists():
            messages.append(Message(severity="pass", text="CHANGE_PLAN.md exists"))
            change_plan_content = change_plan.read_text(encoding="utf-8")
            has_test_plan = bool(get_section_content(change_plan_content, "Test Plan").strip())
            impacted_symbols = parse_bullet_lines(get_section_content(change_plan_content, "Impacted Symbols"))
        elif closeout or loaded_policy.policy.closeout_rules.require_change_plan:
            impacted_symbols = []
            has_test_plan = False
        else:
            impacted_symbols = []
            has_test_plan = False

        initial_evaluation = evaluate_task_policy(
            task,
            loaded_policy.policy,
            context={
                "diff_summary": diff_summary,
                "change_plan_has_test_plan": has_test_plan,
                "impacted_symbols_count": len(impacted_symbols),
                "env_statuses": _env_statuses(env),
                "project_type": env.project_type,
                "phase_ref": task.phase_ref,
                "phase_state": phase_state,
                "phase_task_state": phase_task_state,
            },
        )
        evidence = EvidenceService(task).collect(mobile_required=_is_mobile_required(initial_evaluation.requirements))
        evaluation = evaluate_task_policy(
            task,
            loaded_policy.policy,
            context={
                "diff_summary": diff_summary,
                "change_plan_has_test_plan": has_test_plan,
                "impacted_symbols_count": len(impacted_symbols),
                "env_statuses": _env_statuses(env),
                "project_type": env.project_type,
                "phase_ref": task.phase_ref,
                "phase_state": phase_state,
                "phase_task_state": phase_task_state,
                "evidence_statuses": {
                    "build": evidence.build,
                    "test": evidence.test,
                    "mobile": evidence.mobile,
                },
            },
        )
        requirements.extend(evaluation.requirements)
        warnings.extend(evaluation.warnings)
        blockers.extend(evaluation.blockers)
        next_steps.extend(evaluation.next_steps)
        if parsed_brief:
            if "repro steps required for bug tasks" in evaluation.requirements and not parsed_brief.repro_steps:
                blockers.append("repro steps missing")

        parsed_verify = None
        if verify.exists():
            messages.append(Message(severity="pass", text="VERIFY_CHECKLIST.md exists"))
            parsed_verify = parse_verify_checklist(verify.read_text(encoding="utf-8"))

        parsed_result = None
        result_changed_files_stale = False
        if result.exists():
            messages.append(Message(severity="pass", text="RESULT.md exists"))
            parsed_result = ResultService(task).parse()
            if diff_summary["has_code_changes"]:
                missing_changed_files = [
                    path for path in diff_summary["code_files"] if path not in parsed_result.changed_files
                ]
                result_changed_files_stale = bool(missing_changed_files)

        if env.git.status == "missing":
            warnings.append("Git repository not detected")
        if env.gsd.status == "missing":
            warnings.append("GSD planning dir not found")
        if env.build.status == "missing":
            warnings.append("Build adapter command not configured")
        if env.test.status == "missing":
            warnings.append("Test adapter command not configured")
        if diff_summary["available"]:
            messages.append(
                Message(
                    severity="info",
                    text=f"Diff: {len(diff_summary['changed_files'])} changed files, {len(diff_summary['code_files'])} code files",
                )
            )
        else:
            warnings.append("git diff unavailable")

        stop_conditions = evaluate_stop_conditions(
            closeout=closeout,
            brief_exists=brief.exists(),
            goal_present=bool(parsed_brief.goal) if parsed_brief else False,
            acceptance_present=bool(parsed_brief.acceptance_criteria) if parsed_brief else False,
            risk_present=bool(parsed_brief.risk_level) if parsed_brief else False,
            acceptance_has_conflict_marker=_has_conflict_marker(parsed_brief.acceptance_criteria) if parsed_brief else False,
            change_plan_exists=change_plan.exists(),
            high_risk_missing_test_plan=task.risk_level == "high" and not has_test_plan,
            result_exists=result.exists(),
            result_changed_files_stale=result_changed_files_stale,
            result_build_missing=not bool(parsed_result.build_result) if parsed_result else True,
            result_test_missing=not bool(parsed_result.test_result) if parsed_result else True,
            result_known_issues_missing=not bool(parsed_result.known_issues) if parsed_result else True,
            diff_available=bool(diff_summary["available"]),
            diff_has_code_changes=bool(diff_summary["has_code_changes"]),
            impacted_symbols_present=bool(impacted_symbols),
            build_evidence=evidence.build,
            test_evidence=evidence.test,
            mobile_evidence=evidence.mobile,
            mobile_required=_is_mobile_required(requirements),
            verify_exists=verify.exists(),
            mobile_acknowledged=bool(parsed_verify.mobile_flow_verified) if parsed_verify else False,
            require_change_plan=loaded_policy.policy.closeout_rules.require_change_plan,
            require_result_file=loaded_policy.policy.closeout_rules.require_result_file,
            require_verify_if_flagged=loaded_policy.policy.closeout_rules.require_verify_if_flagged,
        )
        warnings.extend(stop_conditions.warnings)
        blockers.extend(stop_conditions.blockers)
        next_steps.extend(stop_conditions.next_steps)
        _apply_evidence_messages(messages, evidence)

        next_steps.extend(_next_steps_for_blockers(blockers))
        next_steps = list(dict.fromkeys(next_steps))

        for warning in warnings:
            messages.append(Message(severity="warning", text=warning))
        for requirement in requirements:
            messages.append(Message(severity="required", text=requirement))
        for blocker in blockers:
            messages.append(Message(severity="blocked", text=blocker))

        if not blockers and not requirements:
            messages.append(Message(severity="pass", text="Task satisfies current doctor checks."))
        return OperationResult(
            command="task close" if closeout else "task doctor",
            status="blocked" if blockers else ("warning" if warnings or requirements else "ok"),
            messages=messages,
            data={
                "scope": {
                    "kind": "task",
                    "task_id": task.id,
                    "phase": task.phase_ref,
                    "closeout": closeout,
                },
                "summary": {
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                    "requirement_count": len(requirements),
                    "diff_has_code_changes": bool(diff_summary.get("has_code_changes")),
                    "evidence": evidence.model_dump(mode="json"),
                    "stop_condition_count": len(stop_conditions.triggered),
                },
                "task_id": task.id,
                "warnings": warnings,
                "requirements": requirements,
                "blockers": blockers,
                "next_steps": next_steps,
                "stop_conditions": stop_conditions.model_dump(mode="json"),
                "policy_source": loaded_policy.source,
                "evidence": evidence.model_dump(mode="json"),
                "diff_summary": diff_summary,
                "phase_state": phase_state,
                "phase_task_state": phase_task_state,
            },
        )

    def inspect_repo(self) -> OperationResult:
        """Evaluate repository-level readiness for KFlow usage."""
        env_result = EnvironmentService().detect(self.cwd, self.config)
        env = env_result.environment
        gsd_summary = GSDAdapter(
            planning_dir=self.config.paths.planning_dir,
            enabled=self.config.adapters.gsd.enabled,
        ).summarize(self.repo_root)

        warnings: list[str] = []
        blockers: list[str] = []
        messages: list[Message] = [Message(severity="info", text="Repo Doctor")]

        if env.config_file.status == "present":
            messages.append(Message(severity="pass", text="Config file present"))
        else:
            blockers.append("config file missing")

        if env.workflow_file.status == "present":
            messages.append(Message(severity="pass", text="Workflow file present"))
        else:
            warnings.append("workflow file missing, embedded policy will be used")

        if env.planning_dir.status == "present":
            messages.append(Message(severity="pass", text="Planning directory present"))
        else:
            warnings.append("planning directory missing")
        if gsd_summary["present"] and int(gsd_summary["phase_count"]) == 0:
            warnings.append("planning directory present but no phases discovered")
        if gsd_summary["present"] and gsd_summary["current_phase"]:
            messages.append(
                Message(
                    severity="info",
                    text=f"GSD phases: {gsd_summary['ready_phases']}/{gsd_summary['phase_count']} ready, current={gsd_summary['current_phase']}",
                )
            )

        if env.git.status == "present":
            messages.append(Message(severity="pass", text="Git repository detected"))
        else:
            warnings.append("git repository missing")

        _append_tool_status(messages, warnings, "GitNexus", env.gitnexus.status, required=False)
        _append_tool_status(messages, warnings, "Build adapter", env.build.status, required=False)
        _append_tool_status(messages, warnings, "Test adapter", env.test.status, required=False)
        _append_tool_status(messages, warnings, "Mobile verify adapter", env.mobile_verify.status, required=False)

        for warning in warnings:
            messages.append(Message(severity="warning", text=warning))
        for blocker in blockers:
            messages.append(Message(severity="blocked", text=blocker))

        next_steps: list[str] = []
        if "config file missing" in blockers:
            next_steps.append("Run `kflow init` to create `.kflow/config.yaml`.")
        if "workflow file missing, embedded policy will be used" in warnings:
            next_steps.append("Add `WORKFLOW_v2_PRO.md` or keep using embedded policy.")
        if "planning directory missing" in warnings:
            next_steps.append(f"Create `{self.repo_root / self.config.paths.planning_dir}` if you want planning integration.")

        if not warnings and not blockers:
            messages.append(Message(severity="pass", text="Repository checks passed."))

        return OperationResult(
            command="doctor repo",
            status="blocked" if blockers else ("warning" if warnings else "ok"),
            messages=messages,
            data={
                "scope": {
                    "kind": "repo",
                    "repo_root": str(self.repo_root),
                },
                "summary": {
                    "blocker_count": len(blockers),
                    "warning_count": len(warnings),
                    "git": env.git.status,
                    "workflow_file": env.workflow_file.status,
                    "planning_dir": env.planning_dir.status,
                    "phase_count": int(gsd_summary["phase_count"]),
                    "ready_phases": int(gsd_summary["ready_phases"]),
                    "current_phase": gsd_summary["current_phase"],
                },
                "warnings": warnings,
                "blockers": blockers,
                "next_steps": next_steps,
                "environment": env.model_dump(mode="json"),
                "gsd_summary": gsd_summary,
            },
        )


def _env_statuses(env) -> dict[str, str]:
    """Project environment tool statuses into policy-evaluator context."""
    return {
        "git": env.git.status,
        "workflow_file": env.workflow_file.status,
        "config_file": env.config_file.status,
        "xcodebuild": env.xcodebuild.status,
        "gitnexus": env.gitnexus.status,
        "gsd": env.gsd.status,
        "build": env.build.status,
        "test": env.test.status,
        "planning_dir": env.planning_dir.status,
        "mobile_verify": env.mobile_verify.status,
    }


def _is_mobile_required(requirements: list[str]) -> bool:
    """Return true when any requirement string demands mobile verification."""
    return any("mobile verification required" in requirement for requirement in requirements)


def _apply_evidence_messages(
    messages: list[Message],
    evidence: ExecutionEvidence,
) -> None:
    """Project execution evidence into informational doctor messages."""
    if evidence.build == "pass":
        messages.append(Message(severity="pass", text="Build evidence: pass"))
    if evidence.test == "pass":
        messages.append(Message(severity="pass", text="Test evidence: pass"))
    if evidence.mobile == "pass":
        messages.append(Message(severity="pass", text="Mobile verification evidence: pass"))


def _next_steps_for_blockers(blockers: list[str]) -> list[str]:
    """Map common blockers to concrete next steps."""
    steps: list[str] = []
    mappings = {
        "task goal missing": "Fill the Goal section in TASK_BRIEF.md.",
        "acceptance criteria missing": "Add acceptance criteria in TASK_BRIEF.md.",
        "conflicting acceptance criteria marker found": "Resolve the conflicting acceptance criteria markers in TASK_BRIEF.md.",
        "risk level missing": "Set the Risk Level section in TASK_BRIEF.md.",
        "high risk task missing test plan": "Fill the Test Plan section in CHANGE_PLAN.md for this high-risk task.",
        "repro steps missing": "Document repro steps in TASK_BRIEF.md.",
        "code changes detected but build evidence is missing": "Run `kflow build` after code changes or capture build evidence.",
        "code changes detected but test evidence is missing": "Run `kflow test` after code changes or capture test evidence.",
        "result changed files do not reflect current code diff": "Update RESULT.md Changed Files so it matches the current code diff.",
        "mobile verification not acknowledged": "Check off the relevant Mobile items in VERIFY_CHECKLIST.md.",
        "mobile verification evidence missing": "Run `kflow verify mobile` or record manual verification evidence.",
        "build evidence indicates failure": "Re-run `kflow build` and fix the failing build.",
        "test evidence indicates failure": "Re-run `kflow test` and fix the failing tests.",
        "mobile verification evidence indicates failure": "Re-run `kflow verify mobile` and resolve the failing flow.",
        "CHANGE_PLAN.md missing": "Create CHANGE_PLAN.md for this task.",
        "RESULT.md missing": "Create RESULT.md before closeout.",
    }
    for blocker in blockers:
        if blocker in mappings:
            steps.append(mappings[blocker])
        if blocker.startswith("RESULT.md section incomplete: "):
            section = blocker.split(": ", maxsplit=1)[1]
            steps.append(f"Fill the `{section}` section in RESULT.md.")
    return steps


def _append_tool_status(
    messages: list[Message],
    warnings: list[str],
    label: str,
    status: str,
    *,
    required: bool,
) -> None:
    """Map adapter/tool status to user-facing repo doctor output."""
    if status == "present":
        messages.append(Message(severity="pass", text=f"{label} available"))
        return
    if status == "disabled":
        messages.append(Message(severity="info", text=f"{label} disabled"))
        return
    if status == "not_applicable":
        messages.append(Message(severity="info", text=f"{label} not applicable"))
        return
    text = f"{label} missing"
    if required:
        warnings.append(text)
    else:
        warnings.append(text)


def _has_conflict_marker(items: list[str]) -> bool:
    """Detect obvious merge/conflict markers in acceptance criteria text."""
    markers = ("<<<<<<<", "=======", ">>>>>>>", "[conflict]", "conflict:")
    for item in items:
        lowered = item.lower()
        if any(marker in item or marker in lowered for marker in markers):
            return True
    return False
