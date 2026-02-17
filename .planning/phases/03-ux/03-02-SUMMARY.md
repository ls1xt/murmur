---
phase: 03-ux
plan: 02
subsystem: feedback
tags: [pystray, pillow, system-tray, tray-icon, sway, gnome]

requires:
  - phase: 03-ux
    provides: NotifyConfig, TrayConfig, _request_shutdown in DictationApp
provides:
  - "TrayIcon class with idle/recording/error states via PIL-rendered colored circles"
  - "Graceful degradation when pystray or display unavailable"
  - "Tray menu with dynamic status line and Quit action"
  - "State transitions wired into DictationApp lifecycle"
affects: []

tech-stack:
  added: [pystray, Pillow]
  patterns: [daemon-thread-tray, graceful-import-fallback, emoji-style-icons]

key-files:
  created:
    - murmur/feedback/tray.py
    - tests/test_tray.py
  modified:
    - murmur/main.py
    - murmur/feedback/__init__.py
    - pyproject.toml

key-decisions:
  - "Colored circles (gray/red/orange) as 'emoji-style' icons -- avoids font bundling"
  - "Daemon thread for pystray.Icon.run() -- not run_detached (Linux doesn't need it)"
  - "Late import of pystray and PIL inside start() for graceful fallback"
  - "Dynamic menu status text via callable MenuItem text parameter"

patterns-established:
  - "Daemon thread tray pattern: pystray.Icon.run() in threading.Thread(daemon=True)"
  - "Graceful import fallback: try/except ImportError -> _available=False, all methods become no-ops"
  - "State colors dict: centralized color definitions for icon rendering"

requirements-completed: [UX-01]

duration: 5min
completed: 2026-02-17
---

# Phase 3 Plan 02: System Tray Icon Summary

**System tray icon with PIL-rendered colored circles for idle/recording/error states, pystray daemon thread, and graceful degradation**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-17
- **Completed:** 2026-02-17
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created TrayIcon class with three distinct visual states (gray=idle, red=recording, orange=error)
- PIL ImageDraw renders 64x64 RGBA circles -- no font or emoji bundling needed
- pystray runs in daemon thread, non-blocking
- Graceful degradation: if pystray unavailable, logs warning to stderr, daemon continues
- Context menu shows dynamic status text and Quit action
- Quit from tray triggers clean daemon shutdown via _request_shutdown

## Task Commits

1. **Task 1: Create TrayIcon module with PIL-rendered state icons** - `b7876f7` (feat)
2. **Task 2: Wire TrayIcon into DictationApp with state transitions** - `c53cadb` (feat)

## Files Created/Modified
- `murmur/feedback/tray.py` - TrayIcon class with state management, icon rendering, graceful fallback
- `murmur/main.py` - TrayIcon integration, state transitions on activate/deactivate/error
- `murmur/feedback/__init__.py` - Updated exports to include TrayIcon
- `pyproject.toml` - Added pystray>=0.19.5 and Pillow>=10.0.0 dependencies
- `tests/test_tray.py` - 12 tests covering graceful degradation, icon creation, menu, callbacks

## Decisions Made
- Used colored circles instead of actual emoji characters -- more reliable across systems, no font bundling
- Used Callable from collections.abc (not typing) per ruff UP035
- Dynamic menu text via callable parameter in pystray.MenuItem

## Deviations from Plan

### Auto-fixed Issues

**1. [Ruff UP035] Import Callable from collections.abc**
- **Found during:** Task 1 (TrayIcon module creation)
- **Issue:** Ruff flagged `from typing import Callable` as deprecated
- **Fix:** Changed to `from collections.abc import Callable`
- **Verification:** ruff check passes
- **Committed in:** c53cadb

**2. [Ruff SIM117] Combine nested with statements in test**
- **Found during:** Task 2 (test verification)
- **Issue:** Nested `with` statements in test_tray.py
- **Fix:** Combined into single `with` using parenthesized context managers
- **Verification:** ruff check passes
- **Committed in:** c53cadb

---

**Total deviations:** 2 auto-fixed (2 style)
**Impact on plan:** Trivial style fixes, no scope change.

## Issues Encountered
None

## User Setup Required
None - pystray and Pillow installed via pip. AppIndicator extension may be needed on GNOME for tray visibility.

## Next Phase Readiness
- Phase 3 complete: both UX-01 (tray) and UX-02 (notifications) implemented
- All 93 tests pass, pyright strict 0 errors, ruff clean
- Ready for phase verification

---
*Phase: 03-ux*
*Completed: 2026-02-17*
