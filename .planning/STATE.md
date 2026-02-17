# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-17)

**Core value:** Hold a key and talk -- text appears wherever you're typing, in any application, instantly and reliably.
**Current focus:** Phase 2 -- Reliability

## Current Position

Phase: 2 of 3 (Reliability)
Plan: 1 of 3 in current phase
Status: Executing
Last activity: 2026-02-17 -- Plan 02-01 completed

Progress: [##############░░░░░░] 50%

## Performance Metrics

**Velocity:**
- Total plans completed: 4
- Average duration: ~13 minutes
- Total execution time: ~53 minutes

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1. Foundation | 3/3 | ~50 min | ~17 min |
| 2. Reliability | 1/3 | ~3 min | ~3 min |

**Recent Trend:**
- Last 5 plans: 01-01, 01-02, 01-03, 02-01
- Trend: Stable

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

### Pending Todos

None.

### Blockers/Concerns

- Phase 3 (tray icon): pystray AppIndicator graceful-fail behavior on stock GNOME Wayland needs verification during planning.

## Session Continuity

Last session: 2026-02-17
Stopped at: Completed 02-01-PLAN.md. Executing Wave 2 (02-02, 02-03).
Resume file: None
