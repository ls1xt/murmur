# Phase 4: Interaction Polish - Research

**Researched:** 2026-02-18
**Domain:** Linux input subsystem (evdev/uinput), D-Bus SNI protocol (Gio), live text injection, PyAudio under PipeWire
**Confidence:** HIGH

## Summary

Phase 4 has five distinct implementation areas. All five have been verified against the live system. The key finding is that **the infrastructure already works**: PyAudio output succeeds under PipeWire/ALSA, /dev/uinput is writable by the user (already in `input` group), the SNI watcher (waybar) is running and accepting registrations, and the AssemblyAI partial-transcript callback path is wired to `_on_partial_transcript` but that method only logs. The work is purely additive plumbing, not new infrastructure.

The grab-and-forward pattern (evdev `device.grab()` + `UInput.from_device()`) is the correct architecture for hotkey passthrough suppression. The partial injection delta algorithm is straightforward since AssemblyAI only appends to partials within a turn. The SNI implementation can be copied almost verbatim from the test script already running on this system (PID 3880343), which was verified working against waybar. Audio feedback already plays correctly — no PipeWire-specific fix is needed.

The largest structural change is the hotkey system: `HotkeyConfig` and `EvdevHotkeyListener` must support multiple independent bindings (push-to-talk, toggle-start, toggle-stop), each mapping to a distinct callback pair. The current single-binding design must be replaced with a `bindings` list.

**Primary recommendation:** Implement in this order: (1) multi-binding hotkey config + listener, (2) grab-and-forward in EvdevHotkeyListener, (3) partial injection delta in DictationApp, (4) SNI tray replacing the Sway no-op path, (5) audio feedback visibility upgrade. Each area is independently testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Hotkey passthrough suppression
- Use the **grab-and-forward** pattern: `device.grab()` each physical keyboard at startup, create a `UInput` virtual device per keyboard via `UInput.from_device()`, forward all events except the hotkey combo
- Grab once at startup, never ungrab mid-session (avoids ghost modifier problem)
- When hotkey fires: inject synthetic key-up for held modifiers into uinput before callback, so compositor's modifier state is cleared
- When hotkey releases: inject synthetic key-down to restore modifier state
- Requires `/dev/uinput` write access — add udev rule: `KERNEL=="uinput", MODE="0660", GROUP="input"`
- There is no lighter-weight alternative in the Linux kernel; all tools (keyd, interception-tools, xremap, evremap) use this same architecture

#### Live partial injection (delta mode)
- Compute the **diff** between last-injected partial and the new partial — only inject the new characters (no backspace-and-retype)
- Track `_last_partial: str` in DictationApp; on each `_on_partial_transcript(text)`:
  - If `text` starts with `_last_partial`, inject only the suffix `text[len(_last_partial):]`
  - If text diverges (AssemblyAI revised earlier words), fall back to backspace + retype for the changed portion
- On `_on_final_transcript(text)`: backspace the entire partial, inject the finalized/formatted text, reset `_last_partial`
- The transcriber plumbing (`_on_partial` callback) already works end-to-end; the gap is entirely in `DictationApp._on_partial_transcript` which currently only logs

#### Hotkey modes and shortcuts
- Both `push_to_talk` and `toggle` modes are already fully implemented and tested in `hotkey/base.py`
- Expose **three distinct shortcuts**, each with its own action:
  - `Ctrl+Alt+Space` — push-to-talk (hold to record, release to stop)
  - `Ctrl+Alt+K` — toggle start recording (press once to begin)
  - `Ctrl+Alt+L` — stop recording (press to end toggle session)
- The current single-hotkey `HotkeyConfig` needs to evolve into a multi-binding system
- All three shortcuts share the same `Ctrl+Alt` modifier prefix; only the trigger key differs
- Config structure: replace single `modifiers`/`trigger`/`mode` with a `bindings` list or named binding fields

#### Audio feedback
- Audio is already wired: `AudioFeedback.play_start()` and `play_stop()` are called in `_on_activate`/`_on_deactivate`
- The likely issue on Sway/PipeWire: investigate whether the PyAudio output stream opens correctly under PipeWire
- Ensure the ALSA/JACK probe noise is suppressed (run.sh already does this)
- If PyAudio output fails silently (DEBUG-level log), make it more visible so the user knows audio feedback is broken

