# Phase 4: Interaction Polish - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Make dictation feel responsive and polished: hotkey doesn't leak characters, text appears live as you speak, audio confirms start/stop, both push-to-talk and toggle modes are accessible via separate shortcuts, and a tray icon works on Sway/waybar.

</domain>

<decisions>
## Implementation Decisions

### Hotkey passthrough suppression
- Use the **grab-and-forward** pattern: `device.grab()` each physical keyboard at startup, create a `UInput` virtual device per keyboard via `UInput.from_device()`, forward all events except the hotkey combo
- Grab once at startup, never ungrab mid-session (avoids ghost modifier problem)
- When hotkey fires: inject synthetic key-up for held modifiers into uinput before callback, so compositor's modifier state is cleared
- When hotkey releases: inject synthetic key-down to restore modifier state
- Requires `/dev/uinput` write access — add udev rule: `KERNEL=="uinput", MODE="0660", GROUP="input"`
- There is no lighter-weight alternative in the Linux kernel; all tools (keyd, interception-tools, xremap, evremap) use this same architecture

### Live partial injection (delta mode)
- Compute the **diff** between last-injected partial and the new partial — only inject the new characters (no backspace-and-retype)
- Track `_last_partial: str` in DictationApp; on each `_on_partial_transcript(text)`:
  - If `text` starts with `_last_partial`, inject only the suffix `text[len(_last_partial):]`
  - If text diverges (AssemblyAI revised earlier words), fall back to backspace + retype for the changed portion
- On `_on_final_transcript(text)`: backspace the entire partial, inject the finalized/formatted text, reset `_last_partial`
- The transcriber plumbing (`_on_partial` callback) already works end-to-end; the gap is entirely in `DictationApp._on_partial_transcript` which currently only logs

### Hotkey modes and shortcuts
- Both `push_to_talk` and `toggle` modes are already fully implemented and tested in `hotkey/base.py`
- Expose **three distinct shortcuts**, each with its own action:
  - `Ctrl+Alt+Space` — push-to-talk (hold to record, release to stop)
  - `Ctrl+Alt+K` — toggle start recording (press once to begin)
  - `Ctrl+Alt+L` — stop recording (press to end toggle session)
- The current single-hotkey `HotkeyConfig` needs to evolve into a multi-binding system
- All three shortcuts share the same `Ctrl+Alt` modifier prefix; only the trigger key differs
- Config structure: replace single `modifiers`/`trigger`/`mode` with a `bindings` list or named binding fields

### Audio feedback
- Audio is already wired: `AudioFeedback.play_start()` and `play_stop()` are called in `_on_activate`/`_on_deactivate`
- The likely issue on Sway/PipeWire: investigate whether the PyAudio output stream opens correctly under PipeWire
- Ensure the ALSA/JACK probe noise is suppressed (run.sh already does this)
- If PyAudio output fails silently (DEBUG-level log), make it more visible so the user knows audio feedback is broken

### Sway tray (SNI via Gio.DBus)
- Implement `StatusNotifierItem` D-Bus interface directly using `Gio.DBus` (already available via PyGObject dependency)
- No new dependencies needed — `gi.repository.Gio` and `gi.repository.GLib` are already in the venv
- pystray has **no SNI backend** and won't work on Sway; AppIndicator3 crashes on Sway (already guarded)
- Registration: publish object at `/StatusNotifierItem` implementing `org.kde.StatusNotifierItem`, call `RegisterStatusNotifierItem` on waybar's watcher (`org.kde.StatusNotifierWatcher`)
- Icon via `IconPixmap` property: `a(iiay)` format, ARGB32 in network byte order (big-endian)
- Status values: `"Active"` (normal), `"Passive"` (hidden), `"NeedsAttention"` (attention icon)
- GLib main loop in daemon thread, `GLib.idle_add()` for thread-safe updates (same pattern as existing AppIndicator code)
- User's waybar already has a working tray (blueman and nm-applet visible), so once registered the murmur icon will appear

### Claude's Discretion
- Exact udev rule installation approach (document in README vs automate in install script)
- Audio feedback fallback behavior when PyAudio output fails
- Exact default key combo for toggle mode
- Whether to support right-hand modifier variants (KEY_RIGHTCTRL etc.) automatically
- Internal architecture of the dual-shortcut hotkey system

</decisions>

<specifics>
## Specific Ideas

- User reported "ctrl+shift+space enters many new spaces while I speak" — this is the primary pain point driving the grab-and-forward work
- User wants delta injection: "just find out what the diff is, store last inserted and then insert the delta"
- User confirmed their waybar tray works (blueman, nm-applet visible) — so SNI registration is the right path
- The user's sway config uses `bar swaybar_command waybar`, so the tray host is waybar, not swaybar
- Explicit shortcut assignments: `Ctrl+Alt+Space` (push-to-talk), `Ctrl+Alt+K` (toggle start), `Ctrl+Alt+L` (stop recording)
- All shortcuts use `Ctrl+Alt` prefix — deliberately avoids `Shift` to prevent accidental character input

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-interaction-polish*
*Context gathered: 2026-02-18*
