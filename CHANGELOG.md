# Changelog

## 0.1.1
- Added `kflow intake` command for spec-driven task bootstrapping.
  - Drop `.md` or `.txt` spec files into `specs/` (configurable via `paths.intake_dir`), run `kflow intake --apply` to auto-create tasks.
  - Extracts task name from `# H1` heading, infers task type and risk level from content keywords.
  - Pre-fills `TASK_BRIEF.md` with spec content — no manual copy-paste required.
  - Tracks processed specs by file hash; use `--force` to re-ingest updated specs.
- Added `intake_dir` path config (default: `specs`) to `PathsConfig`.
- Expanded `.gitignore` with standard Python patterns (`__pycache__`, `*.pyc`, `.venv`, `dist/`, etc.).

## 0.1.0
- Bootstrapped the KFlow Python CLI foundation and package layout.
- Added init, env, config, task, doctor, inspect, artifacts, sprint, and phase command groups.
- Implemented task state persistence, template rendering, doctor/closeout enforcement, and execution evidence tracking.
- Added build, test, mobile verify, and GitNexus inspect flows with artifact logging.
- Added planning-aware phase and sprint reporting, sprint bootstrap, and task-to-phase evidence rollups.
- Added practical Phase 3 policy depth:
  - diff-aware checks
  - explicit stop-conditions engine
  - environment-required adapters
  - project and phase policy rules
  - sprint policy rules
  - tag-based policy rules and declarative rule messages
  - diff-aware policy rules for impacted-symbol, test-plan, and behavior-review gates
  - phase readiness and linked-task-health gates
- Added CI-oriented surfaces:
  - `doctor ci`
  - `doctor sprint`
  - `doctor report`
  - `artifacts/ci-summary.json`
  - `.kflow/artifacts/doctor-report.json`
  - `artifacts scaffold-ci` for packaged GitHub Actions CI workflow generation
- Added `task handoff` for agent or human continuation artifacts.
- Standardized JSON result metadata with `schema_version` and `generated_at`.
- Extended additive JSON `scope` and `summary` contracts across status, doctor, and report outputs.
- Added config migration/version handling for legacy `.kflow/config.yaml` payloads, including migration metadata in `config show --json` and `config validate --json`.