#### Sway tray (SNI via Gio.DBus)
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

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core (no new dependencies — all already in pyproject.toml)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| evdev | >=1.7.0 | Keyboard grab + UInput virtual device | Already used for hotkey detection; `device.grab()` and `UInput.from_device()` are the standard Linux kernel input passthrough pattern |
| gi.repository.Gio | GLib 2.86.3 (installed) | D-Bus SNI implementation | Already a dependency (PyGObject); `DBusConnection.register_object()` + `bus_own_name()` implement the StatusNotifierItem protocol |
| gi.repository.GLib | GLib 2.86.3 (installed) | Main loop + idle callbacks | Thread-safe cross-thread updates via `GLib.idle_add()`; already used in existing tray code |
| pyaudio | >=0.2.14 | Audio feedback beeps | Already used; verified working under PipeWire/ALSA on this system |
| Pillow | >=10.0.0 | SNI icon pixmap generation | Already used for pystray icons; repurpose for ARGB32 conversion |

### No Alternatives to Consider
The user has locked all library decisions. All required libraries are already installed.

## Architecture Patterns

### Recommended Module Structure
```
murmur/
├── hotkey/
│   ├── base.py          # MODIFY: HotkeyListener → multi-binding support
│   ├── evdev.py         # MODIFY: add grab+forward, multi-trigger dispatch
│   └── __init__.py      # MODIFY: factory reads bindings list
├── feedback/
│   ├── tray.py          # MODIFY: add SNI backend for Sway path
│   └── audio.py         # MODIFY: upgrade error logging from DEBUG to WARNING
├── config.py            # MODIFY: HotkeyConfig → bindings list structure
└── main.py              # MODIFY: _on_partial_transcript delta injection + _last_partial tracking
```

### Pattern 1: Grab-and-Forward with UInput
**What:** Each physical keyboard is grabbed (EVIOCGRAB) so the compositor never sees raw events. A matching virtual UInput device forwards all events except the hotkey combo.
**When to use:** At `start()` time, for every detected keyboard device.

```python
# Source: evdev documentation + verified locally
import evdev
from evdev import ecodes, UInput

# On start():
dev = evdev.InputDevice('/dev/input/event3')
dev.grab()  # EVIOCGRAB: compositor stops receiving events from this device
ui = UInput.from_device(dev, name='murmur-forwarded')  # mirrors capabilities

# In event loop: forward everything except hotkey combo
for event in dev.read():
    is_hotkey = (event.type == ecodes.EV_KEY and
                 event.code == trigger_code and
                 modifier_codes.issubset(held_keys))
    if not is_hotkey:
        ui.write_event(event)
        ui.syn()

# When hotkey fires: clear compositor modifier state
for mod_code in held_modifier_codes:
    ui.write(ecodes.EV_KEY, mod_code, 0)  # synthetic key-up
ui.syn()
# ... invoke callback ...

# When hotkey releases: restore modifier state
for mod_code in held_modifier_codes:
    ui.write(ecodes.EV_KEY, mod_code, 1)  # synthetic key-down
ui.syn()
```

**Verified:** `/dev/uinput` is writable (user is in `input` group, mode 0660 group=input). The existing udev rule at `/usr/lib/udev/rules.d/80-uinput.rules` already sets `GROUP="input" MODE="0660"` — no new udev rule needed on Arch Linux.

### Pattern 2: Multi-Binding Hotkey Config
**What:** Replace the single `modifiers`/`trigger`/`mode` in `HotkeyConfig` with a `bindings` list. Each binding has its own modifiers, trigger, and action.

```python
# config.py — new structure
@dataclass
class HotkeyBinding:
    modifiers: list[str]
    trigger: str
    action: str  # "push_to_talk" | "toggle_start" | "toggle_stop"

@dataclass
class HotkeyConfig:
    bindings: list[HotkeyBinding] = field(default_factory=lambda: [
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
            trigger="KEY_SPACE",
            action="push_to_talk",
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
            trigger="KEY_K",
            action="toggle_start",
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
            trigger="KEY_L",
            action="toggle_stop",
        ),
    ])
    backend: str = "auto"
    evdev_device: str | None = None
```

