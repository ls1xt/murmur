"""
AssemblyAI streaming transcriber using the Universal-Streaming v3 API.

Uses the official assemblyai Python SDK with the new StreamingClient from
assemblyai.streaming.v3.
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import threading
from typing import Any

import assemblyai as aai  # type: ignore[import-untyped]

from murmur.config import TranscriberConfig
from murmur.transcriber.base import Transcriber

logger = logging.getLogger(__name__)

# Import the v3 streaming submodule (can't use aai.streaming.v3 at runtime).
_v3: Any = importlib.import_module("assemblyai.streaming.v3")


class AssemblyAITranscriber(Transcriber):
    """
    Streams audio from the microphone to AssemblyAI's Universal-Streaming
    API and delivers transcript events via callbacks.
    """

    def __init__(self, config: TranscriberConfig) -> None:
        super().__init__()
        self._config = config

        if not config.api_key:
            raise ValueError(
                "AssemblyAI API key is required.\n"
                "Set ASSEMBLYAI_API_KEY env var or add it to config."
            )

        self._client: Any = None
        self._mic_stream: Any = None
        self._stream_thread: threading.Thread | None = None
        self._current_turn_text = ""
        self._all_text_this_session: list[str] = []

    def start(self) -> None:
        """Start mic capture and streaming to AssemblyAI."""
        if self._is_streaming:
            logger.warning("Already streaming")
            return

        self._is_streaming = True
        self._current_turn_text = ""
        self._all_text_this_session = []

        self._client = _v3.StreamingClient(
            _v3.StreamingClientOptions(
                api_key=self._config.api_key,
                api_host="streaming.assemblyai.com",
            )
        )

        events: Any = _v3.StreamingEvents
        self._client.on(events.Begin, self._on_begin)
        self._client.on(events.Turn, self._on_turn)
        self._client.on(events.Termination, self._on_terminated)
        self._client.on(events.Error, self._on_stream_error)

        params: Any = _v3.StreamingParameters(
            sample_rate=self._config.sample_rate,
            format_turns=self._config.format_turns,
        )
        self._client.connect(params)

        self._stream_thread = threading.Thread(target=self._stream_audio, daemon=True)
        self._stream_thread.start()
        logger.info("AssemblyAI streaming session started")

    def _stream_audio(self) -> None:
        """Stream microphone audio to AssemblyAI (runs in background thread)."""
        try:
            self._mic_stream = aai.extras.MicrophoneStream(  # type: ignore[reportUnknownMemberType]
                sample_rate=self._config.sample_rate
            )
            client: Any = self._client
            mic: Any = self._mic_stream  # type: ignore[reportUnknownMemberType]
            if client is not None:
                client.stream(mic)
        except Exception as e:
            if self._is_streaming and self._on_error is not None:
                self._on_error(e)

    def stop(self) -> None:
        """Stop streaming and disconnect."""
        if not self._is_streaming:
            return

        self._is_streaming = False
        logger.info("Stopping AssemblyAI streaming session...")

        if self._mic_stream is not None:
            with contextlib.suppress(Exception):
                self._mic_stream.close()
            self._mic_stream = None

        if self._client is not None:
            try:
                self._client.disconnect(terminate=True)
            except Exception as e:
                logger.debug("Disconnect error (usually harmless): %s", e)
            self._client = None

        if self._stream_thread is not None:
            self._stream_thread.join(timeout=3.0)
            self._stream_thread = None

        full_text = " ".join(self._all_text_this_session).strip()
        if full_text and self._on_final:
            logger.info("Session ended, final text: %s", full_text)

        logger.info("AssemblyAI streaming session stopped")

    # -- Event handlers (called from the SDK's internal thread) --

    def _on_begin(self, client: Any, event: Any) -> None:
        """Handle streaming session begin event."""
        session_id: str = str(event.id)
        logger.info("Streaming session started: id=%s", session_id)

    def _on_turn(self, client: Any, event: Any) -> None:
        """Handle transcript turn event."""
        transcript: str = str(event.transcript)
        is_end_of_turn: bool = bool(event.end_of_turn)
        is_formatted: bool = bool(event.turn_is_formatted)

        logger.debug(
            "Turn event: text=%r end_of_turn=%s formatted=%s",
            transcript,
            is_end_of_turn,
            is_formatted,
        )

        if not transcript:
            return

        if self._on_partial and not is_end_of_turn:
            self._on_partial(transcript)

        if is_end_of_turn and (is_formatted or not self._config.format_turns):
            self._all_text_this_session.append(transcript)
            if self._on_final:
                self._on_final(transcript)

    def _on_terminated(self, client: Any, event: Any) -> None:
        """Handle streaming session termination event."""
        duration: float = float(event.audio_duration_seconds)
        logger.info("Session terminated: %.1fs audio processed", duration)

    def _on_stream_error(self, client: Any, error: Any) -> None:
        """Handle streaming error event."""
        logger.error("AssemblyAI streaming error: %s", error)
        if self._on_error:
            err: Exception = (
                error if isinstance(error, Exception) else Exception(str(error))
            )
            self._on_error(err)
