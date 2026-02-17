"""System tray icon with state management and graceful degradation."""

from __future__ import annotations

import logging
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

    Runs pystray in a daemon thread. Degrades gracefully if pystray or
    display is unavailable -- all methods become no-ops.
    """

    def __init__(self, on_quit: Callable[[], None] | None = None) -> None:
        self._on_quit = on_quit
        self._icon: Any = None
        self._thread: threading.Thread | None = None
        self._state = "idle"
        self._error_reason = ""
        self._available = False

    @property
    def available(self) -> bool:
        """Whether the tray icon is active and visible."""
        return self._available

    def start(self) -> None:
        """Start tray icon in background daemon thread. Non-blocking.

        Gracefully handles import failures and display errors.
        """
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
            logger.info("Tray icon started")
        except Exception as e:
            print(f"murmur: tray icon unavailable: {e}", file=sys.stderr)
            self._available = False

    def set_state(self, state: str, reason: str = "") -> None:
        """Update tray icon to reflect new state. Thread-safe.

        No-op if tray is unavailable.

        Args:
            state: One of "idle", "recording", "error".
            reason: Optional error reason (used for error state title).
        """
        if not self._available or self._icon is None:
            return
        self._state = state
        self._error_reason = reason
        try:
            self._icon.icon = _create_icon_image(state)
            title = _STATE_TITLES.get(state, "Idle")
            if state == "error" and reason:
                title = f"Error: {reason}"
            self._icon.title = f"Murmur - {title}"
            self._icon.update_menu()
        except Exception as e:
            logger.debug("Tray icon update failed: %s", e)

    def stop(self) -> None:
        """Stop tray icon. Safe to call even if not running."""
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
