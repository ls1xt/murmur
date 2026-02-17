---
phase: 02-reliability
plan: 02
subsystem: hotkey
tags: [evdev, device-disconnect, fatal-exit]

requires:
  - phase: 02-reliability
    provides: fatal_from_thread() from murmur/errors.py
provides:
  - "Fatal exit on evdev device disconnect"
affects: []

tech-stack:
  added: []
  patterns: [fatal-exit-on-device-error]

key-files:
  created: []
  modified:
    - murmur/hotkey/evdev.py
    - tests/test_hotkey.py

key-decisions:
  - "Exit on ANY OSError from device read, not just ENODEV -- all are unrecoverable per KISS philosophy"

patterns-established:
  - "Device disconnect pattern: fatal_from_thread with device path in message"

requirements-completed: [RELY-03]

duration: 2min
completed: 2026-02-17
---

# Phase 2 Plan 02: evdev Device Disconnect Fatal Exit Summary

**Fatal exit on evdev device disconnect with device path in error message**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-17
- **Completed:** 2026-02-17
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Replaced silent device disconnect handler with fatal_from_thread() call
- Error message includes device path (e.g., "Input device disconnected: /dev/input/event0")
- Daemon exits immediately instead of continuing in degraded state

## Task Commits

1. **Task 1: Replace silent device disconnect handling with fatal exit** - `3e694b3` (feat)

## Files Created/Modified
- `murmur/hotkey/evdev.py` - OSError handler now calls fatal_from_thread instead of logging warning
- `tests/test_hotkey.py` - Added disconnect test with mocked selector and device

## Decisions Made
- Top-level import of fatal_from_thread (consistent with assemblyai.py pattern from Plan 02-01)

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ready for Plan 02-03 (injection strategies)

---
*Phase: 02-reliability*
*Completed: 2026-02-17*
