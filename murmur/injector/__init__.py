"""Injector factory."""

from __future__ import annotations

import sys

from murmur.config import InjectorConfig
from murmur.injector.base import TextInjector


def create_injector(config: InjectorConfig) -> TextInjector:
    """Create a text injector backend based on config."""
    match config.backend:
        case "ydotool":
            from murmur.injector.ydotool import YdotoolInjector

            return YdotoolInjector(
                ydotool_path=config.ydotool_path,
                key_delay=config.key_delay,
                trailing_space=config.trailing_space,
                inject_strategy=config.inject_strategy,
            )
        case "pynput":
            from murmur.injector.pynput import PynputInjector

            return PynputInjector(
                trailing_space=config.trailing_space,
                inject_strategy=config.inject_strategy,
                key_delay=config.key_delay,
            )
        case "cgevent":
            from murmur.injector.cgevent import CGEventInjector

            return CGEventInjector(
                trailing_space=config.trailing_space,
                key_delay=config.key_delay,
            )
        case "auto":
            if sys.platform == "linux":
                from murmur.injector.ydotool import YdotoolInjector

                return YdotoolInjector(
                    ydotool_path=config.ydotool_path,
                    key_delay=config.key_delay,
                    trailing_space=config.trailing_space,
                    inject_strategy=config.inject_strategy,
                )
            elif sys.platform == "darwin":
                from murmur.injector.pynput import PynputInjector

                return PynputInjector(
                    trailing_space=config.trailing_space,
                    inject_strategy=config.inject_strategy,
                    key_delay=config.key_delay,
                )
            raise RuntimeError(f"No injector backend available for {sys.platform}")
        case _:
            raise ValueError(f"Unknown injector backend: {config.backend!r}")
