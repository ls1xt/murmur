# Phase 2: Reliability - Research

**Researched:** 2026-02-17
**Domain:** Error handling, fail-fast exit patterns, text injection fallback
**Confidence:** HIGH

## Summary

Phase 2 transforms murmur from a happy-path prototype into a tool that fails cleanly. The user's design philosophy is KISS: on any error, exit immediately with a clear message to both stderr and desktop notification via `notify-send`. No retry loops, no reconnection, no buffering.

The technical work breaks into three areas: (1) catching WebSocket and evdev errors and converting them to clean exits, (2) adding startup validation for ydotoold and API key, and (3) implementing a clipboard-based text injection fallback for non-ASCII characters that ydotool cannot type.

**Primary recommendation:** Each error path should call a single `fatal()` helper that logs to stderr, fires `notify-send`, and calls `sys.exit(1)`. This keeps every failure mode consistent and testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Error philosophy:** KISS -- on any error, exit immediately with a clear message
- No retry loops, no reconnection logic, no buffering
- Single exit code (exit 1) for all errors -- the error message explains what happened
- Dual notification: stderr (for terminal/logs) + desktop notification via notify-send (for visibility when terminal is hidden)
- **Network drop:** If WebSocket connection drops mid-session, exit immediately. No auto-reconnect, no buffering of audio during outage
- **Keyboard disconnect:** If evdev device disappears mid-dictation, exit immediately. No attempt to recover key state or re-acquire the device
- **Missing dependencies / bad credentials:** Check for ydotoold at startup -- exit immediately if not running. Check AssemblyAI API key validity at startup -- exit immediately if expired/revoked
- **Text injection strategies:** Implement three strategies: ydotool direct, clipboard fallback (try ydotool, fall back to clipboard on failure), and always-clipboard. User selects strategy via CLI flag: `--inject=ydotool | clipboard-fallback | clipboard`

### Claude's Discretion
- Default injection strategy selection
- Exact error message wording
- Desktop notification formatting
- Startup check ordering

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RELY-01 | AssemblyAI WebSocket auto-reconnects with exponential backoff | **Overridden by user decision:** No reconnect. Exit immediately on WebSocket drop. Error handler in `_on_stream_error` and `_on_terminated` calls `fatal()` |
| RELY-02 | AssemblyAI error codes classified -- retry on 3005, abort on 1008 | **Overridden by user decision:** No retry on any code. Exit immediately on all errors. Still classify codes for error messages: 1008=auth/billing, 3005=session expired |
| RELY-03 | evdev listener flushes `_held_keys` state on device disconnect | **Overridden by user decision:** No flush/recovery. Exit immediately on OSError(ENODEV) from device read |
| RELY-04 | ydotool injector handles non-ASCII via clipboard fallback | Clipboard fallback: `wl-copy` + `ydotool key ctrl+v`. Three strategies selectable via `--inject` CLI flag |
| RELY-05 | ydotoold availability checked at startup with actionable error message | `pgrep -x ydotoold` check already exists in `is_available()`. Enhance: exit with dual notification if not running |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| assemblyai | >=0.33.0 | STT streaming via Universal-Streaming v3 | Already integrated; provides `StreamingEvents.Error` and `StreamingEvents.Termination` |
| evdev | >=1.7.0 | Linux input device reading | Already integrated; raises `OSError(errno.ENODEV)` on disconnect |
| subprocess | stdlib | Shell out to ydotool, wl-copy, notify-send, pgrep | Already used for ydotool; extend for clipboard and notifications |

### Supporting (new for Phase 2)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| wl-clipboard (system) | any | `wl-copy` command for clipboard injection | When using clipboard or clipboard-fallback injection strategy |
| libnotify (system) | any | `notify-send` command for desktop notifications | On every fatal error exit |
| shutil.which | stdlib | Check if `wl-copy` and `notify-send` are in PATH | At startup or first use |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| notify-send (subprocess) | desktop-notifier (pip) or gi.repository.Notify | Extra dependency; subprocess is simpler and keeps KISS philosophy |
| wl-copy (subprocess) | pyclip or pyperclip | Extra dependency; wl-copy is Wayland-native and always available on target systems |

## Architecture Patterns

### Pattern 1: Fatal Exit Helper
**What:** A single function that handles all fatal exits consistently.
**When to use:** Every error path that should kill the daemon.
**Example:**
```python
import subprocess
import sys
import logging

logger = logging.getLogger(__name__)

def fatal(message: str) -> None:
    """Log error, send desktop notification, and exit."""
    logger.error(message)
    print(f"murmur: {message}", file=sys.stderr)
    try:
        subprocess.run(
            ["notify-send", "--urgency=critical", "Murmur", message],
            timeout=5,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # notify-send not available; stderr message is enough
    sys.exit(1)
```

