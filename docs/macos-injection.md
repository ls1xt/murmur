# macOS Text Injection — Design Notes

This document explains why text injection on macOS works the way it does, and the
chain of problems that led to the current design.

---

## The event architecture

macOS has a **single system-wide keyboard event bus**.  All keyboard input —
physical keystrokes and synthetic ones — flows through the same
`CGEventTap`/`HID` pipeline.

pynput's `keyboard.Listener` installs a `CGEventTap` at the HID level to receive
all keyboard events.  pynput's `keyboard.Controller` posts synthetic events to
that same HID tap via `CGEventCreateKeyboardEvent` + `CGEventPost`.

**Consequence:** the listener sees its own controller's events.  There is no
separation between "real keyboard" and "virtual keyboard" at this level — unlike
Linux evdev, where a physical device and a `uinput` virtual device are separate
file descriptors.

macOS CGEvents *do* carry source metadata (`kCGEventSourceStateID`,
`kCGEventSourceUnixProcessID`) that could distinguish synthetic from physical
events, but pynput does not expose or check this field.

---

## Why `controller.type()` broke push-to-talk (historical)

The original injector used `pynput.keyboard.Controller.type(text)` for ASCII
text.  This generates individual keydown/keyup CGEvents for every character,
including spaces.

When the user held **Ctrl+Option+Space** for push-to-talk:

1. pynput's `_held` set contains `{Ctrl, Alt, Space}`.
2. AssemblyAI delivers a final turn — e.g. *"Okay? I'm testing it right now."*
3. `controller.type(text)` is called from the AssemblyAI SDK thread.
4. It posts CGEvents for each character, including the space in *"I'm testing"*.
5. pynput's listener thread receives `KEY RELEASE raw=<Key.space>`.
6. The release check fires: `Space ∈ _held ∧ {Ctrl,Alt} ⊆ _held` → **recording stops**.

The target application received the text correctly (CGEvent flags carry only the
modifiers pynput explicitly set, not the physical keyboard state), but murmur's
own listener interpreted the synthetic Space release as the user releasing the
hotkey.

---

## Why modifier-release tracking doesn't work

An earlier attempt used a set `_ptt_modifiers_held_at_release` to block
re-activation until Ctrl and Alt were released.  This failed because **macOS
does not deliver modifier key-release events through the CGEventTap in pynput's
configuration**.  Ctrl and Alt remained in `_held` forever, permanently blocking
all subsequent sessions.

The fix was a time-based debounce (`_ptt_last_release_time`) instead.

---

## Why Cmd+V fails when modifier keys are physically held

Even when using clipboard injection (`pbcopy` + `Cmd+V`), some applications
blocked the paste when Ctrl+Option were physically held.  The root cause:

CGEvents carry their modifier flags in the event object itself.  pynput's
`Controller` sets only the flags it explicitly manages, so the `Cmd+V` events
it generates do **not** carry Ctrl or Option in their per-event flags.
Applications reading `CGEventGetFlags()` see a plain `Cmd+V` — correct.

However, some applications (notably terminal emulators and tools like Claude Code)
query the **hardware keyboard state** via `[NSEvent modifierFlags]` (a class
method that reads the current physical device state, not the event's flags).
While Ctrl+Option are physically held, this call returns them regardless of what
the CGEvent says.  The application then sees `Ctrl+Option+Cmd+V` and rejects
the paste.

Confirmed via testing: with Ctrl+Option+Space held, paste failed in Claude Code;
with toggle mode (keys released before injection), paste succeeded.

---

## Why suppressing Ctrl/Option via darwin_intercept is impractical

pynput exposes a `darwin_intercept` callback (passed as `intercept=` to
`keyboard.Listener`) that runs after `on_press`/`on_release` and can suppress
events by returning `None`.  This could, in theory, hide Ctrl and Option from
the OS.

The problem is **speculative suppression**: at Ctrl keydown time, there is no way
to know whether the user is starting `Ctrl+Option+Space` (hotkey) or `Ctrl+C`
(copy).  To suppress Ctrl speculatively and re-inject it if it turns out not to
be part of the hotkey, the re-injected event would loop back through the same
CGEventTap and require markers to avoid infinite loops.  This adds latency to
every Ctrl keypress and significant complexity.

---

## The solution: F12 as push-to-talk trigger with event suppression

F12 is not a modifier key, so it can be trivially suppressed without speculation:
at F12 keydown time, the decision to suppress is immediate and unconditional.

**Current design:**

- Push-to-talk is bound to **F12** (no modifier keys required).
- `PynputHotkeyListener` passes `intercept=self._darwin_intercept` to
  `keyboard.Listener` when any binding has `suppress=True`.
- `_darwin_intercept` extracts the CGEvent keycode via
  `CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)` and returns
  `None` (suppress) if it matches a suppress binding's VK code.
  F12 has VK code `0x6F` (111).
- Because `darwin_intercept` runs **after** `on_press`/`on_release`, the
  hotkey logic still fires normally — only the OS forwarding is blocked.

### Hardware modifier state during F12 hold

F12 is not a modifier key.  While the user holds F12:
- `[NSEvent modifierFlags]` returns 0 — no Ctrl, Option, Cmd, or Shift.
- Synthetic events from `controller.type(text)` carry no modifier flags.
- Target applications receive plain character keystrokes with no modifier
  interference.

### Why `controller.type()` is safe with F12

With F12 as the trigger and no modifiers held:

1. Synthetic character events do not match the F12 binding
   (`trigger = Key.f12`, `modifiers = frozenset()`).  Characters have
   different VK codes; none equal `0x6F`.
2. Other bindings (toggle_start, toggle_stop, copy_to_clipboard) require
   Ctrl+Alt in `_held` — never true during F12 hold.
3. No "pasting..." placeholder — text appears inline character by character.
4. Clipboard is not overwritten.

**Current default:** `inject_strategy = "pynput"` (direct `controller.type()`).

### Event tap mode

When `suppress=True` bindings exist, `keyboard.Listener` uses
`kCGEventTapOptionDefault` (active tap) instead of `kCGEventTapOptionListenOnly`.
An active tap requires Accessibility permission (System Preferences → Privacy &
Security → Accessibility) but is already required for `Controller` to post events.
If no suppress bindings are configured, the listener reverts to listen-only mode.

---

## Trailing space

The `trailing_space: true` config (default) appends a space after each injected
turn.  With `inject_strategy = "pynput"` this is typed as a synthetic Space
keydown/keyup.  The Space event arrives at the listener but does not match any
binding (the F12 binding requires `trigger = Key.f12`; other bindings require
Ctrl+Alt), so it is harmless.

A trailing newline would submit forms/terminals, so it is not the default.

---

## Summary of constraints and approaches

| Approach | Works in target app | Triggers pynput listener | Hardware modifier bleed |
|---|---|---|---|
| `controller.type()` with Ctrl+Alt+Space held | Yes (usually) | **Yes** — Space stops recording | No (per-event flags only) |
| `pbcopy` + `Cmd+V` with Ctrl+Alt held | **No** in some apps | No | **Yes** — `[NSEvent modifierFlags]` |
| `pbcopy` + `Cmd+V` with F12 held | Yes | No | No |
| `controller.type()` with F12 held | Yes | No | No |

**Current design:** F12 push-to-talk with `suppress=True` + `inject_strategy = "pynput"`.
