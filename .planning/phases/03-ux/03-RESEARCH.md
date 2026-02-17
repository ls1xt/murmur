# Phase 3: UX - Research

**Researched:** 2026-02-17
**Domain:** System tray icons and desktop notifications on Linux (Sway + GNOME)
**Confidence:** MEDIUM

## Summary

Phase 3 adds visual state feedback to the murmur daemon via a system tray icon and desktop notifications. The primary challenge is cross-environment compatibility: Sway uses the StatusNotifierItem (SNI) protocol via swaybar, while GNOME requires AppIndicator extensions or falls back to GTK. pystray is the standard Python library for system tray icons and supports both backends, but requires careful handling: its `run()` is blocking, so it must run in a dedicated thread (murmur is already thread-based). Icons must be PIL Images -- emoji-style icons will be rendered as text onto PIL images using ImageDraw + a bundled font.

For notifications, the decision to shell out to `notify-send` is well-supported. The `--urgency=critical` flag makes notifications persistent on mako (Sway) and most GNOME notification daemons. The existing `errors.py` already has a `_notify()` function that calls `notify-send --urgency=critical`, which can be extracted and extended for the configurable verbosity levels.

**Primary recommendation:** Use pystray with AppIndicator backend (preferred) + GTK fallback. Run the tray icon loop in a daemon thread. Render emoji characters onto 64x64 PIL images. Extract and extend the existing `_notify()` from errors.py into a notification module with configurable verbosity.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Tray icon states: emoji-style icons (not monochrome symbolic, not colored traditional). Different emoji per state: idle, recording, error. Error state persistent. No animation.
- Notification verbosity configurable via CLI flag: `--notify off|errors|verbose`. Default: errors. Error notifications persistent, informational auto-expire.
- Tray menu: left-click = right-click = context menu. Minimal menu: status line + Quit. Quit is immediate.
- Sway & GNOME: both first-class. Tray failure = log warning + continue. Notifications via notify-send (shell out). Tray absence does not block daemon.

### Claude's Discretion
- Specific emoji choice per state
- Tray library selection (pystray, etc.)
- notify-send flag usage for persistence vs auto-expire
- Exact notification message wording
- Error state recovery detection

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UX-01 | System tray icon shows recording state (idle/recording/error) with graceful degradation when AppIndicator unavailable | pystray supports AppIndicator + GTK + XOrg backends with try/except fallback; PIL ImageDraw renders emoji onto tray icons |
| UX-02 | Desktop notifications on errors via D-Bus with notify-send fallback | Existing `_notify()` in errors.py already shells out to notify-send; extend with verbosity levels and persistence control |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pystray | 0.19.5 | System tray icon | Only mature cross-platform Python tray library; supports AppIndicator (SNI), GTK, XOrg backends on Linux |
| Pillow (PIL) | >=10.0 | Icon image generation | Required by pystray for icon images; already widely used; renders text/emoji onto images |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| notify-send | system | Desktop notifications | Already on user's system (libnotify); shells out from subprocess |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pystray | dbus-python + SNI protocol | Direct SNI would be more correct for Sway but massive implementation effort; pystray handles it |
| pystray | gi.repository (raw GTK) | More control but platform-specific; pystray abstracts backends |
| Pillow text rendering | Pre-rendered PNG files | Simpler but less flexible; Pillow allows dynamic generation and text/emoji rendering at any size |

**Installation:**
```bash
pip install pystray Pillow
```

**pyproject.toml addition:**
```toml
dependencies = [
    ...,
    "pystray>=0.19.5",
    "Pillow>=10.0.0",
]
```

## Architecture Patterns

### Recommended Module Structure
```
murmur/
├── feedback/
│   ├── __init__.py       # exports AudioFeedback, TrayIcon, Notifier
│   ├── audio.py          # existing audio feedback
│   ├── tray.py           # NEW: system tray icon management
│   └── notify.py         # NEW: desktop notification management
```

### Pattern 1: Threaded Tray Icon
**What:** Run pystray's blocking `icon.run()` in a daemon thread, communicate state changes via thread-safe methods.
**When to use:** Always -- murmur uses threading, not asyncio. pystray's `run()` blocks.
**Example:**
```python
import threading
import pystray
from PIL import Image, ImageDraw, ImageFont

class TrayIcon:
    def __init__(self) -> None:
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None
        self._state = "idle"

    def start(self) -> None:
        """Start tray icon in background thread. Non-blocking."""
        self._icon = pystray.Icon(
            "murmur",
            icon=self._create_icon("idle"),
            title="Murmur - Idle",
            menu=pystray.Menu(
                pystray.MenuItem("Idle", None, enabled=False),
                pystray.MenuItem("Quit", self._on_quit),
            ),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def set_state(self, state: str) -> None:
        """Update icon state. Thread-safe."""
        self._state = state
        if self._icon:
            self._icon.icon = self._create_icon(state)
            self._icon.title = f"Murmur - {state.capitalize()}"
            self._icon.update_menu()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
```