### Pattern 2: Startup Validation Chain
**What:** Run all prerequisite checks before entering the event loop.
**When to use:** At daemon startup, before `hotkey.start()`.
**Example:**
```python
def validate_startup(config: DictationConfig) -> None:
    """Check all prerequisites. Exits on first failure."""
    # 1. Check ydotoold is running
    if not injector.is_available():
        fatal("ydotoold is not running. Start it with: systemctl --user start ydotool")

    # 2. Check AssemblyAI API key (lightweight validation)
    if not config.transcriber.api_key:
        fatal("ASSEMBLYAI_API_KEY not set. Get a key at https://www.assemblyai.com/")

    # 3. Check wl-copy if clipboard strategy selected
    if config.injector.strategy in ("clipboard", "clipboard-fallback"):
        if not shutil.which("wl-copy"):
            fatal("wl-copy not found. Install wl-clipboard: pacman -S wl-clipboard")
```

### Pattern 3: Injection Strategy Pattern
**What:** Three injection implementations behind a common interface, selected by CLI flag.
**When to use:** Text injection in `YdotoolInjector.inject()`.
**Strategies:**
- `ydotool` -- Direct `ydotool type` (current behavior, fast, ASCII-only)
- `clipboard` -- Always use `wl-copy` + `ydotool key ctrl+v` (handles all Unicode)
- `clipboard-fallback` -- Try ydotool type first, fall back to clipboard on failure

**Recommended default:** `clipboard-fallback`. Reason: ydotool direct is fastest for ASCII (the common case), and the fallback catches non-ASCII without user configuration. The fallback detection can be based on checking if text contains non-ASCII characters before deciding the path.

### Anti-Patterns to Avoid
- **Swallowing errors silently:** Current code catches exceptions and logs warnings. Phase 2 must convert these to `fatal()` calls for critical errors.
- **Retry loops:** User explicitly said no retries. Do not add backoff, reconnect, or retry logic.
- **Complex error recovery:** No key-state flushing, no device re-acquisition. Exit is the recovery.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Desktop notifications | D-Bus bindings, GObject Introspection | `subprocess.run(["notify-send", ...])` | KISS; notify-send is ubiquitous on Linux desktops |
| Clipboard access | Direct Wayland protocol interaction | `subprocess.run(["wl-copy", ...])` | wl-copy handles all Wayland compositor differences |
| ASCII detection | Manual character range checks | `text.isascii()` | Built-in Python method, handles all edge cases |

## Common Pitfalls

### Pitfall 1: Clipboard Paste Race Condition
**What goes wrong:** `wl-copy` writes to clipboard, then `ydotool key ctrl+v` fires, but the application hasn't received the clipboard content yet, or the clipboard is restored too quickly.
**Why it happens:** Wayland clipboard is asynchronous. wl-copy must remain alive until the paste target reads the data.
**How to avoid:** Do NOT use `--paste-once` with `wl-copy`. Use `wl-copy` without `--paste-once` so it stays as the clipboard owner until overwritten. After pasting, optionally restore the previous clipboard content with a small delay.
**Warning signs:** Pasted text appears blank or shows previous clipboard content.

### Pitfall 2: notify-send Missing
**What goes wrong:** `notify-send` is not installed, and the subprocess call fails with `FileNotFoundError`.
**Why it happens:** Minimal Linux installs or container environments may lack libnotify.
**How to avoid:** Wrap in try/except, treat as non-fatal (stderr message is the primary channel).
**Warning signs:** `FileNotFoundError` from subprocess.

### Pitfall 3: WebSocket Error vs Close Events
**What goes wrong:** Only handling `StreamingEvents.Error` but missing `StreamingEvents.Termination` with error conditions.
**Why it happens:** AssemblyAI SDK has two event types for session end: Error (explicit error) and Termination (normal or abnormal end).
**How to avoid:** Handle both events. Check termination context for unexpected endings.
**Warning signs:** Daemon hangs after WebSocket drops instead of exiting.

### Pitfall 4: evdev OSError Not Always ENODEV
**What goes wrong:** Catching all OSError from device.read() and treating them as disconnects.
**Why it happens:** OSError can also be raised for permission issues, busy devices, etc.
**How to avoid:** Check `err.errno == errno.ENODEV` for true disconnects. For Phase 2 KISS approach, exit on ANY OSError from device read (all are unrecoverable anyway).
**Warning signs:** False disconnect messages on permission errors.

### Pitfall 5: Threading and sys.exit()
**What goes wrong:** `sys.exit(1)` from a non-main thread raises `SystemExit` exception but does not terminate the process.
**Why it happens:** Python's `sys.exit()` only raises `SystemExit` in the calling thread. The main thread continues running.
**How to avoid:** Use `os._exit(1)` from non-main threads, or signal the main thread to exit. Better: use `os.kill(os.getpid(), signal.SIGTERM)` to trigger the existing signal handler for clean shutdown, then exit.
**Warning signs:** Daemon appears to hang after error logging.

