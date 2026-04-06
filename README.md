# KFlow

KFlow is a workflow enforcement CLI for local software delivery inside a repository.

Current internal milestone: `0.1.1`

## Current Scope
- initialize `.kflow/` project state
- detect environment capabilities
- **ingest spec files and auto-bootstrap tasks** (`kflow intake`)
- create managed tasks and task artifacts
- evaluate task readiness and closeout blockers
- run configured build, test, and mobile verification commands
- collect task artifacts for later review

## Current Direction
KFlow is moving toward a detect-first planning model for adoption in active repositories:

- scan existing docs and planning artifacts before asking users to restructure anything
- attach to existing planning systems instead of forcing a mirror or rename workflow
- keep `.kflow` focused on runtime state, task state, and execution evidence

## Install
Preferred target runtime is Python 3.10+.

KFlow does not install on Python 3.9 or older. On macOS, the default system `python3` is often still `3.9.x`, so verify your interpreter first:

```bash
python3 --version
```

If that prints `3.9.x`, install a newer Python and use that interpreter explicitly, for example:

```bash
brew install python@3.11
python3.11 --version
```

Install from the public `v0.1.1` tag:

```bash
python3.11 -m pip install "git+https://github.com/vietvk92/kflow-cli.git@v0.1.1"
```

If `python3` on your machine already points to Python 3.10+:

```bash
python3 -m pip install "git+https://github.com/vietvk92/kflow-cli.git@v0.1.1"
```

Install from source:

```bash
git clone https://github.com/vietvk92/kflow-cli.git
cd kflow-cli
python3.11 -m pip install .
```

If `python3` already points to Python 3.10+:

```bash
python3 -m pip install .
```

For local development:

```bash
python3.11 -m pip install .[dev]
python3.11 -m pytest tests/unit tests/integration
```

If your local `pip` is old and installs fail, use a newer `pip` or install from a fresh Python 3.10+ environment. If the `kflow` command is not found after a user install, add your user Python bin directory to `PATH`.

## How It Works
KFlow is a CLI you install once, then run inside the repository you want to manage.

The model is:
- install `kflow`
- `cd` into a project or repo
- run `kflow init` once in that repo
- create tasks and use doctor/status/build/test/verify commands inside that repo

KFlow works against the current working directory. It does not manage all projects on your machine globally.

## First Project Setup
Inside the project you want to manage:

```bash
cd /path/to/your-project
kflow init
kflow env detect
kflow analyze
kflow plan --apply
```

### Start from specs (recommended)
If you have spec or PRD files, drop them into `specs/` and let kflow bootstrap the tasks for you:

```bash
# Drop your .md or .txt spec files into specs/, then:
kflow intake            # preview what will be created
kflow intake --apply    # create tasks with pre-filled TASK_BRIEF.md
```

This creates `.kflow/` in the current repo and detects available workflow/config/tooling state.

Common files created under the repo:
- `.kflow/config.yaml`
- `.kflow/state/current_task.yaml`
- `.kflow/tasks/<task-id>/TASK_BRIEF.md`
- `.kflow/tasks/<task-id>/CHANGE_PLAN.md`
- `.kflow/tasks/<task-id>/VERIFY_CHECKLIST.md`
- `.kflow/tasks/<task-id>/RESULT.md`

## Quick Start
Start from a spec file (fastest path):

```bash
# Drop specs/my-feature.md into your repo, then:
kflow intake --apply
kflow task status
kflow task doctor
```

Or create a task manually:

```bash
kflow task new --type bug --name "Permission flow"
kflow task status
kflow task doctor
```

Typical day-to-day flow:

```bash
kflow task new --type feat --name "Add permissions fallback" --phase 2
kflow inspect PermissionManager
kflow build
kflow test
kflow verify mobile
kflow task doctor
kflow task close
```

## Common Workflows
### 1. Start using KFlow in a repo
```bash
cd /path/to/repo
kflow init
kflow env detect
kflow analyze
kflow plan
kflow plan --apply
```

