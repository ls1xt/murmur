# Murmur

## What This Is

Murmur is a system-wide voice dictation tool for Linux (Wayland-first) and macOS. Hold a hotkey, speak, release — words appear at the cursor in any application. It bridges cloud STT (AssemblyAI) to kernel-level input injection, filling the gap where no good system-wide dictation exists on Linux or macOS.

## Core Value

Hold a key and talk — text appears wherever you're typing, in any application, instantly and reliably.

## Requirements

### Validated

- ✓ Push-to-talk and toggle hotkey modes — existing
- ✓ evdev hotkey listener for Wayland — existing
- ✓ AssemblyAI Universal-Streaming v3 transcription — existing
- ✓ ydotool text injection (Wayland + X11) — existing
- ✓ Audio feedback (start/stop beeps) — existing
- ✓ Layered config (dataclasses + env vars + JSON) — existing
- ✓ Main orchestrator wiring pipeline — existing

### Active

- [ ] Restructure into `dictation/` package layout with proper modules
- [ ] Pyright strict mode compliance across all modules
- [ ] pytest suite with mocked backends and integration tests
- [ ] Automatic reconnection on AssemblyAI WebSocket disconnect
- [ ] Graceful handling of ydotoold crash/restart mid-session
- [ ] Buffered injection mode (accumulate text, inject on release)
- [ ] Session metrics logging (audio duration, latency, word count)
- [ ] System tray icon with recording state indicator
- [ ] Desktop notifications on errors (e.g. "ydotoold not running")
- [ ] pyproject.toml with proper project metadata and dependencies

### Out of Scope

- Local Whisper / offline transcription — not needed now, ABC architecture supports future addition
- Per-application profiles — defer to future milestone
- Live transcript overlay — defer to future milestone
- Custom vocabulary / keyterms prompting — defer to future milestone
- Packaging (.deb, .rpm, AUR, Homebrew, Flatpak) — run from source for now
- Systemd service file — defer to future milestone
- macOS pynput backends — existing code works, no changes needed this round

## Context

- Working prototype exists with flat file structure in repo root (main.py, config.py, etc.)
- VISION.md describes target `dictation/` package layout with `hotkey/`, `transcriber/`, `injector/`, `feedback/` subpackages
- ABC pattern already established for all components (HotkeyListener, Transcriber, TextInjector)
- AssemblyAI Universal-Streaming v3 SDK with event-based API
- Wayland-native approach: evdev for hotkey detection, ydotool/uinput for text injection
- User is on Arch Linux with Wayland

## Constraints

- **Tech stack**: Python ≥ 3.10, strict Pyright, pytest, Ruff formatting
- **Architecture**: Pluggable ABC pattern — transcriber interface must support future backends without code changes
- **Wayland-native**: evdev + ydotool/uinput, no X11/XWayland dependencies for core path
- **Dependencies**: Minimal — assemblyai, pyaudio, evdev, and what's needed for tray/notifications

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Restructure into dictation/ package | Match VISION.md structure, proper Python packaging | — Pending |
| Pyright strict mode | Catch type errors early, enforce annotations | — Pending |
| Cloud-only STT (no Whisper) | AssemblyAI sufficient, keep scope small | — Pending |
| Basic UX (tray + notifications) | Visible feedback without over-engineering | — Pending |
| Skip packaging | Run from source, ship fast | — Pending |

---
*Last updated: 2025-02-17 after initialization*
