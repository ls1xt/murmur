---
phase: quick-fix-verification
plan: 1
subsystem: core
tags: [thread-safety, resource-management, cli, lockfile, bugfix]
dependency_graph:
  requires: []
  provides: [thread-safe-transcriber, cli-entry-point, pyaudio-leak-fixed, pgrep-error-fixed]
  affects: [murmur/transcriber/base.py, murmur/transcriber/assemblyai.py, murmur/main.py, murmur/feedback/audio.py, murmur/injector/ydotool.py, pyproject.toml, uv.lock]
tech_stack:
  added: []
  patterns: [threading.Lock-as-property, nested-try-finally]
key_files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - murmur/transcriber/base.py
    - murmur/transcriber/assemblyai.py
    - murmur/main.py
    - murmur/feedback/audio.py
    - murmur/injector/ydotool.py
decisions:
  - "_is_streaming exposed as property with Lock (not Lock acquired at call sites) -- keeps all subclass code unchanged"
  - "Nested try/finally for PyAudio (stream inner, pa outer) -- ensures stream closed before pa.terminate()"
  - "_lock in DictationApp guards is_streaming check only, not the entire activate/deactivate body -- avoids blocking the hotkey thread"
metrics:
  duration: "~2 minutes"
  completed: "2026-02-17"
  tasks: 3
  files_modified: 7
---

# Quick Fix 1: Fix All Verification Issues Summary

Seven post-phase-3 audit issues fixed: thread safety on _is_streaming via threading.Lock property, logged audio errors regardless of callback, DictationApp._lock used to prevent double-activation, PyAudio stream/pa closed in nested try/finally, pgrep FileNotFoundError returns False with warning, uv.lock regenerated, and murmur CLI entry point declared.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Regenerate uv.lock and add CLI entry point | 88257b7 | pyproject.toml, uv.lock |
| 2 | Protect _is_streaming with threading.Lock and log errors | 0f83361 | murmur/transcriber/base.py, murmur/transcriber/assemblyai.py |
| 3 | Fix DictationApp._lock, PyAudio resource leak, pgrep error | 16c2a0a | murmur/main.py, murmur/feedback/audio.py, murmur/injector/ydotool.py |

## Changes Made

### Task 1: pyproject.toml + uv.lock

Added `[project.scripts]` section to `pyproject.toml`:
```toml
[project.scripts]
murmur = "murmur.main:main"
```

Ran `uv lock` to regenerate the lockfile so pystray and Pillow appear in `uv.lock`.

### Task 2: Thread-safe _is_streaming + error logging

`murmur/transcriber/base.py`: Added `_streaming_lock = threading.Lock()` and replaced the plain `_is_streaming: bool` attribute with a property that acquires the lock on every read and write. The backing field is `_streaming`. All subclass code using `self._is_streaming` continues to work unchanged.

`murmur/transcriber/assemblyai.py`: In `_stream_audio`, changed the error handler so `logger.error("Audio stream error: %s", e)` is always called when streaming is active, then `_on_error` is called only if the callback is set.

### Task 3: DictationApp._lock, audio.py cleanup, ydotool.py pgrep fix

`murmur/main.py`: `_on_activate` now acquires `self._lock` and returns early if `transcriber.is_streaming` (already recording). `_on_deactivate` acquires `self._lock` and returns early if not streaming (already stopped). This prevents race conditions on rapid double-press.

`murmur/feedback/audio.py`: `_play_tone` now uses nested `try/finally` blocks: outer wraps `pa.terminate()`, inner wraps `stream.stop_stream()`/`stream.close()`. This ensures both resources are cleaned up even if `stream.write()` raises.

`murmur/injector/ydotool.py`: Separated the `except (subprocess.TimeoutExpired, FileNotFoundError)` into two clauses. `FileNotFoundError` now logs a warning and returns `False` instead of falling through to `return True`.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

```
93 passed, 1 skipped in 0.18s
uv lock --check: Resolved 37 packages (lockfile consistent)
entry point importable
```

All 8 success criteria met:
- `uv lock --check` exits 0
- `pyproject.toml` declares `murmur = "murmur.main:main"` under `[project.scripts]`
- `Transcriber._streaming_lock` protects all reads/writes of `_is_streaming`
- Audio stream errors always logged in `assemblyai.py`
- `DictationApp._lock` used in `_on_activate`/`_on_deactivate`
- PyAudio stream and pa closed in nested `try/finally` blocks
- `pgrep` FileNotFoundError returns `False` + warning
- `pytest` reports 93 passed, 0 failed

## Self-Check: PASSED

Files exist:
- pyproject.toml: FOUND
- murmur/transcriber/base.py: FOUND
- murmur/transcriber/assemblyai.py: FOUND
- murmur/main.py: FOUND
- murmur/feedback/audio.py: FOUND
- murmur/injector/ydotool.py: FOUND

Commits exist:
- 88257b7: FOUND (chore: pyproject.toml + uv.lock)
- 0f83361: FOUND (fix: thread safety + error logging)
- 16c2a0a: FOUND (fix: _lock, PyAudio, pgrep)
