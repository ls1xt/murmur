---
phase: 05-macos-coding-support-hotkey-injector-clipboard-backends
plan: "01"
subsystem: hotkey
tags: [pynput, macos, hotkey, keyboard-listener, evdev-translation]

# Dependency graph
requires:
  - phase: 04-interaction-polish
    provides: HotkeyListener ABC and _dispatch_action/_dispatch_release protocol
provides:
  - PynputHotkeyListener concrete class in murmur/hotkey/pynput.py
  - EVDEV-to-pynput canonical key translation table for macOS hotkey backend
affects:
  - 05-02-PLAN.md (hotkey factory update to dispatch to pynput on darwin)
  - 05-03-PLAN.md (macOS injector — depends on same factory pattern)

# Tech tracking
tech-stack:
  added: [pynput (keyboard.Listener)]
  patterns:
    - Manual modifier-set tracking with listener.canonical() for left/right key unification
    - Evdev key name translation table for cross-platform binding config compatibility
    - Fresh Listener instance per start() call (pynput threads are not restartable)

key-files:
  created:
    - murmur/hotkey/pynput.py
  modified: []

key-decisions:
  - "Use raw keyboard.Listener with manual modifier set tracking — not GlobalHotKeys (pynput issue #297: GlobalHotKeys silently fails for Ctrl+Alt on macOS)"
  - "No event suppression on macOS — keys pass through; grab-and-forward is Linux-only"
  - "push_to_talk_debounce_ms accepted in __init__ for API compat with EvdevHotkeyListener but unused (macOS does not generate spurious key-up events)"

patterns-established:
  - "Pattern 1: Canonical key translation table at module level maps evdev names to pynput Key values"
  - "Pattern 2: _translate_evdev_name handles single-letter (KEY_A) and single-digit (KEY_0) keys dynamically"
  - "Pattern 3: _resolve_bindings converts HotkeyBinding list to _ResolvedBinding list at __init__ time"

requirements-completed: []

# Metrics
duration: 5min
completed: 2026-02-20
---

# Phase 5 Plan 01: PynputHotkeyListener Summary

**pynput keyboard.Listener backend for macOS with manual modifier-set tracking, evdev-to-pynput canonical translation table, and no event suppression**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-02-20T10:14:27Z
- **Completed:** 2026-02-20T10:19:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Implemented PynputHotkeyListener as a concrete subclass of HotkeyListener using pynput's raw keyboard.Listener
- Built EVDEV_TO_PYNPUT_CANONICAL translation table covering all modifier keys, common specials, function keys, and dynamic alpha/digit mapping
- Used manual modifier-set tracking (listener.canonical() before set membership) to unify left/right key variants — avoids the GlobalHotKeys Ctrl+Alt bug on macOS
- All abstract methods (start, stop) implemented; _on_press/_on_release handle canonical key canonicalization

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement PynputHotkeyListener** - `547e28b` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `murmur/hotkey/pynput.py` - PynputHotkeyListener class with evdev-to-pynput translation table, _ResolvedBinding dataclass, and raw Listener-based hotkey detection

## Decisions Made

- Used raw `keyboard.Listener` with manual `_held: set` tracking rather than `GlobalHotKeys` because pynput issue #297 documents that GlobalHotKeys silently fails for Ctrl+Alt combos on macOS
- No darwin_intercept / event suppression per earlier user decision: macOS does not support grab-and-forward like Linux evdev
- `push_to_talk_debounce_ms` parameter accepted for API compatibility with EvdevHotkeyListener, stored but not used

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

pynput is not installed on this Linux development machine (expected — it is a macOS-only dependency). The import-time verification step fell back to py_compile syntax check, which passed cleanly. Structural checks verified via Python AST parsing.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `murmur/hotkey/pynput.py` with `PynputHotkeyListener` is ready for plan 05-02 to wire into the hotkey factory (`create_hotkey_listener`) under the `darwin` platform branch
- Translation table covers all keys used in default HotkeyConfig bindings (KEY_LEFTCTRL, KEY_LEFTALT, KEY_SPACE, KEY_K, KEY_L, KEY_C)

---
*Phase: 05-macos-coding-support-hotkey-injector-clipboard-backends*
*Completed: 2026-02-20*
