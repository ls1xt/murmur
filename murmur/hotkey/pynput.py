"""
pynput-based hotkey listener -- works on macOS without accessibility APIs.

Uses pynput's raw keyboard.Listener with manual modifier-state tracking to
detect configured key bindings reliably, including Ctrl+Alt combinations.

Does NOT suppress events (no darwin_intercept) -- per design decision, no
key grabbing or suppression on macOS.

Only imported on darwin (via the hotkey factory). pynput is an optional
dependency; an ImportError here surfaces a clear message to the user.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from pynput import keyboard
from pynput.keyboard import Key, KeyCode

from murmur.config import HotkeyBinding
from murmur.hotkey.base import HotkeyListener

logger = logging.getLogger(__name__)


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
    action: str
    tmux_target: str = ""
    tmux_keys: str = ""


def _resolve_bindings(bindings: list[HotkeyBinding]) -> list[_ResolvedBinding]:
    """Translate a list of HotkeyBindings to _ResolvedBindings.

    Raises ValueError if any evdev key name is unknown.
    """
    resolved: list[_ResolvedBinding] = []
    for binding in bindings:
        mod_keys: set[Key | KeyCode] = set()
        for mod_name in binding.modifiers:
            mod_keys.add(_translate_evdev_name(mod_name))
        trigger_key = _translate_evdev_name(binding.trigger)
        resolved.append(
            _ResolvedBinding(
                modifiers=frozenset(mod_keys),
                trigger=trigger_key,
                action=binding.action,
                tmux_target=binding.tmux_target,
                tmux_keys=binding.tmux_keys,
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

    Events are NOT suppressed -- keys pass through to the foreground
    application normally.  This is intentional: macOS does not support
    grab-and-forward like Linux evdev.

    ``push_to_talk_debounce_ms`` is accepted for API compatibility with
    EvdevHotkeyListener but is not used -- macOS does not generate spurious
    key-up events the way some Linux setups do.
    """

    def __init__(
        self,
        bindings: list[HotkeyBinding],
        push_to_talk_debounce_ms: int = 300,
    ) -> None:
        super().__init__()
        self._bindings: list[_ResolvedBinding] = _resolve_bindings(bindings)
        self._held: set[Key | KeyCode] = set()
        self._listener: keyboard.Listener | None = None
        self._push_to_talk_debounce_ms: int = push_to_talk_debounce_ms
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

    def start(self) -> None:
        """Start listening for hotkeys in a background thread.

        Creates a fresh keyboard.Listener instance each call -- pynput
        threads cannot be restarted after stop().
        """
        if self._listener is not None and self._listener.is_alive():
            logger.warning("PynputHotkeyListener already running")
            return

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

        # Re-canonicalize binding keys using the live listener.  Some keys
        # like Key.space (char=' ') have a different canonical form at runtime
        # (e.g. KeyCode(vk=49) on macOS) than the object returned by
        # _translate_evdev_name.  Without this step, Key.space in a binding
        # would never match the <49> seen in on_press events.
        self._bindings = [
            _ResolvedBinding(
                modifiers=frozenset(
                    self._listener.canonical(m) for m in b.modifiers
                ),
                trigger=self._listener.canonical(b.trigger),
                action=b.action,
                tmux_target=b.tmux_target,
                tmux_keys=b.tmux_keys,
            )
            for b in self._bindings
        ]

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
        self._ptt_last_release_time = 0.0
        self._ptt_press_dispatched = False
        logger.info("pynput hotkey listener stopped")

    def _on_press(self, key: Key | KeyCode | None) -> None:
        """Handle a key-press event.

        Canonicalizes the key (unifying left/right modifier variants), adds
        it to the held set, then checks all bindings for a match.
        """
        if key is None:
            return

        canonical: Key | KeyCode = (
            self._listener.canonical(key) if self._listener is not None else key
        )
        self._held.add(canonical)
        logger.debug("KEY PRESS  raw=%r  canonical=%r  held=%r", key, canonical, self._held)

        for binding in self._bindings:
            if binding.trigger == canonical and binding.modifiers.issubset(self._held):
                # Block push-to-talk re-activation within debounce window.
                # macOS generates phantom Space-press events immediately after
                # release (key-repeat while Ctrl+Option still held).  A short
                # debounce suppresses them; modifier-release tracking is
                # unreliable because macOS does not deliver Ctrl/Alt release
                # events through the CGEventTap in this configuration.
                if binding.action in ("push_to_talk", "copy_to_clipboard"):
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
                if binding.action in ("push_to_talk", "copy_to_clipboard"):
                    self._ptt_press_dispatched = True
                self._dispatch_action(
                    binding.action,
                    binding.tmux_target,
                    binding.tmux_keys,
                )

    def _on_release(self, key: Key | KeyCode | None) -> None:
        """Handle a key-release event.

        Canonicalizes the key, dispatches release callbacks for matching
        bindings where the trigger was the released key, then removes it
        from the held set.
        """
        if key is None:
            return

        canonical: Key | KeyCode = (
            self._listener.canonical(key) if self._listener is not None else key
        )
        logger.debug("KEY RELEASE raw=%r  canonical=%r", key, canonical)

        for binding in self._bindings:
            if (
                binding.trigger == canonical
                and binding.trigger in self._held
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
                    self._dispatch_release(binding.action)
                    # Set debounce timestamp AFTER dispatch returns.
                    # _dispatch_release calls _on_deactivate which calls
                    # feedback.play_stop() -- a blocking ~100 ms beep.
                    # If we set the timestamp before dispatch, the beep
                    # consumes part of the debounce window and phantom
                    # Space presses buffered in the pynput queue slip through.
                    self._ptt_last_release_time = time.monotonic()
                else:
                    self._dispatch_release(binding.action)

        self._held.discard(canonical)