## Code Examples

### WebSocket Error Exit (in assemblyai.py)
```python
def _on_stream_error(self, client: Any, error: Any) -> None:
    """Handle streaming error -- exit immediately per user decision."""
    from murmur.errors import fatal
    error_str = str(error)
    fatal(f"WebSocket error: {error_str}")

def _on_terminated(self, client: Any, event: Any) -> None:
    """Handle streaming termination."""
    # Normal termination after stop() is expected
    if not self._is_streaming:
        return
    # Unexpected termination while streaming = error
    from murmur.errors import fatal
    fatal("WebSocket connection lost unexpectedly")
```

### evdev Disconnect Exit (in evdev.py)
```python
# In _listen_loop, replace the current OSError handler:
except OSError:
    from murmur.errors import fatal
    dev_path: str = str(device.path)
    fatal(f"Input device disconnected: {dev_path}")
```

### Clipboard Injection (in ydotool.py)
```python
def _inject_via_clipboard(self, text: str) -> None:
    """Inject text via clipboard: wl-copy + Ctrl+V."""
    try:
        subprocess.run(
            ["wl-copy", "--", text],
            timeout=5,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [self._ydotool_path, "key", "29:1", "47:1", "47:0", "29:0"],
            timeout=5,
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        from murmur.errors import fatal
        fatal(f"Clipboard injection failed: {e}")
```

Note: `29:1 47:1 47:0 29:0` is ydotool key syntax for Ctrl down, V down, V up, Ctrl up. This is more reliable than `ydotool key ctrl+v` string parsing.

### Startup Validation (in main.py)
```python
def _validate_startup(self) -> None:
    """Run all prerequisite checks before entering event loop."""
    from murmur.errors import fatal

    if not self.injector.is_available():
        fatal(
            "ydotoold is not running. Start it with:\n"
            "  systemctl --user start ydotool"
        )

    # API key format check (real validation happens on first connect)
    if not self.config.transcriber.api_key:
        fatal(
            "ASSEMBLYAI_API_KEY not set.\n"
            "  export ASSEMBLYAI_API_KEY=your_key\n"
            "  Get a key at: https://www.assemblyai.com/"
        )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| xdotool for typing | ydotool (works on Wayland) | 2020+ | ydotool has kernel-level uinput, bypasses Wayland restrictions |
| xclip for clipboard | wl-copy/wl-paste | Wayland adoption | wl-clipboard is the standard for Wayland compositors |
| pynotify for desktop notifications | notify-send (libnotify CLI) | Long established | No Python dependency needed, works everywhere |

**Deprecated/outdated:**
- xdotool: Does not work on Wayland (X11 only)
- xclip/xsel: X11 clipboard tools, not Wayland-compatible

## Open Questions

1. **AssemblyAI API key validation at startup**
   - What we know: The SDK raises errors on invalid keys when connecting
   - What's unclear: Whether there's a lightweight API endpoint to validate keys without starting a streaming session
   - Recommendation: Accept the key at startup if non-empty; let the first connect attempt surface auth errors. The `_on_stream_error` handler will catch 1008 codes and exit with a clear message.

2. **Ctrl+V keycode portability**
   - What we know: ydotool `key 29:1 47:1 47:0 29:0` works for standard US keyboard layouts
   - What's unclear: Whether non-US keyboard layouts map V to a different scancode
   - Recommendation: Use ydotool's string key syntax `ctrl+v` as primary. The numeric codes are a fallback if string parsing is unreliable. Test on the target system.

## Sources

### Primary (HIGH confidence)
- AssemblyAI official docs: [Common session errors and closures](https://www.assemblyai.com/docs/universal-streaming/common-session-errors-and-closures) -- error codes 1008, 3005
- python-evdev issue #64: [Behavior of read() when device disappears](https://github.com/gvalkov/python-evdev/issues/64) -- ENODEV on disconnect
- ydotool issue #249: [Unicode characters not printing](https://github.com/ReimuNotMoe/ydotool/issues/249) -- confirms non-ASCII limitation
- wl-clipboard: [GitHub repo](https://github.com/bugaevc/wl-clipboard) -- wl-copy usage

### Secondary (MEDIUM confidence)
- ydotool issue #9, #22: Historical confirmation of Unicode limitation across multiple character sets
- Emote project PR #32: [ydotool paste under Wayland](https://github.com/tom-james-watson/Emote/pull/32) -- real-world clipboard+paste pattern

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use or are standard Linux tools
- Architecture: HIGH -- patterns are straightforward subprocess calls and Python stdlib
- Pitfalls: HIGH -- clipboard race condition and threading exit are well-documented issues

**Research date:** 2026-02-17
**Valid until:** 2026-03-17 (stable domain, low churn)
