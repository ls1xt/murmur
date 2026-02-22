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
from collections.abc import Callable, Iterator
from typing import Any, TypedDict

import sounddevice as _sd

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

    def __init__(
        self, sample_rate: int = 16_000, device: str | int | None = None
    ) -> None:
        self._sample_rate = sample_rate
        self._chunk_size = int(sample_rate * 0.1)  # 100ms chunks
        self._buf: queue.Queue[bytes | None] = queue.Queue()
        self._closed = threading.Event()
        self._chunk_count = 0

        # Log the default input device
        try:
            dev_info: Any = (
                _sd.query_devices(device=device, kind="input")
                if device is not None
                else _sd.query_devices(kind="input")
            )
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
                self._chunk_count,
                len(data),
                rms,
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
                raise StopIteration from None
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


class _StreamingParams(TypedDict, total=False):
    sample_rate: int
    encoding: str
    language_code: str
    speech_model: str
    format_turns: bool
    keyterms_prompt: list[str]
    language_detection: bool


_EventHandler = Callable[[Any, Any], None]


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

        self._client: Any | None = None
        self._mic_stream: _CallbackMicStream | None = None
        self._stream_thread: threading.Thread | None = None
        self._all_text_this_session: list[str] = []
        # Generation counter: incremented on each start() so stale callbacks
        # from a previous session don't trigger fatal errors.
        self._session_gen: int = 0
        # Cleared at stop() start, set at stop() end so start() can wait.
        self._stop_done = threading.Event()
        self._stop_done.set()
        self._current_language: str | None = None  # set on start(), used by reconnect()
        self._last_partial: str = ""

    @property
    def session_gen(self) -> int:
        """Generation counter for the current session."""
        return self._session_gen

    @property
    def last_partial(self) -> str:
        """Last partial transcript received."""
        return self._last_partial

    def test_connection(self) -> None:
        """Warm PortAudio and the AssemblyAI WebSocket at startup.

        1. Opens and immediately closes a mic stream so PortAudio initialises
           the audio device while the user is not yet recording.  Without this
           the first RawInputStream can take ~4 s on a cold PortAudio stack,
           causing the first recording session to drop several seconds of audio.

        2. Opens a brief WebSocket to AssemblyAI, waits for the Begin event
           (confirming auth), then disconnects.  Costs ~$0.000042 but ensures
           the TLS session is cached so subsequent connects are <1 s.

        Called in a background thread from DictationApp.run().
        """
        # Step 1: warm PortAudio
        logger.info("AssemblyAI: warming PortAudio...")
        try:
            import time as _time

            mic = _CallbackMicStream(
                sample_rate=self._config.sample_rate,
                device=self._config.mic_device,
            )
            _time.sleep(0.2)
            mic.close()
            logger.info("AssemblyAI: PortAudio warmed")
        except Exception as e:
            logger.warning("PortAudio pre-warm failed: %s", e)

        # Step 2: warm WebSocket / TLS
        logger.info("AssemblyAI: testing connection...")
        connected = threading.Event()

        client = _v3.StreamingClient(
            _v3.StreamingClientOptions(
                api_key=self._config.api_key,
                api_host="streaming.assemblyai.com",
            )
        )

        def _on_begin(c: Any, e: Any) -> None:
            connected.set()

        events: Any = _v3.StreamingEvents
        client.on(events.Begin, _on_begin)

        params: Any = _v3.StreamingParameters(
            sample_rate=self._config.sample_rate,
            format_turns=self._config.format_turns,
            encoding=_v3.Encoding.pcm_s16le,
        )

        try:
            client.connect(params)
            if connected.wait(timeout=5.0):
                logger.info("AssemblyAI connection test OK (API key valid, TLS warmed)")
            else:
                logger.warning("AssemblyAI connection test: no Begin event within 5s")
        except Exception as e:
            logger.warning("AssemblyAI connection test failed: %s", e)
        finally:
            with contextlib.suppress(Exception):
                client.disconnect(terminate=True)

    def start(self, language: str | None = None) -> None:
        """Start mic capture and streaming to AssemblyAI."""
        # Wait for any in-progress stop() to finish before claiming the slot.
        # This prevents "Too many concurrent sessions" from AssemblyAI.
        if not self._stop_done.wait(timeout=5.0):
            logger.warning("Previous session did not stop cleanly; starting anyway")

        # Atomic check-and-set: if two start() calls race past the wait above,
        # only the first one to acquire _streaming_lock proceeds.  The second
        # sees _streaming=True and exits without opening a second mic stream.
        with self._streaming_lock:
            if self._streaming:
                logger.warning("Already streaming")
                return
            self._streaming = True
        self._all_text_this_session = []
        self._session_gen += 1
        my_gen = self._session_gen

        client: Any = _v3.StreamingClient(
            _v3.StreamingClientOptions(
                api_key=self._config.api_key,
                api_host="streaming.assemblyai.com",
            )
        )
        self._client = client

        events: Any = _v3.StreamingEvents
        client.on(events.Begin, self._on_begin)
        client.on(events.Turn, self.on_turn)

        # Bind with generation captured now so stale callbacks from old
        # sessions are silently ignored rather than crashing the daemon.
        def _on_term(c: Any, e: Any, g: int = my_gen) -> None:
            self.on_terminated(c, e, g)

        def _on_err(c: Any, e: Any, g: int = my_gen) -> None:
            self.on_stream_error(c, e, g)

        client.on(events.Termination, _on_term)
        client.on(events.Error, _on_err)

        params_kwargs: _StreamingParams = {
            "sample_rate": self._config.sample_rate,
            "format_turns": self._config.format_turns,
            "encoding": _v3.Encoding.pcm_s16le,
        }
        if self._config.keyterms_prompt:
            params_kwargs["keyterms_prompt"] = self._config.keyterms_prompt
        effective_language = language or self._config.language
        self._current_language = effective_language
        # v3 API has no language_code input — use speech_model to select
        # multilingual (non-English) vs English-optimised model.
        if effective_language and not effective_language.startswith("en"):
            params_kwargs["speech_model"] = (
                _v3.SpeechModel.universal_streaming_multilingual
            )
            params_kwargs["language_detection"] = True
        else:
            params_kwargs["speech_model"] = _v3.SpeechModel.universal_streaming_english
        params: Any = _v3.StreamingParameters(**params_kwargs)
        logger.info("StreamingParameters kwargs sent to AssemblyAI: %s", params_kwargs)
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

        client.connect(params)

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
                if self.on_error is not None:
                    self.on_error(e)

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
        if full_text and self.on_final:
            logger.info("Session ended, final text: %s", full_text)

        logger.info("AssemblyAI streaming session stopped")
        self._stop_done.set()

    # -- Event handlers (called from the SDK's internal thread) --

    def _on_begin(self, client: Any, event: Any) -> None:
        """Handle streaming session begin event."""
        session_id: str = str(event.id)
        logger.info("Streaming session started: id=%s", session_id)

    def on_turn(self, client: Any, event: Any) -> None:
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

        if self.on_partial and not is_end_of_turn:
            logger.info("Dispatching partial: %r", transcript[:120])
            self._last_partial = transcript
            self.on_partial(transcript)

        if is_end_of_turn and (is_formatted or not self._config.format_turns):
            self._all_text_this_session.append(transcript)
            logger.info("Dispatching final: %r", transcript[:120])
            if self.on_final:
                self.on_final(transcript)
        elif is_end_of_turn and not is_formatted:
            logger.info(
                "End of turn but waiting for formatted version (format_turns=%s)",
                self._config.format_turns,
            )

    def on_terminated(self, client: Any, event: Any, gen: int) -> None:
        """Handle streaming session termination event.

        Normal termination (after stop()) logs and returns.
        Stale callbacks from a previous session (gen mismatch) are ignored.
        Unexpected termination (while still streaming) attempts reconnect.
        """
        duration: float = float(event.audio_duration_seconds)
        logger.info("Session terminated: %.1fs audio processed (gen=%d)", duration, gen)

        if gen != self._session_gen:
            logger.debug(
                "Ignoring stale termination for gen=%d (current=%d)",
                gen,
                self._session_gen,
            )
            return

        if self._is_streaming:
            # Unexpected termination -- attempt reconnect in background thread
            threading.Thread(target=self.reconnect, daemon=True).start()

    def reconnect(self) -> None:
        """Attempt to reconnect after unexpected WebSocket termination.

        Runs in a background thread.  Tries up to ``reconnect_attempts``
        times with exponential backoff.  Falls back to fatal exit if all
        attempts are exhausted.
        """
        import time

        attempts = self._config.reconnect_attempts
        delay = self._config.reconnect_delay_ms / 1000.0

        logger.warning(
            "WebSocket dropped unexpectedly; attempting reconnect (%d attempts)",
            attempts,
        )

        for attempt in range(1, attempts + 1):
            if not self._is_streaming:
                # User stopped recording while we were waiting -- abort reconnect
                logger.info("Reconnect aborted: user stopped recording")
                return

            logger.info(
                "Reconnect attempt %d/%d (delay=%.1fs)",
                attempt,
                attempts,
                delay if attempt > 1 else 0,
            )

            if attempt > 1:
                time.sleep(delay)
                delay = min(delay * 2, 30.0)  # exponential backoff, cap at 30s

            try:
                # Clean up old client and mic stream
                if self._mic_stream is not None:
                    with contextlib.suppress(Exception):
                        self._mic_stream.close()
                    self._mic_stream = None
                if self._client is not None:
                    with contextlib.suppress(Exception):
                        self._client.disconnect(terminate=False)
                    self._client = None

                # Re-increment generation to invalidate stale callbacks
                self._session_gen += 1
                my_gen = self._session_gen

                reconnect_client: Any = _v3.StreamingClient(
                    _v3.StreamingClientOptions(
                        api_key=self._config.api_key,
                        api_host="streaming.assemblyai.com",
                    )
                )
                self._client = reconnect_client
                events: Any = _v3.StreamingEvents
                reconnect_client.on(events.Begin, self._on_begin)
                reconnect_client.on(events.Turn, self.on_turn)

                def _on_term_r(c: Any, e: Any, g: int = my_gen) -> None:
                    self.on_terminated(c, e, g)

                def _on_err_r(c: Any, e: Any, g: int = my_gen) -> None:
                    self.on_stream_error(c, e, g)

                reconnect_client.on(events.Termination, _on_term_r)
                reconnect_client.on(events.Error, _on_err_r)

                params_kwargs: _StreamingParams = {
                    "sample_rate": self._config.sample_rate,
                    "format_turns": self._config.format_turns,
                    "encoding": _v3.Encoding.pcm_s16le,
                }
                if self._config.keyterms_prompt:
                    params_kwargs["keyterms_prompt"] = self._config.keyterms_prompt
                if self._current_language and not self._current_language.startswith(
                    "en"
                ):
                    params_kwargs["speech_model"] = (
                        _v3.SpeechModel.universal_streaming_multilingual
                    )
                    params_kwargs["language_detection"] = True
                else:
                    params_kwargs["speech_model"] = (
                        _v3.SpeechModel.universal_streaming_english
                    )
                logger.info(
                    "Reconnect StreamingParameters kwargs sent to AssemblyAI: %s",
                    params_kwargs,
                )
                params: Any = _v3.StreamingParameters(**params_kwargs)

                self._mic_stream = _CallbackMicStream(
                    sample_rate=self._config.sample_rate
                )
                reconnect_client.connect(params)

                self._stream_thread = threading.Thread(
                    target=self._stream_audio, daemon=True
                )
                self._stream_thread.start()

                logger.info(
                    "Reconnect successful on attempt %d (gen=%d)", attempt, my_gen
                )
                return

            except Exception as e:
                logger.warning("Reconnect attempt %d failed: %s", attempt, e)

        # All attempts exhausted
        fatal_from_thread(
            f"WebSocket connection lost and reconnect failed after {attempts} attempts"
        )

    def on_stream_error(self, client: Any, error: Any, gen: int) -> None:
        """Handle streaming error.

        Stale callbacks from a previous session (gen mismatch) are ignored.
        """
        if gen != self._session_gen:
            logger.debug(
                "Ignoring stale error for gen=%d (current=%d): %s",
                gen,
                self._session_gen,
                error,
            )
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
