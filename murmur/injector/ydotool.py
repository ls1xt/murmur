"""
ydotool-based text injector -- works on Wayland and X11.

Uses the kernel uinput subsystem to simulate a virtual keyboard, bypassing
Wayland's input restrictions.
"""

from __future__ import annotations

import logging
import shutil
import subprocess

from murmur.injector.base import TextInjector

logger = logging.getLogger(__name__)


class YdotoolInjector(TextInjector):
    """Injects text using ydotool."""

    def __init__(
        self,
        ydotool_path: str = "ydotool",
        key_delay: int = 0,
        trailing_space: bool = True,
    ) -> None:
        self._ydotool_path = ydotool_path
        self._key_delay = key_delay
        self._trailing_space = trailing_space
        self._resolved_path: str | None = shutil.which(self._ydotool_path)
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

        return True

    def inject(self, text: str) -> None:
        """Type text using ydotool."""
        if not text:
            return

        if self._trailing_space:
            text = text + " "

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
