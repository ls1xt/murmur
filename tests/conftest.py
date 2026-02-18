"""Shared fixtures and hardware marker skip logic."""

from __future__ import annotations

import json
import os

import pytest

from murmur.config import (
    CONFIG_FILE,
    DictationConfig,
    FeedbackConfig,
    HotkeyBinding,
    HotkeyConfig,
    InjectorConfig,
    TranscriberConfig,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add --hardware CLI option to pytest."""
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="Run integration tests requiring real hardware",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-skip hardware-marked tests unless --hardware flag is passed."""
    if config.getoption("--hardware"):
        return
    skip_marker = pytest.mark.skip(
        reason="hardware tests skipped (use --hardware to run)"
    )
    for item in items:
        if item.get_closest_marker("hardware"):
            item.add_marker(skip_marker)


@pytest.fixture()
def default_config() -> DictationConfig:
    """Return a DictationConfig with all defaults."""
    return DictationConfig()


@pytest.fixture()
def mock_hotkey_config() -> HotkeyConfig:
    """Return a HotkeyConfig suitable for testing."""
    return HotkeyConfig(
        bindings=[
            HotkeyBinding(
                modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
                trigger="KEY_SPACE",
                action="push_to_talk",
            ),
        ],
        backend="evdev",
    )


@pytest.fixture()
def mock_transcriber_config() -> TranscriberConfig:
    """Return a TranscriberConfig with a fake API key."""
    return TranscriberConfig(
        backend="assemblyai",
        api_key="test_fake_key_12345",
    )


@pytest.fixture()
def mock_injector_config() -> InjectorConfig:
    """Return an InjectorConfig for testing."""
    return InjectorConfig(
        backend="ydotool",
        trailing_space=True,
    )


@pytest.fixture()
def mock_feedback_config() -> FeedbackConfig:
    """Return a FeedbackConfig for testing."""
    return FeedbackConfig(
        audio_enabled=False,
    )


def _load_real_api_key() -> str:
    """Return the API key from env var or ~/.config/murmur/config.json.

    Returns an empty string if neither source has a key.
    """
    key = os.environ.get("ASSEMBLYAI_API_KEY", "")
    if key:
        return key
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            key = data.get("transcriber", {}).get("api_key", "")
        except Exception:
            pass
    return key


@pytest.fixture()
def real_api_key() -> str:
    """Provide a real AssemblyAI API key, or skip the test.

    Reads from (in order):
      1. ASSEMBLYAI_API_KEY environment variable
      2. ~/.config/murmur/config.json  (transcriber.api_key)
    """
    key = _load_real_api_key()
    if not key:
        pytest.skip(
            "No API key found — set ASSEMBLYAI_API_KEY or run ./config-api-key.sh"
        )
    return key
