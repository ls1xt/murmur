"""Shared fixtures and hardware marker skip logic."""

from __future__ import annotations

import pytest

from murmur.config import (
    DictationConfig,
    FeedbackConfig,
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
        backend="evdev",
        modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
        trigger="KEY_SPACE",
        mode="push_to_talk",
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
