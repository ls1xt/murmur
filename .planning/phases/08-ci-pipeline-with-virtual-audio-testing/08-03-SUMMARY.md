---
phase: 08-ci-pipeline-with-virtual-audio-testing
plan: "03"
subsystem: infra
tags: [github-actions, ci, matrix, virtual-audio, snd-aloop, blackhole]

requires:
  - phase: 08-ci-01
    provides: --virtual-mic pytest flag
  - phase: 08-ci-02
    provides: .pre-commit-config.yaml and pre-commit in dev deps

provides:
  - .github/workflows/ci.yml with 2x2 matrix (ubuntu-latest+macos-latest x Python 3.11+3.12)
  - Virtual audio setup steps (snd-aloop Linux, BlackHole macOS)
  - Full CI step pipeline: pre-commit, ruff, pyright, pytest, pytest --virtual-mic

affects: [ci, github-actions]

tech-stack:
  added: []
  patterns:
    - "actions/checkout@v4, actions/setup-python@v5, astral-sh/setup-uv@v5"
    - "HOMEBREW_NO_AUTO_UPDATE=1 for macOS brew installs in CI"
    - "runner.os conditional for platform-specific steps"

key-files:
  created:
    - .github/workflows/ci.yml

key-decisions:
  - "pyright runs as uv run pyright (not via pre-commit) to use project venv with all type stubs"
  - "HOMEBREW_NO_AUTO_UPDATE=1 to prevent brew self-update on macOS runners (~2min savings)"
  - "fail-fast: true (explicit, cancels remaining matrix jobs on first failure)"
  - "Unit tests and virtual-mic tests are separate steps for distinguishable CI failures"

patterns-established:
  - "CI step order: virtual audio setup → install deps → pre-commit → lint → format → type check → unit tests → virtual-mic tests"

requirements-completed:
  - CI-INFRA

duration: 10min
completed: 2026-02-20
---

# Plan 08-03 Summary

**.github/workflows/ci.yml with 2×2 matrix (ubuntu-latest+macos-latest, Python 3.11+3.12), virtual audio device setup (snd-aloop/BlackHole), and complete 7-step CI pipeline**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-02-20
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Created .github/workflows/ci.yml triggering on push/PR to main
- Matrix: 4 parallel jobs (2 OS × 2 Python versions)
- Linux: `sudo modprobe snd-aloop` virtual audio setup
- macOS: `brew install blackhole-2ch` with HOMEBREW_NO_AUTO_UPDATE=1
- astral-sh/setup-uv@v5 for dependency installation
- Full pipeline: pre-commit → ruff check → ruff format --check → pyright → pytest → pytest --virtual-mic

## Task Commits

1. **Task 1: Create .github/workflows/ci.yml** - `b774e6a` (feat: add GitHub Actions CI workflow)

## Files Created/Modified
- `.github/workflows/ci.yml` - Full CI workflow with 4-job matrix

## Decisions Made
- pyright not run via pre-commit hook (isolated env lacks project stubs) — runs as `uv run pyright` step
- No explicit `actions/cache` — `astral-sh/setup-uv@v5` provides built-in caching

## Deviations from Plan
None — implemented exactly as specified.

## Issues Encountered
None.

## Next Phase Readiness
- CI workflow ready for GitHub to execute on push
- Wave 3 (08-04: README badge) unblocked

---
*Phase: 08-ci-pipeline-with-virtual-audio-testing*
*Completed: 2026-02-20*
