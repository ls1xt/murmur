"""Tests for murmur.config module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from murmur.config import (
    CONFIG_DIR,
    DictationConfig,
    FeedbackConfig,
    HotkeyConfig,
    InjectorConfig,
    TranscriberConfig,
)


class TestDefaultValues:
    """Test that default config values match expectations."""

    def test_hotkey_defaults(self) -> None:
        config = HotkeyConfig()
        assert config.mode == "push_to_talk"
        assert config.backend == "auto"
        assert config.modifiers == ["KEY_LEFTCTRL", "KEY_LEFTSHIFT"]
        assert config.trigger == "KEY_SPACE"
        assert config.evdev_device is None

    def test_transcriber_defaults(self) -> None:
        config = TranscriberConfig()
        assert config.backend == "assemblyai"
        assert config.api_key == ""
        assert config.sample_rate == 16_000
        assert config.format_turns is True

    def test_injector_defaults(self) -> None:
        config = InjectorConfig()
        assert config.backend == "auto"
        assert config.trailing_space is True
        assert config.key_delay == 0
        assert config.inject_strategy == "clipboard-fallback"

    def test_feedback_defaults(self) -> None:
        config = FeedbackConfig()
        assert config.audio_enabled is True
        assert config.visual_enabled is False

    def test_dictation_config_defaults(self) -> None:
        config = DictationConfig()
        assert config.log_level == "INFO"
        assert isinstance(config.hotkey, HotkeyConfig)
        assert isinstance(config.transcriber, TranscriberConfig)
        assert isinstance(config.injector, InjectorConfig)
        assert isinstance(config.feedback, FeedbackConfig)


class TestConfigDir:
    """Test config directory path."""

    def test_config_dir_path(self) -> None:
        assert Path.home() / ".config" / "murmur" == CONFIG_DIR


class TestEnvVarOverride:
    """Test environment variable overrides during config load."""

    def test_api_key_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test_key_abc")
        monkeypatch.delenv("DICTATION_LOG_LEVEL", raising=False)
        monkeypatch.delenv("DICTATION_HOTKEY_MODE", raising=False)
        monkeypatch.delenv("DICTATION_HOTKEY_BACKEND", raising=False)
        monkeypatch.delenv("DICTATION_INJECTOR_BACKEND", raising=False)
        monkeypatch.delenv("MURMUR_INJECT_STRATEGY", raising=False)
        config = DictationConfig.load()
        assert config.transcriber.api_key == "test_key_abc"

    def test_hotkey_mode_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DICTATION_HOTKEY_MODE", "toggle")
        monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
        monkeypatch.delenv("DICTATION_LOG_LEVEL", raising=False)
        monkeypatch.delenv("DICTATION_HOTKEY_BACKEND", raising=False)
        monkeypatch.delenv("DICTATION_INJECTOR_BACKEND", raising=False)
        monkeypatch.delenv("MURMUR_INJECT_STRATEGY", raising=False)
        config = DictationConfig.load()
        assert config.hotkey.mode == "toggle"

    def test_log_level_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DICTATION_LOG_LEVEL", "DEBUG")
        monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
        monkeypatch.delenv("DICTATION_HOTKEY_MODE", raising=False)
        monkeypatch.delenv("DICTATION_HOTKEY_BACKEND", raising=False)
        monkeypatch.delenv("DICTATION_INJECTOR_BACKEND", raising=False)
        monkeypatch.delenv("MURMUR_INJECT_STRATEGY", raising=False)
        config = DictationConfig.load()
        assert config.log_level == "DEBUG"

    def test_inject_strategy_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MURMUR_INJECT_STRATEGY", "clipboard")
        monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
        monkeypatch.delenv("DICTATION_LOG_LEVEL", raising=False)
        monkeypatch.delenv("DICTATION_HOTKEY_MODE", raising=False)
        monkeypatch.delenv("DICTATION_HOTKEY_BACKEND", raising=False)
        monkeypatch.delenv("DICTATION_INJECTOR_BACKEND", raising=False)
        config = DictationConfig.load()
        assert config.injector.inject_strategy == "clipboard"


class TestFromDict:
    """Test config construction from a dictionary."""

    def test_from_dict_applies_hotkey_mode(self) -> None:
        data: dict[str, Any] = {"hotkey": {"mode": "toggle"}}
        config = DictationConfig._from_dict(data)
        assert config.hotkey.mode == "toggle"

    def test_from_dict_applies_transcriber_settings(self) -> None:
        data: dict[str, Any] = {
            "transcriber": {"api_key": "my_key", "sample_rate": 8000}
        }
        config = DictationConfig._from_dict(data)
        assert config.transcriber.api_key == "my_key"
        assert config.transcriber.sample_rate == 8000

    def test_from_dict_applies_log_level(self) -> None:
        data: dict[str, Any] = {"log_level": "WARNING"}
        config = DictationConfig._from_dict(data)
        assert config.log_level == "WARNING"

    def test_from_dict_ignores_unknown_fields(self) -> None:
        data: dict[str, Any] = {"hotkey": {"nonexistent_field": "value"}}
        config = DictationConfig._from_dict(data)
        assert not hasattr(config.hotkey, "nonexistent_field")

    def test_from_dict_empty_dict(self) -> None:
        data: dict[str, Any] = {}
        config = DictationConfig._from_dict(data)
        assert config.hotkey.mode == "push_to_talk"
