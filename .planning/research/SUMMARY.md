# Project Research Summary

**Project:** Murmur — system-wide voice dictation daemon
**Domain:** Linux/Wayland system daemon with pluggable STT/input backends (Python)
**Researched:** 2026-02-17
**Confidence:** HIGH

## Executive Summary

Murmur is a brownfield project: a working prototype already exists and the research milestone is about hardening it into a daily-driver tool, not building from scratch. The architecture is well-reasoned — ABC + factory pattern for pluggable backends, threading (not asyncio) for concurrent audio/hotkey I/O, and a clear orchestrator/callback pattern in `DictationApp`. The primary work is reliability (reconnection, error surfacing, Unicode injection), correctness (strict typing, test coverage), and packaging (systemd service, first-run UX). The architecture requires no restructuring; it requires completion and validation.

The recommended approach is sequential: establish the foundation (types, tests, pyproject.toml) first, then fix all reliability gaps before adding any new UX features (tray icon, metrics, service file). This order is non-negotiable because reliability problems are latent in the existing code and adding new features on top of an untested foundation compounds the debt. The test suite (mocked backends, no hardware required) is both a deliverable and the mechanism that validates each reliability fix.

The main risks are Wayland-specific: ydotool silently drops non-ASCII characters (known upstream bug, needs clipboard fallback path), evdev key-state desynchronizes on device disconnect (must flush `_held_keys` on `OSError`), and the tray icon silently fails on stock GNOME Wayland without the AppIndicator extension. All three risks are well-understood and have documented mitigations — the danger is skipping them under time pressure and shipping a tool that works on the developer's machine but fails on users'.

## Key Findings

### Recommended Stack

The existing library choices are sound and should be kept. Python 3.10+ with `uv` for dependency management, `assemblyai` SDK for streaming STT via Universal-Streaming v3, `evdev` for Wayland-native hotkey detection, `pynput` for macOS fallback only. Three additions are needed: `desktop-notifier` for D-Bus desktop notifications (zero dependency on notify-send binary), `pystray` with AppIndicator backend for the tray icon (P2, optional/graceful-fail), and `Pillow` as pystray's required image backend.

For tooling: Ruff replaces Black + isort + Flake8, Pyright in strict mode is required before the test suite can be trusted (the ABC structure means every callback type must be annotated), pytest + pytest-mock for hardware-free unit tests.

