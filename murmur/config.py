"""
Configuration for the dictation tool.
Loads from environment variables and/or a config file.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "murmur"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class HotkeyBinding:
    """A single hotkey binding mapping a key combination to an action.

    For action ``tmux_send_keys``, set ``tmux_target`` to a tmux target pane
    (e.g. ``"my-session:1.1"`` or ``"0"``) and ``tmux_keys`` to the key
    sequence to send (e.g. ``"q"`` or ``"Enter"`` or ``"C-c"``).
    """

    modifiers: list[str] = field(
        default_factory=lambda: ["KEY_LEFTCTRL", "KEY_LEFTALT"]
    )
    trigger: str = "KEY_SPACE"
    action: str = "push_to_talk"
    # tmux_send_keys fields (only used when action == "tmux_send_keys")
    tmux_target: str = ""
    tmux_keys: str = ""
    # suppress=True installs an active CGEventTap to swallow the key event
    suppress: bool = False


def _default_bindings() -> list[HotkeyBinding]:
    """Create the default hotkey configuration."""
    return [
        HotkeyBinding(
            modifiers=[],
            trigger="KEY_F12",
            action="push_to_talk",
            suppress=True,
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
            trigger="KEY_K",
            action="toggle_start",
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
            trigger="KEY_L",
            action="toggle_stop",
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
            trigger="KEY_C",
            action="copy_to_clipboard",
        ),
    ]


@dataclass
class HotkeyConfig:
    """Hotkey detection settings."""

    bindings: list[HotkeyBinding] = field(default_factory=_default_bindings)
    backend: str = "auto"
    evdev_device: str | None = None
    push_to_talk_debounce_ms: int = 300


@dataclass
class TranscriberConfig:
    """Speech-to-text engine settings."""

    backend: str = "assemblyai"
    api_key: str = ""
    sample_rate: int = 16_000
    format_turns: bool = True
    language: str = "en"
    end_of_turn_confidence_threshold: float = 0.4
    min_end_of_turn_silence_when_confident: int = 400
    max_turn_silence: int = 1280
    keyterms_prompt: list[str] = field(default_factory=list)
    keyterms: list[str] = field(default_factory=list)
    inject_partials: bool = False
    reconnect_attempts: int = 5
    reconnect_delay_ms: int = 1000
    mic_device: str | None = None


@dataclass
class InjectorConfig:
    """Text injection settings."""

    backend: str = "auto"
    ydotool_path: str = "ydotool"
    trailing_space: bool = True
    key_delay: int = 0
    inject_strategy: str = "clipboard"


@dataclass
class FeedbackConfig:
    """User feedback settings."""

    audio_enabled: bool = True
    start_hz: float = 440.0
    stop_hz: float = 880.0
    visual_enabled: bool = False


@dataclass
class NotifyConfig:
    """Desktop notification settings."""

    level: str = "errors"  # "off", "errors", "verbose"


@dataclass
class TrayConfig:
    """System tray icon settings."""

    enabled: bool = True


def _apply_section(data: dict[str, Any], key: str, target: object) -> None:
    """Apply a JSON dict section to a dataclass instance.

    Uses setattr for JSON deserialization -- type safety is enforced
    by the dataclass field types at runtime.
    """
    if key not in data:
        return
    section: Any = data[key]
    if not isinstance(section, dict):
        return
    # section is dict[Unknown, Unknown] after isinstance narrowing of Any.
    # Explicit Any cast bypasses strict-mode tracking of untyped JSON values.
    raw_section: Any = section  # type: ignore[reportUnknownVariableType]
    items: list[tuple[str, Any]] = list(raw_section.items())
    for name, value in items:
        if hasattr(target, name):
            setattr(target, name, value)


@dataclass
class DictationConfig:
    """Top-level configuration."""

    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    transcriber: TranscriberConfig = field(default_factory=TranscriberConfig)
    injector: InjectorConfig = field(default_factory=InjectorConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    tray: TrayConfig = field(default_factory=TrayConfig)
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> DictationConfig:
        """Load config from file + environment overrides."""
        config = cls()

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data: dict[str, Any] = json.load(f)
                config = cls._from_dict(data)
                logger.info("Loaded config from %s", CONFIG_FILE)
            except Exception as e:
                logger.warning("Failed to load config file: %s", e)

        if api_key := os.environ.get("ASSEMBLYAI_API_KEY"):
            config.transcriber.api_key = api_key

        if log_level := os.environ.get("MURMUR_LOG_LEVEL") or os.environ.get("DICTATION_LOG_LEVEL"):
            config.log_level = log_level

        if backend := os.environ.get("DICTATION_HOTKEY_BACKEND"):
            config.hotkey.backend = backend

        if backend := os.environ.get("DICTATION_INJECTOR_BACKEND"):
            config.injector.backend = backend

        if strategy := os.environ.get("MURMUR_INJECT_STRATEGY"):
            config.injector.inject_strategy = strategy

        if notify_level := os.environ.get("MURMUR_NOTIFY_LEVEL"):
            config.notify.level = notify_level

        if mic_device := os.environ.get("MURMUR_MIC_DEVICE"):
            config.transcriber.mic_device = mic_device

        return config

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> DictationConfig:
        """Construct config from a dict (loaded from JSON).

        Uses setattr for JSON deserialization -- type safety is enforced
        by the dataclass field types at runtime.

        Handles backward-compatible migration from old hotkey format
        (modifiers/trigger/mode) to new bindings format.
        """
        config = cls()
        hotkey_data: Any = data.get("hotkey")
        if isinstance(hotkey_data, dict):
            raw_hotkey: dict[str, Any] = hotkey_data  # type: ignore[reportUnknownVariableType]
            if "bindings" in raw_hotkey:
                # New format: deserialize bindings list
                bindings_raw: Any = raw_hotkey["bindings"]
                if isinstance(bindings_raw, list):
                    bindings: list[HotkeyBinding] = []
                    for b in bindings_raw:  # type: ignore[reportUnknownVariableType]
                        if isinstance(b, dict):
                            binding = HotkeyBinding()
                            if "modifiers" in b:
                                binding.modifiers = b["modifiers"]
                            if "trigger" in b:
                                binding.trigger = b["trigger"]
                            if "action" in b:
                                binding.action = b["action"]
                            if "tmux_target" in b:
                                binding.tmux_target = str(b["tmux_target"])
                            if "tmux_keys" in b:
                                binding.tmux_keys = str(b["tmux_keys"])
                            if "suppress" in b:
                                binding.suppress = bool(b["suppress"])
                            bindings.append(binding)
                    if bindings:
                        config.hotkey.bindings = bindings
            elif "modifiers" in raw_hotkey or "trigger" in raw_hotkey:
                # Old format: migrate to single binding
                old_mods: list[str] = raw_hotkey.get(
                    "modifiers", ["KEY_LEFTCTRL", "KEY_LEFTALT"]
                )
                old_trigger: str = raw_hotkey.get("trigger", "KEY_SPACE")
                old_action: str = raw_hotkey.get("mode", "push_to_talk")
                config.hotkey.bindings = [
                    HotkeyBinding(
                        modifiers=old_mods,
                        trigger=old_trigger,
                        action=old_action,
                    )
                ]
            # Apply remaining hotkey fields (backend, evdev_device, debounce)
            if "backend" in raw_hotkey:
                config.hotkey.backend = raw_hotkey["backend"]
            if "evdev_device" in raw_hotkey:
                config.hotkey.evdev_device = raw_hotkey["evdev_device"]
            if "push_to_talk_debounce_ms" in raw_hotkey:
                config.hotkey.push_to_talk_debounce_ms = int(
                    raw_hotkey["push_to_talk_debounce_ms"]
                )
        _apply_section(data, "transcriber", config.transcriber)
        _apply_section(data, "injector", config.injector)
        _apply_section(data, "feedback", config.feedback)
        _apply_section(data, "notify", config.notify)
        _apply_section(data, "tray", config.tray)
        if "log_level" in data:
            config.log_level = str(data["log_level"])
        return config

    def save(self) -> None:
        """Save current config to file."""
        import dataclasses

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(dataclasses.asdict(self), f, indent=2)
        logger.info("Saved config to %s", CONFIG_FILE)
