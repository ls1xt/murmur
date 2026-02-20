---
plan: "07-02"
phase: "07"
status: complete
completed: 2026-02-20
---

# Plan 07-02: Keyterms Config and First-Run Setup Wizard

## What was built

Two independent additions for UX-05 and first-run setup:

1. **`keyterms` field** added to `TranscriberConfig` — a `list[str]` persisted to `~/.config/murmur/config.json`. Will be used for AssemblyAI custom vocabulary boosting (integration deferred).

2. **`murmur/setup_wizard.py`** — new module implementing `prompt_setup(config)`:
   - Shows customtkinter GUI dialog when `DISPLAY`/`WAYLAND_DISPLAY` is set and customtkinter is importable
   - Terminal fallback via `input()` otherwise
   - Both paths collect API key (required) and keyterms (optional, comma-separated)
   - Saves config on success, returns `True`; returns `False` on cancel/empty input

## Files modified/created

- `murmur/config.py` — `keyterms: list[str] = field(default_factory=list)` added to TranscriberConfig
- `murmur/setup_wizard.py` — new file; `prompt_setup()`, `_show_gui_dialog()`, `_prompt_terminal()`
- `pyproject.toml` — `customtkinter>=5.2.0` added to main dependencies

## Deviations

- Used file-level `# pyright:` pragma in setup_wizard.py to suppress unknown-member errors from untyped customtkinter library (pyright strict mode issue, not a runtime issue)
- `_show_gui_dialog` marked `# type: ignore[return]` at signature level

## Self-Check: PASSED

- `python -c "from murmur.config import DictationConfig; c = DictationConfig.load(); print(c.transcriber.keyterms)"` → `[]` ✓
- `python -c "from murmur.setup_wizard import prompt_setup; print('imported OK')"` → OK ✓
- `pytest tests/test_config.py` — 17 passed ✓
- `pyright murmur/config.py murmur/setup_wizard.py` — 0 errors ✓
- `ruff check murmur/config.py murmur/setup_wizard.py` — clean ✓
- `grep "customtkinter" pyproject.toml` — confirms dependency added ✓

## key-files

### created
- murmur/setup_wizard.py

### modified
- murmur/config.py
- pyproject.toml
