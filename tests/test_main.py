"""Integration tests for DictationApp orchestration.

Tests the full activate → transcribe → deactivate cycle using mocked
backends, verifying that sequential recordings work without crashes.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

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

        app._on_activate("push_to_talk")

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
        app._on_activate("push_to_talk")

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

    def test_final_transcript_backspaces_partial_first(
        self, mocker: Any
    ) -> None:
        app, _, injector, _ = _make_app(mocker)

        # Simulate a partial was previously injected
        app._last_partial = "Hello"
        app._on_final_transcript("Hello world.")

        injector.inject_backspaces.assert_called_once_with(5)
        injector.inject.assert_called_once_with("Hello world.")
        assert app._last_partial == ""

    def test_blank_transcript_not_injected(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_final_transcript("   ")

        injector.inject.assert_not_called()

    def test_partial_transcript_inject_raw(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("Hello")
        injector.inject_raw.assert_called_once_with("Hello")
        assert app._last_partial == "Hello"

    def test_partial_transcript_delta_suffix(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("Hello")
        app._on_partial_transcript("Hello world")

        # Second call should only inject the suffix
        assert injector.inject_raw.call_count == 2
        assert injector.inject_raw.call_args_list[1][0][0] == " world"

    def test_partial_transcript_diverged(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("Hello")
        injector.inject_raw.reset_mock()

        # Diverge: new text doesn't start with old
        app._on_partial_transcript("Hey there")
        injector.inject_backspaces.assert_called_once_with(5)
        injector.inject_raw.assert_called_once_with("Hey there")

    def test_partial_empty_is_noop(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("")
        injector.inject_raw.assert_not_called()

    def test_sequential_recordings(self, mocker: Any) -> None:
        """Three activate/deactivate cycles must all complete without error."""
        app, transcriber, _, _ = _make_app(mocker)

        for _ in range(3):
            transcriber.is_streaming = False
            app._on_activate("push_to_talk")
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


class TestClipboardMode:
    """Test copy_to_clipboard hotkey action behaviour."""

    def test_activate_clipboard_sets_flag(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)

        app._on_activate("copy_to_clipboard")
        assert app._clipboard_mode is True

    def test_activate_push_to_talk_clears_flag(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_activate("push_to_talk")
        assert app._clipboard_mode is False

    def test_partial_skipped_in_clipboard_mode(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_partial_transcript("Hello world")

        injector.inject_raw.assert_not_called()
        injector.inject_backspaces.assert_not_called()

    def test_final_copies_to_clipboard(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_final_transcript("Hello world.")

        injector.copy_to_clipboard.assert_called_once_with("Hello world.")
        injector.inject.assert_not_called()

    def test_final_clipboard_resets_flag(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_final_transcript("Hello world.")

        assert app._clipboard_mode is False

    def test_final_blank_in_clipboard_mode_skips_copy(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_final_transcript("   ")

        injector.copy_to_clipboard.assert_not_called()

    def test_tray_activate_uses_push_to_talk(self, mocker: Any) -> None:
        """Tray left-click always uses push_to_talk, not clipboard mode."""
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = False
        app._on_tray_activate()

        assert app._clipboard_mode is False
