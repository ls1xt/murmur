# macOS Text Injection — Design Notes

This document explains why text injection on macOS works the way it does, and
the chain of problems that led to the current design. Target audience: a
developer who needs to understand why each architectural decision was made and
what pitfalls to avoid when changing it.

---

## The macOS CGEvent pipeline

macOS routes all keyboard input — physical keystrokes and synthetic ones —
through a single system-wide `CGEvent` pipeline. There are two tap insertion
points relevant to murmur:

| Level | Constant | Description |
|---|---|---|
| 0 | `kCGHIDEventTap` | HID device level; earliest possible interception point |
| 1 | `kCGSessionEventTap` | Session level; after HID taps have processed the event |

pynput's `keyboard.Listener` installs a `CGEventTap` at level 0
(`kCGHIDEventTap`). When suppression is active (`kCGEventTapOptionDefault`,
the "active" tap mode), every keyboard event — including synthetic ones posted
by `pynput.keyboard.Controller` — is serialized through the same tap callback.

This is the central tension: there is no separation between "real keyboard"
and "virtual keyboard" at the HID level, unlike Linux evdev where physical
devices and `uinput` virtual devices are separate file descriptors.

---

## Hotkey detection: PynputHotkeyListener

### How it works

`PynputHotkeyListener` uses pynput's `keyboard.Listener` with manual
modifier-state tracking (a `_held: set` of canonical keys). It does not use
pynput's `GlobalHotKeys` helper, which silently fails for `Ctrl+Alt`
combinations on macOS (pynput GitHub issue #297, unresolved).

Canonical keys are resolved via `listener.canonical(key)`, which unifies
left/right modifier variants — `Key.ctrl_l` and `Key.ctrl_r` both become
`Key.ctrl`. Canonicalization is re-applied after the listener starts because
some keys (e.g. `Key.space`) have a different runtime canonical form on macOS
(a `KeyCode(vk=49)` object) than the static pynput enum value.

### darwin_intercept: the correct kwarg name

When any configured binding has `suppress=True`, pynput must be started in
active tap mode so events can be swallowed. This is done via the
`darwin_intercept` callback kwarg:

```python
keyboard.Listener(
    on_press=self._on_press,
    on_release=self._on_release,
    darwin_intercept=self._darwin_intercept,  # NOT intercept=
)
```

**The kwarg must be `darwin_intercept=`, not `intercept=`.** pynput's
`_base.Listener.__init__` filters kwargs by a platform prefix computed from the
listener class hierarchy (`option_prefix = prefix(Listener, self.__class__)`,
which is `"darwin_"` on macOS). Only kwargs whose names start with this prefix
are stored in `self._options`. Using `intercept=` is silently discarded — no
error, no suppression, and the active tap is never installed.

The darwin backend then reads `self._options.get("intercept")` (without the
prefix) to obtain the callback. Passing `darwin_intercept=fn` causes it to be
stored in `_options` as `"intercept": fn`, which the backend finds correctly.

### VK codes and the _EVDEV_TO_MACOS_VK table

`darwin_intercept` receives raw `CGEvent` objects. To decide whether to
suppress an event, it extracts the hardware virtual key code:

```python
from Quartz import CGEventGetIntegerValueField, kCGKeyboardEventKeycode
keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
```

This VK code must be known at binding creation time. The natural approach —
calling `listener.canonical(Key.f12).vk` — fails because pynput's
`canonical()` returns a `KeyCode` built from a symbol name with `vk=None` for
function keys. The VK information is lost after canonicalization.

To work around this, `pynput.py` maintains a static `_EVDEV_TO_MACOS_VK` dict
mapping evdev key names to macOS CGEvent keycodes (`kVK_*` constants from
Carbon's `HIToolbox/Events.h`). The VK is resolved at binding creation time
(in `_resolve_bindings`) and stored in `_ResolvedBinding.trigger_vk`, which
survives the subsequent canonicalization pass. The collected VKs form the
`_suppressed_vk_codes` set checked by `darwin_intercept`.

F12 has VK code `0x6F` (111 decimal). The full table covers all function keys,
common special keys, and alpha/digit rows.

---

## F12 push-to-talk: why F12 and why suppress=True

### Not a modifier key

The original trigger was `Ctrl+Option+Space`. The modifier keys caused two
independent failure modes (see Pitfalls below). F12 was chosen because:

1. It is not a modifier key — `[NSEvent modifierFlags]` returns 0 while it
   is held, so hardware modifier state is clean during injection.
2. Suppression is unconditional — at F12 keydown time, the decision to
   suppress is immediate. There is no speculative suppression problem (see
   below).

### Key-repeat and the _ptt_press_dispatched guard

While F12 is held, macOS generates key-repeat events at approximately 20 per
second. Each repeat fires `on_press`. The `_ptt_press_dispatched` flag ensures
only the first press starts a recording session; repeats are silently ignored:

```python
if self._ptt_press_dispatched:
    continue  # key-repeat while session in flight
self._ptt_press_dispatched = True
```

The flag is cleared in `on_release` (the matching hotkey release), gating each
press-dispatch to exactly one release-dispatch.

### Debounce timer prevents phantom releases

A `_ptt_last_release_time` monotonic timestamp blocks re-activation for
`push_to_talk_debounce_ms` (default 300 ms) after each real release. This
guards against phantom key events that macOS can deliver after a release, which
would otherwise start a new session immediately after stopping.

The debounce timestamp is set **after** `_dispatch_release` returns, not
before, because `_dispatch_release` calls `feedback.play_stop()` — a blocking
~100 ms audio call. Setting the timestamp before dispatch would consume part of
the debounce window, allowing buffered phantom presses to slip through.

---

## Text injection: CGEventInjector (inject_strategy="cgevent")

### Why controller.type() is incompatible with an active tap

`pynput.keyboard.Controller.type()` posts events via
`CGEventPost(kCGHIDEventTap, event)` — the same HID level 0 tap where our
`darwin_intercept` is installed. With `kCGEventTapOptionDefault` active, all
keyboard events (physical and synthetic) are serialized through the same
listener thread callback.

During F12 hold, the listener receives both real F12 key-repeat events (~20/s)
and synthetic character events from `controller.type()`. On macOS Sequoia,
event coalescing under this load drops or reorders synthetic characters,
producing scrambled output. This is not a bug in murmur — it is a consequence
of the two event streams competing in the same serialization queue.

### CGEventInjector bypasses the HID tap

`CGEventInjector` posts events at `kCGSessionEventTap` (level 1):

```python
CGEventPost(kCGSessionEventTap, event)
```

Events posted at level 1 enter the pipeline **after** all HID-level taps have
already processed them. They bypass `darwin_intercept` entirely, eliminating
the serialization contention. This is the correct fix.

### Unicode injection without keycode mapping

For each character, `CGEventInjector` creates a key event with vk=0 and sets
the Unicode string directly:

```python
e_dn = CGEventCreateKeyboardEvent(source, 0, True)
CGEventKeyboardSetUnicodeString(e_dn, 1, char)
CGEventPost(kCGSessionEventTap, e_dn)
```

This approach delivers the exact Unicode character to the receiving application
regardless of the active keyboard layout. Applications that read the Unicode
string from the generated `NSEvent` — terminals, Electron apps (VSCode, Claude
Code), and native Cocoa apps — all receive the character correctly. Only
applications that dispatch on raw keycode rather than character string would
miss it, but those are not the targets here.

Backspace is an exception: it uses the real VK `0x33` (`kVK_Delete`) so that
applications mapping backspace by keycode receive it correctly.

### CGEventSourceCreate must be lazy

`CGEventInjector` creates its `CGEventSource` lazily on first injection, not
in `__init__`:

```python
def _get_source(self) -> object:
    if self._source is None:
        from Quartz import CGEventSourceCreate, kCGEventSourceStatePrivate
        self._source = CGEventSourceCreate(kCGEventSourceStatePrivate)
    return self._source
```

Calling `CGEventSourceCreate` before `NSApp.run()` initializes the Text
Services Manager (TSM) causes TSM to find multiple keyboard input sources.
This triggers the `_HaveOnlyOneKeyboardInputSource` assertion in TSM and
terminates the process with `SIGABRT`. On macOS with pystray, `NSApp.run()`
runs on the main thread inside pystray's event loop setup; anything constructed
before that point (including `DictationApp.__init__`) must not call
`CGEventSourceCreate`.

### Compatibility

`CGEventInjector` works correctly in:
- Terminal emulators (including vim)
- Electron apps (VSCode, Claude Code)
- Native macOS (Cocoa) apps

It does not use the clipboard, so the clipboard is never overwritten during
dictation.

To activate: set `injector.backend = "cgevent"` in config. The `auto` backend
resolves to `PynputInjector` on macOS (which uses `controller.type()`); use
explicit `cgevent` to get `CGEventInjector`.

---

## Why clipboard injection fails with modifier triggers

With `Ctrl+Option+Space` as the push-to-talk trigger, clipboard injection
(`pbcopy` + `Cmd+V`) fails silently in many applications. The root cause is
`[NSEvent modifierFlags]`.

CGEvents carry their modifier flags in the event object. pynput's
`Controller` sets only the flags it explicitly manages, so the `Cmd+V` event
it generates does not carry Ctrl or Option in its per-event flags.
`CGEventGetFlags()` returns a plain `Cmd+V` — correct.

However, applications that query the **hardware keyboard state** via
`[NSEvent modifierFlags]` (a class method reading the current physical device
state, not the event's flags) see Ctrl+Option as still held, because they
physically are. The application then interprets the paste as
`Ctrl+Option+Cmd+V` and silently ignores it or routes it to a different action.

This affects terminal emulators and applications like Claude Code. Confirmed
empirically: with `Ctrl+Option+Space` held, paste failed; with toggle mode
(keys released before injection), paste succeeded.

**With F12 as the trigger, this problem does not exist.** F12 is not a
modifier key. `[NSEvent modifierFlags]` returns 0 while F12 is held. `Cmd+V`
arrives as a clean paste. The `clipboard` injection strategy therefore works
correctly with F12 as the trigger and remains available as an alternative to
`cgevent`.

---

## Why suppressing Ctrl/Option at the tap level is impractical

In principle, `darwin_intercept` could suppress Ctrl and Option events to
prevent hardware modifier bleed. The obstacle is speculative suppression: at
Ctrl keydown time, there is no way to know whether the user intends
`Ctrl+Option+Space` (hotkey) or `Ctrl+C` (copy). To suppress Ctrl and then
re-inject it if it is not part of the hotkey, the re-injected event would loop
back through the same CGEventTap and require loop-detection markers to avoid
infinite recursion. This adds latency to every Ctrl keypress in the system,
plus significant complexity.

F12 avoids this entirely: at F12 keydown, the suppression decision is immediate
and unconditional.

---

## Audio feedback: afplay vs sounddevice

The start beep is played via `subprocess.Popen(["afplay", wav_path])`, where
`wav_path` is a pre-generated WAV file written to a temp file at
`AudioFeedback.__init__` time. `afplay` is a system binary that CoreAudio
keeps warm; fork+exec latency is approximately 20 ms. The alternative —
opening a `sounddevice.RawOutputStream` — incurs approximately 1000 ms of
PortAudio/CoreAudio initialization latency on the first call, which is
unacceptable for a start-of-recording cue.

The stop beep uses `sounddevice` directly as a blocking call. Using `afplay`
for the stop beep would add approximately 400–500 ms of subprocess startup
overhead on top of the audio duration, making it worse. Because the stop beep
is blocking, callers can safely tear down the microphone stream after it
returns without an audio race.

---

## Websockets log suppression

The AssemblyAI SDK uses `websockets`, which logs raw binary WebSocket frames
at `DEBUG` level. This produces extremely noisy logs during active transcription
sessions. In `_setup_logging`:

```python
logging.getLogger("websockets").setLevel(logging.WARNING)
```

This override is applied unless `MURMUR_LOG_LEVEL=WEBSOCKETS_DEBUG`. The env
var `MURMUR_LOG_LEVEL` sets the root log level and is checked against the
literal string `"WEBSOCKETS_DEBUG"` before applying the suppression; any other
value (e.g. `DEBUG`) suppresses websocket frames but enables all other debug
output.

---

## Pitfalls reference

### 1. `darwin_intercept=` not `intercept=`

pynput's `Listener.__init__` stores kwargs in `_options` only if they start
with the platform prefix `"darwin_"`. Passing `intercept=fn` is silently
ignored — no error, no active tap, no suppression. Always use
`darwin_intercept=fn`.

### 2. CGEventSourceCreate must be lazy

Calling `CGEventSourceCreate` before `NSApp.run()` initializes TSM causes
`_HaveOnlyOneKeyboardInputSource` assertion → `SIGABRT`. Create the source on
the first injection call, not in `__init__`. See `CGEventInjector._get_source`.

### 3. VK codes are lost after canonical()

`Key.f12.value.vk` is `None` in the canonical form pynput returns. Never rely
on `listener.canonical(Key.fN).vk` for darwin_intercept keycode matching.
Always use the static `_EVDEV_TO_MACOS_VK` table to resolve VK codes at
binding-creation time.

### 4. Active tap + controller.type() produces scrambled output

`kCGEventTapOptionDefault` serializes all keyboard events (physical and
synthetic) through the tap callback. Under F12 key-repeat load (~20/s),
synthetic characters from `controller.type()` compete for the queue → macOS
Sequoia event coalescing drops or reorders characters. The fix is
`CGEventInjector`, which posts at `kCGSessionEventTap` and bypasses the HID
tap entirely.

### 5. kCGSessionEventTap vs kCGHIDEventTap

Events posted via `CGEventPost(kCGSessionEventTap, event)` enter the pipeline
after all HID-level taps. They are invisible to the `darwin_intercept` callback
and incur no serialization overhead from it. Events posted via
`CGEventPost(kCGHIDEventTap, event)` (what `controller.type()` does) go through
the HID tap and are subject to the active tap callback.

### 6. Modifier-release events are not delivered through the tap

When using a `Ctrl+Option` combination as a trigger, macOS does not reliably
deliver the Ctrl and Option key-release events through the CGEventTap in
pynput's configuration. Those keys can remain in `_held` indefinitely, which
caused permanent blocking of subsequent sessions when modifier-release tracking
was attempted. The solution is a time-based debounce (`_ptt_last_release_time`)
rather than waiting for modifier releases.

---

## Summary: approach comparison

| Approach | Works in target app | Triggers pynput listener | Hardware modifier bleed | Notes |
|---|---|---|---|---|
| `controller.type()` with Ctrl+Alt+Space held | Yes (usually) | **Yes** — synthetic Space stops recording | No (per-event flags only) | Original approach; abandoned |
| `pbcopy` + `Cmd+V` with Ctrl+Alt held | **No** in many apps | No | **Yes** — `[NSEvent modifierFlags]` | Silently fails in terminals, Electron |
| `pbcopy` + `Cmd+V` with F12 held | Yes | No | No | Supported; `clipboard` strategy |
| `controller.type()` with F12 held | Scrambled on Sequoia | No | No | Incompatible with active tap |
| `CGEventInjector` at `kCGSessionEventTap` with F12 | Yes | No | No | **Current recommended solution** |

**Recommended configuration:** F12 push-to-talk with `suppress=True` and
`injector.backend = "cgevent"`.
