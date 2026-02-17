"""
evdev-based hotkey listener -- works natively on Wayland.

Reads keyboard events directly from /dev/input/event* devices via the Linux
input subsystem. Requires the user to be in the 'input' group.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import Any

import evdev  # type: ignore[import-untyped]
from evdev import categorize, ecodes  # type: ignore[import-untyped]

from murmur.errors import fatal_from_thread
from murmur.hotkey.base import HotkeyListener

logger = logging.getLogger(__name__)

# Typed wrappers for evdev constants (untyped library).
_EV_KEY: int = ecodes.EV_KEY  # type: ignore[reportUnknownMemberType]
_KEY_A: int = ecodes.KEY_A  # type: ignore[reportUnknownMemberType]
_KEY_Z: int = ecodes.KEY_Z  # type: ignore[reportUnknownMemberType]
_ecodes_dict: dict[str, int] = ecodes.ecodes  # type: ignore[reportUnknownMemberType]
_key_names: dict[int, str] = ecodes.KEY  # type: ignore[reportUnknownMemberType]


def _open_device(path: str) -> Any:
    """Open an evdev InputDevice (typed wrapper for untyped library)."""
    return evdev.InputDevice(path)  # type: ignore[reportUnknownMemberType]


def _list_devices() -> list[str]:
    """List available evdev device paths (typed wrapper)."""
    raw: Any = evdev.list_devices()  # type: ignore[reportUnknownMemberType]
    paths: list[Any] = list(raw)  # type: ignore[reportUnknownArgumentType]
    return [str(p) for p in paths]


def find_keyboard_devices() -> list[str]:
    """Auto-detect keyboard input devices."""
    keyboards: list[str] = []
    for path_str in _list_devices():
        try:
            dev: Any = _open_device(path_str)
            caps: dict[int, list[int]] = dev.capabilities(  # type: ignore[reportUnknownMemberType]
                verbose=False
            )
            if _EV_KEY in caps:
                key_caps: list[int] = caps[_EV_KEY]
                if _KEY_A in key_caps and _KEY_Z in key_caps:
                    keyboards.append(path_str)
                    dev_name: str = str(dev.name)  # type: ignore[reportUnknownMemberType]
                    logger.debug("Found keyboard: %s (%s)", dev_name, path_str)
            dev.close()  # type: ignore[reportUnknownMemberType]
        except (PermissionError, OSError) as e:
            logger.debug("Cannot access %s: %s", path_str, e)
    return keyboards


class EvdevHotkeyListener(HotkeyListener):
    """
    Listens for a hotkey combination using evdev.

    The hotkey is defined by a set of modifier key names (e.g. KEY_LEFTCTRL,
    KEY_LEFTSHIFT) and a trigger key (e.g. KEY_SPACE). When all modifiers are
    held and the trigger is pressed, the hotkey fires.
    """

    def __init__(
        self,
        modifiers: list[str],
        trigger: str,
        mode: str = "push_to_talk",
        device_path: str | None = None,
    ) -> None:
        super().__init__(mode=mode)
        self._modifier_codes: set[int] = set()
        for name in modifiers:
            code: int | None = _ecodes_dict.get(name)
            if code is None:
                raise ValueError(f"Unknown evdev key name: {name}")
            self._modifier_codes.add(code)

        trigger_code: int | None = _ecodes_dict.get(trigger)
        if trigger_code is None:
            raise ValueError(f"Unknown evdev key name: {trigger}")
        self._trigger_code: int = trigger_code

        self._device_path = device_path
        self._devices: list[Any] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._held_keys: set[int] = set()

    def start(self) -> None:
        """Start listening in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Hotkey listener already running")
            return

        if self._device_path:
            paths = [self._device_path]
        else:
            paths = find_keyboard_devices()
            if not paths:
                raise RuntimeError(
                    "No keyboard devices found. Are you in the 'input' group?\n"
                    "  sudo usermod -aG input $USER  (then log out and back in)"
                )

        self._devices = []
        for path in paths:
            try:
                dev: Any = _open_device(path)
                self._devices.append(dev)
                dev_name: str = str(dev.name)  # type: ignore[reportUnknownMemberType]
                logger.info("Listening on: %s (%s)", dev_name, path)
            except (PermissionError, OSError) as e:
                logger.warning("Cannot open %s: %s", path, e)

        if not self._devices:
            raise RuntimeError(
                "Could not open any keyboard devices. Check permissions."
            )

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info(
            "evdev hotkey listener started (modifiers=%s, trigger=%s, mode=%s)",
            [_key_names[c] for c in self._modifier_codes],
            _key_names[self._trigger_code],
            self.mode,
        )

    def _listen_loop(self) -> None:
        """Main event loop -- runs in a background thread."""
        from selectors import EVENT_READ, DefaultSelector

        selector = DefaultSelector()
        for dev in self._devices:
            selector.register(dev, EVENT_READ)

        try:
            while not self._stop_event.is_set():
                events = selector.select(timeout=0.1)
                for key, _ in events:
                    device: Any = key.fileobj
                    try:
                        for event in device.read():  # type: ignore[reportUnknownMemberType]
                            ev_type: int = int(event.type)  # type: ignore[reportUnknownMemberType]
                            if ev_type == _EV_KEY:
                                self._handle_key_event(event)
                    except OSError:
                        dev_path: str = str(device.path)  # type: ignore[reportUnknownMemberType]
                        fatal_from_thread(f"Input device disconnected: {dev_path}")
        finally:
            selector.close()

    def _handle_key_event(self, event: Any) -> None:
        """Process a single key event."""
        key_event: Any = categorize(event)  # type: ignore[reportUnknownVariableType]
        code: int = int(event.code)  # type: ignore[reportUnknownArgumentType]
        keystate: int = int(key_event.keystate)  # type: ignore[reportUnknownMemberType]

        # keystate: 0=up, 1=down, 2=hold/repeat
        if keystate == 1:  # Key down
            self._held_keys.add(code)
            if code == self._trigger_code and self._modifier_codes.issubset(
                self._held_keys
            ):
                self._handle_hotkey_press()
        elif keystate == 0:  # Key up
            self._held_keys.discard(code)
            if code == self._trigger_code:
                self._handle_hotkey_release()

    def stop(self) -> None:
        """Stop listening and release devices."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        for dev in self._devices:
            with contextlib.suppress(OSError):
                dev.close()  # type: ignore[reportUnknownMemberType]
        self._devices.clear()
        logger.info("evdev hotkey listener stopped")