**Core technologies:**
- `evdev 1.9.3`: Wayland-native hotkey detection via `/dev/input` — the only correct approach; pynput is confirmed broken on Wayland (GitHub #628)
- `assemblyai 0.52.0`: AssemblyAI Universal-Streaming v3 — stable SDK, ~97% accuracy, streaming via `StreamingClient` + `TurnEvent` callbacks
- `ydotool` (subprocess): Text injection via uinput — works on all Wayland compositors; requires ydotoold daemon running as user service
- `desktop-notifier 6.2.0`: D-Bus notifications — works without libnotify-bin, async API, macOS Notification Center natively
- `pystray 0.19.5` + `Pillow`: System tray icon — AppIndicator backend on Linux; graceful-fail required on stock GNOME Wayland
- `Pyright 1.1.408` (strict): Static type checking — required before test suite is reliable; assemblyai SDK ships `py.typed`
- `Ruff 0.15.1`: Linting + formatting — replaces Black + isort + Flake8 with 10-100x better performance

**Critical version constraint:** PyAudio 0.2.14 has no wheel for Python 3.13+. Pin to Python 3.10-3.12 or plan a future sounddevice migration (same PortAudio backend, better API, actively maintained).

### Expected Features

The existing prototype already implements: hotkey detection (push-to-talk + toggle), text injection at cursor, audio start/stop feedback, push-to-talk and toggle modes, trailing space config, graceful shutdown, and partial transcript logging. The MVP for this milestone adds reliability and testability on top of what exists.

**Must have (table stakes for daily driver — v1):**
- Automatic WebSocket reconnection with exponential backoff — transient network drops require manual restart without this; unacceptable
- Buffered injection mode — streaming partial injection causes character corruption in terminals and IDEs; must be opt-in config flag
- Desktop error notification for ydotoold not running — silent failure is the #1 user confusion point per README troubleshooting
- Pyright strict mode compliance — required before tests can be trusted; prevents threading/callback annotation bugs
- pytest suite with mocked backends — unit tests for config, hotkey state machine, transcriber callbacks, injector (no hardware in CI)
- `--dry-run` flag — safe first-run validation without injecting text into live documents

**Should have (competitive differentiators — v1.x):**
- System tray icon with idle/recording/error states — visual confirmation; implement after core reliability is proven; graceful-fail required
- Session metrics logging (audio duration, word count, latency) — power user value, trivially collected from SDK callbacks
- Systemd user service file — one-command always-on setup; add once daemon is stable enough to restart cleanly

**Defer (v2+):**
- Local Whisper backend (faster-whisper) — 1-4GB models, complex VAD, Phase 3 per VISION.md; ABC accommodates it without restructuring
- Live transcript overlay (floating window) — requires Wayland UI toolkit; high complexity, niche use case
- Per-application hotkey profiles — requires D-Bus/AT-SPI focus tracking; not feasible without compositor-specific portals

**Anti-features to avoid:** Live partial text injection into cursor (creates undo hell; AssemblyAI v3 partials are immutable but often wrong), voice commands ("delete that"), GUI settings panel, clipboard injection as primary path (pollutes clipboard).

### Architecture Approach

The existing architecture is correct and complete. `DictationApp` orchestrates via callbacks; each concern (hotkey, transcriber, injector, feedback) is an ABC with factory function and concrete backends in a subpackage. Threading over asyncio is the right choice — PyAudio and evdev are blocking C extensions that cannot yield to an event loop, and the AssemblyAI SDK is thread-based internally. The project structure should be refactored from flat files to the subpackage layout (`hotkey/`, `transcriber/`, `injector/`, `feedback/`) before adding tests, since the test structure mirrors the package structure.

**Major components:**
1. `DictationApp` (main.py) — orchestrator; lifecycle, signal handling, callback wiring; must be thread-safe (callbacks fire from background threads)
2. `HotkeyListener` ABC + `EvdevHotkeyListener` — reads `/dev/input/event*` via selector; must NOT call `grab()`; must flush `_held_keys` on `OSError`
3. `Transcriber` ABC + `AssemblyAITranscriber` — manages mic stream + WebSocket; must handle error states, session expiry, and reconnection
4. `TextInjector` ABC + `YdotoolInjector` — subprocess-based injection; must handle non-ASCII via clipboard fallback; check ydotoold availability at startup
5. `DictationConfig` — nested dataclasses; layered (defaults → JSON file → env vars); config file must be created with mode 0600
6. Factory functions — inspect config, instantiate correct concrete backend; callers never import concrete classes directly

### Critical Pitfalls

1. **ydotoold socket permission mismatch** — Run ydotoold as user service (`systemctl --user start ydotool`), not system service as root. Root-owned socket has mode 0600; user process cannot connect. Verify: `stat /tmp/.ydotool_socket` shows correct group. Check `YDOTOOL_SOCKET` env var matches between ydotoold and ydotool.

2. **ydotool silently drops non-ASCII / Unicode characters** — Known upstream bug (issue #249, unfixed in v1.0.4). AssemblyAI's formatter produces curly quotes, em-dashes, accented characters. Detection: `if not text.isascii()` → use clipboard injection path (`wl-copy "$text" && ydotool key ctrl+v`). Must be implemented in buffered injection mode.

3. **evdev key-state desync on device disconnect** — USB unplug or Bluetooth drop mid-keystroke leaves `_held_keys` populated with modifiers that were never released. Next spacebar press triggers dictation without modifiers. Fix: on `OSError` from `device.read()`, clear `_held_keys` and call `_handle_hotkey_release()` if recording was in progress.

4. **AssemblyAI session expiry without reconnection (error 3005)** — Sessions expire or close on audio rate violations. Error handler must set `_is_streaming = False` and nullify `_client`. `start()` must assert `_client is None`. Distinguish error codes: 3005 = retry with backoff; 1008 (bad API key/billing) = surface to user and abort, no retry.

5. **PyAudio opens wrong microphone (PortAudio vs PipeWire default mismatch)** — PortAudio queries ALSA default directly, ignoring PipeWire routing. Expose `device_index` config option; log device name opened at startup. Thread `device_index` through AssemblyAI SDK's `MicrophoneStream` constructor.

## Implications for Roadmap

Based on combined research, the build order is determined by dependency graph and risk reduction. The architecture research explicitly documents the Phase 1-5 build sequence; the feature and pitfalls research confirm which phases are reliability-critical.

### Phase 1: Foundation — Typing, Structure, and Test Infrastructure

**Rationale:** Pyright strict mode must pass before tests are trustworthy. Package restructuring into subpackages must happen before test structure mirrors source. This phase has no external dependencies and no risk of breaking existing functionality — it is purely additive structure.
**Delivers:** Correct `pyproject.toml` with all deps declared, subpackage layout (`hotkey/`, `transcriber/`, `injector/`, `feedback/`), Pyright strict mode passing with zero errors, Ruff configured, `conftest.py` with mock factories, and test scaffolding (empty test files with fixture patterns).
**Addresses:** Pyright strict mode compliance, pytest suite infrastructure (FEATURES.md P1 items)
**Avoids:** Thread annotation bugs surfaced by Pyright; import coupling that prevents mocking (ARCHITECTURE.md anti-pattern 1)
**Research flag:** Standard patterns — no additional research needed.

### Phase 2: Reliability — Fix All Known Failure Modes

**Rationale:** The existing prototype has five documented latent bugs (PITFALLS.md). All must be fixed before adding new features; each fix requires a unit test to verify. This phase must complete before v1 is usable as a daily driver.
**Delivers:** Automatic WebSocket reconnection with exponential backoff, buffered injection mode with non-ASCII clipboard fallback, evdev key-state flush on device disconnect, ydotoold availability check at startup with desktop error notification, audio device index config + startup logging, `--dry-run` flag, and a passing unit test suite with 80%+ coverage on non-hardware paths.
**Uses:** `desktop-notifier`, `pytest-mock`, exponential backoff pattern (1s→2s→4s→max 30s + jitter)
**Implements:** Error classification in `AssemblyAITranscriber`, clipboard fallback in `YdotoolInjector`, `_held_keys` flush in `EvdevHotkeyListener`
**Avoids:** All 6 critical pitfalls documented in PITFALLS.md; thread proliferation via reused threads with `threading.Event` signaling
**Research flag:** Standard patterns — exponential backoff, subprocess fallback, and threading patterns are all well-documented. No additional research needed.

### Phase 3: UX — Tray Icon, Metrics, and First-Run Experience

**Rationale:** After reliability is proven, add the features that make the tool pleasant. The tray icon has known Wayland caveats (AppIndicator extension required on GNOME) and must gracefully degrade; tackle it after Phase 2 validates the reliability foundation.
**Delivers:** System tray icon (idle/recording/error states, graceful-fail on GNOME without AppIndicator), session metrics logging to `~/.local/share/murmur/sessions.jsonl`, documented first-run UX with `--config` flag, key delay documentation with per-app-type recommendations.
**Uses:** `pystray 0.19.5` + AppIndicator backend, `Pillow` for icon generation, `TerminationEvent.audio_duration_seconds` from SDK
**Implements:** Background thread for pystray event loop, state machine (idle/recording/error) shared with tray icon
**Avoids:** Requiring tray icon as primary UI (UX pitfall #4); tray must never block daemon startup or disable notifications if absent
**Research flag:** pystray Wayland support is inconsistent across compositors. May need targeted research on specific desktop environments during planning.

### Phase 4: Packaging — Systemd Service and Distribution

**Rationale:** Once the daemon is reliable and has good UX, package it for always-on use. Systemd service requires clean SIGTERM handling (already implemented) and reliable restart behavior (no leaked file handles — verified in Phase 2).
**Delivers:** Systemd user service file with `Restart=on-failure` and `RestartSec`, `make install` / `uv install` flow, config file created with mode 0600, documentation covering group membership (`input` group), ydotoold setup, and AppIndicator extension for GNOME users.
**Avoids:** Config file world-readable (security mistake from PITFALLS.md); running murmur as root (security mistake); system-service ydotoold (socket permission mismatch)
**Research flag:** Standard patterns — systemd user service units are well-documented. No additional research needed.

### Phase 5: Local STT Backend (Future Milestone)

**Rationale:** VISION.md Phase 3. The ABC pattern means `WhisperTranscriber` can be added without touching the orchestrator. Only pursue after cloud path is bulletproof. Explicitly out of scope for the current milestone.
**Delivers:** `faster-whisper` backend behind `[local-stt]` optional dependency group, VAD integration, device/model config
**Uses:** `faster-whisper`, `sounddevice` (replacing PyAudio in custom mic capture class)
**Research flag:** Needs dedicated research phase — VAD tuning, model management, resource requirements, and PipeWire latency are all new problem domains.

### Phase Ordering Rationale

- Phase 1 before Phase 2: Pyright strict mode is a prerequisite for trustworthy tests; tests are the verification mechanism for every reliability fix in Phase 2.
- Phase 2 before Phase 3: The tray icon's graceful-fail behavior depends on the error classification and notification infrastructure built in Phase 2. Adding UX on top of unvalidated reliability creates untestable code.
- Phase 3 before Phase 4: The systemd service must restart a daemon that is already reliable. Packaging a broken daemon makes failures harder to debug (journal vs stderr).
- Phase 5 is a separate milestone: No dependencies on Phases 1-4 content except the ABC architecture, which already accommodates it.

### Research Flags

Phases needing deeper research during planning:
- **Phase 3 (tray icon):** pystray AppIndicator behavior varies across GNOME versions and compositor configurations. During planning, identify minimum supported desktop environments and define the graceful-fail contract precisely.
- **Phase 5 (local STT):** Entirely new problem domain — VAD, model management, PipeWire latency, faster-whisper GPU/CPU path selection. Requires its own research phase before roadmap planning.

Phases with standard patterns (skip research-phase):
- **Phase 1:** Package structure, Pyright config, Ruff config — exhaustively documented in official tooling docs.
- **Phase 2:** Exponential backoff, threading patterns, subprocess fallback — well-established patterns with no project-specific unknowns.
- **Phase 4:** Systemd user service units — official systemd documentation is authoritative and complete.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Library versions verified against PyPI JSON API 2026-02-17; pynput Wayland breakage confirmed via GitHub issue #628 (Feb 2025); pystray Wayland status confirmed via maintainer comment on issue #174 |
| Features | MEDIUM-HIGH | Table stakes and UX patterns corroborated across 5+ competitors; testing patterns from official pytest/pytest-mock docs; competitor source quality is MEDIUM (GitHub README-level) |
| Architecture | HIGH | Based on existing codebase analysis (direct inspection) + official Python docs (abc, threading, packaging); threading-over-asyncio recommendation corroborated by multiple sources |
| Pitfalls | MEDIUM-HIGH | 5 of 6 critical pitfalls verified against official ydotool/evdev GitHub issues and AssemblyAI docs; PyAudio/PipeWire default device mismatch is community consensus (MEDIUM, multiple forum sources agree) |

**Overall confidence:** HIGH

### Gaps to Address

- **ydotool non-ASCII clipboard fallback:** The clipboard path (`wl-copy` + `ydotool key ctrl+v`) is the recommended mitigation, but `wl-copy` adds a runtime dependency not yet declared. Verify `wl-clipboard` packaging for target distros during Phase 2 planning; consider `wl-clipboard-rs` or Python `subprocess` to `wl-copy` vs a Python wayland clipboard library.

- **PyAudio Python 3.13+ compatibility:** No pre-built wheel for 3.13+. If users request 3.13 support before the milestone completes, the mitigation is to replace `MicrophoneStream` with a custom `sounddevice`-based class. Not blocking for the current milestone (pin to 3.10-3.12), but should be flagged in the README.

- **Multiple keyboard device handling:** PITFALLS.md identifies that `evdev` must open all detected keyboards, not just the first. The existing `find_keyboard_devices()` implementation's behavior needs verification during Phase 2 — confirm it opens all `/dev/input/eventN` devices that have `EV_KEY` capabilities matching the trigger key.

- **pystray GNOME Wayland behavior:** The graceful-fail contract (what happens when AppIndicator extension is absent) needs explicit testing against stock GNOME Wayland during Phase 3 planning. Currently characterized as "silently fails" — whether this is a logged warning, a crash, or a hang needs to be determined before writing the fallback code.

## Sources

### Primary (HIGH confidence)

- PyPI JSON API `https://pypi.org/pypi/{package}/json` — version numbers for all declared dependencies (2026-02-17)
- Python official docs: `abc`, `threading`, `packaging/src-vs-flat-layout` — architecture patterns
- Existing codebase: `/home/leon/murmur/` — direct inspection of working prototype
- VISION.md: `/home/leon/murmur/VISION.md` — phase structure, project goals

### Secondary (MEDIUM confidence)

- GitHub issues: ydotool #249 (Unicode drops), #73 (socket perms), #36 (backend unavailable), pynput #628 (Wayland broken), pystray #174 (Wayland tray)
- AssemblyAI docs: Universal-Streaming v3 common session errors (3005, 1008)
- python-evdev issues: #4 (grab behavior), #64 (device disconnect read behavior)
- Competitors: waystt, hyprwhspr, VTT-Voice2Text, Wispr Flow — feature landscape analysis

### Tertiary (LOW confidence)

- desktop-notifier PyPI listing — not verified against D-Bus behavior on all target compositors; needs runtime validation
- PipeWire/PortAudio default device interaction — community forum consensus; behavior may vary by distro

---
*Research completed: 2026-02-17*
*Ready for roadmap: yes*
