---
phase: 05-macos-coding-support-hotkey-injector-clipboard-backends
plan: "04"
subsystem: platform
tags: [pynput, macos, darwin, hotkey, injector, pyobjc, factory]

# Dependency graph
requires:
  - phase: 05-01
    provides: PynputHotkeyListener implementation
  - phase: 05-02
    provides: PynputInjector implementation
  - phase: 05-03
    provides: check_accessibility and check_microphone helpers
provides:
  - Factory wiring: create_hotkey_listener dispatches to PynputHotkeyListener on darwin
  - Factory wiring: create_injector dispatches to PynputInjector on darwin
  - Startup permission checks on darwin (Accessibility + Microphone) with actionable errors
  - Conditional darwin-only deps declared in pyproject.toml
affects: [06-tooling-and-integration-for-linux-and-macos-setup-service-install]

# Tech tracking
tech-stack:
  added:
    - "pynput>=1.7.0 (darwin-only conditional dep in pyproject.toml)"
    - "pyobjc-framework-ApplicationServices>=9.0 (darwin-only conditional dep)"
  patterns:
    - "sys.platform dispatch in match/case factories with explicit 'pynput' case and darwin elif"
    - "Platform-gated startup checks: darwin branch replaces linux ydotoold check with elif"

key-files:
  created: []
  modified:
    - murmur/hotkey/__init__.py
    - murmur/injector/__init__.py
    - murmur/main.py
    - pyproject.toml

key-decisions:
  - "Added import sys to main.py (was missing; required for sys.platform check in run())"
  - "darwin startup block replaces ydotoold check entirely via elif (no is_available() call on darwin since pynput needs Accessibility which check_accessibility covers)"
  - "Pre-existing E501 ruff violations in main.py left deferred (5 violations exist before this plan's changes, none introduced by new code)"

patterns-established:
  - "Factory darwin dispatch: explicit 'pynput' case + elif sys.platform == 'darwin' in auto arm"
  - "Startup guard pattern: if sys.platform == 'darwin': check permissions; elif: check linux daemon"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-02-20
---

# Phase 05 Plan 04: Wire macOS Backends into Application Summary

**Factory functions and startup wired for darwin: pynput backends dispatched on macOS, permission checks at startup, conditional deps in pyproject.toml -- Linux behavior unchanged**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-20T10:18:39Z
- **Completed:** 2026-02-20T10:20:53Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Updated hotkey and injector factories with explicit "pynput" backend case and darwin elif in the "auto" arm, preserving all Linux code paths untouched
- Added macOS startup permission checks (Accessibility + Microphone) to DictationApp.run() with actionable System Settings guidance; Linux ydotoold check preserved in elif
- Added pynput and pyobjc-framework-ApplicationServices as darwin-only conditional dependencies to pyproject.toml; updated description to mention macOS

## Task Commits

Each task was committed atomically:

1. **Task 1: Update factories and pyproject.toml for darwin dispatch** - `5dbeb0b` (feat)
2. **Task 2: Add macOS permission checks to DictationApp.run()** - `339c4a8` (feat)

**Plan metadata:** `[docs commit]` (docs: complete plan)

## Files Created/Modified

- `murmur/hotkey/__init__.py` - Added "pynput" explicit case and darwin elif in auto arm of create_hotkey_listener
- `murmur/injector/__init__.py` - Added "pynput" explicit case and darwin elif in auto arm of create_injector
- `murmur/main.py` - Added import sys; replaced unconditional ydotoold check with platform-aware darwin/elif block calling check_accessibility and check_microphone
- `pyproject.toml` - Added pynput>=1.7.0 and pyobjc-framework-ApplicationServices>=9.0 as darwin-only deps; updated description to "Linux and macOS"

## Decisions Made

- Added `import sys` to main.py (was absent; plan assumed it existed but it did not -- Rule 3 auto-fix)
- darwin startup block uses `elif not self.injector.is_available()` for linux (not a nested if), preserving original semantics exactly
- Pre-existing ruff E501 violations in main.py (5 lines over 88 chars) deferred as out-of-scope

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added missing `import sys` to main.py**
- **Found during:** Task 2 (Add macOS permission checks to DictationApp.run())
- **Issue:** Plan instructed to "Verify the existing `import sys` is present" but sys was not imported in main.py -- required for sys.platform check
- **Fix:** Added `import sys` to the stdlib imports block (alphabetical order, between signal and threading)
- **Files modified:** murmur/main.py
- **Verification:** py_compile passes; sys.platform used correctly in run()
- **Committed in:** 339c4a8 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking missing import)
**Impact on plan:** Essential for the darwin platform check to work. No scope creep.

## Issues Encountered

- ruff E501 check on main.py reveals 5 pre-existing line-length violations (none from this plan's new code). Deferred as out-of-scope per deviation rules.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All macOS backends fully wired: pynput hotkey + injector dispatch on darwin, permission checks at startup
- pyproject.toml declares correct darwin-only conditional deps
- Phase 6 (tooling and integration) can now proceed with install/service setup for both Linux and macOS

---
## Self-Check: PASSED

- murmur/hotkey/__init__.py: FOUND
- murmur/injector/__init__.py: FOUND
- murmur/main.py: FOUND
- pyproject.toml: FOUND
- 05-04-SUMMARY.md: FOUND
- Commit 5dbeb0b: FOUND
- Commit 339c4a8: FOUND

*Phase: 05-macos-coding-support-hotkey-injector-clipboard-backends*
*Completed: 2026-02-20*
