# Roadmap: Murmur

## Overview

Murmur is a working prototype being hardened into a daily-driver voice dictation daemon. The work is sequential: establish the foundation (package structure, types, test infrastructure) first, then fix all known reliability failure modes, then add the UX layer that makes the tool visible and pleasant. Nothing is built from scratch — everything completes and validates what already exists.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Package structure, typing, and test infrastructure
- [ ] **Phase 2: Reliability** - Fix all known failure modes with verified test coverage
- [ ] **Phase 3: UX** - System tray, desktop notifications, and error surfacing

## Phase Details

### Phase 1: Foundation
**Goal**: The project is correctly structured, fully typed, and has a working test harness
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06
**Success Criteria** (what must be TRUE):
  1. `python -m murmur` starts the daemon from the restructured `murmur/` package (not flat files)
  2. `pyright --strict` reports zero errors across all modules
  3. `ruff check` and `ruff format --check` pass with zero violations
  4. `pytest` runs the unit test suite with mocked backends (no hardware required) and all tests pass
  5. `pip install -e .` succeeds from a clean venv using `pyproject.toml`
**Plans**: TBD

Plans:
- [ ] 01-01: Restructure flat files into `murmur/` package with subpackages
- [ ] 01-02: Write `pyproject.toml`, achieve Pyright strict compliance, configure Ruff
- [ ] 01-03: Build pytest suite with mocked backends and hardware-gated integration tier

### Phase 2: Reliability
**Goal**: Every known failure mode is handled, tested, and surfaced to the user
**Depends on**: Phase 1
**Requirements**: RELY-01, RELY-02, RELY-03, RELY-04, RELY-05
**Success Criteria** (what must be TRUE):
  1. Dropping and restoring the network connection does not require restarting the daemon — transcription resumes automatically
  2. Unplugging and replugging the keyboard mid-session does not leave dictation stuck in a recording state
  3. Dictating text containing curly quotes, em-dashes, or accented characters produces correct output (not garbled or missing characters)
  4. Starting the daemon without `ydotoold` running produces a clear error message immediately, not a silent failure later
  5. An expired or revoked AssemblyAI API key causes the daemon to stop retrying and surface an error, not loop forever
**Plans**: TBD

Plans:
- [ ] 02-01: Implement WebSocket auto-reconnect with exponential backoff and error code classification
- [ ] 02-02: Implement evdev key-state flush on device disconnect and ydotoold startup check
- [ ] 02-03: Implement non-ASCII clipboard fallback in `YdotoolInjector`

### Phase 3: UX
**Goal**: The daemon's state is visible and errors are impossible to miss
**Depends on**: Phase 2
**Requirements**: UX-01, UX-02
**Success Criteria** (what must be TRUE):
  1. A tray icon changes appearance when recording starts and stops, visible in the system tray
  2. When the daemon starts without `ydotoold` running, a desktop notification appears within 2 seconds
  3. The tray icon's absence (e.g., stock GNOME without AppIndicator) does not prevent the daemon from starting or delivering notifications
**Plans**: TBD

Plans:
- [ ] 03-01: Implement system tray icon with idle/recording/error states and graceful-fail
- [ ] 03-02: Implement desktop notifications via D-Bus with notify-send fallback

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/3 | Not started | - |
| 2. Reliability | 0/3 | Not started | - |
| 3. UX | 0/2 | Not started | - |
