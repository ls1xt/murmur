---
phase: 02-reliability
plan: 01
subsystem: error-handling
tags: [fatal-exit, notify-send, websocket, assemblyai, startup-validation]

requires:
  - phase: 01-foundation
    provides: Package structure, test infrastructure, pyright strict
provides:
  - "fatal() and fatal_from_thread() error exit helpers in murmur/errors.py"
  - "Startup validation for ydotoold and API key"
  - "WebSocket error classification (1008=auth, 3005=session expired)"
  - "Unexpected termination detection in AssemblyAI transcriber"
affects: [02-reliability, 03-ux]

tech-stack:
  added: [notify-send]
  patterns: [fatal-exit-helper, dual-notification-stderr-desktop]

key-files:
  created:
    - murmur/errors.py
    - tests/test_errors.py
  modified:
    - murmur/main.py
    - murmur/transcriber/assemblyai.py
    - tests/test_transcriber.py

key-decisions:
  - "Extracted _notify() helper for desktop notification (best-effort, non-fatal if missing)"
  - "Top-level import of fatal_from_thread in assemblyai.py (not lazy) for testability"
  - "contextlib.suppress for notify-send errors per Ruff SIM105"

patterns-established:
  - "Fatal exit pattern: fatal() for main thread, fatal_from_thread() for background threads"
  - "Error classification: parse error string for known codes before formatting message"

requirements-completed: [RELY-01, RELY-02, RELY-05]

duration: 3min
completed: 2026-02-17
---

# Phase 2 Plan 01: Fatal Error Infrastructure Summary

**Fatal exit helpers with dual notification (stderr + notify-send), WebSocket error classification, and startup validation for ydotoold and API key**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-17
- **Completed:** 2026-02-17
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created `murmur/errors.py` with `fatal()` and `fatal_from_thread()` for consistent error exits
- Wired WebSocket error classification into AssemblyAI transcriber (1008=auth, 3005=session expired)
- Added unexpected termination detection (exits if WebSocket drops while streaming)
- Replaced ad-hoc startup checks with `fatal()` calls for ydotoold and API key

## Task Commits

1. **Task 1: Create murmur/errors.py with fatal() helper and startup validation** - `e04c24a` (feat)
2. **Task 2: Wire fatal exits into AssemblyAI transcriber error handlers** - `04be552` (feat)
3. **Style fix:** - `2ab2983` (style)

## Files Created/Modified
- `murmur/errors.py` - Fatal exit helpers: fatal(), fatal_from_thread(), _notify()
- `murmur/main.py` - Startup validation now uses fatal() for ydotoold and API key
- `murmur/transcriber/assemblyai.py` - Error classification and unexpected termination exit
- `tests/test_errors.py` - 10 tests for fatal exit behavior and startup validation
- `tests/test_transcriber.py` - 5 new tests for error handling and termination

## Decisions Made
- Used top-level import of fatal_from_thread in assemblyai.py instead of lazy imports for clean mock patching
- Extracted _notify() as shared helper between fatal() and fatal_from_thread()
- Used contextlib.suppress for notify-send errors per Ruff SIM105 preference

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused sys import from main.py**
- **Found during:** Task 1 (startup validation update)
- **Issue:** After replacing sys.exit(1) with fatal(), the sys import became unused (pyright reportUnusedImport)
- **Fix:** Removed `import sys` from main.py
- **Verification:** pyright 0 errors
- **Committed in:** e04c24a

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial cleanup, no scope change.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- fatal() and fatal_from_thread() are ready for Plans 02-02 (evdev disconnect) and 02-03 (clipboard injection)
- All 64 tests pass, pyright strict and ruff at zero errors

---
*Phase: 02-reliability*
*Completed: 2026-02-17*