### Pattern 2: Graceful Tray Failure
**What:** Wrap tray initialization in try/except, log warning on failure, continue without tray.
**When to use:** Always -- tray icon is optional, daemon must work without it.
**Example:**
```python
def start(self) -> None:
    try:
        import pystray  # late import -- optional dependency
        self._icon = pystray.Icon(...)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
    except Exception as e:
        import sys
        print(f"murmur: tray icon unavailable: {e}", file=sys.stderr)
        self._icon = None
```

### Pattern 3: Configurable Notification Verbosity
**What:** Notification module respects `--notify off|errors|verbose` flag.
**Example:**
```python
class Notifier:
    def __init__(self, level: str = "errors") -> None:
        self._level = level  # "off", "errors", "verbose"

    def error(self, message: str) -> None:
        if self._level == "off":
            return
        self._send(message, urgency="critical")

    def info(self, message: str) -> None:
        if self._level != "verbose":
            return
        self._send(message, urgency="normal")

    def _send(self, message: str, urgency: str = "normal") -> None:
        subprocess.run(
            ["notify-send", f"--urgency={urgency}", "Murmur", message],
            timeout=5, capture_output=True,
        )
```

### Anti-Patterns to Avoid
- **Running pystray in main thread:** Blocks the entire daemon. Must use daemon thread.
- **Using `run_detached()`:** Only strictly needed on macOS. On Linux, a plain daemon thread with `run()` is simpler and more reliable.
- **Direct D-Bus for notifications:** User decision locks notify-send (shell out). D-Bus is more complex and fragile across environments.
- **Hardcoded icon files:** User wants emoji-style. Rendering with PIL is more maintainable than shipping icon files.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| System tray icon | Custom D-Bus SNI client | pystray | SNI protocol is complex; pystray handles AppIndicator/GTK/XOrg |
| Icon rendering | Custom bitmap generation | Pillow ImageDraw.text() | Font rendering, anti-aliasing, sizing handled correctly |
| Desktop notifications | Custom D-Bus org.freedesktop.Notifications | subprocess + notify-send | User decision; simpler, works everywhere |

## Common Pitfalls

### Pitfall 1: pystray Icon Not Visible on GNOME
**What goes wrong:** GTK backend creates icon but GNOME Shell hides legacy tray icons.
**Why it happens:** GNOME removed StatusIcon support; needs AppIndicator extension.
**How to avoid:** Use AppIndicator backend (install `libappindicator3-1` or `libayatana-appindicator3-1`). Document in README. If neither AppIndicator nor GTK works, log warning and continue.
**Warning signs:** Icon object runs without error but nothing appears in tray.

### Pitfall 2: pystray Blocking Main Thread
**What goes wrong:** `icon.run()` never returns, daemon hangs.
**Why it happens:** `run()` is intentionally blocking.
**How to avoid:** Always run in a daemon thread. Never call from main thread.

### Pitfall 3: Thread Safety with Icon Updates
**What goes wrong:** Updating icon image or menu from another thread causes race conditions.
**Why it happens:** pystray's internal state isn't fully thread-safe on all backends.
**How to avoid:** Use `icon.icon = new_image` (property setter handles backend update). Call `update_menu()` after menu state changes. Keep updates minimal and atomic.

### Pitfall 4: notify-send Not Installed
**What goes wrong:** `FileNotFoundError` when shelling out.
**Why it happens:** notify-send (libnotify-bin) not installed.
**How to avoid:** Already handled in existing `_notify()` with `contextlib.suppress(FileNotFoundError)`. Maintain this pattern.

### Pitfall 5: Emoji Rendering in Tray Icons
**What goes wrong:** Emoji characters don't render or render as boxes in PIL.
**Why it happens:** Default PIL font doesn't include emoji glyphs.
**How to avoid:** Use a bundled emoji-capable font (e.g., Noto Emoji) or render simple geometric shapes/text with standard fonts. Alternative: use colored Unicode characters that are in standard fonts (like colored circles: red/green/yellow) drawn with ImageDraw shapes rather than actual emoji glyphs.
**Recommendation:** Draw simple colored shapes (circles, squares) with text labels rather than actual emoji characters. This is more reliable across systems and doesn't require font bundling.

