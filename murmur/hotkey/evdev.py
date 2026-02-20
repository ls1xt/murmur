"""
evdev-based hotkey listener -- works natively on Wayland.

Reads keyboard events directly from /dev/input/event* devices via the Linux
input subsystem. Grabs keyboards and forwards non-hotkey events through UInput
virtual devices so hotkey keys are suppressed while all other input passes
through transparently.

Requires the user to be in the 'input' group.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

import evdev  # type: ignore[import-untyped]
from evdev import UInput, categorize, ecodes  # type: ignore[import-untyped]

from murmur.config import HotkeyBinding
from murmur.errors import fatal_from_thread
from murmur.hotkey.base import HotkeyListener

logger = logging.getLogger(__name__)

# Typed wrappers for evdev constants (untyped library).
_EV_KEY: int = ecodes.EV_KEY  # type: ignore[reportUnknownMemberType]
_KEY_A: int = ecodes.KEY_A  # type: ignore[reportUnknownMemberType]
_KEY_Z: int = ecodes.KEY_Z  # type: ignore[reportUnknownMemberType]
_ecodes_dict: dict[str, int] = ecodes.ecodes  # type: ignore[reportUnknownMemberType]
_key_names: dict[int, str] = ecodes.KEY  # type: ignore[reportUnknownMemberType]

# Actions that use hold-to-activate (press to start, release to stop).
# These get debounced release to filter spurious key-up events.
_DEBOUNCED_ACTIONS: frozenset[str] = frozenset({"push_to_talk", "copy_to_clipboard"})


def _open_device(path: str) -> Any:
    """Open an evdev InputDevice (typed wrapper for untyped library)."""
    return evdev.InputDevice(path)  # type: ignore[reportUnknownMemberType]


def _list_devices() -> list[str]:
    """List available evdev device paths (typed wrapper)."""
    raw: Any = evdev.list_devices()  # type: ignore[reportUnknownMemberType]
    paths: list[Any] = list(raw)  # type: ignore[reportUnknownArgumentType]
    return [str(p) for p in paths]


def find_keyboard_devices() -> list[str]:
    """Auto-detect physical keyboard input devices.

    Skips virtual/uinput devices to avoid grabbing the ydotoold injection
    device or leftover murmur UInput devices from a previous run.
    Virtual devices are identified by phys=="" (ydotoold) or
    phys=="py-evdev-uinput" (py-evdev UInput, used by murmur itself).
    """
    keyboards: list[str] = []
    for path_str in _list_devices():
        try:
            dev: Any = _open_device(path_str)
            # Skip virtual devices: real keyboards have a USB/PCI phys path
            # (e.g. "usb-0000:00:14.0-1/input0"). Virtual devices have
            # phys="" (ydotoold) or phys="py-evdev-uinput" (py-evdev UInput).
            phys: str = str(dev.phys or "")  # type: ignore[reportUnknownMemberType]
            if not phys or phys == "py-evdev-uinput":
                dev_name_skip: str = str(dev.name)  # type: ignore[reportUnknownMemberType]
                logger.debug(
                    "Skipping virtual device: %s (%s)", dev_name_skip, path_str
                )
                dev.close()  # type: ignore[reportUnknownMemberType]
                continue
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


@dataclass
class _ResolvedBinding:
    """A binding with key names resolved to evdev key codes."""

    modifier_codes: set[int]
    trigger_code: int
    action: str
    tmux_target: str = ""
    tmux_keys: str = ""


class EvdevHotkeyListener(HotkeyListener):
    """
    Listens for hotkey combinations using evdev with grab-and-forward.

    Grabs all keyboards via EVIOCGRAB, creates UInput virtual devices to
    forward non-hotkey events, and suppresses hotkey combos. Manages
    modifier state on hotkey fire/release so the compositor sees clean
    modifier transitions.

    Push-to-talk releases are debounced (default 300 ms) to filter
    spurious key-up events that some systems generate periodically.
    """

    def __init__(
        self,
        bindings: list[HotkeyBinding],
        device_path: str | None = None,
        push_to_talk_debounce_ms: int = 300,
    ) -> None:
        super().__init__()
        self._bindings: list[_ResolvedBinding] = []
        self._all_modifier_codes: set[int] = set()

        for binding in bindings:
            mod_codes: set[int] = set()
            for name in binding.modifiers:
                code: int | None = _ecodes_dict.get(name)
                if code is None:
                    raise ValueError(f"Unknown evdev key name: {name}")
                mod_codes.add(code)

            trigger_code: int | None = _ecodes_dict.get(binding.trigger)
            if trigger_code is None:
                raise ValueError(f"Unknown evdev key name: {binding.trigger}")

            self._bindings.append(
                _ResolvedBinding(
                    modifier_codes=mod_codes,
                    trigger_code=trigger_code,
                    action=binding.action,
                    tmux_target=binding.tmux_target,
                    tmux_keys=binding.tmux_keys,
                )
            )
            self._all_modifier_codes.update(mod_codes)

        self._device_path = device_path
        self._devices: list[tuple[Any, Any]] = []  # (physical_dev, uinput)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._held_keys: set[int] = set()
        self._suppressed_triggers: set[int] = set()

        # Debounce state: maps trigger code -> (release_timestamp, binding, uinput)
        # When a debounced action's trigger key goes up, we don't dispatch the
        # release immediately -- instead we wait push_to_talk_debounce_ms before
        # dispatching.  If the key goes down again within that window (spurious
        # event), we cancel the pending release.
        self._push_to_talk_debounce_sec: float = push_to_talk_debounce_ms / 1000.0
        self._pending_releases: dict[int, tuple[float, _ResolvedBinding, Any]] = {}

    def start(self) -> None:
        """Start listening in a background thread with grab-and-forward."""
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
                dev.grab()  # type: ignore[reportUnknownMemberType]
                uinput: Any = UInput.from_device(dev, name=f"murmur-{dev.name}")  # type: ignore[reportUnknownMemberType]
                self._devices.append((dev, uinput))
                dev_name: str = str(dev.name)  # type: ignore[reportUnknownMemberType]
                logger.info("Grabbed and forwarding: %s (%s)", dev_name, path)
            except (PermissionError, OSError) as e:
                logger.warning("Cannot open %s: %s", path, e)

        if not self._devices:
            raise RuntimeError(
                "Could not open any keyboard devices. Check permissions."
            )

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

        for binding in self._bindings:
            mod_names = [_key_names.get(c, str(c)) for c in binding.modifier_codes]
            trigger_name = _key_names.get(
                binding.trigger_code, str(binding.trigger_code)
            )
            logger.info(
                "Binding: %s+%s -> %s",
                "+".join(mod_names),
                trigger_name,
                binding.action,
            )

    def _listen_loop(self) -> None:
        """Main event loop -- runs in a background thread."""
        from selectors import EVENT_READ, DefaultSelector

        selector = DefaultSelector()
        for dev, _uinput in self._devices:
            selector.register(dev, EVENT_READ)

        try:
            while not self._stop_event.is_set():
                events = selector.select(timeout=0.1)

                # Fire any debounced releases whose window has expired.
                self._check_pending_releases()

                for key, _ in events:
                    device: Any = key.fileobj
                    # Find the matching uinput for this device
                    uinput: Any = None
                    for d, u in self._devices:
                        if d is device:
                            uinput = u
                            break
                    try:
                        for event in device.read():  # type: ignore[reportUnknownMemberType]
                            ev_type: int = int(event.type)  # type: ignore[reportUnknownMemberType]
                            if ev_type == _EV_KEY:
                                self._handle_key_event(event, uinput)
                            else:
                                # Forward non-key events unconditionally
                                if uinput is not None:
                                    uinput.write_event(event)  # type: ignore[reportUnknownMemberType]
                                    uinput.syn()  # type: ignore[reportUnknownMemberType]
                    except OSError:
                        dev_path: str = str(device.path)  # type: ignore[reportUnknownMemberType]
                        fatal_from_thread(f"Input device disconnected: {dev_path}")
        finally:
            selector.close()

    def _check_pending_releases(self, now: float | None = None) -> None:
        """Fire debounced releases whose window has elapsed.

        Called from the listen loop on each iteration.  Can also be called
        directly (e.g. in tests) with an explicit ``now`` timestamp to
        simulate time passage without sleeping.
        """
        ts = now if now is not None else time.monotonic()
        expired = [
            (code, binding, uinput)
            for code, (t, binding, uinput) in list(self._pending_releases.items())
            if ts - t >= self._push_to_talk_debounce_sec
        ]
        for code, binding, uinput in expired:
            del self._pending_releases[code]
            self._suppressed_triggers.discard(code)
            self._dispatch_release(binding.action)
            logger.debug(
                "Debounce fired: dispatched release for code=%d action=%s",
                code,
                binding.action,
            )
            # Restore modifier state: re-press still-held modifiers, explicitly
            # release any that were released during the debounce window
            # (their key-up events were suppressed while the trigger was active).
            if uinput is not None:
                for mod_code in binding.modifier_codes:
                    if mod_code in self._held_keys:
                        uinput.write(  # type: ignore[reportUnknownMemberType]
                            _EV_KEY, mod_code, 1
                        )
                    else:
                        # Modifier was released during debounce window but its
                        # key-up was suppressed -- send the explicit release now.
                        uinput.write(  # type: ignore[reportUnknownMemberType]
                            _EV_KEY, mod_code, 0
                        )
                uinput.syn()  # type: ignore[reportUnknownMemberType]

    def _handle_key_event(self, event: Any, uinput: Any) -> None:
        """Process a single key event with grab-and-forward logic."""
        key_event: Any = categorize(event)  # type: ignore[reportUnknownVariableType]
        code: int = int(event.code)  # type: ignore[reportUnknownArgumentType]
        keystate: int = int(key_event.keystate)  # type: ignore[reportUnknownMemberType]

        # keystate: 0=up, 1=down, 2=hold/repeat
        if keystate == 1:  # Key down
            self._held_keys.add(code)

            # Cancel any pending debounced release for this trigger code.
            # This handles spurious key-up/key-down pairs: the key was never
            # actually released, so we just resume the active hotkey silently.
            if code in self._pending_releases:
                del self._pending_releases[code]
                logger.debug(
                    "Debounce cancelled: trigger re-pressed, code=%d (spurious key-up)",
                    code,
                )
                # The trigger is still in _suppressed_triggers; don't re-fire.
                return

            # Check all bindings for a match
            matched_binding: _ResolvedBinding | None = None
            for binding in self._bindings:
                if code == binding.trigger_code and binding.modifier_codes.issubset(
                    self._held_keys
                ):
                    matched_binding = binding
                    break

            if matched_binding is not None:
                # Suppress the trigger key
                self._suppressed_triggers.add(code)

                # Release modifiers in UInput so compositor sees clean state
                if uinput is not None:
                    for mod_code in matched_binding.modifier_codes:
                        if mod_code in self._held_keys:
                            uinput.write(  # type: ignore[reportUnknownMemberType]
                                _EV_KEY, mod_code, 0
                            )
                    uinput.syn()  # type: ignore[reportUnknownMemberType]

                self._dispatch_action(
                    matched_binding.action,
                    matched_binding.tmux_target,
                    matched_binding.tmux_keys,
                )
            else:
                # Not a hotkey -- forward the event
                if uinput is not None:
                    uinput.write_event(event)  # type: ignore[reportUnknownMemberType]
                    uinput.syn()  # type: ignore[reportUnknownMemberType]

        elif keystate == 0:  # Key up
            self._held_keys.discard(code)

            if code in self._suppressed_triggers:
                # Find which binding this trigger belongs to
                released_binding: _ResolvedBinding | None = None
                for binding in self._bindings:
                    if code == binding.trigger_code:
                        released_binding = binding
                        break

                if released_binding is not None:
                    if released_binding.action in _DEBOUNCED_ACTIONS:
                        # Schedule a debounced release instead of firing immediately.
                        # Trigger stays in _suppressed_triggers until debounce fires.
                        self._pending_releases[code] = (
                            time.monotonic(),
                            released_binding,
                            uinput,
                        )
                        logger.debug(
                            "Debouncing release: code=%d action=%s (%.0f ms window)",
                            code,
                            released_binding.action,
                            self._push_to_talk_debounce_sec * 1000,
                        )
                    else:
                        # Toggle actions: release immediately, no debounce needed.
                        self._suppressed_triggers.discard(code)
                        self._dispatch_release(released_binding.action)

                        # Restore modifiers: re-press those physically held
                        if uinput is not None:
                            for mod_code in released_binding.modifier_codes:
                                if mod_code in self._held_keys:
                                    uinput.write(  # type: ignore[reportUnknownMemberType]
                                        _EV_KEY, mod_code, 1
                                    )
                            uinput.syn()  # type: ignore[reportUnknownMemberType]
            elif code in self._all_modifier_codes and self._suppressed_triggers:
                # Modifier released while a hotkey trigger is active (or in its
                # debounce window) -- suppress the key-up so the compositor
                # doesn't see a spurious modifier release.
                # _check_pending_releases() will send the explicit release if
                # the modifier was released during a debounce window.
                pass
            else:
                # Normal key up -- forward
                if uinput is not None:
                    uinput.write_event(event)  # type: ignore[reportUnknownMemberType]
                    uinput.syn()  # type: ignore[reportUnknownMemberType]

        elif keystate == 2:  # Key repeat/hold
            if code in self._suppressed_triggers:
                # Suppress repeats for active hotkey triggers
                pass
            elif code in self._all_modifier_codes and self._suppressed_triggers:
                # Suppress modifier repeats while a hotkey is active
                pass
            else:
                # Forward repeats for normal keys
                if uinput is not None:
                    uinput.write_event(event)  # type: ignore[reportUnknownMemberType]
                    uinput.syn()  # type: ignore[reportUnknownMemberType]

    def stop(self) -> None:
        """Stop listening and release devices."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        for dev, uinput in self._devices:
            with contextlib.suppress(OSError):
                dev.ungrab()  # type: ignore[reportUnknownMemberType]
            with contextlib.suppress(OSError):
                uinput.close()  # type: ignore[reportUnknownMemberType]
            with contextlib.suppress(OSError):
                dev.close()  # type: ignore[reportUnknownMemberType]
        self._devices.clear()
        logger.info("evdev hotkey listener stopped")
