"""Hotkey listener factory."""

from __future__ import annotations

import sys

from murmur.config import HotkeyConfig
from murmur.hotkey.base import HotkeyListener


def create_hotkey_listener(config: HotkeyConfig) -> HotkeyListener:
    """Create a hotkey listener backend based on config."""
    match config.backend:
        case "evdev":
            from murmur.hotkey.evdev import EvdevHotkeyListener

            return EvdevHotkeyListener(
                bindings=config.bindings,
                device_path=config.evdev_device,
            )
        case "auto":
            if sys.platform == "linux":
                from murmur.hotkey.evdev import EvdevHotkeyListener

                return EvdevHotkeyListener(
                    bindings=config.bindings,
                    device_path=config.evdev_device,
                )
            raise RuntimeError(f"No hotkey backend available for {sys.platform}")
        case _:
            raise ValueError(f"Unknown hotkey backend: {config.backend!r}")
