"""Tests for murmur.feedback.audio module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

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
        assert call_args.kwargs["args"] == (440.0, 0.1)

    def test_enabled_plays_stop_synchronous(self, mocker: Any) -> None:
        """play_stop calls _play_tone directly (blocking, no thread)."""
        mock_play = mocker.patch.object(AudioFeedback, "_play_tone")

        fb = AudioFeedback(enabled=True)
        fb._enabled = True
        fb.play_stop()

        mock_play.assert_called_once_with(880.0, 0.1)

    def test_play_tone_noop_on_error(self, mocker: Any) -> None:
        """_play_tone is a no-op (logs warning) when sounddevice raises."""
        mocker.patch("murmur.feedback.audio._sd.RawOutputStream", side_effect=Exception("no device"))
        # Should not raise
        AudioFeedback._play_tone(440, 0.1)

    def test_play_tone_with_mock_sounddevice(self, mocker: Any) -> None:
        """_play_tone opens a stream, writes samples, and closes it."""
        mock_stream = MagicMock()
        mocker.patch("murmur.feedback.audio._sd.RawOutputStream", return_value=mock_stream)

        AudioFeedback._play_tone(440, 0.05)

        mock_stream.start.assert_called_once()
        mock_stream.write.assert_called_once()
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

    def test_custom_frequencies_stored(self) -> None:
        """Custom start_hz and stop_hz are stored on the instance."""
        fb = AudioFeedback(enabled=True, start_hz=523.0, stop_hz=1047.0)
        assert fb._start_hz == 523.0
        assert fb._stop_hz == 1047.0
