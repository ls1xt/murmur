"""
ydotool-based text injector -- works on Wayland and X11.

Uses the kernel uinput subsystem to simulate a virtual keyboard, bypassing
Wayland's input restrictions. Supports three injection strategies:

- ``ydotool``: Direct ``ydotool type`` (fast, ASCII-only).
- ``clipboard``: Always ``wl-copy`` + Ctrl+V (handles all Unicode).
- ``clipboard-fallback``: ydotool for ASCII, clipboard for non-ASCII.
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import time
import unicodedata

from murmur.injector.base import TextInjector

logger = logging.getLogger(__name__)


def _sanitize_text(text: str) -> str:
    """Strip control characters before injection.

    Control characters (newline, carriage return, tab, NUL, …) can cause
    dangerous effects when injected into terminal applications -- for example,
    a newline would submit the current input buffer.  Only printable Unicode
    characters (general category != C*) are kept.
    """
    clean = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    removed = len(text) - len(clean)
    if removed:
        logger.warning("Sanitized %d control character(s) from injection text", removed)
    return clean


class YdotoolInjector(TextInjector):
    """Injects text using ydotool with configurable strategy."""

    def __init__(
        self,
        ydotool_path: str = "ydotool",
        key_delay: int = 0,
        trailing_space: bool = True,
        inject_strategy: str = "clipboard-fallback",
    ) -> None:
        self._ydotool_path = ydotool_path
        self._key_delay = key_delay
        self._trailing_space = trailing_space
        self._inject_strategy = inject_strategy
        self._resolved_path: str | None = shutil.which(self._ydotool_path)
        self._wl_copy_path: str | None = shutil.which("wl-copy")
        self._wl_copy_proc: subprocess.Popen[bytes] | None = None

        if not self._resolved_path:
            logger.warning("ydotool not found in PATH")

    def is_available(self) -> bool:
        """Check if ydotool is installed and the daemon is running."""
        if not self._resolved_path:
            return False

        try:
            result = subprocess.run(
                ["pgrep", "-x", "ydotoold"],
                capture_output=True,
                timeout=2,
            )
            if result.returncode != 0:
                logger.warning(
                    "ydotoold daemon is not running. Start it with:\n"
                    "  systemctl --user start ydotool\n"
                    "  # or: ydotoold &"
                )
                return False
        except subprocess.TimeoutExpired:
            pass
        except FileNotFoundError:
            logger.warning("pgrep not found; cannot verify ydotoold is running")
            return False

        # Check wl-copy if clipboard strategy is needed
        if (
            self._inject_strategy in ("clipboard", "clipboard-fallback")
            and not self._wl_copy_path
        ):
            logger.warning(
                "wl-copy not found. Install wl-clipboard for non-ASCII text injection."
            )

        return True

    def inject(self, text: str) -> None:
        """Inject text using the configured strategy."""
        if not text:
            return

        text = _sanitize_text(text)
        if not text:
            return

        if self._trailing_space:
            text = text + " "

        if self._inject_strategy == "clipboard":
            self._inject_via_clipboard(text)
        elif self._inject_strategy == "clipboard-fallback":
            if text.isascii():
                self._inject_via_ydotool(text)
            else:
                self._inject_via_clipboard(text)
        else:
            # "ydotool" strategy (default fallback)
            self._inject_via_ydotool(text)

    def inject_raw(self, text: str) -> None:
        """Inject text without trailing space, routing through the configured strategy.

        Used for partial transcripts that are mid-sentence.  Routes through the
        same strategy as inject() to ensure non-ASCII characters are handled
        consistently -- which keeps the injected character count in sync with
        len(text) used by inject_backspaces().
        """
        if not text:
            return

        text = _sanitize_text(text)
        if not text:
            return

        logger.debug("Injecting raw partial: %r", text[:80])

        if self._inject_strategy == "clipboard":
            self._inject_via_clipboard(text)
        elif self._inject_strategy == "clipboard-fallback":
            if text.isascii():
                self._inject_via_ydotool_raw(text)
            else:
                self._inject_via_clipboard(text)
        else:
            # "ydotool" strategy
            self._inject_via_ydotool_raw(text)

    def inject_return(self) -> None:
        """Inject a Return/Enter keypress via ydotool.

        Uses Linux keycode 28 (KEY_ENTER).
        """
        cmd = [self._ydotool_path, "key", "--key-delay", "0", "28:1", "28:0"]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                logger.error(
                    "ydotool return failed (rc=%d): %s",
                    result.returncode,
                    result.stderr.strip(),
                )
        except subprocess.TimeoutExpired:
            logger.error("ydotool return timed out")
        except FileNotFoundError:
            logger.error("ydotool not found at %s", self._ydotool_path)

    def inject_backspaces(self, count: int) -> None:
        """Inject N backspace keypresses to erase previous text.

        Uses ydotool key with keycode 14 (KEY_BACKSPACE).
        """
        if count <= 0:
            return

        logger.debug("Injecting %d backspaces", count)

        # Generate key press/release pairs for KEY_BACKSPACE (code 14)
        key_args: list[str] = []
        for _ in range(count):
            key_args.extend(["14:1", "14:0"])

        cmd = [self._ydotool_path, "key", "--key-delay", "0", *key_args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(
                    "ydotool backspace failed (rc=%d): %s",
                    result.returncode,
                    result.stderr.strip(),
                )
        except subprocess.TimeoutExpired:
            logger.error("ydotool backspace timed out")
        except FileNotFoundError:
            logger.error("ydotool not found at %s", self._ydotool_path)

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to the system clipboard via wl-copy (no injection).

        wl-copy stays alive to serve clipboard requests so we use Popen and
        do not wait.  The previous wl-copy process (if any) is killed first
        so we don't leave orphaned processes accumulating.
        """
        if not text:
            return
        if not self._wl_copy_path:
            logger.error("wl-copy not found; cannot copy to clipboard")
            return
        # Kill previous wl-copy if still running (covers both copy_to_clipboard
        # and _inject_via_clipboard procs since both store into _wl_copy_proc).
        if self._wl_copy_proc is not None:
            with contextlib.suppress(OSError):
                self._wl_copy_proc.kill()
            self._wl_copy_proc = None
        logger.debug("Copying to clipboard: %r", text[:80])
        try:
            self._wl_copy_proc = subprocess.Popen(
                [self._wl_copy_path, "--", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as e:
            logger.error("wl-copy error: %s", e)
            return
        # Poll briefly to catch immediate wl-copy failures (e.g. compositor
        # unavailable, wrong WAYLAND_DISPLAY).  These fail silently otherwise
        # because Popen succeeds but wl-copy exits before serving any paste.
        time.sleep(0.1)
        ret = self._wl_copy_proc.poll()
        if ret is not None:
            stderr_bytes = (
                self._wl_copy_proc.stderr.read() if self._wl_copy_proc.stderr else b""
            )
            err = stderr_bytes.decode(errors="replace").strip()
            logger.error(
                "wl-copy exited immediately (rc=%d)%s",
                ret,
                f": {err}" if err else "",
            )
            self._wl_copy_proc = None

    def _inject_via_ydotool_raw(self, text: str) -> None:
        """Inject text via ydotool type without a trailing space.

        Used for ASCII partial transcripts in inject_raw().
        """
        cmd = [
            self._ydotool_path,
            "type",
            "--clearmodifiers",
            "--key-delay",
            "0",
            "--key-hold",
            "0",
            "--",
            text,
        ]
        logger.debug("Injecting raw via ydotool: %r", text[:80])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(
                    "ydotool raw inject failed (rc=%d): %s",
                    result.returncode,
                    result.stderr.strip(),
                )
        except subprocess.TimeoutExpired:
            logger.error("ydotool raw inject timed out")
        except FileNotFoundError:
            logger.error("ydotool not found at %s", self._ydotool_path)

    def _inject_via_ydotool(self, text: str) -> None:
        """Inject text directly via ydotool type."""
        cmd = [self._ydotool_path, "type", "--clearmodifiers"]

        cmd.extend(["--key-delay", str(self._key_delay), "--key-hold", "0"])

        cmd.extend(["--", text])

        logger.debug("Injecting text via ydotool: %r", text[:80])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(
                    "ydotool failed (rc=%d): %s",
                    result.returncode,
                    result.stderr.strip(),
                )
        except subprocess.TimeoutExpired:
            logger.error("ydotool timed out")
        except FileNotFoundError:
            logger.error("ydotool not found at %s", self._ydotool_path)

    def _inject_via_clipboard(self, text: str) -> None:
        """Inject text via clipboard: wl-copy + Ctrl+V."""
        if not self._wl_copy_path:
            from murmur.errors import fatal

            fatal("wl-copy not found. Install wl-clipboard: pacman -S wl-clipboard")
            return  # unreachable, but makes type checker happy

        logger.debug("Injecting text via clipboard: %r", text[:80])

        # Kill any previous wl-copy (could be from copy_to_clipboard or a
        # prior inject) before starting a new one.  Untracked orphans steal
        # Wayland clipboard ownership without being cleanable later.
        if self._wl_copy_proc is not None:
            with contextlib.suppress(OSError):
                self._wl_copy_proc.kill()
            self._wl_copy_proc = None

        # Write to Wayland clipboard.
        # wl-copy stays alive to serve clipboard requests; use Popen and do
        # NOT wait.  Give it 50 ms to register with the compositor before
        # sending Ctrl+V.  Store in _wl_copy_proc so the next clipboard
        # operation can clean it up properly.
        try:
            self._wl_copy_proc = subprocess.Popen(
                [self._wl_copy_path, "--", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as e:
            logger.error("wl-copy error: %s", e)
            return
        time.sleep(0.05)

        # Simulate Ctrl+V paste via ydotool
        # Keycodes: 29=KEY_LEFTCTRL, 47=KEY_V
        # Format: code:value (1=press, 0=release)
        try:
            result = subprocess.run(
                [
                    self._ydotool_path,
                    "key",
                    "29:1",
                    "47:1",
                    "47:0",
                    "29:0",
                ],
                timeout=5,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.error("ydotool key failed: %s", result.stderr.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error("ydotool key error: %s", e)
