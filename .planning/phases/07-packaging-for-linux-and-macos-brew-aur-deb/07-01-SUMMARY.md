---
plan: "07-01"
phase: "07"
status: complete
completed: 2026-02-20
---

# Plan 07-01: CLI Subcommand Refactor

## What was built

Refactored `murmur/main.py` from a single flat `main()` function into a proper argparse-based CLI with three subcommands:

- `murmur config [--key KEY] [--value VALUE]` — view/set config values via dot-notation keys
- `murmur record [--inject ...] [--notify ...] [--inject-partials]` — single dictation session
- `murmur daemon {start|stop|status|enable}` — manage background service

### Key implementation details

- `_cmd_config()`: loads config, prints JSON (no args), gets/sets dot-notation keys with type coercion
- `_cmd_record()`: applies CLI overrides, sets up logging, launches setup wizard if no API key, starts DictationApp
- `_cmd_daemon()`: start delegates to `_cmd_record`, stop/status use `pgrep`, enable looks for `install-service.sh`
- `contextlib.suppress` used for clean PID kill error handling

## Files modified

- `murmur/main.py` — full refactor of `main()`, kept DictationApp class intact
- `tests/test_main.py` — rewrote with subcommand test classes (9 new tests for config, record, daemon)
- `tests/test_errors.py` — updated `test_exits_when_api_key_missing` to use `record` subcommand

## Self-Check: PASSED

- `murmur --help` shows config, record, daemon subcommands ✓
- `murmur config` prints config as JSON ✓
- `murmur config --key transcriber.api_key --value TEST_KEY` saves and confirms ✓
- `murmur daemon status` reports "Daemon not running" ✓
- `pyright murmur/main.py` — 0 errors ✓
- `ruff check murmur/main.py` — no new violations (4 pre-existing E501) ✓
- `pytest tests/test_main.py` — 25 passed, 5 pre-existing failures (partial/clipboard async) ✓
- `pytest tests/` — 23 failed (all pre-existing), 133 passed ✓

## key-files

### created
- (none — modified existing)

### modified
- murmur/main.py
- tests/test_main.py
- tests/test_errors.py