**Dispatch in EvdevHotkeyListener:** Each binding gets its own `_modifier_codes: set[int]` and `_trigger_code: int`. On key-down, check all bindings. The push-to-talk action calls `_on_activate` on press, `_on_deactivate` on release. The toggle-start action calls `_on_activate` on press. The toggle-stop action calls `_on_deactivate` on press.

**Backward compatibility:** The `HotkeyListener.set_callbacks(on_activate, on_deactivate)` interface is unchanged. The action dispatch replaces the `mode` field in `HotkeyListener.base`.

### Pattern 3: Partial Injection Delta
**What:** Track `_last_partial: str` in `DictationApp`. On each partial, inject only the new suffix. On final, backspace the partial and inject the formatted final.

```python
# main.py additions
class DictationApp:
    def __init__(self, config):
        ...
        self._last_partial: str = ""

    def _on_partial_transcript(self, text: str) -> None:
        if not text:
            return
        if text.startswith(self._last_partial):
            # Common case: AssemblyAI appended words
            suffix = text[len(self._last_partial):]
            if suffix:
                self.injector.inject_raw(suffix)  # no trailing space
        else:
            # Diverged: backspace the old partial, type new text
            backspaces = len(self._last_partial)
            if backspaces > 0:
                self.injector.inject_backspaces(backspaces)
            self.injector.inject_raw(text)
        self._last_partial = text

    def _on_final_transcript(self, text: str) -> None:
        # Backspace the partial first
        if self._last_partial:
            self.injector.inject_backspaces(len(self._last_partial))
            self._last_partial = ""
        if not text.strip():
            return
        logger.info("Injecting: %s", text)
        self.injector.inject(text)  # existing method, adds trailing space

    def _on_deactivate(self) -> None:
        ...
        self._last_partial = ""  # reset on recording stop
        ...
```

**YdotoolInjector additions needed:**
- `inject_raw(text: str)` — like `inject()` but no trailing space, no strategy routing for partials (use ydotool type directly since partials are ASCII)
- `inject_backspaces(n: int)` — use `ydotool key` with KEY_BACKSPACE repeated n times, or `ydotool type` with `\x08` * n

**Backspace via ydotool:** Keycode for KEY_BACKSPACE is 14. Use `ydotool key 14:1 14:0` per backspace, or `ydotool type $'\x08\x08\x08'` for multiple. The `ydotool type` approach is simpler and handles batches efficiently.

### Pattern 4: SNI Tray via Gio.DBus
**What:** Publish a `org.kde.StatusNotifierItem` object on D-Bus, own a bus name following the `org.kde.StatusNotifierItem-{PID}-{N}` convention, and register with the watcher.

**Verified interface from live inspection of waybar's watcher:**
```xml
<!-- Minimal SNI interface — verified against org.kde.StatusNotifierWatcher introspection -->
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <signal name="NewIcon"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
```

**Registration flow (verified working — PID 3880343 is the test script):**
```python
import os
from gi.repository import Gio, GLib

conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
sni_name = f'org.kde.StatusNotifierItem-{os.getpid()}-1'

node = Gio.DBusNodeInfo.new_for_xml(SNI_XML)
iface_info = node.interfaces[0]

reg_id = conn.register_object(
    '/StatusNotifierItem',
    iface_info,
    handle_method_call,   # method_call_closure
    handle_get_property,  # get_property_closure
    None,                 # set_property_closure
)

def on_name_acquired(conn, name, data):
    conn.call_sync(
        'org.kde.StatusNotifierWatcher',
        '/StatusNotifierWatcher',
        'org.kde.StatusNotifierWatcher',
        'RegisterStatusNotifierItem',
        GLib.Variant('(s)', (sni_name,)),
        None,
        Gio.DBusCallFlags.NONE,
        5000,
        None,
    )

owner_id = Gio.bus_own_name(
    Gio.BusType.SESSION,
    sni_name,
    Gio.BusNameOwnerFlags.NONE,
    None,           # bus_acquired_closure
    on_name_acquired,
    None,           # name_lost_closure
)

loop = GLib.MainLoop()
thread = threading.Thread(target=loop.run, daemon=True)
thread.start()
```

