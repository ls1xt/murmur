# Phase 2: Reliability - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix all known failure modes so the daemon handles errors cleanly. Network drops, keyboard disconnects, non-ASCII encoding issues, missing ydotoold, and bad API keys all exit immediately with a clear error. No complex recovery — fail fast, notify, let the user restart.

</domain>

<decisions>
## Implementation Decisions

### Error philosophy
- KISS: on any error, exit immediately with a clear message
- No retry loops, no reconnection logic, no buffering
- Single exit code (exit 1) for all errors — the error message explains what happened
- Dual notification: stderr (for terminal/logs) + desktop notification via notify-send (for visibility when terminal is hidden)

### Network drop
- If WebSocket connection drops mid-session, exit immediately
- Error message should say what happened (e.g., "WebSocket connection lost")
- No auto-reconnect, no buffering of audio during outage

### Keyboard disconnect
- If evdev device disappears mid-dictation, exit immediately
- No attempt to recover key state or re-acquire the device
- Error message identifies the failure (e.g., "Input device disconnected")

### Missing dependencies / bad credentials
- Check for ydotoold at startup — exit immediately if not running
- Check AssemblyAI API key validity at startup — exit immediately if expired/revoked
- Both produce clear error messages explaining the problem and how to fix it

### Text injection strategies
- Implement three strategies: ydotool direct, clipboard fallback (try ydotool, fall back to clipboard on failure), and always-clipboard
- User selects strategy via CLI flag: `--inject=ydotool | clipboard-fallback | clipboard`
- Default strategy: Claude's discretion
- All three will be tested to determine which works best in practice

### Claude's Discretion
- Default injection strategy selection
- Exact error message wording
- Desktop notification formatting
- Startup check ordering

</decisions>

<specifics>
## Specific Ideas

- "Do not try to be smart — if there is an error just exit and send a notification with the error code"
- Keep it KISS — simplicity over resilience
- All three injection strategies exist so they can be tested empirically to find what works best

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-reliability*
*Context gathered: 2026-02-17*
