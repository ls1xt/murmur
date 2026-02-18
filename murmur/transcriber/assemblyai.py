"""
AssemblyAI streaming transcriber using the Universal-Streaming v3 API.

Uses the official assemblyai Python SDK with the new StreamingClient from
assemblyai.streaming.v3.
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import queue
import threading
from typing import Any, Iterator

import pyaudio as _pyaudio  # type: ignore[import-untyped]  # noqa: N812

from murmur.config import TranscriberConfig
from murmur.errors import fatal_from_thread
from murmur.transcriber.base import Transcriber

logger = logging.getLogger(__name__)

# Import the v3 streaming submodule (can't use aai.streaming.v3 at runtime).
_v3: Any = importlib.import_module("assemblyai.streaming.v3")


class _CallbackMicStream:
    """Thread-safe microphone stream using PyAudio callback mode.

    The SDK's ``MicrophoneStream`` uses blocking ``stream.read()`` which
    segfaults when ``close()`` is called from another thread (PortAudio
    does not support concurrent ``Pa_ReadStream`` / ``Pa_CloseStream``).

    This implementation uses callback mode instead: PortAudio pushes audio
    into a ``queue.Queue`` from its own thread, and ``__next__`` reads from
    that queue.  ``close()`` is safe to call from any thread because it
    never races with a native read call.
    """

    def __init__(self, sample_rate: int = 16_000) -> None:
        self._sample_rate = sample_rate
        self._chunk_size = int(sample_rate * 0.1)
        self._buf: queue.Queue[bytes | None] = queue.Queue()
        self._closed = threading.Event()

        self._pa = _pyaudio.PyAudio()
        self._stream: Any = self._pa.open(
            format=_pyaudio.paInt16,
            channels=1,
            rate=sample_rate,
            input=True,
            frames_per_buffer=self._chunk_size,
            stream_callback=self._callback,
        )

    def _callback(
        self,
        in_data: bytes | None,
        frame_count: int,  # noqa: ARG002
        time_info: Any,  # noqa: ARG002
        status_flags: int,  # noqa: ARG002
    ) -> tuple[None, int]:
        if self._closed.is_set():
            return (None, _pyaudio.paComplete)
        self._buf.put(in_data)
        return (None, _pyaudio.paContinue)

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        if self._closed.is_set():
            raise StopIteration
        try:
            data = self._buf.get(timeout=0.5)
        except queue.Empty:
            if self._closed.is_set():
                raise StopIteration
            return b""
        if data is None:
            raise StopIteration
        return data

    def close(self) -> None:
        """Signal the callback to stop, then tear down PortAudio resources."""
        if self._closed.is_set():
            return
        self._closed.set()
        self._buf.put(None)  # unblock any waiting __next__
        with contextlib.suppress(Exception):
            self._stream.stop_stream()
        with contextlib.suppress(Exception):
            self._stream.close()
        with contextlib.suppress(Exception):
            self._pa.terminate()


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
            self._mic_stream = _CallbackMicStream(
                sample_rate=self._config.sample_rate
            )
            client: Any = self._client
            mic: Any = self._mic_stream
            if client is not None:
                client.stream(mic)
        except Exception as e:
            if self._is_streaming:
                logger.error("Audio stream error: %s", e)
                if self._on_error is not None:
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
        """Handle streaming session termination event.

        Normal termination (after stop()) logs and returns.
        Unexpected termination (while still streaming) exits the daemon.
        """
        duration: float = float(event.audio_duration_seconds)
        logger.info("Session terminated: %.1fs audio processed", duration)

        if self._is_streaming:
            # Unexpected termination -- we didn't call stop()
            fatal_from_thread("WebSocket connection lost unexpectedly")

    def _on_stream_error(self, client: Any, error: Any) -> None:
        """Handle streaming error -- exit immediately per user decision."""
        error_str = str(error)

        # Classify error codes for user-friendly messages
        if "1008" in error_str:
            message = (
                "AssemblyAI auth error (code 1008): "
                "check your API key and account balance"
            )
        elif "3005" in error_str:
            message = "AssemblyAI session expired (code 3005)"
        else:
            message = f"WebSocket error: {error_str}"

        fatal_from_thread(message)
