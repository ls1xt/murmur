---
phase: 04-interaction-polish
plan: 03
subsystem: injection
tags: [partial-injection, delta, backspace, ydotool, audio-feedback]

requires:
  - phase: 04-interaction-polish
    provides: Multi-binding hotkey config from plan 04-01
provides:
  - Delta partial transcript injection (live text as user speaks)
  - inject_raw and inject_backspaces in TextInjector API
  - Thread-safe injection serialization via _inject_lock
  - WARNING-level audio feedback error logging
affects: [injection, main, audio]

tech-stack:
  added: []
  patterns: [delta injection with suffix detection, backspace-and-replace]

key-files:
  created: []
  modified:
    - murmur/main.py
    - murmur/injector/base.py
    - murmur/injector/ydotool.py
    - murmur/feedback/audio.py

key-decisions:
  - "inject_raw uses ydotool type without trailing space or strategy routing"
  - "inject_backspaces uses ydotool key with keycode 14 press/release pairs"
  - "First audio error at WARNING, subsequent at DEBUG to avoid spam"

patterns-established:
  - "Delta injection: if text.startswith(last_partial) -> inject suffix only"
  - "Diverged injection: backspace old partial length, then inject_raw new text"
  - "_inject_lock serializes all partial and final injection calls"

duration: ~5min
completed: 2026-02-18
---

# Plan 04-03 Summary

**Delta partial transcript injection with backspace-and-replace and serialized injection lock**

## Performance

- **Duration:** ~5 min
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Partial transcripts appear live in the focused window while speaking
- Delta algorithm: only new suffix injected when AssemblyAI appends words
- Backspace-and-replace when text diverges (e.g., AssemblyAI corrects earlier words)
- Final transcripts backspace partial and inject formatted text
- Injection serialized via threading.Lock to prevent partial/final races
- Audio feedback errors visible at WARNING on first occurrence

## Task Commits

1. **Task 1: Add inject_raw and inject_backspaces to injector** - `daae405` (feat)
2. **Task 2: Delta partial injection in DictationApp and audio upgrade** - `daae405` (feat, combined)

## Files Created/Modified
- `murmur/injector/base.py` - inject_raw and inject_backspaces abstract methods
- `murmur/injector/ydotool.py` - inject_raw (ydotool type) and inject_backspaces (ydotool key 14:1/14:0)
- `murmur/main.py` - _last_partial, _inject_lock, delta _on_partial_transcript, backspace _on_final_transcript
- `murmur/feedback/audio.py` - WARNING on first failure, DEBUG on subsequent

## Decisions Made
- Combined Tasks 1 and 2 into single commit since they're tightly coupled
- Used ydotool key with KEY_BACKSPACE keycode 14 (press/release pairs) for backspaces
- Reset _last_partial in _on_deactivate to prevent stale partial state across recordings

## Deviations from Plan
None - plan executed as specified.

## Issues Encountered
None.

## Next Phase Readiness
- All Phase 4 features complete
- Ready for phase verification

---
*Phase: 04-interaction-polish*
*Completed: 2026-02-18*
