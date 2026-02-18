"""System tray icon with state management and graceful degradation.

Supports two backends:
- pystray: Works on GNOME, KDE, and other compositors with AppIndicator support.
- SNI (StatusNotifierItem): Direct D-Bus implementation for Sway/waybar via Gio.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Icon colors: (fill, outline) per state
_STATE_COLORS: dict[str, tuple[str, str]] = {
    "idle": ("#888888", "#444444"),
    "recording": ("#ff3333", "#cc0000"),
    "error": ("#ff9933", "#cc6600"),
}

_STATE_TITLES: dict[str, str] = {
    "idle": "Idle",
    "recording": "Recording",
    "error": "Error",
}

ICON_SIZE = 64


def _create_icon_image(state: str) -> Any:
    """Create a 64x64 RGBA PIL image with a colored circle for the state.

    Returns a PIL.Image.Image or raises ImportError if Pillow unavailable.
    """
    from PIL import Image, ImageDraw  # type: ignore[import-untyped]

    fill, outline = _STATE_COLORS.get(state, _STATE_COLORS["idle"])

    img: Any = Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))
    draw: Any = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, ICON_SIZE - margin, ICON_SIZE - margin],
        fill=fill,
        outline=outline,
        width=2,
    )
    return img


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
        self._icon: Any = None
        self._sni: Any = None
        self._use_sni = False
        self._thread: threading.Thread | None = None
        self._state = "idle"
        self._error_reason = ""
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
            import pystray  # type: ignore[import-untyped]

            icon_image = _create_icon_image("idle")
            menu = pystray.Menu(
                pystray.MenuItem(
                    self._status_text,
                    None,
                    enabled=False,
                ),
                pystray.MenuItem("Quit", self._on_quit_clicked),
            )
            self._icon = pystray.Icon(
                "murmur",
                icon=icon_image,
                title="Murmur - Idle",
                menu=menu,
            )
            self._thread = threading.Thread(
                target=self._icon.run, daemon=True
            )
            self._thread.start()
            self._available = True
            logger.info("Tray icon started (pystray)")
        except Exception as e:
            print(
                f"murmur: tray icon unavailable: {e}", file=sys.stderr
            )
            self._available = False

    def _start_sni(self) -> None:
        """Start the SNI tray backend for Sway/waybar."""
        try:
            from murmur.feedback.sni import SniTray

            self._sni = SniTray(on_quit=self._on_quit, on_activate=self._on_activate)
            self._sni.start()
            self._use_sni = True
            self._available = True
            logger.info("Tray icon started (SNI/Sway)")
        except Exception as e:
            logger.warning("SNI tray failed: %s", e)
            self._available = False

    def set_state(self, state: str, reason: str = "") -> None:
        """Update tray icon to reflect new state. Thread-safe.

        Marshals the update onto the GLib main loop when AppIndicator
        or SNI is in use, so D-Bus signal emission always runs on the
        correct thread. No-op if tray is unavailable.

        Args:
            state: One of "idle", "recording", "error".
            reason: Optional error reason (used for error state title).
        """
        if not self._available:
            return
        self._state = state
        self._error_reason = reason

        if self._use_sni and self._sni is not None:
            self._sni.set_state(state)
            return

        if self._icon is None:
            return
        try:
            from gi.repository import GLib  # type: ignore[import-untyped]

            GLib.idle_add(  # type: ignore[reportUnknownMemberType]
                self._apply_state, state, reason
            )
        except ImportError:
            self._apply_state(state, reason)

    def _apply_state(self, state: str, reason: str) -> bool:
        """Apply state update for pystray backend."""
        try:
            self._icon.icon = _create_icon_image(state)
            title = _STATE_TITLES.get(state, "Idle")
            if state == "error" and reason:
                title = f"Error: {reason}"
            self._icon.title = f"Murmur - {title}"
            self._icon.update_menu()
        except Exception as e:
            logger.debug("Tray icon update failed: %s", e)
            self._available = False
        return False  # don't repeat the idle callback

    def stop(self) -> None:
        """Stop tray icon. Safe to call even if not running."""
        if self._use_sni and self._sni is not None:
            self._sni.stop()
            return
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as e:
                logger.debug("Tray icon stop failed: %s", e)

    def _status_text(self) -> str:
        """Dynamic status text for the menu item."""
        title = _STATE_TITLES.get(self._state, "Idle")
        if self._state == "error" and self._error_reason:
            return f"Error: {self._error_reason}"
        return title

    def _on_quit_clicked(
        self,
        icon: Any = None,
        item: Any = None,
    ) -> None:
        """Handle Quit menu click."""
        if self._on_quit is not None:
            self._on_quit()
