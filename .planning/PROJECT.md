# Murmur

## What This Is

Murmur is a system-wide voice dictation tool for Linux (Wayland-first) and macOS. Hold a hotkey, speak, release — words appear at the cursor in any application. It bridges cloud STT (AssemblyAI) to kernel-level input injection, filling the gap where no good system-wide dictation exists on Linux or macOS.

## Core Value

Hold a key and talk — text appears wherever you're typing, in any application, instantly and reliably.

## Requirements

### Validated

- ✓ Push-to-talk and toggle hotkey modes — Phase 4
- ✓ evdev hotkey listener for Wayland — Phase 1
- ✓ AssemblyAI Universal-Streaming v3 transcription — Phase 2
- ✓ ydotool text injection (Wayland + X11) — Phase 2
- ✓ Audio feedback (start/stop beeps) — Phase 4
- ✓ Layered config (dataclasses + env vars + JSON) — Phase 1
- ✓ Main orchestrator wiring pipeline — Phase 1
- ✓ Restructure into `murmur/` package layout with proper modules — Phase 1
- ✓ Pyright strict mode compliance across all modules — Phase 1
- ✓ pytest suite with mocked backends and integration tests — Phase 1
- ✓ pyproject.toml with proper project metadata and dependencies — Phase 1
- ✓ Automatic reconnection on AssemblyAI WebSocket disconnect — Phase 2
- ✓ Graceful handling of ydotoold crash/restart mid-session — Phase 2
- ✓ System tray icon with recording state indicator — Phase 3
- ✓ Desktop notifications on errors (e.g. "ydotoold not running") — Phase 3
- ✓ Hotkey suppression via grab-and-forward (EVIOCGRAB + UInput) — Phase 4
- ✓ Live partial transcript injection with delta suffix updates — Phase 4
- ✓ Toggle mode (separate start/stop hotkeys) — Phase 4
- ✓ SNI tray backend for Sway/waybar — Phase 4
- ✓ pynput hotkey backend for macOS (raw Listener + modifier set tracking) — Phase 5
- ✓ pynput+pbcopy text injection backend for macOS — Phase 5
- ✓ macOS permission checks (Accessibility + Microphone) at startup — Phase 5
- ✓ darwin-only conditional deps (pynput, pyobjc-framework-ApplicationServices) — Phase 5

### Active

- [ ] Buffered injection mode (accumulate text, inject on release) — deferred to future milestone
- [ ] Session metrics logging (audio duration, latency, word count) — deferred to future milestone

### Out of Scope

- Local Whisper / offline transcription — not needed now, ABC architecture supports future addition
- Per-application profiles — defer to future milestone
- Live transcript overlay — defer to future milestone
- Custom vocabulary / keyterms prompting — defer to future milestone
- X11 hotkey/injector backend — future, after X11 platform demand established

## Context

- Production codebase: `murmur/` package with `hotkey/`, `injector/`, `transcriber/`, `feedback/`, `platform/` subpackages
- All backends use ABC pattern: HotkeyListener, TextInjector, Transcriber
- Linux: evdev hotkey + ydotool injection (Wayland-native)
- macOS: pynput hotkey + pynput/pbcopy injection
- Factory functions dispatch on `sys.platform` ("linux" → evdev/ydotool, "darwin" → pynput)
- AssemblyAI Universal-Streaming v3 SDK with event-based API
- Pyright strict mode throughout; Ruff formatting enforced

## Constraints

- **Tech stack**: Python ≥ 3.10, strict Pyright, pytest, Ruff formatting
- **Architecture**: Pluggable ABC pattern — backends must slot in without structural changes
- **Wayland-native**: evdev + ydotool/uinput for Linux; pynput + pbcopy for macOS
- **Dependencies**: Minimal — assemblyai, pyaudio, evdev (linux), pynput (darwin), pyobjc (darwin)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Restructure into murmur/ package | Proper Python packaging, match intended layout | Done — Phase 1 |
| Pyright strict mode | Catch type errors early, enforce annotations | Done — Phase 1 |
| Cloud-only STT (no Whisper) | AssemblyAI sufficient, keep scope small | Active |
| Threading over asyncio | PyAudio and evdev are blocking C extensions | Active |
| Grab-and-forward hotkey suppression | Compositor-transparent suppression via EVIOCGRAB + UInput | Done — Phase 4 |
| Delta partial injection | Suffix-only injection, backspace-and-replace on diverge | Done — Phase 4 |
| SNI tray backend | pyright strict mode requires explicit D-Bus protocol implementation | Done — Phase 4 |
| Raw Listener + manual modifier-set tracking (macOS) | GlobalHotKeys silently fails for Ctrl+Alt on macOS (pynput issue #297, unresolved) | Done — Phase 5 |
| No event suppression on macOS | EVIOCGRAB is Linux-only; pynput has no equivalent grab API | Done — Phase 5 |
| clipboard-fallback as macOS default inject strategy | Controller.type() for ASCII, pbcopy+Cmd+V for non-ASCII — mirrors Linux behavior | Done — Phase 5 |
| AXIsProcessTrusted() with ImportError fallback | pyobjc availability varies; graceful degradation preferred over hard dep | Done — Phase 5 |
| macOS framework imports gated inside function bodies | Ensures murmur/platform/macos.py is safely importable on Linux dev machines | Done — Phase 5 |
| _sanitize_text copied per-module | Avoid coupling macOS injector to Linux ydotool module | Done — Phase 5 |

---
*Last updated: 2026-02-20 after Phase 5*
