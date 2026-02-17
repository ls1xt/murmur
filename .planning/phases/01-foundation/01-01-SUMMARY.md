# Plan 01-01 Summary: Package Restructure

**Completed:** 2026-02-17
**Duration:** ~15 minutes

## What Was Done

Restructured the flat-file prototype into a proper `murmur/` Python package with 4 subpackages, created build configuration, and removed all flat files from the project root.

## Artifacts Created

| File | Purpose |
|------|---------|
| `murmur/__init__.py` | Package root, exports `__version__ = "0.1.0"` |
| `murmur/__main__.py` | Entry point for `python -m murmur` |
| `murmur/main.py` | DictationApp orchestrator (migrated from root `main.py`) |
| `murmur/config.py` | Dataclass configuration (migrated, renamed config dir to `~/.config/murmur`) |
| `murmur/hotkey/base.py` | HotkeyListener ABC with push_to_talk/toggle mode logic |
| `murmur/hotkey/evdev.py` | EvdevHotkeyListener backend (migrated from `evdev_listener.py`) |
| `murmur/hotkey/__init__.py` | Factory: `create_hotkey_listener(config)` |
| `murmur/transcriber/base.py` | Transcriber ABC with callback slots |
| `murmur/transcriber/assemblyai.py` | AssemblyAITranscriber (migrated from `assemblyai_transcriber.py`) |
| `murmur/transcriber/__init__.py` | Factory: `create_transcriber(config)` |
| `murmur/injector/base.py` | TextInjector ABC |
| `murmur/injector/ydotool.py` | YdotoolInjector (migrated from `ydotool_injector.py`) |
| `murmur/injector/__init__.py` | Factory: `create_injector(config)` |
| `murmur/feedback/__init__.py` | Feedback module init |
| `murmur/feedback/audio.py` | AudioFeedback (PCM sine tones via PyAudio) |
| `pyproject.toml` | hatchling build, dependencies, tool configs |
| `setup.sh` | Multi-distro system dependency installer |

## Flat Files Removed

- `main.py`, `config.py`, `evdev_listener.py`, `assemblyai_transcriber.py`, `ydotool_injector.py`

## Key Changes from Prototype

- Package root renamed from `dictation/` to `murmur/`
- Config directory changed from `~/.config/dictation` to `~/.config/murmur`
- All imports updated to `murmur.*` absolute imports
- `Optional[X]` replaced with `X | None` (Python 3.10+)
- `Type[StreamingClient]` corrected to `Any` (SDK passes instance, not class)
- AudioFeedback extracted into `murmur/feedback/audio.py`

## Verification

- `python -c "import murmur"` -- succeeds
- `pip install -e .` -- succeeds
- `uv sync` -- succeeds
- All import chains resolve
- No `.py` files in project root
