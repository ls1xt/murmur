"""
AssemblyAI streaming transcriber using the Universal-Streaming v3 API.

Uses the official assemblyai Python SDK with the new StreamingClient from
assemblyai.streaming.v3.
"""

import logging
import threading
from typing import Optional, Type

import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent,
    StreamingClient,
    StreamingClientOptions,
    StreamingError,
    StreamingEvents,
    StreamingParameters,
    TerminationEvent,
    TurnEvent,
)

from .base import Transcriber
from ..config import TranscriberConfig

logger = logging.getLogger(__name__)


class AssemblyAITranscriber(Transcriber):
    """
    Streams audio from the microphone to AssemblyAI's Universal-Streaming
    API and delivers transcript events via callbacks.
    """

    def __init__(self, config: TranscriberConfig):
        super().__init__()
        self._config = config

        if not config.api_key:
            raise ValueError(
                "AssemblyAI API key is required.\n"
                "Set ASSEMBLYAI_API_KEY env var or add it to config."
            )

        self._client: Optional[StreamingClient] = None
        self._mic_stream = None
        self._stream_thread: Optional[threading.Thread] = None

        # Accumulate transcript text within a session
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

        # Create the streaming client
        self._client = StreamingClient(
            StreamingClientOptions(
                api_key=self._config.api_key,
                api_host="streaming.assemblyai.com",
            )
        )

        # Register event handlers
        self._client.on(StreamingEvents.Begin, self._on_begin)
        self._client.on(StreamingEvents.Turn, self._on_turn)
        self._client.on(StreamingEvents.Termination, self._on_terminated)
        self._client.on(StreamingEvents.Error, self._on_stream_error)

        # Connect with parameters
        params = StreamingParameters(
            sample_rate=self._config.sample_rate,
            format_turns=self._config.format_turns,
        )
        self._client.connect(params)

        # Start streaming audio from mic in a background thread
        self._stream_thread = threading.Thread(
            target=self._stream_audio, daemon=True
        )
        self._stream_thread.start()
        logger.info("AssemblyAI streaming session started")

    def _stream_audio(self) -> None:
        """Stream microphone audio to AssemblyAI (runs in background thread)."""
        try:
            self._mic_stream = aai.extras.MicrophoneStream(
                sample_rate=self._config.sample_rate
            )
            # client.stream() blocks until the stream ends
            self._client.stream(self._mic_stream)
        except Exception as e:
            if self._is_streaming:
                logger.error("Mic streaming error: %s", e)
                if self._on_error:
                    self._on_error(e)

    def stop(self) -> None:
        """Stop streaming and disconnect."""
        if not self._is_streaming:
            return

        self._is_streaming = False
        logger.info("Stopping AssemblyAI streaming session...")

        # Close the mic stream — this will cause client.stream() to return
        if self._mic_stream:
            try:
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        # Disconnect the client
        if self._client:
            try:
                self._client.disconnect(terminate=True)
            except Exception as e:
                logger.debug("Disconnect error (usually harmless): %s", e)
            self._client = None

        # Wait for the streaming thread to finish
        if self._stream_thread:
            self._stream_thread.join(timeout=3.0)
            self._stream_thread = None

        # Deliver any accumulated text as a final callback
        full_text = " ".join(self._all_text_this_session).strip()
        if full_text and self._on_final:
            # If the last turn wasn't yet marked end_of_turn, deliver it now
            logger.info("Session ended, final text: %s", full_text)

        logger.info("AssemblyAI streaming session stopped")

    # ── Event handlers (called from the SDK's internal thread) ──

    def _on_begin(self, client: Type[StreamingClient], event: BeginEvent) -> None:
        logger.info("Streaming session started: id=%s", event.id)

    def _on_turn(self, client: Type[StreamingClient], event: TurnEvent) -> None:
        transcript = event.transcript
        is_end_of_turn = event.end_of_turn
        is_formatted = event.turn_is_formatted

        logger.debug(
            "Turn event: text=%r end_of_turn=%s formatted=%s",
            transcript,
            is_end_of_turn,
            is_formatted,
        )

        if not transcript:
            return

        # For live captioning / preview, emit partials
        if self._on_partial and not is_end_of_turn:
            self._on_partial(transcript)

        # When we get the formatted end-of-turn, that's our finalized text
        if is_end_of_turn:
            if is_formatted:
                # Formatted turn — this is the polished version with punctuation
                self._all_text_this_session.append(transcript)
                if self._on_final:
                    self._on_final(transcript)
            elif not self._config.format_turns:
                # format_turns is disabled, so unformatted end_of_turn is final
                self._all_text_this_session.append(transcript)
                if self._on_final:
                    self._on_final(transcript)
            # If format_turns is enabled and this is an unformatted end_of_turn,
            # we wait for the formatted version that arrives shortly after.

    def _on_terminated(
        self, client: Type[StreamingClient], event: TerminationEvent
    ) -> None:
        logger.info(
            "Session terminated: %.1fs audio processed",
            event.audio_duration_seconds,
        )

    def _on_stream_error(
        self, client: Type[StreamingClient], error: StreamingError
    ) -> None:
        logger.error("AssemblyAI streaming error: %s", error)
        if self._on_error:
            self._on_error(error)
