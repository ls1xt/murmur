"""Tests for murmur.feedback.audio module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from murmur.feedback.audio import AudioFeedback


class TestAudioFeedback:
    """Test AudioFeedback with mocked/disabled PyAudio."""

    def test_disabled_noop(self) -> None:
        """Disabled feedback should not raise or play anything."""
        fb = AudioFeedback(enabled=False)
        fb.play_start()
        fb.play_stop()

    def test_enabled_plays_start_async(self, mocker: Any) -> None:
        """play_start spawns a background thread (non-blocking)."""
        mock_thread_cls = mocker.patch("murmur.feedback.audio.threading.Thread")
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        fb = AudioFeedback(enabled=True)
        fb._enabled = True
        fb.play_start()

        mock_thread_cls.assert_called_once()
        mock_thread.start.assert_called_once()
        call_args = mock_thread_cls.call_args
        assert call_args.kwargs["args"] == (440, 0.1)

    def test_enabled_plays_stop_synchronous(self, mocker: Any) -> None:
        """play_stop calls _play_tone directly (blocking, no thread)."""
        mock_play = mocker.patch.object(AudioFeedback, "_play_tone")

        fb = AudioFeedback(enabled=True)
        fb._enabled = True
        fb.play_stop()

        mock_play.assert_called_once_with(880, 0.1)

    def test_play_tone_noop_without_pyaudio(self, mocker: Any) -> None:
        """_play_tone is a no-op if _get_pa() returns None."""
        mocker.patch("murmur.feedback.audio._get_pa", return_value=None)
        # Should not raise
        AudioFeedback._play_tone(440, 0.1)

    def test_play_tone_with_mock_pyaudio(self, mocker: Any) -> None:
        """_play_tone opens a stream, writes samples, and closes it."""
        mock_stream = MagicMock()
        mock_pa = MagicMock()
        mock_pa.open.return_value = mock_stream

        mock_module = MagicMock()
        mock_module.paInt16 = 8

        mocker.patch("murmur.feedback.audio._get_pa", return_value=mock_pa)
        mocker.patch("murmur.feedback.audio._pyaudio_module", mock_module)

        AudioFeedback._play_tone(440, 0.05)

        mock_pa.open.assert_called_once()
        mock_stream.write.assert_called_once()
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
