"""Integration tests for DictationApp orchestration.

Tests the full activate → transcribe → deactivate cycle using mocked
backends, verifying that sequential recordings work without crashes.
"""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from murmur.config import DictationConfig, FeedbackConfig, TrayConfig
from murmur.main import DictationApp


def _make_app(mocker: Any) -> tuple[DictationApp, MagicMock, MagicMock, MagicMock]:
    """Build a DictationApp with all hardware backends mocked out.

    Returns (app, mock_transcriber, mock_injector, mock_hotkey).
    """
    config = DictationConfig()
    config.transcriber.api_key = "fake_key"
    config.feedback = FeedbackConfig(audio_enabled=False)
    config.tray = TrayConfig(enabled=False)

    mock_transcriber = MagicMock()
    mock_transcriber.is_streaming = False
    mock_injector = MagicMock()
    mock_injector.is_available.return_value = True
    mock_hotkey = MagicMock()

    mocker.patch("murmur.main.create_transcriber", return_value=mock_transcriber)
    mocker.patch("murmur.main.create_injector", return_value=mock_injector)
    mocker.patch("murmur.main.create_hotkey_listener", return_value=mock_hotkey)

    app = DictationApp(config)
    return app, mock_transcriber, mock_injector, mock_hotkey


class TestDictationAppLifecycle:
    def test_activate_starts_transcription(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        app._on_activate()

        # Give the thread a moment to call start()
        time.sleep(0.05)
        transcriber.start.assert_called_once()

    def test_deactivate_stops_transcription(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = True
        app._on_deactivate()

        time.sleep(0.05)
        transcriber.stop.assert_called_once()

    def test_activate_noop_when_already_streaming(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = True
        app._on_activate()

        time.sleep(0.05)
        transcriber.start.assert_not_called()

    def test_deactivate_noop_when_not_streaming(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = False
        app._on_deactivate()

        time.sleep(0.05)
        transcriber.stop.assert_not_called()

    def test_final_transcript_injects_text(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_final_transcript("Hello world.")

        injector.inject.assert_called_once_with("Hello world.")

    def test_blank_transcript_not_injected(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_final_transcript("   ")

        injector.inject.assert_not_called()

    def test_sequential_recordings(self, mocker: Any) -> None:
        """Three activate/deactivate cycles must all complete without error."""
        app, transcriber, _, _ = _make_app(mocker)

        for i in range(3):
            transcriber.is_streaming = False
            app._on_activate()
            time.sleep(0.05)

            transcriber.is_streaming = True
            app._on_deactivate()
            time.sleep(0.05)

            transcriber.is_streaming = False

        assert transcriber.start.call_count == 3
        assert transcriber.stop.call_count == 3

    def test_transcriber_error_updates_state(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)
        mock_set_state = mocker.patch.object(app.tray, "set_state")

        app._on_transcriber_error(RuntimeError("boom"))

        mock_set_state.assert_called_once_with("error", reason="boom")

    def test_shutdown_stops_hotkey_and_transcriber(self, mocker: Any) -> None:
        app, transcriber, _, hotkey = _make_app(mocker)

        transcriber.is_streaming = True
        app.shutdown()

        transcriber.stop.assert_called_once()
        hotkey.stop.assert_called_once()
