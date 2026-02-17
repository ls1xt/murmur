# Plan 01-03 Summary: pytest Suite with Mocked Backends

**Completed:** 2026-02-17
**Duration:** ~15 minutes

## What Was Done

Built a comprehensive pytest test suite with mocked backends for all components. All 49 unit tests pass without requiring hardware, network, or API keys. One hardware-gated integration test is auto-skipped.

## Test Files Created

| File | Tests | Covers |
|------|-------|--------|
| `tests/conftest.py` | -- | `--hardware` flag, auto-skip logic, shared fixtures |
| `tests/test_config.py` | 14 | Default values, env var overrides, `_from_dict`, CONFIG_DIR |
| `tests/test_hotkey.py` | 12 | HotkeyListener ABC modes, EvdevHotkeyListener events, device detection |
| `tests/test_transcriber.py` | 10 | Transcriber ABC, AssemblyAI start/stop/callbacks, factory |
| `tests/test_injector.py` | 9 | YdotoolInjector subprocess calls, availability checks, factory |
| `tests/test_feedback.py` | 5 | AudioFeedback disabled/enabled, PyAudio mock, tone generation |
| **Total** | **50** | |

## Mock Boundaries

- **evdev:** `categorize()`, `_list_devices()`, `_open_device()` mocked at module level
- **subprocess:** `murmur.injector.ydotool.subprocess.run` patched for ydotool commands
- **shutil.which:** Patched to control ydotool path resolution
- **AssemblyAI SDK:** `murmur.transcriber.assemblyai._v3` module reference patched entirely
- **PyAudio:** `_pyaudio` module reference patched, `threading.Thread` patched for tone playback
- **threading.Thread:** Patched in transcriber tests to prevent background thread creation

## Hardware Marker

- `@pytest.mark.hardware` decorator auto-skips tests without `--hardware` flag
- One placeholder test (`test_real_keyboard_detection`) demonstrates the pattern
- `pytest --hardware` enables hardware tests

## Verification

- `pytest tests/ -v` -- 49 passed, 1 skipped
- `pyright tests/` -- 0 errors
- `ruff check tests/` -- 0 violations
- `ruff format --check tests/` -- all formatted
