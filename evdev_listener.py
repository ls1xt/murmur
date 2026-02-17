"""
evdev-based hotkey listener — works natively on Wayland.

Reads keyboard events directly from /dev/input/event* devices via the Linux
input subsystem. Requires the user to be in the 'input' group (same
requirement as ydotool).

This is the recommended hotkey backend for Wayland.
"""

import logging
import threading
from typing import Optional

import evdev
from evdev import InputDevice, categorize, ecodes

from .base import HotkeyListener

logger = logging.getLogger(__name__)


def find_keyboard_devices() -> list[str]:
    """Auto-detect keyboard input devices."""
    keyboards = []
    for path in evdev.list_devices():
        try:
            dev = InputDevice(path)
            caps = dev.capabilities(verbose=False)
            # EV_KEY = 1; check if device has typical keyboard keys
            if ecodes.EV_KEY in caps:
                key_caps = caps[ecodes.EV_KEY]
                # A real keyboard will have letter keys (KEY_A = 30)
                if ecodes.KEY_A in key_caps and ecodes.KEY_Z in key_caps:
                    keyboards.append(path)
                    logger.debug("Found keyboard: %s (%s)", dev.name, path)
            dev.close()
        except (PermissionError, OSError) as e:
            logger.debug("Cannot access %s: %s", path, e)
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
        device_path: Optional[str] = None,
    ):
        super().__init__(mode=mode)
        # Convert key names to evdev key codes
        self._modifier_codes: set[int] = set()
        for name in modifiers:
            code = ecodes.ecodes.get(name)
            if code is None:
                raise ValueError(f"Unknown evdev key name: {name}")
            self._modifier_codes.add(code)

        trigger_code = ecodes.ecodes.get(trigger)
        if trigger_code is None:
            raise ValueError(f"Unknown evdev key name: {trigger}")
        self._trigger_code: int = trigger_code

        self._device_path = device_path
        self._devices: list[InputDevice] = []
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Track which modifier keys are currently held
        self._held_keys: set[int] = set()

    def start(self) -> None:
        """Start listening in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Hotkey listener already running")
            return

        # Open keyboard devices
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
                dev = InputDevice(path)
                # NOTE: do NOT grab() — we only want to monitor, not steal input
                self._devices.append(dev)
                logger.info("Listening on: %s (%s)", dev.name, path)
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
            [ecodes.KEY[c] for c in self._modifier_codes],
            ecodes.KEY[self._trigger_code],
            self.mode,
        )

    def _listen_loop(self) -> None:
        """Main event loop — runs in a background thread."""
        from selectors import DefaultSelector, EVENT_READ

        selector = DefaultSelector()
        for dev in self._devices:
            selector.register(dev, EVENT_READ)

        try:
            while not self._stop_event.is_set():
                # Timeout so we can check the stop event periodically
                events = selector.select(timeout=0.1)
                for key, _ in events:
                    device: InputDevice = key.fileobj  # type: ignore
                    try:
                        for event in device.read():
                            if event.type == ecodes.EV_KEY:
                                self._handle_key_event(event)
                    except OSError:
                        # Device disconnected
                        logger.warning("Device disconnected: %s", device.path)
                        selector.unregister(device)
        finally:
            selector.close()

    def _handle_key_event(self, event: evdev.InputEvent) -> None:
        """Process a single key event."""
        key_event = categorize(event)
        code = event.code

        # key_event.keystate: 0=up, 1=down, 2=hold/repeat
        if key_event.keystate == 1:  # Key down
            self._held_keys.add(code)

            if code == self._trigger_code:
                # Check if all modifiers are held
                if self._modifier_codes.issubset(self._held_keys):
                    self._handle_hotkey_press()

        elif key_event.keystate == 0:  # Key up
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
            try:
                dev.close()
            except OSError:
                pass
        self._devices.clear()
        logger.info("evdev hotkey listener stopped")
