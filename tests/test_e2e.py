"""End-to-end hardware test: real mic + real AssemblyAI API.

Run with:
    pytest --hardware tests/test_e2e.py

Requires:
  - A real microphone
  - An API key in ASSEMBLYAI_API_KEY env var or ~/.config/murmur/config.json
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from murmur.config import DictationConfig, FeedbackConfig, TrayConfig
from murmur.injector.base import TextInjector
from murmur.main import DictationApp
from murmur.transcriber.assemblyai import AssemblyAITranscriber


class CapturingInjector(TextInjector):
    """Stub injector that records injected text instead of using ydotool."""

    def __init__(self) -> None:
        self.injected: list[str] = []

    def inject(self, text: str) -> None:
        self.injected.append(text)

    def inject_raw(self, text: str) -> None:
        self.injected.append(text)

    def inject_backspaces(self, count: int) -> None:
        pass

    def is_available(self) -> bool:
        return True


def _make_app(
    real_api_key: str, mocker: Any
) -> tuple[DictationApp, AssemblyAITranscriber, CapturingInjector]:
    """Build a DictationApp with a real transcriber and capturing injector."""
    config = DictationConfig()
    config.transcriber.api_key = real_api_key
    config.feedback = FeedbackConfig(audio_enabled=False)
    config.tray = TrayConfig(enabled=False)

    injector = CapturingInjector()
    transcriber = AssemblyAITranscriber(config.transcriber)

    mocker.patch("murmur.main.create_transcriber", return_value=transcriber)
    mocker.patch("murmur.main.create_injector", return_value=injector)
    mocker.patch("murmur.main.create_hotkey_listener", return_value=MagicMock())

    # Prevent fatal_from_thread from sending SIGTERM to pytest
    mocker.patch("murmur.transcriber.assemblyai.fatal_from_thread")

    app = DictationApp(config)
    return app, transcriber, injector


def _wait_for(condition: Any, timeout: float = 10.0, poll: float = 0.1) -> bool:
    """Poll condition() until it returns True or timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(poll)
    return False


@pytest.mark.hardware
class TestE2ETranscription:
    """End-to-end tests using real hardware (mic + AssemblyAI API)."""

    def test_connect_and_disconnect(self, real_api_key: str, mocker: Any) -> None:
        """Session connects to AssemblyAI and cleanly disconnects."""
        app, transcriber, injector = _make_app(real_api_key, mocker)

        assert not transcriber.is_streaming

        app._on_activate()

        started = _wait_for(lambda: transcriber.is_streaming)
        assert started, "Transcriber did not start streaming within 10s"

        # Brief pause — say something aloud to get a transcript
        time.sleep(3.0)

        app._on_deactivate()

        stopped = _wait_for(lambda: not transcriber.is_streaming)
        assert stopped, "Transcriber did not stop within 10s"

        # Any injected text must be non-empty
        for text in injector.injected:
            assert text.strip(), f"Empty string was injected: {text!r}"

    def test_no_fatal_errors_during_session(self, real_api_key: str, mocker: Any) -> None:
        """No fatal errors occur during a normal activate → deactivate cycle."""
        app, transcriber, _injector = _make_app(real_api_key, mocker)
        from murmur.transcriber import assemblyai as _aai_mod

        app._on_activate()
        _wait_for(lambda: transcriber.is_streaming)
        time.sleep(2.0)
        app._on_deactivate()
        _wait_for(lambda: not transcriber.is_streaming)

        _aai_mod.fatal_from_thread.assert_not_called()  # type: ignore[attr-defined]

    def test_sequential_sessions(self, real_api_key: str, mocker: Any) -> None:
        """Two consecutive activate/deactivate cycles both complete cleanly."""
        app, transcriber, _injector = _make_app(real_api_key, mocker)

        for _ in range(2):
            app._on_activate()
            assert _wait_for(lambda: transcriber.is_streaming), "Did not start"
            time.sleep(2.0)
            app._on_deactivate()
            assert _wait_for(lambda: not transcriber.is_streaming), "Did not stop"