## Code Examples

### Creating Emoji-Style Tray Icons with PIL
```python
from PIL import Image, ImageDraw

ICON_SIZE = 64

def create_tray_icon(state: str) -> Image.Image:
    """Create a tray icon for the given state."""
    colors = {
        "idle": ("#444444", "#888888"),      # gray
        "recording": ("#cc0000", "#ff3333"),  # red
        "error": ("#cc6600", "#ff9933"),      # orange/amber
    }
    bg, fg = colors.get(state, colors["idle"])

    img = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw filled circle
    margin = 4
    draw.ellipse(
        [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
        fill=fg, outline=bg, width=2,
    )

    return img
```

### Integrating Tray with DictationApp
```python
# In main.py DictationApp.__init__:
self.tray = TrayIcon()

# In run():
self.tray.start()  # non-blocking, daemon thread

# In _on_activate:
self.tray.set_state("recording")

# In _on_deactivate:
self.tray.set_state("idle")

# In shutdown:
self.tray.stop()
```

### Notification with Persistence Control
```python
import contextlib
import subprocess

def send_notification(
    message: str,
    urgency: str = "normal",
    expire_ms: int | None = None,
) -> None:
    """Send desktop notification via notify-send."""
    cmd = ["notify-send", f"--urgency={urgency}", "Murmur", message]
    if expire_ms is not None:
        cmd.insert(-2, f"--expire-time={expire_ms}")
    with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
        subprocess.run(cmd, timeout=5, capture_output=True)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| GTK StatusIcon | StatusNotifierItem (SNI) / AppIndicator | GNOME 3.26 (2017) | Old StatusIcon deprecated; use AppIndicator or SNI |
| XEmbed tray protocol | SNI on Wayland compositors | Sway 1.0+ | XEmbed doesn't exist on Wayland; swaybar supports SNI |
| Direct D-Bus notifications | notify-send (libnotify) | Stable for years | notify-send is the standard CLI interface |

**Deprecated/outdated:**
- GTK StatusIcon: Deprecated since GTK 3.14, removed in GTK 4. pystray's AppIndicator backend is the replacement.
- XEmbed system tray: Not available on Wayland. Sway only supports SNI.

## Open Questions

1. **AppIndicator availability on user's GNOME setup**
   - What we know: GNOME needs `gnome-shell-extension-appindicator` or similar for tray icons
   - What's unclear: Whether user has this installed; whether stock GNOME shows icons
   - Recommendation: Graceful degradation (requirement SC-3 mandates this). Log warning, continue without tray.

2. **PIL emoji font rendering reliability**
   - What we know: Default PIL font lacks emoji. Bundling a font adds complexity.
   - What's unclear: Whether simple geometric shapes satisfy "emoji-style" requirement
   - Recommendation: Use colored geometric shapes (circles with state indicators). If user wants literal emoji characters, would need to bundle Noto Color Emoji font (~10MB). Start with shapes, iterate if needed.

## Sources

### Primary (HIGH confidence)
- [pystray official docs - Usage](https://pystray.readthedocs.io/en/latest/usage.html) - API, run(), run_detached(), icon creation
- [pystray official docs - Reference](https://pystray.readthedocs.io/en/latest/reference.html) - Full API: Icon, MenuItem, Menu classes
- [pystray official docs - FAQ](https://pystray.readthedocs.io/en/latest/faq.html) - Linux virtualenv, AppIndicator requirements, run_detached behavior

### Secondary (MEDIUM confidence)
- [pystray PyPI](https://pypi.org/project/pystray/) - Version 0.19.5, platform support
- [mako GitHub](https://github.com/emersion/mako) - Wayland notification daemon, urgency handling
- [ArchWiki Desktop notifications](https://wiki.archlinux.org/title/Desktop_notifications) - notify-send usage, FreeDesktop spec

### Tertiary (LOW confidence)
- Arch Linux forums on Sway system tray - Community reports on SNI support in swaybar

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - pystray is well-documented but Wayland/Sway support has gaps in docs; real testing needed
- Architecture: HIGH - Threading pattern is well-established; murmur already uses threads
- Pitfalls: MEDIUM - Known issues documented in pystray issues/FAQ; Wayland edge cases may surface during implementation

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (30 days -- stable domain, libraries don't change frequently)