**IconPixmap format — verified from live D-Bus inspection:**
The `a(iiay)` format is `[(width, height, bytes)]`. The bytes are ARGB32 in **network byte order (big-endian)**. Each pixel is 4 bytes: `[A, R, G, B]`. Pillow's `Image.tobytes()` produces RGBA, so the channel order must be swapped:

```python
def _make_sni_pixmap(state: str) -> bytes:
    """Convert PIL RGBA image to SNI ARGB32 big-endian bytes."""
    from PIL import Image, ImageDraw
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # ... draw circle ...
    rgba_bytes = img.tobytes()  # R,G,B,A per pixel
    # Convert RGBA -> ARGB (rotate channels: A goes first)
    result = bytearray(len(rgba_bytes))
    for i in range(size * size):
        r, g, b, a = rgba_bytes[i*4 : i*4+4]
        result[i*4]   = a  # A
        result[i*4+1] = r  # R
        result[i*4+2] = g  # G
        result[i*4+3] = b  # B
    return bytes(result)
```

**State change (thread-safe via GLib.idle_add):**
```python
def set_state(self, state: str) -> None:
    GLib.idle_add(self._emit_new_icon_signal)

def _emit_new_icon_signal(self) -> bool:
    # Emit NewIcon signal so waybar re-fetches IconPixmap property
    self._conn.emit_signal(
        None,  # destination (broadcast)
        '/StatusNotifierItem',
        'org.kde.StatusNotifierItem',
        'NewIcon',
        None,
    )
    return False  # don't repeat
```

**Integration into TrayIcon:** The `start()` method already has a Sway guard (`_appindicator_works()` returns False when `SWAYSOCK` in env). Replace the `logger.info("Tray icon disabled (Sway detected; SNI not yet implemented)")` path with the SNI implementation. The non-Sway path (pystray) stays unchanged.

### Pattern 5: Audio Feedback Error Visibility
**Current state:** PyAudio output verified working — `stream.open(output=True)` succeeds on this PipeWire/ALSA system (tested in research). The current `logger.debug("Audio feedback error: %s", e)` in `_play_tone` means failures are invisible at the default INFO log level.

**Fix:** Upgrade the log level and add a one-time warning:
```python
# In AudioFeedback.__init__:
self._audio_warned = False

# In _play_tone exception handler:
except Exception as e:
    if not warned:
        logger.warning("Audio feedback unavailable: %s", e)
    # Use a class-level flag to avoid spamming
```

**Simpler approach:** In `_get_pa()`, log at WARNING (not DEBUG) when init fails. This matches the pattern used throughout the codebase for unavailable optional features.

### Anti-Patterns to Avoid
- **Ungrabbing during a session:** If `device.ungrab()` is called while modifiers are held, the compositor sees orphaned key-down events with no matching key-up — "ghost modifier" problem. Grab once at `start()`, ungrab at `stop()` only.
- **Forgetting `ui.syn()` after each forwarded event:** The UInput only delivers events after a `SYN_REPORT`. Omitting `syn()` causes batched delivery with wrong timestamps.
- **Using `GLib.idle_add()` from non-GLib threads for the SNI pixmap property:** The `handle_get_property` callback is called from the GLib main loop thread already — no need to marshal into it. Only `set_state()` (called from the app thread) needs `idle_add()`.
- **Registering the SNI object before owning the bus name:** The watcher validates that the service name making the `RegisterStatusNotifierItem` call actually owns the name. Register the object first, then acquire the name, then call `RegisterStatusNotifierItem` from the `name_acquired` callback.
- **Partial injection with trailing space:** `inject_raw()` for partials must NOT add a trailing space — partials are mid-word. Only the final injection via `inject()` gets the trailing space.
- **Counting backspaces on Unicode:** `len(text)` counts Unicode code points, not characters visible on screen (some emoji are multi-codepoint). Since AssemblyAI transcribes speech as ASCII-range text (English words), this is safe for this use case. Document this assumption.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Keyboard event forwarding | Custom kernel module | evdev `UInput.from_device()` | Already the standard; handles all event types, timestamps, SYN automatically |
| SNI protocol parsing | Custom D-Bus XML parser | `Gio.DBusNodeInfo.new_for_xml()` | GLib handles all type marshalling and introspection |
| GLib thread safety | Manual mutex for D-Bus | `GLib.idle_add()` | GLib main loop is the correct serialization point for D-Bus signal emission |
| Icon format conversion | Custom pixel packing | Pillow `Image.tobytes()` + channel swap | Pillow guarantees correct RGBA byte layout; only channel order needs fixing |

