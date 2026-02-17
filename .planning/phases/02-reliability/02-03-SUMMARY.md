---
phase: 02-reliability
plan: 03
subsystem: injector
tags: [ydotool, wl-copy, clipboard, unicode, wayland]

requires:
  - phase: 02-reliability
    provides: fatal() from murmur/errors.py
provides:
  - "Three injection strategies: ydotool, clipboard, clipboard-fallback"
  - "Non-ASCII text injection via wl-copy + Ctrl+V"
  - "--inject CLI flag and MURMUR_INJECT_STRATEGY env var"
affects: [03-ux]

tech-stack:
  added: [wl-clipboard, argparse]
  patterns: [strategy-dispatch, ascii-detection-fallback]

key-files:
  created: []
  modified:
    - murmur/injector/ydotool.py
    - murmur/injector/__init__.py
    - murmur/config.py
    - murmur/main.py
    - tests/test_injector.py
    - tests/test_config.py

key-decisions:
  - "Default strategy: clipboard-fallback (fast ASCII via ydotool, reliable Unicode via clipboard)"
  - "Use text.isascii() for strategy dispatch in clipboard-fallback mode"
  - "ydotool key 29:1 47:1 47:0 29:0 for Ctrl+V (numeric keycodes for reliability)"

patterns-established:
  - "Injection strategy pattern: dispatch in inject() based on _inject_strategy field"
  - "CLI argument override: argparse flag -> config field override"

requirements-completed: [RELY-04]

duration: 4min
completed: 2026-02-17
---

# Phase 2 Plan 03: Three Injection Strategies Summary

**Three injection strategies (ydotool direct, clipboard, clipboard-fallback) with wl-copy + Ctrl+V for non-ASCII text and --inject CLI flag**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-17
- **Completed:** 2026-02-17
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- Implemented three injection strategies selectable via --inject CLI flag
- clipboard-fallback (default): ydotool type for ASCII, wl-copy + Ctrl+V for non-ASCII
- clipboard: always wl-copy + ydotool key for all text
- ydotool: direct ydotool type (ASCII only, fast)
- Added argparse to main() entry point
- Added MURMUR_INJECT_STRATEGY env var override

## Task Commits

1. **Task 1: Add inject_strategy config and --inject CLI flag** - `3bef5d6` (feat)
2. **Task 2: Implement three injection strategies** - `8519c3d` (feat)

## Files Created/Modified
- `murmur/config.py` - Added inject_strategy field (default: clipboard-fallback) and env var override
- `murmur/main.py` - Added argparse with --inject flag
- `murmur/injector/ydotool.py` - Three strategies, _inject_via_clipboard() method
- `murmur/injector/__init__.py` - Pass inject_strategy to YdotoolInjector
- `tests/test_injector.py` - 16 tests covering all strategies
- `tests/test_config.py` - inject_strategy default and env var tests

## Decisions Made
- Default strategy is clipboard-fallback (Claude's discretion per CONTEXT.md)
- Use text.isascii() for ASCII detection (Python built-in, reliable)
- Use numeric keycodes (29:1 47:1 47:0 29:0) for Ctrl+V simulation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fix test_exits_when_api_key_missing for argparse**
- **Found during:** Task 1 (argparse addition)
- **Issue:** Adding argparse to main() caused existing test to fail (pytest args passed to argparse)
- **Fix:** Mock sys.argv in test
- **Verification:** Test passes
- **Committed in:** 8519c3d

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Trivial test fix, no scope change.

## Issues Encountered
None

## User Setup Required
None - wl-clipboard (wl-copy) is a system package, typically pre-installed on Wayland.

## Next Phase Readiness
- Phase 2 complete: all reliability requirements addressed
- Ready for Phase 3 (UX) or verification

---
*Phase: 02-reliability*
*Completed: 2026-02-17*
