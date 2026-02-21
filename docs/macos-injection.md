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

## Why `controller.type()` broke push-to-talk

The original injector used `pynput.keyboard.Controller.type(text)` for ASCII
text.  This generates individual keydown/keyup CGEvents for every character,
including spaces.

When the user holds **Ctrl+Option+Space** for push-to-talk:

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

## Why `controller.type()` is also wrong for the target app

Even if murmur's listener didn't intercept synthetic events, using
`controller.type()` while Ctrl+Option are physically held raises a subtlety:
CGEvents carry their modifier flags in the event object itself.  pynput's
Controller sets only the flags it explicitly manages, so the injected character
events arrive at the target application **without** Ctrl or Option — correct for
text input.

However, some applications (notably terminals and readline-based CLIs) query the
hardware keyboard state separately alongside the event, and may observe the
physical modifier keys.  The safest injection method is one that does not send
individual character keystrokes at all.

---

## The fix: clipboard injection (`inject_strategy = "clipboard"`)

`PynputInjector._inject_via_clipboard()` does:

```python
subprocess.run(["pbcopy"], input=text.encode("utf-8"), ...)
with self._controller.pressed(keyboard.Key.cmd):
    self._controller.tap(keyboard.KeyCode.from_char("v"))
```

This generates exactly **four** synthetic key events: Cmd↓, V↓, V↑, Cmd↑.
None of those match the push-to-talk binding (`Ctrl+Alt+Space`), so the listener
is never triggered mid-hold.

The default `inject_strategy` is set to `"clipboard"` for this reason.

### Modifier flags on the Cmd+V events

pynput's Controller sets flags based only on its own modifier-tracking state.
When it presses Cmd, only the Cmd flag is set on the event.  The physical
Ctrl+Option state is **not** merged into the synthetic event.  Target
applications that read `CGEventGetFlags()` see a plain `Cmd+V`.

### Claude Code "pasting..." behaviour

Claude Code (and some other terminal-based tools) intercept `Cmd+V` and display
a `"pasting..."` placeholder while processing clipboard content.  This is
application-level paste handling, not a murmur issue.  The text is delivered
correctly; it simply appears after Claude Code processes the paste event rather
than inline character by character.

---

## Trailing space

The `trailing_space: true` config (default) appends a space to the text **before
it is written to the clipboard**, so the space is part of the pasted content.
No extra key event is needed, and the listener never sees a synthetic Space.

A trailing newline would follow the same logic (safe from the hotkey perspective)
but would insert unwanted line breaks between sentences in most editors, so it is
not the default.

---

## Summary of constraints

| Approach | Works in target app | Triggers pynput listener |
|---|---|---|
| `controller.type(text)` for ASCII | Yes (usually) | **Yes** — Space in text stops recording |
| `controller.type(text)` for non-ASCII | Partial | **Yes** |
| `pbcopy` + `Cmd+V` | Yes | No — Cmd/V don't match any binding |
| Typing `\n` after paste | Dangerous (submits forms) | No — Enter not in bindings |
| Typing ` ` after paste | Bad | **Yes** — Space stops recording |

**Current design:** always use `pbcopy` + `Cmd+V` (`inject_strategy = "clipboard"`).