**Key insight:** The Linux input subsystem's grab-and-forward pattern via UInput is the same mechanism used by keyd, xremap, and interception-tools. There is no lightweight alternative; evdev UInput IS the standard.

## Common Pitfalls

### Pitfall 1: Ghost Modifier Keys After Ungrab
**What goes wrong:** If the device is ungrabbed while modifier keys are held (e.g., Ctrl is down), the compositor receives a key-up for Ctrl with no matching key-down, causing Ctrl to "stick" or be ignored.
**Why it happens:** The compositor tracks modifier state from raw events. When grab starts, it loses visibility of the key-down. When ungrab happens, it sees key-up without key-down.
**How to avoid:** Never ungrab while any hotkey modifiers are held. The decision to "grab once, never ungrab mid-session" eliminates this entirely. On `stop()`, only ungrab after all modifier states are cleared via synthetic key-up events.
**Warning signs:** After stopping murmur, Ctrl+C or other shortcuts behave as if Ctrl is permanently held.

### Pitfall 2: SNI Object Path Must Be Exactly `/StatusNotifierItem`
**What goes wrong:** Waybar (and other SNI hosts) call methods on the registered object path. If the path doesn't match what `RegisterStatusNotifierItem` was called with, the host can't reach the object.
**Why it happens:** The `RegisterStatusNotifierItem` call takes a service name. The host then connects to that service and uses the path `/StatusNotifierItem` by convention (part of the KDE SNI spec).
**How to avoid:** Always register the object at `/StatusNotifierItem`. The service name (bus name) carries the PID; the object path is fixed.
**Warning signs:** The icon doesn't appear in waybar even though `RegisterStatusNotifierItem` returns success.

### Pitfall 3: IconPixmap Byte Order (ARGB vs RGBA)
**What goes wrong:** The icon appears as a solid color smear or the wrong color. Pillow produces RGBA; SNI wants ARGB big-endian.
**Why it happens:** The `a(iiay)` D-Bus type for IconPixmap uses ARGB32 in network byte order. This is different from Pillow's default RGBA output.
**How to avoid:** Explicitly swap channels: for each pixel, reorder `(R, G, B, A)` to `(A, R, G, B)`. Verified from live D-Bus inspection of the test script's pixmap output — the bytes show `[0xFF, 0x88, 0x88, 0x88]` = fully opaque gray, which is `[A=0xFF, R=0x88, G=0x88, B=0x88]` confirming ARGB order.
**Warning signs:** Wrong colors in waybar tray, or transparent icon.

### Pitfall 4: Partial Injection Race with Final Transcript
**What goes wrong:** A partial arrives and starts injecting; then immediately a final arrives and tries to backspace the partial. Both run on the transcriber callback thread, but `inject()` calls subprocess — they can interleave.
**Why it happens:** `_on_partial_transcript` and `_on_final_transcript` are called from the AssemblyAI SDK's internal thread. If the injector is not serialized, two concurrent ydotool subprocesses can race.
**How to avoid:** Add a lock (`threading.Lock`) around injection operations in `DictationApp`, or use a single-threaded injection queue. The existing `self._lock` is used only for the transcriber streaming state check — extend it to cover injection, or add a separate `self._inject_lock`.
**Warning signs:** Random extra characters in the injected text, or missing backspaces.

