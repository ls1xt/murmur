# Requirements: Murmur

**Defined:** 2025-02-17
**Core Value:** Hold a key and talk — text appears wherever you're typing, in any application, instantly and reliably.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Foundation

- [x] **FOUND-01**: Project restructured into `murmur/` package with `hotkey/`, `transcriber/`, `injector/`, `feedback/` subpackages
- [x] **FOUND-02**: `pyproject.toml` with dependencies, entry points (`python -m murmur`), and optional dependency groups
- [x] **FOUND-03**: All modules pass Pyright strict mode with zero errors
- [x] **FOUND-04**: pytest suite with unit tests using mocked backends (evdev, ydotool, AssemblyAI)
- [x] **FOUND-05**: Integration test tier gated behind `pytest.mark.hardware` for real device tests
- [x] **FOUND-06**: Ruff formatting and linting enforced across all modules

### Reliability

- [ ] **RELY-01**: AssemblyAI WebSocket auto-reconnects with exponential backoff (1s → 30s, ±25% jitter) on transient errors
- [ ] **RELY-02**: AssemblyAI error codes classified — retry on 3005 (session expired), abort on 1008 (auth/billing) with user notification
- [ ] **RELY-03**: evdev listener flushes `_held_keys` state on device disconnect (OSError) to prevent spurious hotkey triggers
- [ ] **RELY-04**: ydotool injector detects and handles non-ASCII characters (curly quotes, em-dashes) via clipboard fallback (`wl-copy` + `ydotool key ctrl+v`)
- [ ] **RELY-05**: ydotoold availability checked at startup with actionable error message if daemon not running

### UX

- [ ] **UX-01**: System tray icon shows recording state (idle/recording/error) with graceful degradation when AppIndicator unavailable
- [ ] **UX-02**: Desktop notifications on errors (ydotoold not running, WebSocket disconnect, permission issues) via D-Bus with notify-send fallback

### Distribution

- [ ] **DIST-01**: CLI subcommand structure (murmur config / record / daemon) for installable package UX
- [ ] **DIST-02**: Package manager distribution: Homebrew formula, AUR PKGBUILD, .deb package, PyPI
- [ ] **DIST-03**: Guided first-run setup: auto-prompt for API key if missing, with GUI (customtkinter) or terminal fallback

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Reliability

- **RELY-06**: Buffered injection mode (accumulate all text, inject on hotkey release)
- **RELY-07**: Session metrics logging (audio duration, latency, word count)
- **RELY-08**: Configurable audio device selection (override PyAudio/PipeWire default)

### UX

- **UX-03**: Live transcript overlay (floating window showing words as they arrive)
- **UX-04**: Per-application profiles (different hotkeys/behavior per app)
- **UX-05**: Custom vocabulary / keyterms prompting via config *(pulled into Phase 7 — implemented via setup_wizard.py and TranscriberConfig.keyterms)*

### Distribution

- **DIST-04**: RPM packaging (Fedora/RHEL) — deferred, add to backlog if needed

## Out of Scope

| Feature | Reason |
|---------|--------|
| Local Whisper / offline STT | Not needed now; ABC architecture supports future addition |
| macOS backend changes | Existing pynput backends work, no changes this round |
| Voice commands (dictate/delete/select) | Massive scope increase, different product |
| Real-time partial text injection into cursor | Already works via live turn injection; no changes needed |
| Flatpak packaging | uinput portal permissions add complexity |
| RPM packaging | Not in scope for Phase 7; tracked as DIST-04 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Done |
| FOUND-02 | Phase 1 | Done |
| FOUND-03 | Phase 1 | Done |
| FOUND-04 | Phase 1 | Done |
| FOUND-05 | Phase 1 | Done |
| FOUND-06 | Phase 1 | Done |
| RELY-01 | Phase 2 | Pending |
| RELY-02 | Phase 2 | Pending |
| RELY-03 | Phase 2 | Pending |
| RELY-04 | Phase 2 | Pending |
| RELY-05 | Phase 2 | Pending |
| UX-01 | Phase 3 | Pending |
| UX-02 | Phase 3 | Pending |
| DIST-01 | Phase 7 | Pending |
| DIST-02 | Phase 7 | Pending |
| DIST-03 | Phase 7 | Pending |
| UX-05 | Phase 7 | Pending (pulled from v2) |

**Coverage:**
- v1 requirements: 16 total (added DIST-01, DIST-02, DIST-03; UX-05 promoted from v2)
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2025-02-17*
*Last updated: 2026-02-20 — Phase 7 planning: added DIST-01/02/03, promoted UX-05 from v2*
