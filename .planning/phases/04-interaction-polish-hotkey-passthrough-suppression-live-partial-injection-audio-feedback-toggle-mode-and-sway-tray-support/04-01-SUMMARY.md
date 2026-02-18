---
phase: 04-interaction-polish
plan: 01
subsystem: hotkey
tags: [evdev, uinput, grab-and-forward, multi-binding, wayland]

requires:
  - phase: 03-ux
    provides: hotkey system with single binding, tray icon
provides:
  - Multi-binding hotkey config (push-to-talk, toggle-start, toggle-stop)
  - Grab-and-forward input passthrough with UInput virtual devices
  - Backward-compatible config migration from old hotkey format
affects: [04-03, hotkey, config]

tech-stack:
  added: []
  patterns: [grab-and-forward via EVIOCGRAB + UInput, action-based dispatch]

key-files:
  created: []
  modified:
    - murmur/config.py
    - murmur/hotkey/base.py
    - murmur/hotkey/evdev.py
    - murmur/hotkey/__init__.py
    - murmur/main.py

key-decisions:
  - "Three default bindings: Ctrl+Alt+Space (push-to-talk), Ctrl+Alt+K (toggle-start), Ctrl+Alt+L (toggle-stop)"
  - "Action-based dispatch replaces mode-based dispatch in HotkeyListener"
  - "Synthetic modifier release/restore on hotkey fire/release for clean compositor state"

patterns-established:
  - "HotkeyBinding dataclass with modifiers/trigger/action for config"
  - "_ResolvedBinding with pre-resolved ecodes for runtime dispatch"
  - "Grab-and-forward: EVIOCGRAB + UInput.from_device + selective forwarding"

duration: ~8min
completed: 2026-02-18
---

# Plan 04-01 Summary

**Multi-binding hotkey config with grab-and-forward input passthrough via EVIOCGRAB and UInput**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Three independent hotkey bindings with Ctrl+Alt modifier combos
- Grab-and-forward pattern suppresses hotkey keys while forwarding all other input
- Modifier state management on hotkey fire/release for clean compositor transitions
- Backward-compatible config migration from old modifiers/trigger/mode format

## Task Commits

1. **Task 1: Multi-binding hotkey config and base class refactor** - `f5f87eb` (feat)
2. **Task 2: Grab-and-forward input passthrough in EvdevHotkeyListener** - `f5f87eb` (feat, combined with Task 1)

## Files Created/Modified
- `murmur/config.py` - HotkeyBinding dataclass, _default_bindings(), backward-compat migration
- `murmur/hotkey/base.py` - Action-based _dispatch_action/_dispatch_release replacing mode logic
- `murmur/hotkey/evdev.py` - EVIOCGRAB, UInput.from_device, grab-and-forward event loop
- `murmur/hotkey/__init__.py` - Factory passes bindings instead of modifiers/trigger/mode
- `murmur/main.py` - Startup banner shows all three bindings with labels

## Decisions Made
- Combined Tasks 1 and 2 into a single commit since they're tightly coupled
- Used _ResolvedBinding dataclass for resolved ecodes to avoid repeated lookups
- Suppressed modifier repeats during active hotkey to avoid compositor confusion

## Deviations from Plan
None - plan executed as specified.

## Issues Encountered
None.

## Next Phase Readiness
- Hotkey system ready for delta partial injection (04-03)
- All three binding modes functional: push-to-talk, toggle-start, toggle-stop

---
*Phase: 04-interaction-polish*
*Completed: 2026-02-18*