### Pitfall 5: Multi-Binding Hotkey Config Backward Compatibility
**What goes wrong:** Existing `config.json` files on disk use the old `{"hotkey": {"modifiers": [...], "trigger": "...", "mode": "..."}}` format. After migration to `bindings` list, loading old configs fails or produces empty bindings.
**Why it happens:** `_apply_section` uses `setattr` and `hasattr` — if the field names change, old values are silently ignored.
**How to avoid:** Add migration logic in `HotkeyConfig` or `DictationConfig._from_dict()`: if `hotkey.bindings` is absent but `hotkey.modifiers`/`trigger`/`mode` are present, construct a single binding from them for backward compatibility.
**Warning signs:** All three shortcuts fail to work after upgrade because the bindings list is empty.

## Code Examples

### Verified: UInput.from_device() + grab()
```python
# Source: evdev docs + verified API locally (evdev installed in .venv)
import evdev
from evdev import ecodes, UInput

dev = evdev.InputDevice('/dev/input/event3')
dev.grab()  # EVIOCGRAB
ui = UInput.from_device(dev, name='murmur-passthrough')

# Forward one event:
ui.write_event(event)
ui.syn()

# Synthetic modifier release:
ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTCTRL, 0)
ui.write(ecodes.EV_KEY, ecodes.KEY_LEFTALT, 0)
ui.syn()

# Cleanup:
dev.ungrab()
ui.close()
dev.close()
```

### Verified: Gio.DBusConnection.register_object() signature
```python
# Source: verified with help(Gio.DBusConnection.register_object) locally
reg_id = conn.register_object(
    object_path: str,          # '/StatusNotifierItem'
    interface_info: Gio.DBusInterfaceInfo,  # from DBusNodeInfo.new_for_xml()
    method_call_closure,       # callable(conn, sender, path, iface, method, params, invocation)
    get_property_closure,      # callable(conn, sender, path, iface, prop_name) -> GLib.Variant
    set_property_closure,      # None (read-only properties)
) -> int  # registration ID for unregister_object()
```

### Verified: Waybar SNI watcher registration call
```python
# Source: verified live -- dbus-send introspection of org.kde.StatusNotifierWatcher
conn.call_sync(
    'org.kde.StatusNotifierWatcher',          # destination bus name
    '/StatusNotifierWatcher',                  # object path
    'org.kde.StatusNotifierWatcher',          # interface name
    'RegisterStatusNotifierItem',              # method name
    GLib.Variant('(s)', (sni_name,)),         # args: the service name
    None,                                      # reply_type (infer)
    Gio.DBusCallFlags.NONE,
    5000,                                      # timeout ms
    None,                                      # cancellable
)
```

### Verified: ecodes for new shortcuts
```python
# Source: verified locally via evdev.ecodes
KEY_LEFTCTRL  = 29  # ecodes.KEY_LEFTCTRL
KEY_LEFTALT   = 56  # ecodes.KEY_LEFTALT
KEY_SPACE     = 57  # ecodes.KEY_SPACE   (push-to-talk trigger)
KEY_K         = 37  # ecodes.KEY_K       (toggle start trigger)
KEY_L         = 38  # ecodes.KEY_L       (toggle stop trigger)
KEY_RIGHTCTRL = 97  # ecodes.KEY_RIGHTCTRL
KEY_RIGHTALT  = 100 # ecodes.KEY_RIGHTALT
```

