---
phase: 04-interaction-polish
plan: 02
subsystem: feedback
tags: [sni, dbus, gio, waybar, sway, tray]

requires:
  - phase: 03-ux
    provides: TrayIcon with pystray backend and state management
provides:
  - SNI tray backend for Sway/waybar via Gio.DBus
  - Colored circle ARGB32 pixmap icons
  - Thread-safe state updates via GLib.idle_add
affects: [tray, feedback, sway]

tech-stack:
  added: []
  patterns: [StatusNotifierItem D-Bus protocol, RGBA-to-ARGB32 pixel conversion]

key-files:
  created:
    - murmur/feedback/sni.py
  modified:
    - murmur/feedback/tray.py

key-decisions:
  - "Extracted SNI code into separate sni.py with file-level pyright suppression for untyped gi.repository"
  - "SniTray registers at /StatusNotifierItem with bus name org.kde.StatusNotifierItem-{PID}-1"
  - "Left-click Activate triggers quit callback (simplest behavior)"

patterns-established:
  - "File-level pyright suppression for heavy untyped library usage (gi.repository)"
  - "RGBA to ARGB32 big-endian conversion for SNI IconPixmap"
  - "_is_sway() detection via SWAYSOCK env var"

duration: ~5min
completed: 2026-02-18
---

# Plan 04-02 Summary

**SNI tray backend for Sway/waybar via Gio.DBus with ARGB32 colored circle icons**

## Performance

- **Duration:** ~5 min
- **Tasks:** 1
- **Files modified:** 3

## Accomplishments
- StatusNotifierItem D-Bus implementation registers with waybar's StatusNotifierWatcher
- Colored circle icons rendered as ARGB32 pixmaps (gray=idle, red=recording, orange=error)
- Thread-safe state updates via GLib.idle_add with NewIcon signal emission
- Existing pystray backend unchanged and functional for non-Sway compositors

## Task Commits

1. **Task 1: SNI tray backend via Gio.DBus for Sway/waybar** - `ca0ec2e` (feat)

## Files Created/Modified
- `murmur/feedback/sni.py` - SniTray class with full SNI D-Bus lifecycle
- `murmur/feedback/tray.py` - Routes to SNI on Sway, pystray elsewhere
- `tests/test_tray.py` - SNI detection tests, delegation tests

## Decisions Made
- Extracted SNI into separate file for clean pyright suppression of untyped gi.repository
- Fixed pre-existing test bug: _appindicator_works() renamed to _is_sway() and uses module-level os import

## Deviations from Plan
- Extracted _SniTray into murmur/feedback/sni.py as SniTray (plan had it inline in tray.py)
- Reason: pyright strict mode requires file-level suppression for gi.repository untyped access

## Issues Encountered
None.

## Next Phase Readiness
- Tray icon visible in waybar on Sway
- pystray path continues to work unchanged on GNOME/KDE

---
*Phase: 04-interaction-polish*
*Completed: 2026-02-18*
