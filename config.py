"""
Configuration for the dictation tool.
Loads from environment variables and/or a config file.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "dictation"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class HotkeyConfig:
    """Hotkey detection settings."""

    # Keys that form the hotkey combo (modifier names + trigger key)
    # For evdev: use evdev key names like "KEY_LEFTCTRL", "KEY_LEFTSHIFT", "KEY_SPACE"
    # For pynput: use pynput names like "<ctrl>+<shift>+<space>"
    modifiers: list[str] = field(
        default_factory=lambda: ["KEY_LEFTCTRL", "KEY_LEFTSHIFT"]
    )
    trigger: str = "KEY_SPACE"

    # "toggle" or "push_to_talk"
    mode: str = "push_to_talk"

    # Backend: "evdev" (Wayland), "pynput" (macOS/X11), "auto"
    backend: str = "auto"

    # For evdev: specific device path, or None for auto-detect
    evdev_device: Optional[str] = None


@dataclass
class TranscriberConfig:
    """Speech-to-text engine settings."""

    # Backend: "assemblyai" (more to come)
    backend: str = "assemblyai"

    # AssemblyAI settings
    api_key: str = ""
    sample_rate: int = 16_000
    format_turns: bool = True
    language: str = "en"

    # Endpointing tuning
    end_of_turn_confidence_threshold: float = 0.4
    min_end_of_turn_silence_when_confident: int = 400  # ms
    max_turn_silence: int = 1280  # ms


@dataclass
class InjectorConfig:
    """Text injection settings."""

    # Backend: "ydotool", "dotool", "pynput", "auto"
    backend: str = "auto"

    # ydotool settings
    ydotool_path: str = "ydotool"

    # Whether to add a trailing space after injected text
    trailing_space: bool = True

    # Delay between keystrokes in ms (ydotool --key-delay)
    key_delay: int = 0


@dataclass
class FeedbackConfig:
    """User feedback settings."""

    # Audio feedback
    audio_enabled: bool = True
    start_sound: str = "start"  # built-in or path to .wav
    stop_sound: str = "stop"

    # Visual feedback (future: tray icon, notification)
    visual_enabled: bool = False


@dataclass
class DictationConfig:
    """Top-level configuration."""

    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    transcriber: TranscriberConfig = field(default_factory=TranscriberConfig)
    injector: InjectorConfig = field(default_factory=InjectorConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)

    log_level: str = "INFO"

    @classmethod
    def load(cls) -> "DictationConfig":
        """Load config from file + environment overrides."""
        config = cls()

        # Load from config file if it exists
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data = json.load(f)
                config = cls._from_dict(data)
                logger.info("Loaded config from %s", CONFIG_FILE)
            except Exception as e:
                logger.warning("Failed to load config file: %s", e)

        # Environment variable overrides (highest priority)
        if api_key := os.environ.get("ASSEMBLYAI_API_KEY"):
            config.transcriber.api_key = api_key

        if log_level := os.environ.get("DICTATION_LOG_LEVEL"):
            config.log_level = log_level

        if hotkey_mode := os.environ.get("DICTATION_HOTKEY_MODE"):
            config.hotkey.mode = hotkey_mode

        if backend := os.environ.get("DICTATION_HOTKEY_BACKEND"):
            config.hotkey.backend = backend

        if backend := os.environ.get("DICTATION_INJECTOR_BACKEND"):
            config.injector.backend = backend

        return config

    @classmethod
    def _from_dict(cls, data: dict) -> "DictationConfig":
        """Construct config from a dict (loaded from JSON)."""
        config = cls()
        if "hotkey" in data:
            for k, v in data["hotkey"].items():
                if hasattr(config.hotkey, k):
                    setattr(config.hotkey, k, v)
        if "transcriber" in data:
            for k, v in data["transcriber"].items():
                if hasattr(config.transcriber, k):
                    setattr(config.transcriber, k, v)
        if "injector" in data:
            for k, v in data["injector"].items():
                if hasattr(config.injector, k):
                    setattr(config.injector, k, v)
        if "feedback" in data:
            for k, v in data["feedback"].items():
                if hasattr(config.feedback, k):
                    setattr(config.feedback, k, v)
        if "log_level" in data:
            config.log_level = data["log_level"]
        return config

    def save(self) -> None:
        """Save current config to file."""
        import dataclasses

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(dataclasses.asdict(self), f, indent=2)
        logger.info("Saved config to %s", CONFIG_FILE)
