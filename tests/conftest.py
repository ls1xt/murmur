"""Shared fixtures and hardware marker skip logic."""

from __future__ import annotations

import contextlib
import json
import os
import sys
from collections.abc import Generator

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
    """Add --hardware and --virtual-mic CLI options to pytest."""
    parser.addoption(
        "--hardware",
        action="store_true",
        default=False,
        help="Run integration tests requiring real hardware",
    )
    parser.addoption(
        "--virtual-mic",
        action="store_true",
        default=False,
        help=(
            "Run audio pipeline tests using virtual mic device"
            " (snd-aloop on Linux, BlackHole on macOS)"
        ),
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-skip hardware and virtual-mic marked tests unless the flag is passed."""
    if not config.getoption("--hardware"):
        skip_hardware = pytest.mark.skip(
            reason="hardware tests skipped (use --hardware to run)"
        )
        for item in items:
            if item.get_closest_marker("hardware"):
                item.add_marker(skip_hardware)

    if not config.getoption("--virtual-mic"):
        skip_virtual_mic = pytest.mark.skip(
            reason="virtual-mic tests skipped (use --virtual-mic to run)"
        )
        for item in items:
            if item.get_closest_marker("requires_virtual_mic"):
                item.add_marker(skip_virtual_mic)

    for item in items:
        if item.get_closest_marker("linux_only") and sys.platform != "linux":
            item.add_marker(pytest.mark.skip(reason="Linux only"))
        if item.get_closest_marker("macos_only") and sys.platform != "darwin":
            item.add_marker(pytest.mark.skip(reason="macOS only"))


@pytest.fixture(scope="session", autouse=True)
def _portaudio_cleanup() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Terminate PortAudio after the test session to prevent shutdown segfaults.

    Importing sounddevice initializes PortAudio, which spawns CoreAudio
    background threads on macOS.  Explicitly terminating before Python exits
    prevents a race between those threads and interpreter teardown.
    """
    yield
    import sounddevice  # noqa: PLC0415

    with contextlib.suppress(Exception):
        sounddevice._terminate()  # type: ignore[attr-defined]


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
                mode="push_to_talk",
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


@pytest.fixture(scope="session")
def virtual_mic_device(
    request: pytest.FixtureRequest,
) -> Generator[str | int]:
    """Yield the virtual mic device name or index for audio pipeline tests.

    On Linux: detects snd-aloop ALSA loopback device by name (contains 'loopback').
    On macOS: detects BlackHole virtual audio device by name (contains 'blackhole').

    Skips the test session if no suitable virtual device is found.
    """
    import sounddevice as sd

    _ = request  # session-scoped fixture; request unused but required by pytest API
    devices = sd.query_devices()  # type: ignore[no-untyped-call]
    if sys.platform == "linux":
        for i, dev in enumerate(devices):
            name: str = dev["name"].lower()
            max_in: int = int(dev["max_input_channels"])
            if max_in > 0 and "loopback" in name:
                yield i
                return
    elif sys.platform == "darwin":
        for _i, dev in enumerate(devices):
            name = dev["name"].lower()
            max_in = int(dev["max_input_channels"])
            if max_in > 0 and "blackhole" in name:
                yield dev["name"]
                return
    pytest.skip(
        "No virtual mic device found"
        " — load snd-aloop (Linux) or install BlackHole (macOS)"
    )
