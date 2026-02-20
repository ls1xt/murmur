# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Hold a key and talk -- text appears wherever you're typing, in any application, instantly and reliably.
**Current focus:** Phase 6 complete -- all roadmap phases done

## Current Position

Phase: 6 of 6 (Tooling and Integration -- Linux and macOS setup, service, install)
Plan: 2 of 2 in current phase
Status: Complete
Last activity: 2026-02-20 - Completed Phase 6 (tooling and integration — all 2 plans)

Progress: [████████████████████] 100% (17/17 estimated plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 14
- Average duration: ~7 minutes
- Total execution time: ~92 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3/3 | ~50 min | ~17 min |
| 2. Reliability | 3/3 | ~9 min | ~3 min |
| 3. UX | 2/2 | ~10 min | ~5 min |
| 4. Interaction Polish | 3/3 | ~18 min | ~6 min |
| 5. macOS Coding Support | 4/4 | ~10 min | ~2.5 min |
| 6. Tooling and Integration | 2/2 | ~5 min | ~2.5 min |

**Recent Trend:**
- Last 5 plans: 05-02, 05-03, 05-04, 06-01, 06-02
- Trend: Consistent, fast

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Restructure into `murmur/` package (not `dictation/`) -- entry point is `python -m murmur`
- Threading over asyncio -- PyAudio and evdev are blocking C extensions; AssemblyAI SDK is thread-based internally
- Cloud-only STT (AssemblyAI) -- local Whisper deferred to future milestone
- `assemblyai.streaming.v3` must be imported via `importlib.import_module()` -- dotted attribute access fails at runtime
- evdev/pyaudio/assemblyai typed via `Any` wrappers -- no type stubs available
- `reportPrivateUsage` and `reportUntypedFunctionDecorator` suppressed in pyright config for test compatibility
- Colored circles (gray/red/orange) as emoji-style tray icons -- avoids font bundling
- Daemon thread for pystray -- not run_detached (Linux doesn't need it)
- notify-send via subprocess for notifications -- no direct D-Bus
- Three default hotkey bindings: Ctrl+Alt+Space (push-to-talk), Ctrl+Alt+K (toggle-start), Ctrl+Alt+L (toggle-stop)
- Grab-and-forward via EVIOCGRAB + UInput for hotkey suppression
- SNI tray backend extracted to sni.py for pyright strict mode compatibility
- Delta partial injection: suffix-only injection, backspace-and-replace on diverge
- First audio error at WARNING, subsequent at DEBUG
- [Phase 05-01]: Use raw keyboard.Listener with manual modifier set tracking (not GlobalHotKeys) -- GlobalHotKeys silently fails for Ctrl+Alt on macOS (pynput issue #297)
- [Phase 05-01]: No event suppression on macOS -- keys pass through; grab-and-forward is Linux-only (evdev)
- [Phase 05-02]: Copy _sanitize_text verbatim per-module to avoid coupling macOS backend to Linux ydotool module
- [Phase 05-02]: clipboard-fallback as default strategy: Controller.type() for ASCII, pbcopy+Cmd+V for non-ASCII
- [Phase 05-02]: is_available() returns True on ImportError (no pyobjc) for graceful dev-machine fallback
- [Phase 05-03]: All macOS framework imports (ApplicationServices, AVFoundation) gated inside function bodies with try/except ImportError -- ensures importable on Linux without crashing
- [Phase 05-03]: notDetermined microphone status (0) returns True with warning -- lets PyAudio trigger system dialog on first use rather than failing at startup
- [Phase 05-03]: ImportError fallback returns True (not False) -- cannot verify permission, assume ok, let actual runtime fail with a useful error if missing
- [Phase 05-04]: Added missing import sys to main.py (was absent; plan assumed present but was not) -- Rule 3 auto-fix
- [Phase 05-04]: darwin startup block uses elif for linux ydotoold check, replacing unconditional check -- preserves linux semantics exactly
- [Phase 06-01]: Service file templates use @@MURMUR_DIR@@ placeholder instead of hardcoded paths -- sed substitution in install-service.sh is clean and portable
- [Phase 06-01]: murmur.plist uses KeepAlive.SuccessfulExit: false to match Restart=on-failure semantics (restart on crash, not clean exit)
- [Phase 06-02]: setup.sh and run.sh both use uname -s for OS detection; macOS branch skips all ydotoold/input-group/ALSA concerns

### Pending Todos

None.

### Roadmap Evolution

- Phase 4 added: Interaction polish — hotkey passthrough suppression, live partial injection, audio feedback, toggle mode, and Sway tray support
- Phase 5 added: macOS coding support (hotkey, injector, clipboard backends)
- Phase 6 added: tooling and integration for Linux and macOS (setup, service, install)
- Phase 7 added: Packaging for Linux and macOS (brew, AUR, deb)

### Blockers/Concerns

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Fix all verification issues | 2026-02-17 | 3dc241d | [1-fix-all-verification-issues](./quick/1-fix-all-verification-issues/) |

## Session Continuity

Last session: 2026-02-20
Stopped at: Phase 5 complete, ready to plan Phase 6
Resume file: None