### Verified: PyAudio output works under PipeWire
```python
# Source: tested locally — output: "PyAudio output: SUCCESS"
# Host API: ALSA (type=8), default output device: 'default', 64ch, 44100 Hz
# No PipeWire-specific workaround needed
import pyaudio, struct, math
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=44100, output=True)
stream.write(samples)
stream.stop_stream()
stream.close()
p.terminate()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pystray for Sway tray | Direct Gio.DBus SNI | Phase 4 | pystray has no SNI backend; direct D-Bus is required |
| Single hotkey binding | Multiple named bindings | Phase 4 | Enables separate push-to-talk + toggle-start + toggle-stop shortcuts |
| Final-only injection | Delta partial injection | Phase 4 | Text appears live during speech, not only on sentence completion |
| DEBUG-level audio errors | WARNING-level audio errors | Phase 4 | User can detect audio feedback failure without debug logging |

**Deprecated/outdated in this phase:**
- `HotkeyConfig.modifiers` / `.trigger` / `.mode` fields: replaced by `bindings` list (with migration path)
- `TrayIcon._appindicator_works()` no-op path on Sway: replaced by actual SNI implementation

## Open Questions

1. **Right-hand modifier support**
   - What we know: `KEY_RIGHTCTRL=97`, `KEY_RIGHTALT=100` exist in ecodes. The user uses `Ctrl+Alt+Space/K/L` with both hands.
   - What's unclear: Should each binding automatically match both left and right variants of Ctrl and Alt? This doubles the modifier set per binding.
   - Recommendation: Claude's Discretion — implement as an opt-in config field `match_right_modifiers: bool = False` or simply hard-code both left/right for the default bindings and let the user override via config.

2. **Partial injection when `format_turns=True` diverges**
   - What we know: AssemblyAI's `format_turns=True` runs a formatting pass on final turns (capitalization, punctuation). Partials are unformatted. The final text can differ significantly from the partial in casing.
   - What's unclear: When the final arrives and we backspace the partial + inject the final, the count of backspaces is `len(_last_partial)` characters. If the formatted final is longer, this is fine. If the partial had a different word count due to mid-stream revision, the backspace count could be off by a few characters.
   - Recommendation: On final, backspace `len(_last_partial)` characters and inject the final. Accept occasional off-by-one and let the user correct; this is significantly better than no partial injection at all.

3. **Config file migration for `bindings`**
   - What we know: Existing `~/.config/murmur/config.json` may have `{"hotkey": {"modifiers": [...], "trigger": "...", "mode": "..."}}`.
   - What's unclear: Is there a user with this config on disk who would be broken by the migration?
   - Recommendation: The only user is the developer (you). Add migration code in `DictationConfig._from_dict()` that reads old fields and constructs a `bindings` list from them if `bindings` is absent.

## Sources

### Primary (HIGH confidence)
- evdev Python library — installed in `.venv`, API verified via `help()` locally: `UInput`, `UInput.from_device()`, `InputDevice.grab()`, `InputDevice.ungrab()`, `UInput.write()`, `UInput.syn()`
- `gi.repository.Gio` — GLib 2.86.3 installed, API verified via `help()`: `DBusConnection.register_object()`, `bus_own_name()`, `DBusNodeInfo.new_for_xml()`
- D-Bus introspection of live `org.kde.StatusNotifierWatcher` (waybar) — `RegisterStatusNotifierItem(s)` method confirmed
- D-Bus introspection of live `org.kde.StatusNotifierItem-3880343-1` (test Python script) — full interface confirmed including `IconPixmap: a(iiay)` with ARGB32 big-endian byte format confirmed from `GetAll` response
- PyAudio output test — verified `stream.open(output=True)` succeeds on PipeWire/ALSA, `"PyAudio output: SUCCESS"`
- `/dev/uinput` access — verified writable (mode 0660 group=input, user is in `input` group); `/usr/lib/udev/rules.d/80-uinput.rules` already sets correct permissions (no new rule needed)
- Evdev keycodes: `KEY_LEFTCTRL=29`, `KEY_LEFTALT=56`, `KEY_SPACE=57`, `KEY_K=37`, `KEY_L=38` — verified via `ecodes.ecodes` dict

### Secondary (MEDIUM confidence)
- Existing murmur codebase analysis: `DictationApp._on_partial_transcript` currently only logs, confirming the gap; `AudioFeedback._play_tone` uses `logger.debug` for errors
- `/usr/lib/udev/rules.d/80-uinput.rules` content: `KERNEL=="uinput", GROUP="input", MODE="0660"` — already the right rule, no new udev rule needed

### Tertiary (LOW confidence)
- None — all critical claims verified locally or from live system inspection.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries installed and API-verified locally
- Architecture patterns: HIGH — grab-and-forward verified via UInput API; SNI registration verified via live D-Bus introspection; delta injection is pure Python string logic
- Pitfalls: HIGH for ghost modifier/SNI path (verified from spec + live system); MEDIUM for partial injection race (theoretical, based on code analysis)

**Research date:** 2026-02-18
**Valid until:** 2026-03-20 (stable APIs; evdev and Gio don't change frequently)
