"""Hotkey listener factory."""

from __future__ import annotations

import sys
from collections.abc import Callable

from murmur.config import HotkeyConfig
from murmur.hotkey.base import HotkeyListener


def create_hotkey_listener(
    config: HotkeyConfig,
    is_injecting: Callable[[], bool] | None = None,
) -> HotkeyListener:
    """Create a hotkey listener backend based on config."""
    match config.backend:
        case "evdev":
            from murmur.hotkey.evdev import EvdevHotkeyListener

            return EvdevHotkeyListener(
                bindings=config.bindings,
                device_path=config.evdev_device,
                push_to_talk_debounce_ms=config.push_to_talk_debounce_ms,
                stop_on_keypress=config.stop_on_keypress,
            )
        case "pynput":
            from murmur.hotkey.pynput import PynputHotkeyListener

            return PynputHotkeyListener(
                bindings=config.bindings,
                push_to_talk_debounce_ms=config.push_to_talk_debounce_ms,
                stop_on_keypress=config.stop_on_keypress,
                is_injecting=is_injecting,
            )
        case "auto":
            if sys.platform == "linux":
                from murmur.hotkey.evdev import EvdevHotkeyListener

                return EvdevHotkeyListener(
                    bindings=config.bindings,
                    device_path=config.evdev_device,
                    push_to_talk_debounce_ms=config.push_to_talk_debounce_ms,
                    stop_on_keypress=config.stop_on_keypress,
                )
            elif sys.platform == "darwin":
                from murmur.hotkey.pynput import PynputHotkeyListener

                return PynputHotkeyListener(
                    bindings=config.bindings,
                    push_to_talk_debounce_ms=config.push_to_talk_debounce_ms,
                    stop_on_keypress=config.stop_on_keypress,
                    is_injecting=is_injecting,
                )
            raise RuntimeError(f"No hotkey backend available for {sys.platform}")
        case _:
            raise ValueError(f"Unknown hotkey backend: {config.backend!r}")
