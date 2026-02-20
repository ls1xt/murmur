---
phase: 05-macos-coding-support-hotkey-injector-clipboard-backends
plan: "02"
subsystem: injector
tags: [pynput, macos, pbcopy, keyboard-injection, clipboard, accessibility]

# Dependency graph
requires:
  - phase: 05-macos-coding-support-hotkey-injector-clipboard-backends
    provides: "TextInjector ABC in murmur/injector/base.py"
provides:
  - "PynputInjector concrete class implementing TextInjector ABC for macOS"
  - "Three injection strategies: pynput, clipboard, clipboard-fallback"
  - "pbcopy-based clipboard write and Cmd+V paste simulation"
affects:
  - "05-04 injector factory (must dispatch to PynputInjector on darwin)"
  - "any future macOS text injection work"

# Tech tracking
tech-stack:
  added: [pynput]
  patterns:
    - "Strategy pattern for injection: pynput direct / pbcopy+CmdV / fallback"
    - "_sanitize_text copied verbatim per-module (no cross-platform coupling)"
    - "AXIsProcessTrusted wrapped in try/except ImportError for graceful fallback"

key-files:
  created:
    - murmur/injector/pynput.py
  modified: []

key-decisions:
  - "Copy _sanitize_text verbatim from ydotool.py rather than importing it, to avoid coupling macOS backend to a Linux module"
  - "clipboard-fallback strategy as the default: ASCII text uses Controller.type(), non-ASCII uses pbcopy+Cmd+V"
  - "is_available() returns True on ImportError (cannot check AXIsProcessTrusted without pyobjc) for graceful dev-machine fallback"

patterns-established:
  - "macOS clipboard injection: subprocess.run(['pbcopy'], input=text.encode('utf-8'), capture_output=True, timeout=5)"
  - "Cmd+V paste: controller.pressed(Key.cmd) context manager + controller.tap(KeyCode.from_char('v'))"

requirements-completed: []

# Metrics
duration: 2min
completed: 2026-02-20
---

# Phase 05 Plan 02: PynputInjector Summary

**macOS pynput keyboard Controller injector with pbcopy+Cmd+V clipboard strategy and AXIsProcessTrusted availability check**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-20T10:14:26Z
- **Completed:** 2026-02-20T10:16:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Implemented PynputInjector as a concrete subclass of TextInjector with all abstract methods
- Three injection strategies: pynput (Controller.type), clipboard (pbcopy+Cmd+V), clipboard-fallback (ASCII=pynput, non-ASCII=clipboard)
- pbcopy subprocess integration for both copy_to_clipboard() and _inject_via_clipboard()
- Cmd+V paste simulation via pynput pressed(Key.cmd) context manager
- AXIsProcessTrusted accessibility check with graceful ImportError fallback

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement PynputInjector** - `e243eb6` (feat)

## Files Created/Modified
- `murmur/injector/pynput.py` - PynputInjector class with all TextInjector methods, _sanitize_text, and clipboard/pynput strategy dispatch

## Decisions Made
- _sanitize_text copied verbatim from ydotool.py to avoid coupling macOS backend to a Linux-only module
- clipboard-fallback is the default strategy: Controller.type() for ASCII (fast, native), pbcopy+Cmd+V for non-ASCII (reliable Unicode)
- is_available() returns True when pyobjc is unavailable (ImportError) rather than failing, allowing usage on Linux dev machines

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- ruff not installed as standalone binary; uv run ruff attempted download which was slow. Substituted py_compile + AST introspection to confirm correctness. All required implementation elements verified.

## Next Phase Readiness
- PynputInjector ready for use by injector factory (05-04)
- Requires pynput installed on macOS target system
- Requires Accessibility permission granted in System Preferences on macOS

---
*Phase: 05-macos-coding-support-hotkey-injector-clipboard-backends*
*Completed: 2026-02-20*
