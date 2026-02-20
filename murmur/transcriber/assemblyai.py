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

import sounddevice as _sd  # type: ignore[import-untyped]

from murmur.config import TranscriberConfig
from murmur.errors import fatal_from_thread
from murmur.transcriber.base import Transcriber

logger = logging.getLogger(__name__)


def _rms_level(data: bytes) -> float:
    """Compute RMS audio level from PCM s16le bytes."""
    import struct as _struct

    n = len(data) // 2
    if n == 0:
        return 0.0
    samples = _struct.unpack(f"<{n}h", data)
    return (sum(s * s for s in samples) / n) ** 0.5

# Import the v3 streaming submodule (can't use aai.streaming.v3 at runtime).
_v3: Any = importlib.import_module("assemblyai.streaming.v3")


class _CallbackMicStream:
    """Thread-safe microphone stream using sounddevice (PortAudio).

    Uses ``sounddevice.RawInputStream`` in callback mode which works
    reliably with PipeWire, PulseAudio, and ALSA.  Audio chunks are
    pushed into a ``queue.Queue`` and consumed via ``__next__``.
    ``close()`` is safe to call from any thread.
    """

    def __init__(self, sample_rate: int = 16_000, device: str | int | None = None) -> None:
        self._sample_rate = sample_rate
        self._chunk_size = int(sample_rate * 0.1)  # 100ms chunks
        self._buf: queue.Queue[bytes | None] = queue.Queue()
        self._closed = threading.Event()
        self._chunk_count = 0

        # Log the default input device
        try:
            dev_info: Any = _sd.query_devices(device=device, kind="input") if device is not None else _sd.query_devices(kind="input")
            logger.info(
                "Mic device: %s (index=%s, channels=%s, rate=%s)",
                dev_info.get("name", "unknown"),
                dev_info.get("index", "?"),
                dev_info.get("max_input_channels", "?"),
                dev_info.get("default_samplerate", "?"),
            )
        except Exception as e:
            logger.warning("Could not query input device: %s", e)

        self._stream: Any = _sd.RawInputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=self._chunk_size,
            callback=self._callback,
            device=device,
        )
        self._stream.start()

    def _callback(
        self,
        indata: bytes,
        frames: int,  # noqa: ARG002
        time_info: Any,  # noqa: ARG002
        status: Any,  # noqa: ARG002
    ) -> None:
        if self._closed.is_set():
            return
        data = bytes(indata)
        self._buf.put(data)
        self._chunk_count += 1
        # Log audio level every ~1s (10 chunks at 100ms each)
        if self._chunk_count % 10 == 1:
            rms = _rms_level(data)
            logger.info(
                "Mic audio chunk #%d: %d bytes, RMS=%.0f",
                self._chunk_count, len(data), rms,
            )

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
        """Stop the stream and release resources."""
        if self._closed.is_set():
            return
        self._closed.set()
        self._buf.put(None)  # unblock any waiting __next__
        with contextlib.suppress(Exception):
            self._stream.stop()
        with contextlib.suppress(Exception):
            self._stream.close()


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
        self._all_text_this_session: list[str] = []
        # Generation counter: incremented on each start() so stale callbacks
        # from a previous session don't trigger fatal errors.
        self._session_gen: int = 0
        # Cleared at stop() start, set at stop() end so start() can wait.
        self._stop_done = threading.Event()
        self._stop_done.set()

    def start(self) -> None:
        """Start mic capture and streaming to AssemblyAI."""
        if self._is_streaming:
            logger.warning("Already streaming")
            return

        # Wait for any in-progress stop() to finish before opening a new
        # session -- prevents "Too many concurrent sessions" from AssemblyAI.
        if not self._stop_done.wait(timeout=5.0):
            logger.warning("Previous session did not stop cleanly; starting anyway")

        self._is_streaming = True
        self._all_text_this_session = []
        self._session_gen += 1
        my_gen = self._session_gen

        self._client = _v3.StreamingClient(
            _v3.StreamingClientOptions(
                api_key=self._config.api_key,
                api_host="streaming.assemblyai.com",
            )
        )

        events: Any = _v3.StreamingEvents
        self._client.on(events.Begin, self._on_begin)
        self._client.on(events.Turn, self._on_turn)
        # Bind with generation captured now so stale callbacks from old
        # sessions are silently ignored rather than crashing the daemon.
        self._client.on(
            events.Termination,
            lambda c, e, g=my_gen: self._on_terminated(c, e, g),
        )
        self._client.on(
            events.Error,
            lambda c, e, g=my_gen: self._on_stream_error(c, e, g),
        )

        params_kwargs: dict[str, Any] = {
            "sample_rate": self._config.sample_rate,
            "format_turns": self._config.format_turns,
            "encoding": _v3.Encoding.pcm_s16le,
        }
        if self._config.keyterms_prompt:
            params_kwargs["keyterms_prompt"] = self._config.keyterms_prompt
        if self._config.language and self._config.language != "en":
            params_kwargs["language_code"] = self._config.language
        params: Any = _v3.StreamingParameters(**params_kwargs)
        logger.info(
            "StreamingParameters: sample_rate=%d, format_turns=%s, encoding=%s, keyterms=%s, language=%s",
            self._config.sample_rate,
            self._config.format_turns,
            "pcm_s16le",
            self._config.keyterms_prompt or [],
            self._config.language,
        )
        # Open the mic stream BEFORE connecting so that audio captured during
        # the WebSocket handshake (~200-500 ms) is buffered in the queue and
        # not lost.
        try:
            self._mic_stream = _CallbackMicStream(
                sample_rate=self._config.sample_rate,
                device=self._config.mic_device,
            )
        except Exception as e:
            self._is_streaming = False
            logger.error("Failed to open mic stream: %s", e)
            raise

        self._client.connect(params)

        self._stream_thread = threading.Thread(target=self._stream_audio, daemon=True)
        self._stream_thread.start()
        logger.info("AssemblyAI streaming session started (gen=%d)", my_gen)

    def _stream_audio(self) -> None:
        """Stream microphone audio to AssemblyAI (runs in background thread).

        The mic stream is created in start() before connect() so that audio
        captured during the WebSocket handshake is already buffered here.
        """
        try:
            logger.info("Starting audio stream to AssemblyAI")
            client: Any = self._client
            mic: Any = self._mic_stream
            if client is not None and mic is not None:
                client.stream(mic)
            logger.info("Audio stream ended")
        except Exception as e:
            if self._is_streaming:
                logger.error("Audio stream error: %s", e)
                if self._on_error is not None:
                    self._on_error(e)

    def stop(self) -> None:
        """Stop streaming and disconnect."""
        if not self._is_streaming:
            return

        self._stop_done.clear()
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
        self._stop_done.set()

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

        logger.info(
            "Turn event: end_of_turn=%s formatted=%s text=%r",
            is_end_of_turn,
            is_formatted,
            transcript[:120] if transcript else "",
        )

        if not transcript:
            logger.debug("Turn event had empty transcript, skipping")
            return

        if self._on_partial and not is_end_of_turn:
            logger.info("Dispatching partial: %r", transcript[:120])
            self._on_partial(transcript)

        if is_end_of_turn and (is_formatted or not self._config.format_turns):
            self._all_text_this_session.append(transcript)
            logger.info("Dispatching final: %r", transcript[:120])
            if self._on_final:
                self._on_final(transcript)
        elif is_end_of_turn and not is_formatted:
            logger.info(
                "End of turn but waiting for formatted version (format_turns=%s)",
                self._config.format_turns,
            )

    def _on_terminated(self, client: Any, event: Any, gen: int) -> None:
        """Handle streaming session termination event.

        Normal termination (after stop()) logs and returns.
        Stale callbacks from a previous session (gen mismatch) are ignored.
        Unexpected termination (while still streaming) exits the daemon.
        """
        duration: float = float(event.audio_duration_seconds)
        logger.info("Session terminated: %.1fs audio processed (gen=%d)", duration, gen)

        if gen != self._session_gen:
            logger.debug("Ignoring stale termination for gen=%d (current=%d)", gen, self._session_gen)
            return

        if self._is_streaming:
            # Unexpected termination -- we didn't call stop()
            fatal_from_thread("WebSocket connection lost unexpectedly")

    def _on_stream_error(self, client: Any, error: Any, gen: int) -> None:
        """Handle streaming error.

        Stale callbacks from a previous session (gen mismatch) are ignored.
        """
        if gen != self._session_gen:
            logger.debug("Ignoring stale error for gen=%d (current=%d): %s", gen, self._session_gen, error)
            return

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
