"""
ydotool-based text injector -- works on Wayland and X11.

Uses the kernel uinput subsystem to simulate a virtual keyboard, bypassing
Wayland's input restrictions. Supports three injection strategies:

- ``ydotool``: Direct ``ydotool type`` (fast, ASCII-only).
- ``clipboard``: Always ``wl-copy`` + Ctrl+V (handles all Unicode).
- ``clipboard-fallback``: ydotool for ASCII, clipboard for non-ASCII.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from murmur.injector.base import TextInjector

logger = logging.getLogger(__name__)


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
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

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

    def _inject_via_ydotool(self, text: str) -> None:
        """Inject text directly via ydotool type."""
        cmd = [self._ydotool_path, "type", "--clearmodifiers"]

        if self._key_delay > 0:
            cmd.extend(["--key-delay", str(self._key_delay)])

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

        # Write to Wayland clipboard
        try:
            result = subprocess.run(
                [self._wl_copy_path, "--", text],
                timeout=5,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                logger.error("wl-copy failed: %s", result.stderr.strip())
                return
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error("wl-copy error: %s", e)
            return

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