### 2. Ingest specs and bootstrap tasks
```bash
# Drop .md or .txt files into specs/, then:
kflow intake            # dry-run preview
kflow intake --apply    # create tasks
kflow intake --apply --force  # re-ingest updated specs
```

### 3. Create a task manually
```bash
kflow task new --type bug --name "Fix permission regression" --risk high --tags permissions
```

### 3. Check what is still missing
```bash
kflow task status
kflow task doctor
```

Use `task status` for a lighter summary and `task doctor` for blocking gates, requirements, warnings, and next steps.

### 4. Run execution steps
```bash
kflow build
kflow test
kflow verify mobile
```

These commands write logs and evidence into the active task's `artifacts/` directory and update managed result files.

### 5. Collect artifacts for review or CI
```bash
kflow artifacts list
kflow artifacts collect
kflow doctor report --json
```

### 6. Close a task
```bash
kflow task close
```

If closeout is blocked, run:

```bash
kflow task doctor --json
```

### 7. Work with planning and sprint state
```bash
kflow sprint status
kflow phase check 2
kflow doctor sprint
```

### 8. Generate a CI starter workflow
```bash
kflow artifacts scaffold-ci
```

## Core Commands
- `kflow init`
- `kflow analyze`
- `kflow intake`
- `kflow plan`
- `kflow env detect`
- `kflow config show`
- `kflow config set`
- `kflow config validate`
- `kflow task new`
- `kflow task status`
- `kflow task doctor`
- `kflow task close`
- `kflow task handoff`
- `kflow doctor repo`
- `kflow doctor sprint`
- `kflow doctor ci`
- `kflow doctor report`
- `kflow inspect`
- `kflow build`
- `kflow test`
- `kflow verify mobile`
- `kflow artifacts list`
- `kflow artifacts collect`
- `kflow artifacts scaffold-ci`
- `kflow sprint status`
- `kflow sprint start`
- `kflow phase check`

## Command Guide
- `kflow init`: bootstrap `.kflow/` in the current repo
- `kflow analyze`: analyze repository to identify planning modes, artifacts, and product specs
- `kflow intake`: scan `specs/` for spec files and auto-create tasks with pre-filled `TASK_BRIEF.md` (`--apply` creates tasks, `--force` re-ingests)
- `kflow plan`: preview the proposed mapping and bootstrapper state from existing docs (`--apply` persists states)
- `kflow env detect`: inspect repo, workflow, and adapter/tool availability
- `kflow task new`: create a managed task with markdown artifacts
- `kflow task status`: quick summary of the active task
- `kflow task doctor`: full gate evaluation with blockers, warnings, requirements, and next steps
- `kflow build` / `kflow test` / `kflow verify mobile`: run configured execution steps and capture evidence
- `kflow inspect`: pull GitNexus context/impact into task artifacts and `CHANGE_PLAN.md`
- `kflow artifacts collect`: snapshot CI/debug artifacts for the current task
- `kflow doctor repo`: repo-wide health view
- `kflow doctor sprint`: sprint-wide readiness and linked-task execution health
- `kflow doctor ci`: CI-friendly doctor command with non-zero exit on blocked state
- `kflow doctor report`: aggregated repo/sprint/task report artifact

## Troubleshooting
### `Package 'kflow' requires a different Python`
Your interpreter is too old. Use Python 3.10+ explicitly:

```bash
python3.11 -m pip install "git+https://github.com/vietvk92/kflow-cli.git@v0.1.1"
```

### `kflow: command not found`
The package likely installed into your user Python bin directory. Add it to `PATH`, then reopen the shell.

### Installed successfully but running in the wrong repo
`kflow` uses the current working directory. `cd` into the project you want to manage before running commands.

## JSON Status Contract
Automation-oriented status commands expose a shared additive contract:
- `data.scope`
- `data.summary`
- command-specific detail fields

Current commands using this pattern:
- `kflow task status --json`
- `kflow phase check <n> --json`
- `kflow sprint status --json`
- `kflow config show --json`
- `kflow config validate --json`
- `kflow doctor repo --json`
- `kflow doctor sprint --json`
- `kflow task doctor --json`
- `kflow doctor report --json`

