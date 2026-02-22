"""
pynput-based hotkey listener -- works on macOS without accessibility APIs.

Uses pynput's raw keyboard.Listener with manual modifier-state tracking to
detect configured key bindings reliably, including Ctrl+Alt combinations.

Supports optional per-binding event suppression via the darwin_intercept
callback.  Bindings with ``suppress=True`` (e.g. F12 push-to-talk) use an
active CGEventTap so the key never reaches the foreground application.
Bindings without suppression use a passive listen-only tap.

Only imported on darwin (via the hotkey factory). pynput is an optional
dependency; an ImportError here surfaces a clear message to the user.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from murmur.config import HotkeyBinding
from murmur.hotkey.base import HotkeyListener

logger = logging.getLogger(__name__)

# Canonical modifier keys (after listener.canonical()).  Left/right variants
# collapse to these, so checking this set is sufficient.
_MODIFIER_KEYS: frozenset[Key] = frozenset(
    {
        Key.ctrl,
        Key.alt,
        Key.shift,
        Key.cmd,
        Key.ctrl_l,
        Key.ctrl_r,
        Key.alt_l,
        Key.alt_r,
        Key.shift_l,
        Key.shift_r,
        Key.cmd_l,
        Key.cmd_r,
    }
)


# ---------------------------------------------------------------------------
# Evdev-to-pynput canonical key translation table
# ---------------------------------------------------------------------------
# Maps evdev key names (as used in HotkeyBinding.modifiers / .trigger) to
# canonical pynput Key or KeyCode values.  "Canonical" means the left/right
# variant-agnostic form that listener.canonical() returns, so set membership
# tests unify e.g. Key.ctrl_l and Key.ctrl_r → Key.ctrl.

_EVDEV_TO_PYNPUT_CANONICAL: dict[str, Key | KeyCode] = {
    # Ctrl
    "KEY_LEFTCTRL": Key.ctrl,
    "KEY_RIGHTCTRL": Key.ctrl,
    # Alt / Option
    "KEY_LEFTALT": Key.alt,
    "KEY_RIGHTALT": Key.alt,
    # Shift
    "KEY_LEFTSHIFT": Key.shift,
    "KEY_RIGHTSHIFT": Key.shift,
    # Meta / Cmd / Super
    "KEY_LEFTMETA": Key.cmd,
    "KEY_RIGHTMETA": Key.cmd,
    # Common special keys
    "KEY_SPACE": Key.space,
    "KEY_ENTER": Key.enter,
    "KEY_BACKSPACE": Key.backspace,
    "KEY_ESC": Key.esc,
    "KEY_TAB": Key.tab,
    "KEY_DELETE": Key.delete,
    # Function keys
    "KEY_F1": Key.f1,
    "KEY_F2": Key.f2,
    "KEY_F3": Key.f3,
    "KEY_F4": Key.f4,
    "KEY_F5": Key.f5,
    "KEY_F6": Key.f6,
    "KEY_F7": Key.f7,
    "KEY_F8": Key.f8,
    "KEY_F9": Key.f9,
    "KEY_F10": Key.f10,
    "KEY_F11": Key.f11,
    "KEY_F12": Key.f12,
}


# ---------------------------------------------------------------------------
# Evdev-name → macOS CGEvent keycode table
# ---------------------------------------------------------------------------
# CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode) returns the
# hardware virtual key code (kVK_*) from Carbon/HIToolbox/Events.h.
# pynput's canonical() loses this VK after translating Key.fN to a
# symbol-based KeyCode (vk=None), so we maintain our own static table here
# for keys that may be used as suppress=True triggers.

_EVDEV_TO_MACOS_VK: dict[str, int] = {
    # Function keys (kVK_F* from Carbon Events.h)
    "KEY_F1": 0x7A,
    "KEY_F2": 0x78,
    "KEY_F3": 0x63,
    "KEY_F4": 0x76,
    "KEY_F5": 0x60,
    "KEY_F6": 0x61,
    "KEY_F7": 0x62,
    "KEY_F8": 0x64,
    "KEY_F9": 0x65,
    "KEY_F10": 0x6D,
    "KEY_F11": 0x67,
    "KEY_F12": 0x6F,
    # Common special keys
    "KEY_SPACE": 0x31,
    "KEY_ENTER": 0x24,
    "KEY_BACKSPACE": 0x33,
    "KEY_ESC": 0x35,
    "KEY_TAB": 0x30,
    "KEY_DELETE": 0x75,
    # Alpha keys (ANSI positions, layout-independent)
    "KEY_A": 0x00,
    "KEY_B": 0x0B,
    "KEY_C": 0x08,
    "KEY_D": 0x02,
    "KEY_E": 0x0E,
    "KEY_F": 0x03,
    "KEY_G": 0x05,
    "KEY_H": 0x04,
    "KEY_I": 0x22,
    "KEY_J": 0x26,
    "KEY_K": 0x28,
    "KEY_L": 0x25,
    "KEY_M": 0x2E,
    "KEY_N": 0x2D,
    "KEY_O": 0x1F,
    "KEY_P": 0x23,
    "KEY_Q": 0x0C,
    "KEY_R": 0x0F,
    "KEY_S": 0x01,
    "KEY_T": 0x11,
    "KEY_U": 0x20,
    "KEY_V": 0x09,
    "KEY_W": 0x0D,
    "KEY_X": 0x07,
    "KEY_Y": 0x10,
    "KEY_Z": 0x06,
    # Digit keys (main row)
    "KEY_0": 0x1D,
    "KEY_1": 0x12,
    "KEY_2": 0x13,
    "KEY_3": 0x14,
    "KEY_4": 0x15,
    "KEY_5": 0x17,
    "KEY_6": 0x16,
    "KEY_7": 0x1A,
    "KEY_8": 0x1C,
    "KEY_9": 0x19,
}


def _translate_evdev_name(name: str) -> Key | KeyCode:
    """Translate a single evdev key name to its canonical pynput equivalent.

    Handles:
    - Explicit entries in _EVDEV_TO_PYNPUT_CANONICAL (modifiers, specials).
    - Single-letter keys: KEY_A..KEY_Z → KeyCode.from_char('a'..'z').
    - Single-digit keys: KEY_0..KEY_9 → KeyCode.from_char('0'..'9').

    Raises ValueError for unknown names.
    """
    if name in _EVDEV_TO_PYNPUT_CANONICAL:
        return _EVDEV_TO_PYNPUT_CANONICAL[name]

    # Single alpha key: KEY_A .. KEY_Z
    if name.startswith("KEY_") and len(name) == 5 and name[4].isalpha():
        return KeyCode.from_char(name[4].lower())

    # Single digit key: KEY_0 .. KEY_9
    if name.startswith("KEY_") and len(name) == 5 and name[4].isdigit():
        return KeyCode.from_char(name[4])

    raise ValueError(
        f"Unknown evdev key name {name!r}. "
        "Add it to _EVDEV_TO_PYNPUT_CANONICAL or extend _translate_evdev_name."
    )


# ---------------------------------------------------------------------------
# Internal resolved binding
# ---------------------------------------------------------------------------


@dataclass
class _ResolvedBinding:
    """A HotkeyBinding with key names translated to canonical pynput forms."""

    modifiers: frozenset[Key | KeyCode]
    trigger: Key | KeyCode
    trigger_vk: int | None  # macOS CGEvent keycode; None if unknown
    action: str
    binding: HotkeyBinding = field(default_factory=HotkeyBinding)
    suppress: bool = False


def _resolve_bindings(bindings: list[HotkeyBinding]) -> list[_ResolvedBinding]:
    """Translate a list of HotkeyBindings to _ResolvedBindings.

    Raises ValueError if any evdev key name is unknown.
    """
    import sys

    resolved: list[_ResolvedBinding] = []
    for binding in bindings:
        # On macOS, Alt/Option transforms key characters at the OS level
        # (e.g. Alt+M → 'µ'), so Alt-based hotkeys break on non-US layouts.
        # Warn the user and suggest Cmd (KEY_LEFTMETA / KEY_RIGHTMETA) instead.
        if sys.platform == "darwin" and any(
            m in ("KEY_LEFTALT", "KEY_RIGHTALT") for m in binding.modifiers
        ):
            logger.warning(
                "Binding %s+%s uses Alt/Option as a modifier. On macOS, "
                "Option transforms key characters (e.g. Option+M → 'µ'), "
                "which breaks hotkeys on non-US keyboard layouts. "
                "Consider using Cmd (KEY_LEFTMETA) instead.",
                "+".join(binding.modifiers),
                binding.trigger,
            )
        mod_keys: set[Key | KeyCode] = set()
        for mod_name in binding.modifiers:
            mod_keys.add(_translate_evdev_name(mod_name))
        trigger_key = _translate_evdev_name(binding.trigger)
        # Look up the macOS CGEvent keycode from the evdev name directly.
        # pynput's canonical() loses VK info for function keys, so we maintain
        # _EVDEV_TO_MACOS_VK to get a reliable VK for darwin_intercept.
        trigger_vk: int | None = _EVDEV_TO_MACOS_VK.get(binding.trigger)
        resolved.append(
            _ResolvedBinding(
                modifiers=frozenset(mod_keys),
                trigger=trigger_key,
                trigger_vk=trigger_vk,
                action=binding.action,
                binding=binding,
                suppress=binding.suppress,
            )
        )
        logger.debug(
            "Resolved binding: %s+%s -> %s",
            "+".join(str(m) for m in mod_keys),
            trigger_key,
            binding.action,
        )
    return resolved


# ---------------------------------------------------------------------------
# PynputHotkeyListener
# ---------------------------------------------------------------------------


class PynputHotkeyListener(HotkeyListener):
    """
    Hotkey listener using pynput's raw keyboard.Listener.

    Uses manual modifier-set tracking (not GlobalHotKeys) to detect
    configured key bindings.  GlobalHotKeys silently fails for Ctrl+Alt
    combinations on macOS (pynput GitHub issue #297, unresolved).

    Bindings with ``suppress=True`` use an active CGEventTap
    (``kCGEventTapOptionDefault``) so the key never reaches the foreground
    application.  Bindings without suppression use a passive listen-only tap.
    The active tap is installed only when at least one binding requires it.

    ``push_to_talk_debounce_ms`` is accepted for API compatibility with
    EvdevHotkeyListener but is not used -- macOS does not generate spurious
    key-up events the way some Linux setups do.
    """

    def __init__(
        self,
        bindings: list[HotkeyBinding],
        push_to_talk_debounce_ms: int = 300,
        stop_on_keypress: bool = True,
    ) -> None:
        super().__init__()
        self._stop_on_keypress = stop_on_keypress
        self._bindings: list[_ResolvedBinding] = _resolve_bindings(bindings)
        self._held: set[Key | KeyCode] = set()
        # VK codes of currently-held keys — used as a layout-independent
        # fallback for trigger matching (see _on_press / _on_release).
        self._held_vks: set[int] = set()
        self._listener: keyboard.Listener | None = None
        self._push_to_talk_debounce_ms: int = push_to_talk_debounce_ms
        self._suppressed_vk_codes: set[int] = set()
        # Monotonic timestamp of the last push-to-talk real release.
        # macOS generates phantom Space-press events immediately after release
        # (while Ctrl+Option are still held) and also phantom Space-release
        # events that can arrive seconds later.  We block re-activation for
        # push_to_talk_debounce_ms after the real release to suppress both.
        # Note: we cannot rely on Ctrl/Alt release events to clear the guard
        # because macOS does not deliver modifier-key releases through the
        # CGEventTap in this configuration.
        self._ptt_last_release_time: float = 0.0
        # True between a dispatched push_to_talk press and its release.
        # Phantom Space-release events from macOS can arrive seconds after the
        # real release and fire again during a subsequent session (when Space
        # is back in self._held).  Gating release dispatch on this flag ensures
        # each press is matched to exactly one release.
        self._ptt_press_dispatched: bool = False
        # id() of the HotkeyBinding that set _ptt_press_dispatched.
        # Key-repeat suppression only applies to the same binding — a different
        # toggle binding must always be able to stop a running session.
        self._ptt_dispatched_binding_id: int | None = None

    def start(self) -> None:
        """Start listening for hotkeys in a background thread.

        Creates a fresh keyboard.Listener instance each call -- pynput
        threads cannot be restarted after stop().
        """
        if self._listener is not None and self._listener.is_alive():
            logger.warning("PynputHotkeyListener already running")
            return

        has_suppress = any(b.suppress for b in self._bindings)
        listener_kwargs: dict[str, Any] = {
            "on_press": self._on_press,
            "on_release": self._on_release,
        }
        if has_suppress:
            # pynput's base Listener filters kwargs by platform prefix ("darwin_")
            # before storing in self._options; the darwin backend then reads
            # self._options.get("intercept").  So the kwarg must be named
            # "darwin_intercept", not "intercept".
            listener_kwargs["darwin_intercept"] = self._darwin_intercept
        self._listener = keyboard.Listener(**listener_kwargs)
        self._listener.start()

        # Re-canonicalize binding keys using the live listener.  Some keys
        # like Key.space (char=' ') have a different canonical form at runtime
        # (e.g. KeyCode(vk=49) on macOS) than the object returned by
        # _translate_evdev_name.  Without this step, Key.space in a binding
        # would never match the <49> seen in on_press events.
        self._bindings = [
            _ResolvedBinding(
                modifiers=frozenset(self._listener.canonical(m) for m in b.modifiers),
                trigger=self._listener.canonical(b.trigger),
                trigger_vk=b.trigger_vk,  # preserved from _resolve_bindings
                action=b.action,
                binding=b.binding,
                suppress=b.suppress,
            )
            for b in self._bindings
        ]

        # Build set of VK codes for suppress=True bindings (for darwin_intercept).
        # Use trigger_vk from _EVDEV_TO_MACOS_VK -- reliable even after
        # canonicalization which loses VK info for function keys.
        self._suppressed_vk_codes = {
            b.trigger_vk
            for b in self._bindings
            if b.suppress and b.trigger_vk is not None
        }

        logger.info("pynput hotkey listener started")

        for binding in self._bindings:
            logger.info(
                "Binding: %s+%s -> %s",
                "+".join(str(m) for m in binding.modifiers),
                binding.trigger,
                binding.action,
            )

    def stop(self) -> None:
        """Stop listening and release resources."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        self._held.clear()
        self._suppressed_vk_codes = set()
        self._held_vks = set()
        self._ptt_last_release_time = 0.0
        self._ptt_press_dispatched = False
        logger.info("pynput hotkey listener stopped")

    def _darwin_intercept(self, event_type: int, event: object) -> object | None:
        """Suppress key events for bindings with suppress=True.

        Called by pynput after on_press/on_release have been dispatched.
        Returning None suppresses the event (not forwarded to the OS).
        Returning the event passes it through normally.

        Only active when at least one binding has suppress=True.
        """
        if not self._suppressed_vk_codes:
            return event
        try:
            from Quartz import (  # pyright: ignore[reportMissingImports]
                CGEventGetIntegerValueField,
                kCGKeyboardEventKeycode,
            )

            keycode = CGEventGetIntegerValueField(event, kCGKeyboardEventKeycode)
            if keycode in self._suppressed_vk_codes:
                logger.debug("darwin_intercept: suppressing keycode %d", keycode)
                return None
        except Exception as exc:
            logger.debug("darwin_intercept error: %s", exc)
        return event

    def _on_press(self, key: Key | KeyCode | None, injected: bool = False) -> None:
        """Handle a key-press event.

        Canonicalizes the key (unifying left/right modifier variants), adds
        it to the held set, then checks all bindings for a match.

        ``injected`` is True for synthetic events posted by pynput's own
        Controller (e.g. from controller.type()).  We skip those to avoid
        false hotkey triggers and unnecessary _held churn.
        """
        if key is None:
            return
        if injected:
            return  # ignore synthetic events from our own controller

        # Capture the hardware VK before canonical() -- it may be stripped.
        # On macOS, Option+M produces 'µ' at the character level but the
        # hardware VK is still 0x2E (KEY_M).  We use this as a layout-
        # independent fallback so bindings work on any keyboard layout.
        raw_vk: int | None = getattr(key, "vk", None)

        canonical: Key | KeyCode = (
            self._listener.canonical(key) if self._listener is not None else key
        )
        self._held.add(canonical)
        if raw_vk is not None:
            self._held_vks.add(raw_vk)
        logger.debug(
            "KEY PRESS  raw=%r  canonical=%r  held=%r", key, canonical, self._held
        )

        any_binding_matched = False
        for binding in self._bindings:
            # Match by character (normal) OR by hardware VK (handles
            # Option-transformed chars like Alt+M → 'µ' on macOS).
            trigger_match = binding.trigger == canonical or (
                binding.trigger_vk is not None
                and raw_vk is not None
                and binding.trigger_vk == raw_vk
            )
            if trigger_match and binding.modifiers.issubset(self._held):
                any_binding_matched = True
                if binding.action in ("push_to_talk", "copy_to_clipboard", "toggle"):  # noqa: SIM102
                    # Ignore key-repeat from the SAME binding while a session
                    # is in flight.  F12 (no modifiers) generates key-repeat
                    # ~20x/s while held; only the first press should start.
                    # A DIFFERENT toggle binding must still pass through so it
                    # can stop a session started by another binding.
                    if (
                        self._ptt_press_dispatched
                        and id(binding.binding) == self._ptt_dispatched_binding_id
                    ):
                        logger.debug(
                            "Ignoring %s key-repeat (same binding, session in flight)",
                            binding.action,
                        )
                        continue
                if binding.action in ("push_to_talk", "copy_to_clipboard"):
                    # Block re-activation within debounce window after release.
                    debounce_s = self._push_to_talk_debounce_ms / 1000.0
                    elapsed = time.monotonic() - self._ptt_last_release_time
                    if elapsed < debounce_s:
                        logger.debug(
                            "Ignoring %s: debounce (%.0fms remaining)",
                            binding.action,
                            (debounce_s - elapsed) * 1000,
                        )
                        continue
                logger.debug(
                    "Hotkey pressed: %s+%s -> %s",
                    "+".join(str(m) for m in binding.modifiers),
                    binding.trigger,
                    binding.action,
                )
                if binding.action in ("push_to_talk", "copy_to_clipboard", "toggle"):
                    self._ptt_press_dispatched = True
                    self._ptt_dispatched_binding_id = id(binding.binding)
                self.dispatch_action(binding.binding)

        # stop_on_keypress: any real, non-modifier, non-hotkey keypress stops
        # an active toggle recording.  Injected events are already filtered
        # above (injected=True guard), so only genuine user input reaches here.
        if (
            not any_binding_matched
            and self._stop_on_keypress
            and canonical not in _MODIFIER_KEYS
            and self.on_deactivate is not None
        ):
            logger.debug("stop_on_keypress: stopping recording (key=%r)", canonical)
            self.on_deactivate()

    def _on_release(self, key: Key | KeyCode | None, injected: bool = False) -> None:
        """Handle a key-release event.

        Canonicalizes the key, dispatches release callbacks for matching
        bindings where the trigger was the released key, then removes it
        from the held set.
        """
        if key is None:
            return
        if injected:
            return  # ignore synthetic releases from our own controller

        raw_vk: int | None = getattr(key, "vk", None)

        canonical: Key | KeyCode = (
            self._listener.canonical(key) if self._listener is not None else key
        )
        logger.debug("KEY RELEASE raw=%r  canonical=%r", key, canonical)

        for binding in self._bindings:
            trigger_match = binding.trigger == canonical or (
                binding.trigger_vk is not None
                and raw_vk is not None
                and binding.trigger_vk == raw_vk
            )
            trigger_was_held = binding.trigger in self._held or (
                binding.trigger_vk is not None and binding.trigger_vk in self._held_vks
            )
            if (
                trigger_match
                and trigger_was_held
                and binding.modifiers.issubset(self._held)
            ):
                logger.debug(
                    "Hotkey released: %s -> %s",
                    binding.trigger,
                    binding.action,
                )
                if binding.action in ("push_to_talk", "copy_to_clipboard"):
                    if not self._ptt_press_dispatched:
                        # Phantom release from a previous session: Space is
                        # back in self._held (new session) but no matching
                        # press was dispatched in this session yet.  Drop it.
                        logger.debug(
                            "Ignoring phantom release for %s (no press in flight)",
                            binding.action,
                        )
                        continue
                    self._ptt_press_dispatched = False
                    self.dispatch_release(binding.binding)
                    # Set debounce timestamp AFTER dispatch returns.
                    # _dispatch_release calls _on_deactivate which calls
                    # feedback.play_stop() -- a blocking ~100 ms beep.
                    # If we set the timestamp before dispatch, the beep
                    # consumes part of the debounce window and phantom
                    # Space presses buffered in the pynput queue slip through.
                    self._ptt_last_release_time = time.monotonic()
                elif binding.action == "toggle":
                    # Toggle: clear the key-repeat guard on release.
                    # The actual start/stop logic is handled in the app layer;
                    # no _dispatch_release needed here.
                    self._ptt_press_dispatched = False
                    self._ptt_dispatched_binding_id = None
                else:
                    self.dispatch_release(binding.binding)

        self._held.discard(canonical)
        if raw_vk is not None:
            self._held_vks.discard(raw_vk)
