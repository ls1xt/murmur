"""Desktop notifications via notify-send with configurable verbosity."""

from __future__ import annotations

import contextlib
import logging
import subprocess
from typing import Literal

logger = logging.getLogger(__name__)


class Notifier:
    """Send desktop notifications with configurable verbosity.

    Levels:
        - ``"off"``: No notifications
        - ``"errors"``: Only error/critical notifications (persistent)
        - ``"verbose"``: Errors + informational (state changes, startup)
    """

    def __init__(self, level: Literal["off", "errors", "verbose"] = "errors") -> None:
        self._level = level

    def error(self, message: str) -> None:
        """Send persistent error notification (urgency=critical).

        Fires unless level is ``"off"``.
        """
        if self._level == "off":
            return
        self._send(message, urgency="critical")

    def info(self, message: str) -> None:
        """Send auto-expiring informational notification.

        Only fires when level is ``"verbose"``.
        """
        if self._level != "verbose":
            return
        self._send(message, urgency="normal", expire_ms=5000)

    def _send(
        self,
        message: str,
        urgency: Literal["critical", "normal"] = "normal",
        expire_ms: int | None = None,
    ) -> None:
        """Shell out to notify-send. Best-effort, never crashes."""
        cmd = ["notify-send", f"--urgency={urgency}"]
        if expire_ms is not None:
            cmd.append(f"--expire-time={expire_ms}")
        cmd.extend(["Murmur", message])
        with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
            subprocess.run(cmd, timeout=5, capture_output=True)
