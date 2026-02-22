"""Audio feedback -- start/stop beeps via sounddevice or afplay."""

from __future__ import annotations

import logging
import math
import os
import struct
import subprocess
import sys
import tempfile
import threading
import wave
from typing import Any

import sounddevice as _sd  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class AudioFeedback:
    """Generates PCM sine tone beeps for start/stop feedback.

    On macOS, uses ``afplay`` to play pre-generated WAV files.  ``afplay``
    starts in ~20–50 ms (fork+exec of a system binary that CoreAudio keeps
    warm), versus ~1 s for opening a fresh PortAudio/CoreAudio stream via
    sounddevice.  On other platforms falls back to sounddevice.
    """

    _SAMPLE_RATE = 44100

    def __init__(
        self,
        enabled: bool = True,
        start_hz: float = 440.0,
        stop_hz: float = 880.0,
        amplitude: float = 0.3,
        start_duration_ms: int = 100,
        stop_duration_ms: int = 100,
    ) -> None:
        self._enabled = enabled
        self._start_hz = start_hz
        self._stop_hz = stop_hz
        self._amplitude = amplitude
        self._start_duration_ms = start_duration_ms
        self._stop_duration_ms = stop_duration_ms
        self._start_wav: str | None = None

        if enabled and start_duration_ms > 0 and sys.platform == "darwin":
            try:
                self._start_wav = self._write_wav(start_hz, start_duration_ms / 1000.0, amplitude)
                logger.debug("Pre-generated start WAV: %s", self._start_wav)
            except Exception as exc:
                logger.debug("WAV pre-generation failed, using sounddevice: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play_start(self) -> None:
        """Play a short beep indicating recording started (non-blocking)."""
        if not self._enabled or self._start_duration_ms <= 0:
            return
        if self._start_wav:
            # afplay starts near-instantly; fire-and-forget
            try:
                subprocess.Popen(
                    ["afplay", self._start_wav],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception as exc:
                logger.debug("afplay failed: %s", exc)
        threading.Thread(
            target=self._play_tone,
            args=(self._start_hz, self._start_duration_ms / 1000.0, self._amplitude),
            daemon=True,
        ).start()

    def play_stop(self) -> None:
        """Play a short beep indicating recording stopped.

        Blocking: completes before returning so the caller can safely tear
        down the mic stream without a concurrent audio race.

        Uses sounddevice directly (not afplay) -- afplay's subprocess startup
        adds ~400 ms of overhead on top of the audio duration, making it worse
        than sounddevice for this blocking call.
        """
        if not self._enabled or self._stop_duration_ms <= 0:
            return
        self._play_tone(self._stop_hz, self._stop_duration_ms / 1000.0, self._amplitude)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @classmethod
    def _write_wav(cls, frequency: float, duration: float, amplitude: float = 0.3) -> str:
        """Generate a sine-wave WAV file and return its path."""
        n = int(cls._SAMPLE_RATE * duration)
        data = struct.pack(
            f"{n}h",
            *[
                int(
                    32767
                    * amplitude
                    * math.sin(2.0 * math.pi * frequency * i / cls._SAMPLE_RATE)
                )  # noqa: E501
                for i in range(n)
            ],
        )
        fd, path = tempfile.mkstemp(suffix=".wav")
        try:
            with wave.open(os.fdopen(fd, "wb"), "w") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(cls._SAMPLE_RATE)
                wf.writeframes(data)
        except Exception:
            import contextlib

            with contextlib.suppress(OSError):
                os.close(fd)
            os.unlink(path)
            raise
        return path

    @staticmethod
    def _play_tone(frequency: float, duration: float, amplitude: float = 0.3) -> None:
        """Generate and play a sine wave tone via sounddevice (fallback)."""
        sample_rate = AudioFeedback._SAMPLE_RATE
        num_samples = int(sample_rate * duration)

        samples = b"".join(
            struct.pack(
                "h",
                int(
                    32767
                    * amplitude
                    * math.sin(2.0 * math.pi * frequency * i / sample_rate)
                ),
            )
            for i in range(num_samples)
        )

        try:
            stream: Any = _sd.RawOutputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
            )
            stream.start()
            try:
                stream.write(samples)
            finally:
                stream.stop()
                stream.close()
        except Exception as e:
            if not getattr(AudioFeedback, "_audio_warned", False):
                logger.warning("Audio feedback error: %s", e)
                AudioFeedback._audio_warned = True  # type: ignore[attr-defined]
            else:
                logger.debug("Audio feedback error: %s", e)
