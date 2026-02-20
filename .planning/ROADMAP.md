# Roadmap: Murmur

## Overview

Murmur is a working prototype being hardened into a daily-driver voice dictation daemon. The work is sequential: establish the foundation (package structure, types, test infrastructure) first, then fix all known reliability failure modes, then add the UX layer that makes the tool visible and pleasant. Nothing is built from scratch — everything completes and validates what already exists.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Package structure, typing, and test infrastructure
- [x] **Phase 2: Reliability** - Fix all known failure modes with verified test coverage
- [ ] **Phase 3: UX** - System tray, desktop notifications, and error surfacing
- [ ] **Phase 4: Interaction Polish** - Hotkey suppression, live injection, audio feedback, toggle mode, Sway tray
- [x] **Phase 5: Cross-platform** - macOS backends (hotkey, injector, clipboard), pystray Wayland fix, macOS permissions (completed 2026-02-20)

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
**Plans:** 3 plans

Plans:
- [x] 01-01-PLAN.md — Restructure flat files into murmur/ package with subpackages, create pyproject.toml and setup.sh
- [x] 01-02-PLAN.md — Achieve Pyright strict mode and Ruff compliance across all modules
- [x] 01-03-PLAN.md — Build pytest suite with mocked backends and hardware-gated integration tier

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
**Plans:** 3 plans

Plans:
- [x] 02-01-PLAN.md — Fatal error infrastructure, WebSocket error exits, and startup validation (RELY-01, RELY-02, RELY-05)
- [x] 02-02-PLAN.md — evdev device disconnect fatal exit (RELY-03)
- [x] 02-03-PLAN.md — Three injection strategies with clipboard fallback for non-ASCII (RELY-04)

### Phase 3: UX
**Goal**: The daemon's state is visible and errors are impossible to miss
**Depends on**: Phase 2
**Requirements**: UX-01, UX-02
**Success Criteria** (what must be TRUE):
  1. A tray icon changes appearance when recording starts and stops, visible in the system tray
  2. When the daemon starts without `ydotoold` running, a desktop notification appears within 2 seconds
  3. The tray icon's absence (e.g., stock GNOME without AppIndicator) does not prevent the daemon from starting or delivering notifications
**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — Configurable desktop notifications via notify-send with --notify CLI flag
- [ ] 03-02-PLAN.md — System tray icon with idle/recording/error states and graceful degradation

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 3/3 | Complete | 2026-02-17 |
| 2. Reliability | 3/3 | Complete | 2026-02-17 |
| 3. UX | 0/2 | Not started | - |
| 4. Interaction Polish | 0/3 | Not started | - |

### Phase 4: Interaction Polish
**Goal**: Dictation feels responsive and polished — keys don't leak, text appears live, audio confirms state, and the tray works on Sway
**Depends on**: Phase 3
**Success Criteria** (what must be TRUE):
  1. Holding the hotkey does not insert spurious characters (e.g. spaces) into the focused application
  2. Partial transcripts appear in the focused window while still speaking, not only after releasing the hotkey
  3. Audible beeps play on recording start and stop (PyAudio output works under PipeWire/Sway)
  4. A toggle mode exists: one keypress starts recording, a second keypress stops it
  5. A tray indicator is visible in swaybar (or waybar) showing idle/recording/error state
**Plans:** 3 plans

Plans:
- [ ] 04-01-PLAN.md — Multi-binding hotkey config and grab-and-forward input passthrough
- [ ] 04-02-PLAN.md — SNI tray backend for Sway/waybar via Gio.DBus
- [ ] 04-03-PLAN.md — Delta partial transcript injection and audio feedback visibility upgrade

### Phase 5: Cross-platform coding support (macOS backends, pystray Wayland fix, permissions)

**Goal:** Add macOS runtime support at the code level — pynput hotkey backend, pynput+pbcopy injector backend, macOS clipboard backend, and macOS permission detection. No tooling, service files, or shell scripts.
**Depends on:** Phase 4
**Plans:** 4/4 plans complete

Plans:
- [ ] 05-01-PLAN.md — PynputHotkeyListener: macOS hotkey backend with manual modifier-set tracking
- [ ] 05-02-PLAN.md — PynputInjector: macOS text injector with pynput type() and pbcopy clipboard fallback
- [ ] 05-03-PLAN.md — murmur/platform/macos.py: Accessibility and Microphone permission checks
- [ ] 05-04-PLAN.md — Wire factories, main.py startup checks, and pyproject.toml darwin deps

### Phase 6: tooling and integration for Linux and macOS (setup, service, install)

**Goal:** [To be planned]
**Depends on:** Phase 5
**Plans:** 0 plans

Plans:
- [ ] TBD (run /gsd:plan-phase 6 to break down)

### Phase 7: Packaging for Linux and macOS (brew, AUR, deb)

**Goal:** Distribute murmur through package managers (Homebrew, AUR, .deb, PyPI) with a proper CLI subcommand structure (murmur config / record / daemon) and guided first-run setup for the API key and custom vocabulary.
**Depends on:** Phase 6
**Requirements**: DIST-01, DIST-02, DIST-03, UX-05
**Plans:** 5 plans

Plans:
- [ ] 07-01-PLAN.md — CLI subcommand refactor (config/record/daemon) and test_main.py update
- [ ] 07-02-PLAN.md — customtkinter GUI setup wizard and keyterms config field (UX-05)
- [ ] 07-03-PLAN.md — PyPI packaging: pyproject.toml metadata, wheel verification, publish script
- [ ] 07-04-PLAN.md — Homebrew formula and AUR PKGBUILD packaging artifacts
- [ ] 07-05-PLAN.md — .deb build script and README installation documentation
