"""pystray tray backend for GNOME, KDE, and other compositors."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pystray
from murmur.feedback._tray_common import STATE_TITLES, TrayState, create_icon_image

__all__ = ["PystrayTray"]

logger = logging.getLogger(__name__)


class PystrayTray:
    """pystray tray backend.

    Runs the pystray icon loop in a daemon thread. All state updates are
    marshalled onto the GLib main loop when available (AppIndicator
    compositors), falling back to direct calls otherwise.
    """

    def __init__(
        self,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        self._on_quit = on_quit
        self._icon: Any = None
        self._thread: threading.Thread | None = None
        self._state: TrayState = "idle"
        self._error_reason = ""

    @property
    def state(self) -> TrayState:
        """Current tray state."""
        return self._state

    @state.setter
    def state(self, value: TrayState) -> None:
        """Set the tray state."""
        self._state = value

    @property
    def error_reason(self) -> str | None:
        """Error reason if in error state."""
        return self._error_reason if self._error_reason else None

    @error_reason.setter
    def error_reason(self, value: str) -> None:
        """Set the error reason."""
        self._error_reason = value

    def _build_icon(self) -> Any:
        """Build and return a pystray Icon without running it."""
        import pystray

        icon_image = create_icon_image("idle")
        menu = pystray.Menu(
            pystray.MenuItem(
                self.status_text,
                None,
                enabled=False,
            ),
            pystray.MenuItem("Quit", self.on_quit_clicked),
        )
        return pystray.Icon(
            "murmur",
            icon=icon_image,
            title="Murmur - Idle",
            menu=menu,
        )

    def start(self) -> None:
        """Start the pystray icon in a background daemon thread (Linux/GTK path)."""
        self._icon = self._build_icon()
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def _platform_setup(self) -> None:
        """Platform-specific initialisation called before the icon is built.

        On macOS: pre-initialises NSApplication.sharedApplication() on the
        calling (main) thread.  NSApplication is a singleton so this is
        idempotent, but doing it here guarantees AppKit is bootstrapped while
        we are definitely on the main thread — preventing an intermittent
        SIGABRT inside NSApp.run() caused by a race in AppKit's own startup.

        On Linux/other: no-op.
        """
        import sys

        if sys.platform != "darwin":
            return
        try:
            import AppKit

            AppKit.NSApplication.sharedApplication()
        except ImportError:
            pass

    def run_blocking(self, setup_fn: Callable[[], None]) -> None:
        """Build and run the pystray icon on the calling thread.

        Must be called from the main thread on macOS because pystray's
        Darwin backend calls ``NSApp.run()`` which requires the main thread.
        ``setup_fn`` is invoked in a background thread once the icon is ready;
        when it returns the event loop is stopped.
        """
        self._platform_setup()
        self._icon = self._build_icon()

        def _setup(icon: Any) -> None:
            icon.visible = True
            setup_fn()
            icon.stop()

        self._icon.run(setup=_setup)

    def set_state(self, state: TrayState, reason: str = "") -> None:
        """Update icon state. Thread-safe via GLib.idle_add when available."""
        self._state = state
        self._error_reason = reason
        if self._icon is None:
            return
        try:
            from gi.repository import GLib  # type: ignore[reportMissingImports]

            GLib.idle_add(  # type: ignore[reportUnknownMemberType]
                self._apply_state, state, reason
            )
        except ImportError:
            self._apply_state(state, reason)

    def _apply_state(self, state: TrayState, reason: str) -> bool:
        """Apply state update (must run on GLib thread when AppIndicator active)."""
        try:
            self._icon.icon = create_icon_image(state)
            title = STATE_TITLES.get(state, "Idle")
            if state == "error" and reason:
                title = f"Error: {reason}"
            self._icon.title = f"Murmur - {title}"
            self._icon.update_menu()
        except Exception as e:
            logger.debug("Tray icon update failed: %s", e)
        return False  # don't repeat the idle callback

    def stop(self) -> None:
        """Stop the pystray icon loop."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as e:
                logger.debug("Tray icon stop failed: %s", e)

    def status_text(self, item: pystray.MenuItem | None = None) -> str:
        """Dynamic status text for the menu item (called by pystray with item arg)."""
        title = STATE_TITLES.get(self._state, "Idle")
        if self._state == "error" and self._error_reason:
            return f"Error: {self._error_reason}"
        return title

    def on_quit_clicked(
        self,
        icon: Any = None,
        item: Any = None,
    ) -> None:
        """Handle Quit menu click."""
        if self._on_quit is not None:
            self._on_quit()
