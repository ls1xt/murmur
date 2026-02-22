"""System tray icon with state management and graceful degradation.

Supports two backends:
- pystray: Works on GNOME, KDE, and other compositors with AppIndicator support.
- SNI (StatusNotifierItem): Direct D-Bus implementation for Sway/waybar via Gio.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from typing import Any

from murmur.feedback._tray_common import (
    create_icon_image as _create_icon_image,  # noqa: F401 – re-exported
)

logger = logging.getLogger(__name__)


class TrayIcon:
    """System tray icon showing daemon state (idle/recording/error).

    Uses SNI backend on Sway, pystray elsewhere. Degrades gracefully
    if neither backend is available -- all methods become no-ops.
    """

    def __init__(
        self,
        on_quit: Callable[[], None] | None = None,
        on_activate: Callable[[], None] | None = None,
    ) -> None:
        self._on_quit = on_quit
        self._on_activate = on_activate
        self._backend: Any = None
        self._available = False

    @property
    def available(self) -> bool:
        """Whether the tray icon is active and visible."""
        return self._available

    @staticmethod
    def _is_sway() -> bool:
        """Return True if running under Sway compositor.

        Sway's swaybar speaks StatusNotifierItem (SNI), not AppIndicator3.
        Attempting to use libappindicator3 on Sway results in a NULL D-Bus
        object_path which causes GLib to abort() on icon updates.
        """
        return "SWAYSOCK" in os.environ

    def start(self) -> None:
        """Start tray icon in background daemon thread. Non-blocking.

        Gracefully handles import failures and display errors.
        """
        if self._is_sway():
            self._start_sni()
            return
        try:
            from murmur.feedback.tray_pystray import PystrayTray

            self._backend = PystrayTray(on_quit=self._on_quit)
            self._backend.start()
            self._available = True
            logger.info("Tray icon started (pystray)")
        except Exception as e:
            print(f"murmur: tray icon unavailable: {e}", file=sys.stderr)
            self._available = False

    def _start_sni(self) -> None:
        """Start the SNI tray backend for Sway/waybar."""
        try:
            from murmur.feedback.sni import SniTray

            self._backend = SniTray(on_quit=self._on_quit, on_activate=self._on_activate)
            self._backend.start()
            self._available = True
            logger.info("Tray icon started (SNI/Sway)")
        except Exception as e:
            logger.warning("SNI tray failed: %s", e)
            self._available = False

    def run_blocking(self, setup_fn: Callable[[], None]) -> None:
        """Run the tray icon on the calling (main) thread.

        Required on macOS where ``pystray`` must run on the main thread.
        ``setup_fn`` is called in a background thread once the icon is ready;
        when it returns the event loop exits.  Falls back to calling
        ``setup_fn()`` directly if the tray is unavailable.
        """
        if self._is_sway():
            self._start_sni()
            setup_fn()
            return
        try:
            from murmur.feedback.tray_pystray import PystrayTray

            self._backend = PystrayTray(on_quit=self._on_quit)
            self._available = True
            logger.info("Tray icon started (pystray)")
            self._backend.run_blocking(setup_fn)
        except Exception as e:
            print(f"murmur: tray icon unavailable: {e}", file=sys.stderr)
            self._available = False
            setup_fn()

    def set_state(self, state: str, reason: str = "") -> None:
        """Update tray icon to reflect new state. Thread-safe.

        No-op if tray is unavailable.

        Args:
            state: One of "idle", "recording", "error".
            reason: Optional error reason (used for error state title).
        """
        if not self._available or self._backend is None:
            return
        self._backend.set_state(state, reason)

    def stop(self) -> None:
        """Stop tray icon. Safe to call even if not running."""
        if self._backend is not None:
            self._backend.stop()
