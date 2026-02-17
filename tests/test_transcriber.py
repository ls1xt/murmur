"""Tests for murmur.transcriber module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from murmur.config import TranscriberConfig
from murmur.transcriber.base import Transcriber


class TestTranscriberBase:
    """Test the Transcriber ABC."""

    def test_is_streaming_initially_false(self) -> None:
        class StubTranscriber(Transcriber):
            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

        t = StubTranscriber()
        assert t.is_streaming is False

    def test_set_callbacks_stores_them(self) -> None:
        class StubTranscriber(Transcriber):
            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

        t = StubTranscriber()
        on_partial = MagicMock()
        on_final = MagicMock()
        on_error = MagicMock()
        t.set_callbacks(on_partial=on_partial, on_final=on_final, on_error=on_error)
        assert t._on_partial is on_partial
        assert t._on_final is on_final
        assert t._on_error is on_error


class TestAssemblyAITranscriber:
    """Test AssemblyAITranscriber with mocked SDK."""

    def _mock_v3(self, mocker: Any) -> MagicMock:
        """Patch the _v3 module reference and threading to use mocks."""
        mock_v3 = MagicMock()
        mock_client = MagicMock()
        mock_v3.StreamingClient.return_value = mock_client
        mock_v3.StreamingClientOptions.return_value = MagicMock()
        mock_v3.StreamingParameters.return_value = MagicMock()
        mock_v3.StreamingEvents = MagicMock()
        mocker.patch("murmur.transcriber.assemblyai._v3", mock_v3)
        # Mock threading.Thread so _stream_audio doesn't actually run
        mock_thread = MagicMock()
        mocker.patch(
            "murmur.transcriber.assemblyai.threading.Thread",
            return_value=mock_thread,
        )
        return mock_v3

    def test_missing_api_key_raises(self) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        config = TranscriberConfig(api_key="")
        with pytest.raises(ValueError, match="API key is required"):
            AssemblyAITranscriber(config)

    def test_start_creates_client_and_connects(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        mock_v3 = self._mock_v3(mocker)
        mock_client = mock_v3.StreamingClient.return_value

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)
        transcriber.start()

        mock_v3.StreamingClient.assert_called_once()
        mock_client.connect.assert_called_once()
        assert transcriber.is_streaming is True

    def test_stop_disconnects_client(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        mock_v3 = self._mock_v3(mocker)
        mock_client = mock_v3.StreamingClient.return_value

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)
        transcriber.start()
        transcriber.stop()

        mock_client.disconnect.assert_called_once_with(terminate=True)
        assert transcriber.is_streaming is False

    def test_on_turn_final_fires_callback(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)

        config = TranscriberConfig(api_key="test_key", format_turns=True)
        transcriber = AssemblyAITranscriber(config)

        on_final = MagicMock()
        on_partial = MagicMock()
        on_error = MagicMock()
        transcriber.set_callbacks(
            on_partial=on_partial, on_final=on_final, on_error=on_error
        )

        mock_event = MagicMock()
        mock_event.transcript = "Hello world."
        mock_event.end_of_turn = True
        mock_event.turn_is_formatted = True

        transcriber._on_turn(MagicMock(), mock_event)

        on_final.assert_called_once_with("Hello world.")
        on_partial.assert_not_called()

    def test_on_turn_partial_fires_callback(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)

        on_final = MagicMock()
        on_partial = MagicMock()
        on_error = MagicMock()
        transcriber.set_callbacks(
            on_partial=on_partial, on_final=on_final, on_error=on_error
        )

        mock_event = MagicMock()
        mock_event.transcript = "Hello"
        mock_event.end_of_turn = False
        mock_event.turn_is_formatted = False

        transcriber._on_turn(MagicMock(), mock_event)

        on_partial.assert_called_once_with("Hello")
        on_final.assert_not_called()

    def test_is_streaming_property(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)

        assert transcriber.is_streaming is False
        transcriber.start()
        assert transcriber.is_streaming is True
        transcriber.stop()
        assert transcriber.is_streaming is False

    def test_on_turn_unformatted_end_of_turn_fires_when_format_disabled(
        self, mocker: Any
    ) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)

        config = TranscriberConfig(api_key="test_key", format_turns=False)
        transcriber = AssemblyAITranscriber(config)

        on_final = MagicMock()
        transcriber.set_callbacks(
            on_partial=MagicMock(), on_final=on_final, on_error=MagicMock()
        )

        mock_event = MagicMock()
        mock_event.transcript = "hello world"
        mock_event.end_of_turn = True
        mock_event.turn_is_formatted = False

        transcriber._on_turn(MagicMock(), mock_event)
        on_final.assert_called_once_with("hello world")


class TestAssemblyAIErrorHandling:
    """Test AssemblyAI transcriber fatal error exits."""

    def _mock_v3(self, mocker: Any) -> MagicMock:
        """Patch the _v3 module reference and threading to use mocks."""
        mock_v3 = MagicMock()
        mock_client = MagicMock()
        mock_v3.StreamingClient.return_value = mock_client
        mock_v3.StreamingClientOptions.return_value = MagicMock()
        mock_v3.StreamingParameters.return_value = MagicMock()
        mock_v3.StreamingEvents = MagicMock()
        mocker.patch("murmur.transcriber.assemblyai._v3", mock_v3)
        mock_thread = MagicMock()
        mocker.patch(
            "murmur.transcriber.assemblyai.threading.Thread",
            return_value=mock_thread,
        )
        return mock_v3

    def test_stream_error_calls_fatal(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)
        mock_fatal = mocker.patch("murmur.transcriber.assemblyai.fatal_from_thread")

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)
        transcriber._on_stream_error(MagicMock(), "some error")

        mock_fatal.assert_called_once()
        call_msg: str = mock_fatal.call_args[0][0]
        assert "WebSocket error" in call_msg

    def test_stream_error_classifies_1008(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)
        mock_fatal = mocker.patch("murmur.transcriber.assemblyai.fatal_from_thread")

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)
        transcriber._on_stream_error(MagicMock(), "Connection closed: 1008")

        mock_fatal.assert_called_once()
        call_msg: str = mock_fatal.call_args[0][0]
        assert "auth error" in call_msg
        assert "1008" in call_msg

    def test_stream_error_classifies_3005(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)
        mock_fatal = mocker.patch("murmur.transcriber.assemblyai.fatal_from_thread")

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)
        transcriber._on_stream_error(MagicMock(), "Session error: 3005")

        mock_fatal.assert_called_once()
        call_msg: str = mock_fatal.call_args[0][0]
        assert "session expired" in call_msg
        assert "3005" in call_msg

    def test_unexpected_termination_calls_fatal(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)
        mock_fatal = mocker.patch("murmur.transcriber.assemblyai.fatal_from_thread")

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)
        transcriber.start()
        # is_streaming is True -- unexpected termination
        mock_event = MagicMock()
        mock_event.audio_duration_seconds = 5.0
        transcriber._on_terminated(MagicMock(), mock_event)

        mock_fatal.assert_called_once()
        call_msg: str = mock_fatal.call_args[0][0]
        assert "connection lost" in call_msg.lower()

    def test_normal_termination_does_not_call_fatal(self, mocker: Any) -> None:
        from murmur.transcriber.assemblyai import AssemblyAITranscriber

        self._mock_v3(mocker)
        mock_fatal = mocker.patch("murmur.transcriber.assemblyai.fatal_from_thread")

        config = TranscriberConfig(api_key="test_key")
        transcriber = AssemblyAITranscriber(config)
        transcriber.start()
        transcriber.stop()
        # is_streaming is now False -- normal termination
        mock_event = MagicMock()
        mock_event.audio_duration_seconds = 5.0
        transcriber._on_terminated(MagicMock(), mock_event)

        mock_fatal.assert_not_called()


class TestTranscriberFactory:
    """Test the transcriber factory function."""

    def test_unknown_backend_raises(self) -> None:
        from murmur.transcriber import create_transcriber

        config = TranscriberConfig(backend="nonexistent")
        with pytest.raises(ValueError, match="Unknown transcriber backend"):
            create_transcriber(config)
