# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""StatusNotifierItem (SNI) tray backend via Gio.DBus for Sway/waybar.

gi.repository (GLib, Gio) has no type stubs -- pyright Unknown-member
diagnostics are suppressed at file level above.
"""

from __future__ import annotations

import contextlib
import logging
import os
import struct
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

# SNI D-Bus XML interface definition (minimal)
_SNI_XML = """\
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <signal name="NewIcon"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""


def _create_icon_image(state: str) -> Any:
    """Create a 64x64 RGBA PIL image with a colored circle for the state."""
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


def _rgba_to_argb32(img: Any) -> bytes:
    """Convert a PIL RGBA image to ARGB32 big-endian bytes for SNI."""
    raw: bytes = img.tobytes()
    result = bytearray(len(raw))
    for i in range(0, len(raw), 4):
        r, g, b, a = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
        struct.pack_into(">BBBB", result, i, a, r, g, b)
    return bytes(result)


class SniTray:
    """StatusNotifierItem tray backend via Gio.DBus for Sway/waybar."""

    def __init__(self, on_quit: Callable[[], None] | None) -> None:
        self._on_quit = on_quit
        self._state = "idle"
        self._conn: Any = None
        self._owner_id: int = 0
        self._reg_id: int = 0
        self._loop: Any = None
        self._loop_thread: threading.Thread | None = None
        self._bus_name: str = ""
        self._node_info: Any = None

    def start(self) -> None:
        """Register SNI object on the session D-Bus and start GLib loop."""
        from gi.repository import Gio, GLib  # type: ignore[import-untyped]

        self._node_info = Gio.DBusNodeInfo.new_for_xml(_SNI_XML)
        iface_info: Any = self._node_info.interfaces[0]

        self._conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        self._reg_id = self._conn.register_object(
            "/StatusNotifierItem",
            iface_info,
            self._handle_method_call,
            self._handle_get_property,
            None,
        )

        self._bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self._owner_id = Gio.bus_own_name(
            Gio.BusType.SESSION,
            self._bus_name,
            Gio.BusNameOwnerFlags.NONE,
            None,
            self._on_name_acquired,
            None,
        )

        self._loop = GLib.MainLoop()
        loop_run: Any = self._loop.run
        self._loop_thread = threading.Thread(
            target=loop_run, daemon=True
        )
        self._loop_thread.start()
        logger.info("SNI tray started (bus=%s)", self._bus_name)

    def _on_name_acquired(
        self,
        conn: Any,
        name: Any,
        *args: Any,
    ) -> None:
        """Called when the bus name is acquired. Register with watcher."""
        from gi.repository import GLib  # type: ignore[import-untyped]

        try:
            conn.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (str(name),)),
                None,
                0,
                -1,
                None,
            )
            logger.info("Registered with StatusNotifierWatcher")
        except Exception as e:
            logger.warning("Failed to register with watcher: %s", e)

    def _handle_method_call(
        self,
        conn: Any,
        sender: Any,
        path: Any,
        iface: Any,
        method: Any,
        params: Any,
        invocation: Any,
    ) -> None:
        """Handle D-Bus method calls (Activate, ContextMenu)."""
        method_name: str = str(method)
        if method_name == "Activate" and self._on_quit is not None:
            self._on_quit()
        invocation.return_value(None)

    def _handle_get_property(
        self,
        conn: Any,
        sender: Any,
        path: Any,
        iface: Any,
        prop_name: Any,
    ) -> Any:
        """Handle D-Bus property reads."""
        from gi.repository import GLib  # type: ignore[import-untyped]

        _v: Any = GLib.Variant
        name: str = str(prop_name)
        if name == "Category":
            return _v("s", "ApplicationStatus")
        if name == "Id":
            return _v("s", "murmur")
        if name == "Status":
            return _v("s", "Active")
        if name == "Title":
            title = _STATE_TITLES.get(self._state, "Idle")
            return _v("s", f"Murmur - {title}")
        if name == "IconName":
            return _v("s", "")
        if name == "IconPixmap":
            try:
                img = _create_icon_image(self._state)
                pixmap_bytes = _rgba_to_argb32(img)
                return _v(
                    "a(iiay)",
                    [(ICON_SIZE, ICON_SIZE, pixmap_bytes)],
                )
            except ImportError:
                return _v("a(iiay)", [])
        if name == "ItemIsMenu":
            return _v("b", False)
        return None

    def set_state(self, state: str) -> None:
        """Update the SNI state. Thread-safe via GLib.idle_add."""
        self._state = state
        try:
            from gi.repository import GLib  # type: ignore[import-untyped]

            GLib.idle_add(self._emit_new_icon)
        except ImportError:
            pass

    def _emit_new_icon(self) -> bool:
        """Emit NewIcon signal to trigger waybar to re-read properties."""
        if self._conn is not None:
            try:
                self._conn.emit_signal(
                    None,
                    "/StatusNotifierItem",
                    "org.kde.StatusNotifierItem",
                    "NewIcon",
                    None,
                )
            except Exception as e:
                logger.debug("Failed to emit NewIcon: %s", e)
        return False

    def stop(self) -> None:
        """Stop the SNI tray: unregister, unown, quit loop."""
        from gi.repository import Gio  # type: ignore[import-untyped]

        if self._conn is not None and self._reg_id:
            with contextlib.suppress(Exception):
                self._conn.unregister_object(self._reg_id)
            self._reg_id = 0

        if self._owner_id:
            Gio.bus_unown_name(self._owner_id)
            self._owner_id = 0

        if self._loop is not None:
            self._loop.quit()
            self._loop = None
