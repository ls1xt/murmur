# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Hold a key and talk -- text appears wherever you're typing, in any application, instantly and reliably.
**Current focus:** Phase 4 -- Interaction Polish

## Current Position

Phase: 4 of 4 (Interaction Polish)
Plan: 3 of 3 in current phase
Status: Phase complete, awaiting verification
Last activity: 2026-02-18 - Completed all Phase 4 plans (04-01, 04-02, 04-03)

Progress: [████████████████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 11
- Average duration: ~8 minutes
- Total execution time: ~87 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3/3 | ~50 min | ~17 min |
| 2. Reliability | 3/3 | ~9 min | ~3 min |
| 3. UX | 2/2 | ~10 min | ~5 min |
| 4. Interaction Polish | 3/3 | ~18 min | ~6 min |

**Recent Trend:**
- Last 5 plans: 03-01, 03-02, 04-01, 04-02, 04-03
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

### Pending Todos

None.

### Roadmap Evolution

- Phase 4 added: Interaction polish — hotkey passthrough suppression, live partial injection, audio feedback, toggle mode, and Sway tray support

### Blockers/Concerns

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 1 | Fix all verification issues | 2026-02-17 | 3dc241d | [1-fix-all-verification-issues](./quick/1-fix-all-verification-issues/) |

## Session Continuity

Last session: 2026-02-18
Stopped at: Phase 4 execution complete, awaiting verification
