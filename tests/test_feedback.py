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
        # Should not raise
        fb.play_start()
        fb.play_stop()

    def test_enabled_plays_start(self, mocker: Any) -> None:
        """When enabled and PyAudio available, play_start should spawn a thread."""
        mock_thread_cls = mocker.patch("murmur.feedback.audio.threading.Thread")
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        # Ensure _HAS_PYAUDIO is True for this test
        mocker.patch("murmur.feedback.audio._HAS_PYAUDIO", True)

        fb = AudioFeedback(enabled=True)
        # Force _enabled since we patched _HAS_PYAUDIO after init
        fb._enabled = True
        fb.play_start()

        mock_thread_cls.assert_called_once()
        mock_thread.start.assert_called_once()
        # Verify 440 Hz was passed
        call_args = mock_thread_cls.call_args
        assert call_args.kwargs["args"] == (440, 0.1)

    def test_enabled_plays_stop(self, mocker: Any) -> None:
        """When enabled, play_stop should play 880 Hz tone."""
        mock_thread_cls = mocker.patch("murmur.feedback.audio.threading.Thread")
        mock_thread = MagicMock()
        mock_thread_cls.return_value = mock_thread

        mocker.patch("murmur.feedback.audio._HAS_PYAUDIO", True)

        fb = AudioFeedback(enabled=True)
        fb._enabled = True
        fb.play_stop()

        call_args = mock_thread_cls.call_args
        assert call_args.kwargs["args"] == (880, 0.1)

    def test_play_tone_noop_without_pyaudio(self, mocker: Any) -> None:
        """_play_tone should be a no-op if pyaudio is None."""
        mocker.patch("murmur.feedback.audio._pyaudio", None)
        # Should not raise
        AudioFeedback._play_tone(440, 0.1)

    def test_play_tone_with_mock_pyaudio(self, mocker: Any) -> None:
        """_play_tone should open a stream and write samples."""
        mock_pa_instance = MagicMock()
        mock_stream = MagicMock()
        mock_pa_instance.open.return_value = mock_stream

        mock_pa_module = MagicMock()
        mock_pa_module.PyAudio.return_value = mock_pa_instance
        mock_pa_module.paInt16 = 8  # arbitrary constant

        mocker.patch("murmur.feedback.audio._pyaudio", mock_pa_module)

        AudioFeedback._play_tone(440, 0.05)

        mock_pa_module.PyAudio.assert_called_once()
        mock_pa_instance.open.assert_called_once()
        mock_stream.write.assert_called_once()
        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_pa_instance.terminate.assert_called_once()