Shared fields:
- `data.scope.kind`: one of `task`, `phase`, `sprint`, `repo`, `repo_report`
- `data.summary`: normalized high-level status block for automation
- `meta.schema_version`
- `meta.generated_at`

Examples:

```bash
kflow task status --json
kflow phase check 2 --json
kflow sprint status --json
kflow doctor ci --json
kflow doctor ci --repo --json
kflow doctor report --json
```

Typical payload shape:

```json
{
  "command": "task status",
  "status": "ok",
  "data": {
    "scope": {
      "kind": "task",
      "task_id": "permission-flow",
      "phase": "2"
    },
    "summary": {
      "status": "verification_pending",
      "missing_artifacts": 0,
      "is_current_task": true,
      "evidence": {
        "build": "pass",
        "test": "pass",
        "mobile": "not_required"
      }
    }
  },
  "meta": {
    "schema_version": 1,
    "generated_at": "2026-04-05T00:00:00Z"
  }
}
```

Doctor/report payloads use the same additive pattern, but with doctor-specific summary fields. For example:

```json
{
  "command": "doctor report",
  "status": "warning",
  "data": {
    "scope": {
      "kind": "repo_report",
      "repo_root": "/path/to/repo"
    },
    "summary": {
      "overall_status": "warning",
      "repo_status": "ok",
      "sprint_status": "warning",
      "sprint_doctor_status": "warning",
      "task_doctor_status": "blocked"
    }
  }
}
```

## Notes
- Missing optional tools degrade to warnings where possible.
- JSON output is supported on automation-oriented command paths and includes a stable `meta` block with `schema_version` and `generated_at`.
- `kflow config show --json` and `kflow config validate --json` now also expose migration metadata for legacy `.kflow/config.yaml` payloads.
- Status-style and doctor/report JSON commands now expose additive `scope` and `summary` fields to reduce per-command special-casing.
- Policy loading now follows the practical priority chain: `.kflow/policy.yaml`, workflow-embedded fenced policy blocks, then embedded defaults.
- Policy gates can now be expressed declaratively through `project_rules`, `phase_rules`, `sprint_rules`, `tag_rules`, and `diff_rules`, including custom `messages` blocks for requirements, warnings, blockers, and next steps.
- `kflow artifacts collect` now emits `artifacts/ci-summary.json` for CI-style machine consumption of task status, doctor gates, evidence, and environment readiness.
- `artifacts/ci-summary.json` now also carries `doctor.policy_source` and `doctor.stop_conditions` for direct CI/debug consumption.
- `kflow artifacts scaffold-ci` generates a packaged GitHub Actions workflow at `.github/workflows/kflow-ci.yml` and refuses to overwrite it unless `--force` is passed.
- `kflow doctor ci` exits non-zero when doctor status is `blocked`, which is useful for CI gating.
- `kflow doctor ci --repo` exits non-zero from an aggregated repo/sprint/current-task report.
- `kflow doctor sprint` exposes sprint-wide blockers and warnings over planning readiness plus linked-task execution health.
- `kflow doctor report` writes `.kflow/artifacts/doctor-report.json` with repo, sprint, and current-task rollups.
- `doctor-report.json` now includes task policy-source and stop-condition summary fields so aggregated automation does not need to call `task doctor` separately.
- `kflow doctor repo --json` now includes `gsd_summary` with discovered phase count, ready-phase count, and current phase inference when `.planning/` exists.
- `kflow task handoff` writes a task-scoped `agent-handoff.md` artifact for AI-agent or human continuation.
- `kflow inspect` now also writes `inspect-summary.json` with parsed line output plus simple `key: value` field extraction for downstream automation.
- `kflow task doctor --json` now includes `data.stop_conditions` so automation can distinguish explicit stop-condition hits from broader policy warnings.
- Managed task files live under `.kflow/tasks/<task-id>/`.
- Internal milestone summary is tracked in `CHANGELOG.md`.
- Current practical release baseline is `0.1.0` with `82 passed` across unit and integration tests.
