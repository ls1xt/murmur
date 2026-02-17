---
phase: 03-ux
plan: 01
subsystem: feedback
tags: [notify-send, desktop-notifications, cli-flags]

requires:
  - phase: 02-reliability
    provides: Fatal error infrastructure with _notify() helper
provides:
  - "Notifier class with configurable verbosity (off/errors/verbose)"
  - "--notify CLI flag for notification control"
  - "NotifyConfig and TrayConfig dataclasses in config.py"
  - "Integration into DictationApp lifecycle (startup, recording, errors)"
affects: []

tech-stack:
  added: [notify-send]
  patterns: [configurable-verbosity, cli-override-config]

key-files:
  created:
    - murmur/feedback/notify.py
    - tests/test_notify.py
  modified:
    - murmur/config.py
    - murmur/main.py
    - murmur/feedback/__init__.py

key-decisions:
  - "Kept existing _notify() in errors.py as fallback for early startup (before DictationApp exists)"
  - "Added TrayConfig alongside NotifyConfig to config.py (prep for plan 02)"
  - "Used --urgency=critical for error notifications (persistent) and --expire-time=5000 for info (auto-expire)"

patterns-established:
  - "CLI flag override pattern: argparse flag -> config field override (same as --inject)"
  - "Notification verbosity pattern: off/errors/verbose with _send() helper"

requirements-completed: [UX-02]

duration: 5min
completed: 2026-02-17
---

# Phase 3 Plan 01: Desktop Notifications Summary

**Configurable desktop notifications via notify-send with --notify off|errors|verbose CLI flag and DictationApp integration**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-17
- **Completed:** 2026-02-17
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created Notifier class with error() and info() methods respecting three verbosity levels
- Added --notify CLI flag with off|errors|verbose choices
- Wired notifications into DictationApp: startup info, recording state changes, transcriber errors
- Error notifications use --urgency=critical (persistent), info uses --expire-time=5000 (auto-expire)
- Missing notify-send never crashes daemon (contextlib.suppress)

## Task Commits

1. **Task 1: Create Notifier module with configurable verbosity** - `280e3f3` (feat)
2. **Task 2: Wire Notifier into DictationApp and add --notify CLI flag** - `ccf53ab` (feat)

## Files Created/Modified
- `murmur/feedback/notify.py` - Notifier class with error/info methods and verbosity control
- `murmur/config.py` - Added NotifyConfig and TrayConfig dataclasses, env var MURMUR_NOTIFY_LEVEL
- `murmur/main.py` - Notifier integration, --notify CLI flag, _stop_event refactor, _request_shutdown
- `murmur/feedback/__init__.py` - Updated exports
- `tests/test_notify.py` - 8 tests covering all verbosity levels and resilience

## Decisions Made
- Kept errors.py _notify() intact as module-level fallback for early startup before DictationApp
- Added both NotifyConfig and TrayConfig to config.py in one pass to avoid plan 02 needing config changes
- Moved stop_event from local variable to self._stop_event instance attribute (needed for tray Quit)

## Deviations from Plan
None - plan executed as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Notifier and TrayConfig ready for plan 02 (tray icon integration)
- _request_shutdown method ready for tray Quit callback
- All 81+8=89 tests pass, pyright strict, ruff clean

---
*Phase: 03-ux*
*Completed: 2026-02-17*
