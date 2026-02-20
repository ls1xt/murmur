# Phase 5: macOS Coding Support (Hotkey, Injector, Clipboard, Permissions) - Research

**Researched:** 2026-02-20
**Domain:** macOS Python keyboard/input control, pynput, subprocess clipboard, TCC permissions
**Confidence:** HIGH (core APIs), MEDIUM (ctrl+alt workaround), HIGH (permissions via pyobjc)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Backend abstraction**
- Introduce ABC (abstract base class) for hotkey listener and for text injector
- Existing Linux evdev and ydotool implementations become the Linux concrete classes
- New macOS concrete classes added alongside — no Linux code touched beyond the ABC extraction
- Factory functions in `hotkey/__init__.py` and `injector/__init__.py` dispatch on `sys.platform`
- Design must allow a future X11 backend to slot in without restructuring (i.e., don't hardcode only two platforms)

**macOS hotkey backend**
- Use `pynput.keyboard.Listener` for key event detection
- Key names in config stay as evdev format (`KEY_LEFTCTRL`, `KEY_SPACE`, etc.) — macOS backend translates them to pynput equivalents at runtime
- No key grabbing/suppression on macOS for now (evdev EVIOCGRAB is Linux-only; pynput has no equivalent)

**macOS text injection backend**
- Primary: `pynput.keyboard.Controller.type()` for direct typing
- Fallback: clipboard paste via `pbcopy` + Cmd+V keystroke (mirrors the Linux clipboard fallback tier)
- Same 3-tier structure as Linux where applicable: direct type → slow type → clipboard paste

**macOS clipboard**
- Use `pbcopy` / `pbpaste` subprocess calls (already available on all macOS versions)
- No new Python dependency needed

**macOS permissions**
- Check for Accessibility permission (required by pynput for keyboard monitoring) at daemon startup
- Check for Microphone permission (required for audio capture) at daemon startup
- Missing permission → fatal error with a clear, actionable message pointing to System Settings → Privacy
- Same pattern as the existing ydotoold startup check on Linux
- Use `pyobjc` or subprocess + `osascript` for detection — whichever requires no new mandatory dependency

**Linux compatibility**
- All existing Linux behavior unchanged after ABC extraction
- Existing evdev and ydotool classes simply implement the new ABCs
- No Linux user sees any behavioural difference

### Claude's Discretion
- Exact ABC method signatures and naming
- Whether permissions check uses pyobjc or osascript
- Key name translation table (evdev → pynput)
- Exact error message wording

### Deferred Ideas (OUT OF SCOPE)
- X11 hotkey/injector backend — explicitly future, not Phase 5
- Shell scripts, setup.sh Homebrew path, LaunchAgent plist — Phase 6
- macOS-specific tests for new backends — can be included in Phase 5 plans or Phase 6; planner to decide
- Notification backend for macOS (osascript / notify-send equivalent) — Phase 6 or later
</user_constraints>

---

## Summary

Phase 5 adds macOS runtime support by adding concrete pynput-based implementations alongside the existing Linux evdev/ydotool implementations. The ABCs already exist in the codebase (`murmur/hotkey/base.py`, `murmur/injector/base.py`) — this phase is purely additive. The two new files to write are `murmur/hotkey/pynput.py` and `murmur/injector/pynput.py`, plus updates to the two factory `__init__.py` files and a new `murmur/platform/macos.py` for permission checks.

The most significant technical discovery is that pynput's `GlobalHotKeys` and `HotKey` helpers do **not work reliably** with Ctrl+Alt modifiers on macOS (confirmed open bug: GitHub issue #297, unresolved as of Aug 2022). The workaround is to use a raw `keyboard.Listener` with manual modifier-state tracking in the `on_press`/`on_release` callbacks — mirroring what the evdev backend already does. This approach works reliably across all modifier combinations.

For permissions, the recommended approach is `from ApplicationServices import AXIsProcessTrusted` (provided by `pyobjc-framework-ApplicationServices`, which is a transitive dependency of many macOS Python packages). Since this is a conditional macOS-only import, no new mandatory dependency is added to Linux users. The microphone permission check is best done with `pyobjc-framework-AVFoundation`'s `AVCaptureDevice.authorizationStatusForMediaType_()`.

**Primary recommendation:** Implement the pynput backend with raw `Listener` + manual modifier tracking (not `GlobalHotKeys`). Use `pyobjc` frameworks for permission checks since they are already available in most macOS Python environments and avoid subprocess brittleness.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pynput | 1.8.1 (latest) | Keyboard listening and injection on macOS | Cross-platform, actively maintained, Quartz-based on macOS |
| pyobjc-framework-ApplicationServices | latest | `AXIsProcessTrusted()` for Accessibility check | Zero-dep approach — already present in most macOS Python envs |
| pbcopy / pbpaste | built-in macOS | Clipboard read/write via subprocess | Available on all macOS versions, no dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyobjc-framework-AVFoundation | latest | Microphone permission check via `AVCaptureDevice` | Optional: if pyobjc is available, use it; otherwise skip mic check |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pyobjc for permission check | osascript via subprocess | osascript returns errors with no easy distinction; pyobjc is cleaner but requires optional dep |
| pynput Controller.type() | applescript / osascript type | osascript requires more setup; pynput is already in the dependency |
| pynput GlobalHotKeys | raw Listener + manual tracking | GlobalHotKeys fails silently for Ctrl+Alt on macOS (see Critical Pitfall below) |

**Installation (macOS only):**
```bash
pip install pynput
# pyobjc-framework-ApplicationServices is typically available via Xcode CLI tools
# or can be added as a conditional dependency
```

**pyproject.toml additions:**
```toml
dependencies = [
    ...
    "pynput>=1.7.0; sys_platform == 'darwin'",
    "pyobjc-framework-ApplicationServices>=9.0; sys_platform == 'darwin'",
]
```

---

## Architecture Patterns

### Recommended Project Structure After Phase 5
```
murmur/
├── hotkey/
│   ├── __init__.py       # factory — updated to dispatch "darwin"
│   ├── base.py           # HotkeyListener ABC (unchanged)
│   ├── evdev.py          # Linux backend (unchanged)
│   └── pynput.py         # NEW: macOS backend
├── injector/
│   ├── __init__.py       # factory — updated to dispatch "darwin"
│   ├── base.py           # TextInjector ABC (unchanged)
│   ├── ydotool.py        # Linux backend (unchanged)
│   └── pynput.py         # NEW: macOS backend
└── platform/
    └── macos.py          # NEW: check_accessibility(), check_microphone()
```

The `platform/` subpackage is guarded at import time so `murmur/platform/macos.py` is only imported when `sys.platform == "darwin"`.

### Pattern 1: Raw Listener + Manual Modifier Set (the correct macOS hotkey approach)

**What:** Track pressed keys in a set inside `on_press`/`on_release` callbacks. When a key-down event fires, check whether the current held-key set matches any configured binding.

**When to use:** Always — do not use `GlobalHotKeys` or `HotKey` helpers for Ctrl+Alt combinations on macOS.

**Example:**
```python
# Source: pynput docs + GitHub issue #297 workaround
from pynput import keyboard

class PynputHotkeyListener(HotkeyListener):
    def __init__(self, bindings, push_to_talk_debounce_ms=300):
        super().__init__()
        self._bindings = _resolve_bindings(bindings)  # evdev names -> pynput Keys
        self._held: set[keyboard.Key | keyboard.KeyCode] = set()
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_press(self, key):
        canonical = self._listener.canonical(key) if self._listener else key
        self._held.add(canonical)
        for binding in self._bindings:
            if binding.trigger == canonical and binding.modifiers.issubset(self._held):
                self._dispatch_action(binding.action)

    def _on_release(self, key):
        canonical = self._listener.canonical(key) if self._listener else key
        for binding in self._bindings:
            if binding.trigger == canonical and binding.trigger in self._held:
                self._dispatch_release(binding.action)
        self._held.discard(canonical)
```

### Pattern 2: Evdev → pynput Key Name Translation

**What:** The config stores evdev key names (`KEY_LEFTCTRL`, `KEY_SPACE`, etc.). The pynput backend must translate these at `__init__` time to `pynput.keyboard.Key` enum values or `KeyCode` objects.

**Key translation table (evdev → pynput.keyboard.Key):**
```python
# Source: pynput docs (Key enum) + evdev ecodes cross-reference
_EVDEV_TO_PYNPUT: dict[str, keyboard.Key | keyboard.KeyCode] = {
    # Modifiers
    "KEY_LEFTCTRL":  keyboard.Key.ctrl_l,
    "KEY_RIGHTCTRL": keyboard.Key.ctrl_r,
    "KEY_LEFTALT":   keyboard.Key.alt_l,
    "KEY_RIGHTALT":  keyboard.Key.alt_r,
    "KEY_LEFTSHIFT": keyboard.Key.shift_l,
    "KEY_RIGHTSHIFT":keyboard.Key.shift_r,
    "KEY_LEFTMETA":  keyboard.Key.cmd_l,
    "KEY_RIGHTMETA": keyboard.Key.cmd_r,
    # Common keys
    "KEY_SPACE":     keyboard.Key.space,
    "KEY_ENTER":     keyboard.Key.enter,
    "KEY_BACKSPACE": keyboard.Key.backspace,
    "KEY_ESC":       keyboard.Key.esc,
    "KEY_TAB":       keyboard.Key.tab,
    "KEY_DELETE":    keyboard.Key.delete,
    # Alphanumeric: KEY_A..KEY_Z, KEY_0..KEY_9 -> KeyCode.from_char('a'..'z', '0'..'9')
}

def _evdev_to_pynput(name: str) -> keyboard.Key | keyboard.KeyCode:
    if name in _EVDEV_TO_PYNPUT:
        return _EVDEV_TO_PYNPUT[name]
    # Handle KEY_A .. KEY_Z, KEY_0 .. KEY_9
    if name.startswith("KEY_") and len(name) == 5:
        char = name[4].lower()
        return keyboard.KeyCode.from_char(char)
    raise ValueError(f"Cannot translate evdev key name to pynput: {name!r}")
```

**Important:** Use `listener.canonical(key)` to normalize left/right variants before set membership tests. `canonical(Key.ctrl_l)` returns `Key.ctrl`, unifying left/right. Store translated binding modifiers as the generic form (e.g., `Key.ctrl`, `Key.alt`) OR use the canonical form returned by `listener.canonical()` — be consistent.

**Recommendation:** Store modifier sets in the binding as the canonical pynput Keys (`Key.ctrl`, `Key.alt`, etc.) which are what `listener.canonical()` returns. Map `KEY_LEFTCTRL` → `Key.ctrl`, `KEY_LEFTALT` → `Key.alt` (use generic forms in the canonical set).

Updated canonical mapping:
```python
_EVDEV_TO_PYNPUT_CANONICAL: dict[str, keyboard.Key | keyboard.KeyCode] = {
    "KEY_LEFTCTRL":  keyboard.Key.ctrl,   # canonical form
    "KEY_RIGHTCTRL": keyboard.Key.ctrl,
    "KEY_LEFTALT":   keyboard.Key.alt,    # canonical form
    "KEY_RIGHTALT":  keyboard.Key.alt,
    "KEY_LEFTSHIFT": keyboard.Key.shift,
    "KEY_RIGHTSHIFT":keyboard.Key.shift,
    "KEY_LEFTMETA":  keyboard.Key.cmd,
    "KEY_RIGHTMETA": keyboard.Key.cmd,
    "KEY_SPACE":     keyboard.Key.space,
    "KEY_ENTER":     keyboard.Key.enter,
    "KEY_BACKSPACE": keyboard.Key.backspace,
    "KEY_ESC":       keyboard.Key.esc,
    "KEY_TAB":       keyboard.Key.tab,
    ...
}
```

### Pattern 3: pynput Controller for Text Injection

**What:** `pynput.keyboard.Controller.type(text)` types a full Unicode string. `Controller.press(Key.backspace)` + `Controller.release(Key.backspace)` sends a backspace.

**Example:**
```python
# Source: pynput official docs
from pynput import keyboard

class PynputInjector(TextInjector):
    def __init__(self, trailing_space=True, inject_strategy="pynput"):
        self._controller = keyboard.Controller()
        self._trailing_space = trailing_space
        self._inject_strategy = inject_strategy

    def inject(self, text: str) -> None:
        text = _sanitize_text(text)
        if self._trailing_space:
            text = text + " "
        if self._inject_strategy == "clipboard":
            self._inject_via_clipboard(text)
        elif self._inject_strategy == "clipboard-fallback":
            if text.isascii():
                self._controller.type(text)
            else:
                self._inject_via_clipboard(text)
        else:
            self._controller.type(text)

    def inject_backspaces(self, count: int) -> None:
        for _ in range(count):
            self._controller.press(keyboard.Key.backspace)
            self._controller.release(keyboard.Key.backspace)

    def _inject_via_clipboard(self, text: str) -> None:
        # pbcopy writes text to clipboard, then simulate Cmd+V
        proc = subprocess.run(
            ["pbcopy"],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=5,
        )
        if proc.returncode != 0:
            logger.error("pbcopy failed")
            return
        # Cmd+V paste
        with self._controller.pressed(keyboard.Key.cmd):
            self._controller.tap(keyboard.KeyCode.from_char("v"))
```

### Pattern 4: macOS Permission Check

**What:** Check Accessibility (for pynput keyboard monitoring) and optionally Microphone (for audio capture) at startup. Exit with a clear message if missing.

**Accessibility check (pyobjc — preferred):**
```python
# Source: https://github.com/ActivityWatch/aw-watcher-window/commit/82e90b2
# Requires: pyobjc-framework-ApplicationServices (conda/pip on macOS)
def check_accessibility() -> bool:
    """Return True if this process has Accessibility permission."""
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except ImportError:
        # pyobjc not available — cannot check, assume OK and let pynput fail
        return True
```

**Accessibility check (fallback: subprocess osascript — less reliable):**
```python
# osascript can itself fail if the terminal running it lacks accessibility
# This approach is fragile; prefer pyobjc when available
def _check_accessibility_osascript() -> bool:
    result = subprocess.run(
        ["osascript", "-e", 'tell application "System Events" to return true'],
        capture_output=True, timeout=5,
    )
    return result.returncode == 0
```

**Recommendation:** Use pyobjc `AXIsProcessTrusted()` as primary, with a graceful `ImportError` fallback (log a warning, continue). Do not hard-fail on missing pyobjc.

**Microphone check (pyobjc — AVFoundation):**
```python
def check_microphone() -> bool:
    """Return True if this process has Microphone permission."""
    try:
        import AVFoundation
        status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
            AVFoundation.AVMediaTypeAudio
        )
        # 0=notDetermined, 1=restricted, 2=denied, 3=authorized
        return int(status) == 3
    except ImportError:
        return True  # cannot check; let PyAudio fail at runtime
```

**Startup integration in main.py (macOS path):**
```python
# In DictationApp.run() or a new check_platform_permissions() helper
if sys.platform == "darwin":
    from murmur.platform.macos import check_accessibility, check_microphone
    if not check_accessibility():
        fatal(
            "Accessibility permission required.\n"
            "Go to System Settings → Privacy & Security → Accessibility\n"
            "and enable Terminal (or your Python interpreter)."
        )
    if not check_microphone():
        fatal(
            "Microphone permission required.\n"
            "Go to System Settings → Privacy & Security → Microphone\n"
            "and enable Terminal (or your Python interpreter)."
        )
```

### Pattern 5: Factory `__init__.py` Extension (Extensible for Future X11)

**What:** Update both factory functions to handle `"darwin"` without hardcoding a two-platform assumption. The `"pynput"` backend name covers both macOS and any future X11 usage.

**Example (hotkey factory):**
```python
def create_hotkey_listener(config: HotkeyConfig) -> HotkeyListener:
    match config.backend:
        case "evdev":
            from murmur.hotkey.evdev import EvdevHotkeyListener
            return EvdevHotkeyListener(...)
        case "pynput":
            from murmur.hotkey.pynput import PynputHotkeyListener
            return PynputHotkeyListener(...)
        case "auto":
            if sys.platform == "linux":
                from murmur.hotkey.evdev import EvdevHotkeyListener
                return EvdevHotkeyListener(...)
            elif sys.platform == "darwin":
                from murmur.hotkey.pynput import PynputHotkeyListener
                return PynputHotkeyListener(...)
            raise RuntimeError(f"No hotkey backend available for {sys.platform}")
        case _:
            raise ValueError(f"Unknown hotkey backend: {config.backend!r}")
```

The `"auto"` arm grows one `elif` per new platform; the `"pynput"` explicit arm handles X11 in the future without any factory change.

### Anti-Patterns to Avoid
- **Using `GlobalHotKeys` or `HotKey.parse()` for Ctrl+Alt bindings on macOS:** These fail silently. Use raw `Listener` + manual set tracking.
- **Suppressing events on macOS:** Not required by the decision (and requires `darwin_intercept` + Quartz, adding complexity). Skip suppression entirely.
- **Importing pynput at module level in shared code:** Gate the import inside the class or factory function so Linux users never touch it.
- **Hard-failing when pyobjc is missing:** pyobjc availability varies; log a warning and continue if the permission check library is absent.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Typing Unicode text on macOS | Custom Quartz CGEventPost sequence | `pynput.keyboard.Controller.type()` | type() handles all Unicode, deadkeys, modifier state automatically |
| Clipboard write on macOS | Pasteboard API via ctypes | `pbcopy` subprocess | pbcopy is available on all macOS, zero dependency |
| Accessibility permission check | TCC database SQL query | `AXIsProcessTrusted()` (pyobjc) | TCC database path changes between macOS versions; public API is stable |
| Modifier state normalization | Custom left/right key mapping | `listener.canonical(key)` | pynput canonical() handles platform-specific left/right key unification |

**Key insight:** The macOS keyboard event API (Quartz CGEvent) is significantly more complex than evdev. pynput already wraps it correctly. Do not bypass it.

---

## Common Pitfalls

### Pitfall 1: GlobalHotKeys Silent Failure for Ctrl+Alt on macOS
**What goes wrong:** `keyboard.GlobalHotKeys({'<ctrl>+<alt>+<space>': callback})` registers without error but never fires. The callback is never invoked for Ctrl+Alt combinations.
**Why it happens:** macOS transforms the Unicode representation of key events when Ctrl or Alt are held (e.g., Ctrl+K produces `\x0b`, Alt+K produces `˚`). pynput's GlobalHotKeys uses character matching internally and fails to match.
**How to avoid:** Use raw `keyboard.Listener(on_press=..., on_release=...)` with a manual `set` tracking held keys.
**Warning signs:** Hotkeys with `cmd` or `shift` work fine; hotkeys with `ctrl` or `alt` are silent.
**Source:** GitHub issue #297 (open as of Aug 2022, unresolved as of pynput 1.8.1)

### Pitfall 2: Listener Cannot Be Restarted After stop()
**What goes wrong:** Calling `listener.stop()` then `listener.start()` again raises an error or silently does nothing.
**Why it happens:** pynput Listener inherits from `threading.Thread`; once stopped, the thread is consumed.
**How to avoid:** In `PynputHotkeyListener.start()`, always create a fresh `keyboard.Listener` instance. In `stop()`, set `self._listener = None`.
**Warning signs:** Second call to `hotkey.start()` has no effect.

### Pitfall 3: pynput Requires Accessibility Permission Before First Use
**What goes wrong:** On macOS, pynput's `keyboard.Listener` silently does nothing (no events fire) if the running process lacks Accessibility permission.
**Why it happens:** macOS enforces TCC (Transparency, Consent, and Control) for keyboard monitoring. The permission prompt appears when the process first attempts to create a global event tap.
**How to avoid:** Check `AXIsProcessTrusted()` at startup before creating the listener. Fatal-exit with instructions if not granted.
**Warning signs:** Listener starts without error, no callbacks fire, no exception raised.

### Pitfall 4: pbcopy Blocks on stdin by Default
**What goes wrong:** `subprocess.Popen(['pbcopy'])` waits for stdin forever if `.communicate()` is not called.
**Why it happens:** pbcopy reads from stdin until EOF.
**How to avoid:** Use `subprocess.run(['pbcopy'], input=text.encode('utf-8'), ...)` which pipes the input and closes stdin automatically.

### Pitfall 5: Canonical Key Form Must Match Binding Translation
**What goes wrong:** Binding stores `Key.ctrl_l` (left-specific) but `listener.canonical()` returns `Key.ctrl` (generic). Set membership check fails even when Ctrl is held.
**Why it happens:** pynput normalizes left/right modifier keys in `canonical()` to their generic form.
**How to avoid:** The translation table (`_EVDEV_TO_PYNPUT_CANONICAL`) must map `KEY_LEFTCTRL` and `KEY_RIGHTCTRL` both to `Key.ctrl` (generic). Always call `listener.canonical(key)` before adding to the held-key set.

### Pitfall 6: Controller.type() Fails for Control Characters
**What goes wrong:** Injecting text containing `\n`, `\t`, or other control characters via `Controller.type()` sends the actual control sequence, not a literal character — potentially submitting a terminal command.
**Why it happens:** pynput translates control characters to their key equivalents.
**How to avoid:** Apply `_sanitize_text()` (already in ydotool.py) before calling `Controller.type()`. Reuse the same sanitizer in the pynput injector.

### Pitfall 7: pyobjc Framework Import Naming
**What goes wrong:** `import ApplicationServices` works, but `import pyobjc_framework_ApplicationServices` does not. The package is installed as `pyobjc-framework-ApplicationServices` but imported as `ApplicationServices`.
**Why it happens:** pyobjc framework packages use the macOS framework name as the import name, not the pip package name.
**How to avoid:** Use `from ApplicationServices import AXIsProcessTrusted` (not `from pyobjc_framework_ApplicationServices import ...`).

---

## Code Examples

### Verified: pynput Listener start/stop lifecycle
```python
# Source: https://pynput.readthedocs.io/en/latest/keyboard.html
from pynput import keyboard

listener = keyboard.Listener(
    on_press=lambda key: print(f'pressed: {key}'),
    on_release=lambda key: print(f'released: {key}'),
)
listener.start()
# ... do other work ...
listener.stop()
# To restart: create a new instance
```

### Verified: pynput Controller.type() and backspace
```python
# Source: https://pynput.readthedocs.io/en/latest/keyboard.html
from pynput import keyboard

controller = keyboard.Controller()
controller.type("Hello, World!")  # types full string

# Backspace one character
controller.press(keyboard.Key.backspace)
controller.release(keyboard.Key.backspace)
```

### Verified: pbcopy via subprocess
```python
# Source: standard macOS subprocess pattern, verified against multiple sources
import subprocess

def pbcopy(text: str) -> None:
    subprocess.run(
        ["pbcopy"],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=5,
        check=True,
    )

def pbpaste() -> str:
    result = subprocess.run(
        ["pbpaste"],
        capture_output=True,
        timeout=5,
        check=True,
    )
    return result.stdout.decode("utf-8")
```

### Verified: AXIsProcessTrusted check
```python
# Source: https://github.com/ActivityWatch/aw-watcher-window/commit/82e90b2
# Source: https://developer.apple.com/documentation/applicationservices/1460720-axisprocesstrusted
try:
    from ApplicationServices import AXIsProcessTrusted
    trusted: bool = bool(AXIsProcessTrusted())
except ImportError:
    trusted = True  # cannot check without pyobjc
```

### Verified: manual modifier tracking hotkey pattern (working Ctrl+Alt workaround)
```python
# Source: GitHub pynput issue #297 workaround (community-verified)
from pynput import keyboard

held: set = set()

def on_press(key):
    held.add(listener.canonical(key))
    # Check bindings:
    if (keyboard.Key.ctrl in held
            and keyboard.Key.alt in held
            and keyboard.Key.space in held):
        print("Ctrl+Alt+Space fired!")

def on_release(key):
    held.discard(listener.canonical(key))

listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pynput 1.7.x | pynput 1.8.1 (March 2025) | pynput 1.8.0 | 1.8.0 adds ability to detect injected events; no breaking changes |
| GlobalHotKeys for Ctrl+Alt | Raw Listener + manual set | Bug since early pynput on macOS, unresolved | Must use manual tracking for our bindings |
| osascript for permission checks | pyobjc AXIsProcessTrusted | N/A | pyobjc is cleaner; osascript approach is fragile |

**Deprecated/outdated:**
- `pynput.keyboard.HotKey` with `parse('<ctrl>+<alt>+...')`: Do not use for Ctrl+Alt on macOS — silent failure.
- Global `suppress=True` on Listener: Not needed by the design decision; adds Quartz complexity.

---

## Existing Codebase: What Already Exists

The following files are fully implemented and **must not be modified** (beyond adding ABC inheritance markers, which are already there):

| File | Status | Notes |
|------|--------|-------|
| `murmur/hotkey/base.py` | Complete | `HotkeyListener` ABC with `start()`, `stop()`, `set_callbacks()`, `_dispatch_action()`, `_dispatch_release()` |
| `murmur/injector/base.py` | Complete | `TextInjector` ABC with `inject()`, `inject_raw()`, `inject_backspaces()`, `is_available()`, `copy_to_clipboard()` |
| `murmur/hotkey/evdev.py` | Complete | Already subclasses `HotkeyListener`, no changes needed |
| `murmur/injector/ydotool.py` | Complete | Already subclasses `TextInjector`, no changes needed |
| `murmur/hotkey/__init__.py` | Needs update | Add `"pynput"` case and `darwin` auto-dispatch |
| `murmur/injector/__init__.py` | Needs update | Add `"pynput"` case and `darwin` auto-dispatch |
| `murmur/main.py` | Needs update | Add macOS permission check before `self.hotkey.start()` |
| `murmur/config.py` | Needs update | Document `"pynput"` as valid backend value (default stays `"auto"`) |
| `pyproject.toml` | Needs update | Add `pynput` and `pyobjc-framework-ApplicationServices` as conditional deps |

**New files to create:**
- `murmur/hotkey/pynput.py` — `PynputHotkeyListener(HotkeyListener)`
- `murmur/injector/pynput.py` — `PynputInjector(TextInjector)`
- `murmur/platform/__init__.py` — empty
- `murmur/platform/macos.py` — `check_accessibility()`, `check_microphone()`

---

## `is_available()` Implementation for macOS

The Linux injector's `is_available()` checks for ydotoold running. The macOS pynput injector's `is_available()` should check Accessibility permission instead (since pynput does not need a daemon):

```python
def is_available(self) -> bool:
    """On macOS, availability means Accessibility permission is granted."""
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except ImportError:
        return True  # cannot verify; assume available
```

**Note:** The startup check in `main.py` currently calls `self.injector.is_available()` and emits a hard-coded ydotool error message. This must be updated to call the platform-appropriate check or delegate to the injector's own message.

---

## Open Questions

1. **pynput dependency on Linux**
   - What we know: `evdev` is already conditional (`sys_platform == 'linux'`). pynput also runs on Linux (uses Xorg backend there), but we don't want Linux users to get pynput installed.
   - What's unclear: Should pynput be a `darwin`-only dep or unconditional? If unconditional, Linux users get it but it won't be used.
   - Recommendation: Make it `sys_platform == 'darwin'` conditional in pyproject.toml to keep Linux installs clean.

2. **Microphone permission check timing**
   - What we know: `AVCaptureDevice.authorizationStatusForMediaType_` may return `notDetermined` (0) on first run, meaning PyAudio will trigger the system permission dialog itself.
   - What's unclear: Should we proactively request authorization (which shows the dialog) or just check status and advise?
   - Recommendation: Check status only. If `notDetermined`, log a warning but don't fatal-exit — let PyAudio trigger the dialog naturally on first use. Fatal-exit only if `denied` (2) or `restricted` (1).

3. **`inject_strategy` naming for macOS**
   - What we know: Linux injector has strategies `"ydotool"`, `"clipboard"`, `"clipboard-fallback"`. macOS should have `"pynput"`, `"clipboard"`, `"clipboard-fallback"`.
   - What's unclear: Should `InjectorConfig.inject_strategy` default remain `"clipboard-fallback"` on macOS, or should `"pynput"` be the default?
   - Recommendation: Keep `"clipboard-fallback"` as default. On macOS, this means: pynput type for ASCII, pbcopy+Cmd+V for non-ASCII. This mirrors the Linux behavior.

---

## Sources

### Primary (HIGH confidence)
- [pynput docs — Handling the keyboard](https://pynput.readthedocs.io/en/latest/keyboard.html) — Listener API, Controller API, Key enum
- [pynput source — `_base.py` module](https://pynput.readthedocs.io/en/latest/_modules/pynput/keyboard/_base.html) — Key enum values
- [pynput source — `_darwin.py`](https://github.com/moses-palmer/pynput/blob/master/lib/pynput/keyboard/_darwin.py) — macOS Quartz implementation, Controller._handle
- [Apple Developer: AXIsProcessTrusted](https://developer.apple.com/documentation/applicationservices/1460720-axisprocesstrusted) — Accessibility permission check API
- [ActivityWatch aw-watcher-window commit 82e90b2](https://github.com/ActivityWatch/aw-watcher-window/commit/82e90b2) — Real-world pyobjc permission check example

### Secondary (MEDIUM confidence)
- [pynput issue #297](https://github.com/moses-palmer/pynput/issues/389) — GlobalHotKeys Ctrl+Alt failure on macOS (confirmed open bug)
- [pynput issue #389](https://github.com/moses-palmer/pynput/issues/389) — Silent failure without Accessibility permission; IS_TRUSTED flag added to Listener
- [pynput FAQ](https://pynput.readthedocs.io/en/latest/faq.html) — darwin_intercept suppression, packaging notes
- [pyobjc-framework-ApplicationServices PyPI](https://pypi.org/project/pyobjc-framework-ApplicationServices/) — Package name for AXIsProcessTrusted

### Tertiary (LOW confidence)
- Various WebSearch results on macOS Microphone permission check via AVFoundation — architecture confirmed but exact Python binding call not directly verified against running code

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pynput is the only viable option; pbcopy is built-in macOS; versions confirmed via PyPI
- Architecture: HIGH — codebase already has ABCs in place; pattern follows existing evdev structure
- pynput Ctrl+Alt workaround: MEDIUM — GitHub issue is open, community workaround is manual tracking; confirmed as working pattern by multiple sources but not an official pynput fix
- Pitfalls: HIGH for #1 (GlobalHotKeys), #2 (Listener non-restartable), #3 (Accessibility silent fail), #4 (pbcopy stdin), #5 (canonical key form)
- Permission check via pyobjc: MEDIUM-HIGH — API is official Apple, Python binding via pyobjc is established pattern

**Research date:** 2026-02-20
**Valid until:** 2026-08-20 (pynput 1.x API is stable; macOS TCC API is stable)
