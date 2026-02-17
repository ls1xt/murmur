# Phase 3: UX - Context

**Gathered:** 2026-02-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the daemon's state visible and errors impossible to miss. System tray icon shows idle/recording/error states. Desktop notifications surface errors. Must work on both Sway and GNOME. Tray absence does not prevent the daemon from running.

</domain>

<decisions>
## Implementation Decisions

### Tray icon states
- Use emoji-style icons (not monochrome symbolic, not colored traditional icons)
- Different emoji per state: idle, recording, error (Claude picks specific emoji)
- Error state is persistent — stays until the underlying issue is resolved
- No animation

### Notification behavior
- Notification verbosity is configurable via CLI flag: `--notify off|errors|verbose`
- Default level: `errors` (only fatal/critical errors trigger notifications)
- `verbose` level includes state changes (recording start/stop) and startup confirmation
- `off` disables all notifications
- Error notifications are persistent (stay until user dismisses)
- Informational notifications (verbose mode) auto-expire
- Use system default notification sound

### Tray menu & interaction
- Left-click opens context menu (same as right-click)
- Minimal menu: status line + Quit
- Status line shows state only: "Idle", "Recording", or "Error: [reason]"
- Quit is immediate — no confirmation dialog

### Sway & GNOME compatibility
- Must work on both Sway (with swaybar) and GNOME
- If tray icon can't display: log warning to stderr, daemon continues without tray
- Notifications via `notify-send` (shell out) — no direct D-Bus
- Primary notification daemon is mako on Sway, but should work with any standard daemon
- Tray absence does not block daemon startup or notification delivery

### Claude's Discretion
- Specific emoji choice per state
- Tray library selection (pystray, etc.) — whatever works across Sway + GNOME
- notify-send flag usage for persistence vs auto-expire
- Exact notification message wording
- Error state recovery detection (how to know when to clear error icon)

</decisions>

<specifics>
## Specific Ideas

- User runs Sway + GNOME — both are first-class targets, not one primary and one fallback
- mako is the notification daemon on Sway
- Keep it simple: notify-send over D-Bus, minimal menu, emoji icons

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-ux*
*Context gathered: 2026-02-17*
