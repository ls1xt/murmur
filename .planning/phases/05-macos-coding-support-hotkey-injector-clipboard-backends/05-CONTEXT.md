# Phase 5: Cross-platform coding support - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Add macOS runtime support at the code level: abstract base classes for the hotkey listener and text injector, concrete Linux (evdev) and macOS (pynput) implementations, macOS clipboard integration, and macOS permission detection. No tooling, service files, or shell scripts — those are Phase 6. Linux behavior must be identical after the refactor.

</domain>

<decisions>
## Implementation Decisions

### Backend abstraction
- Introduce ABC (abstract base class) for hotkey listener and for text injector
- Existing Linux evdev and ydotool implementations become the Linux concrete classes
- New macOS concrete classes added alongside — no Linux code touched beyond the ABC extraction
- Factory functions in `hotkey/__init__.py` and `injector/__init__.py` dispatch on `sys.platform`
- Design must allow a future X11 backend to slot in without restructuring (i.e., don't hardcode only two platforms)

### macOS hotkey backend
- Use `pynput.keyboard.Listener` for key event detection
- Key names in config stay as evdev format (`KEY_LEFTCTRL`, `KEY_SPACE`, etc.) — macOS backend translates them to pynput equivalents at runtime
- No key grabbing/suppression on macOS for now (evdev EVIOCGRAB is Linux-only; pynput has no equivalent)

### macOS text injection backend
- Primary: `pynput.keyboard.Controller.type()` for direct typing
- Fallback: clipboard paste via `pbcopy` + Cmd+V keystroke (mirrors the Linux clipboard fallback tier)
- Same 3-tier structure as Linux where applicable: direct type → slow type → clipboard paste

### macOS clipboard
- Use `pbcopy` / `pbpaste` subprocess calls (already available on all macOS versions)
- No new Python dependency needed

### macOS permissions
- Check for Accessibility permission (required by pynput for keyboard monitoring) at daemon startup
- Check for Microphone permission (required for audio capture) at daemon startup
- Missing permission → fatal error with a clear, actionable message pointing to System Settings → Privacy
- Same pattern as the existing ydotoold startup check on Linux
- Use `pyobjc` or subprocess + `osascript` for detection — whichever requires no new mandatory dependency

### Linux compatibility
- All existing Linux behavior unchanged after ABC extraction
- Existing evdev and ydotool classes simply implement the new ABCs
- No Linux user sees any behavioural difference

### Claude's Discretion
- Exact ABC method signatures and naming
- Whether permissions check uses pyobjc or osascript
- Key name translation table (evdev → pynput)
- Exact error message wording

</decisions>

<specifics>
## Specific Ideas

- "It would be great if Linux still works after doing all the edits" — the refactor must be a pure extract-and-add, not a rewrite
- "Find some channel-wise and in best case abstract classes that we then implement for Linux and for macOS" — ABC is the explicit pattern
- "In the future we might add X Server support" — the factory dispatch and ABC must accommodate a third backend without structural changes
- Wayland tray issues are already fixed (custom tray implementation, not pystray) — no tray work in this phase

</specifics>

<deferred>
## Deferred Ideas

- X11 hotkey/injector backend — explicitly future, not Phase 5
- Shell scripts, setup.sh Homebrew path, LaunchAgent plist — Phase 6
- macOS-specific tests for new backends — can be included in Phase 5 plans or Phase 6; planner to decide
- Notification backend for macOS (osascript / notify-send equivalent) — Phase 6 or later

</deferred>

---

*Phase: 05-macos-coding-support-hotkey-injector-clipboard-backends*
*Context gathered: 2026-02-20*
