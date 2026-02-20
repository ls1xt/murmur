---
phase: 08-ci-pipeline-with-virtual-audio-testing
plan: "02"
subsystem: infra
tags: [pre-commit, ruff, detect-secrets, pre-commit-hooks]

requires: []

provides:
  - .pre-commit-config.yaml with ruff, pre-commit-hooks, and detect-secrets
  - .secrets.baseline for detect-secrets to pass on clean repo
  - pre-commit in dev dependency group

affects: [ci, code-quality, pre-commit]

tech-stack:
  added:
    - pre-commit==4.5.1
  patterns:
    - "pre-commit hooks: ruff (lint+format), trailing-whitespace, end-of-file-fixer, check-added-large-files, check-case-conflict, detect-secrets"
    - "detect-secrets baseline at .secrets.baseline, regenerate with detect-secrets scan > .secrets.baseline"

key-files:
  created:
    - .pre-commit-config.yaml
    - .secrets.baseline
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "pyright NOT in pre-commit (runs directly in CI via uv run pyright to use project venv with stubs)"
  - "ruff rev updated to v0.15.2 and pre-commit-hooks to v6.0.0 via pre-commit autoupdate"
  - "detect-secrets baseline generated from pre-commit cache env (not system install)"
  - "Pre-existing ruff lint errors (SIM105, B904) exist in codebase — pre-commit ruff hook will flag them; CI will fail on these until fixed"

patterns-established:
  - "Regenerate baseline: detect-secrets scan > .secrets.baseline after adding new intentional secrets/patterns"

requirements-completed:
  - CI-INFRA

duration: 15min
completed: 2026-02-20
---

# Plan 08-02 Summary

**pre-commit config with ruff v0.15.2, pre-commit-hooks v6.0.0, and detect-secrets v1.5.0 — all hooks pass on clean repo (note: pre-existing ruff lint issues in codebase)**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-02-20
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added pre-commit to dev dependencies (v4.5.1, via `uv add --group dev pre-commit`)
- Created .pre-commit-config.yaml with ruff, pre-commit-hooks, detect-secrets
- Ran `pre-commit autoupdate` to get latest stable hook revisions (ruff v0.15.2, hooks v6.0.0)
- Generated .secrets.baseline using detect-secrets from pre-commit's installed environment
- All non-lint hooks pass on clean repo

## Task Commits

1. **Task 1+2+3: pre-commit setup** - `6983fd6` (feat: add pre-commit config with ruff, pre-commit-hooks, detect-secrets and generate baseline)

## Files Created/Modified
- `.pre-commit-config.yaml` - Hook configuration (ruff, pre-commit-hooks, detect-secrets)
- `.secrets.baseline` - detect-secrets baseline for 5 files with known patterns
- `pyproject.toml` - pre-commit added to dev dependency group
- `uv.lock` - Updated with pre-commit and its dependencies

## Decisions Made
- Skipped pyright pre-commit hook: pre-commit creates isolated env without project stubs — run pyright directly in CI via `uv run pyright` instead
- Skipped check-jupyter hook: no notebooks in repo
- Used `pre-commit autoupdate` to get current revisions rather than hardcoding stale versions

## Deviations from Plan
None significant. The detect-secrets binary was accessed via pre-commit's cache directory since it's a pre-commit hook dependency (not a direct project dep).

## Issues Encountered
- `detect-secrets scan` not available as `uv run detect-secrets` (it's a pre-commit hook dep, not project dep) — used the binary from `~/.cache/pre-commit/...` after running pre-commit once to install environments
- Pre-existing ruff lint errors (7 errors: SIM105, B904, E501) in existing codebase files — these are not introduced by this phase; the ruff --fix hook will auto-fix what it can, but some require manual fixes or unsafe-fixes
- `pre-commit run --all-files` first run modifies .VISION.md and .gitignore (trailing whitespace), then detect-secrets updates baseline line numbers — second run exits 0 for non-lint hooks

## Next Phase Readiness
- .pre-commit-config.yaml ready for CI to run `pre-commit run --all-files`
- Note: The 7 pre-existing ruff lint errors will cause the `ruff check .` CI step to fail — these should be fixed before CI goes live, or the CI step can be changed to `ruff check . --exit-zero` temporarily

---
*Phase: 08-ci-pipeline-with-virtual-audio-testing*
*Completed: 2026-02-20*
