"""Audio feedback -- start/stop beeps via PyAudio."""

from __future__ import annotations

import logging
import math
import struct
import threading
from typing import Any

logger = logging.getLogger(__name__)

_pyaudio: Any = None


def _load_pyaudio() -> bool:
    """Attempt to import pyaudio. Returns True if available."""
    global _pyaudio  # noqa: PLW0603
    try:
        import pyaudio as _pa  # type: ignore[import-untyped]

        _pyaudio = _pa
    except ImportError:
        logger.debug("PyAudio not available; audio feedback disabled")
        return False
    return True


_HAS_PYAUDIO: bool = _load_pyaudio()


class AudioFeedback:
    """Generates PCM sine tone beeps for start/stop feedback."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled and _HAS_PYAUDIO

    def play_start(self) -> None:
        """Play a short beep indicating recording started (440 Hz)."""
        if not self._enabled:
            return
        threading.Thread(target=self._play_tone, args=(440, 0.1), daemon=True).start()

    def play_stop(self) -> None:
        """Play a short beep indicating recording stopped (880 Hz)."""
        if not self._enabled:
            return
        threading.Thread(target=self._play_tone, args=(880, 0.1), daemon=True).start()

    @staticmethod
    def _play_tone(frequency: float, duration: float) -> None:
        """Generate and play a sine wave tone."""
        if _pyaudio is None:
            return

        sample_rate = 44100
        num_samples = int(sample_rate * duration)

        samples = b"".join(
            struct.pack(
                "h",
                int(
                    32767 * 0.3 * math.sin(2.0 * math.pi * frequency * i / sample_rate)
                ),
            )
            for i in range(num_samples)
        )

        try:
            pa: Any = _pyaudio.PyAudio()
            try:
                stream: Any = pa.open(
                    format=_pyaudio.paInt16,
                    channels=1,
                    rate=sample_rate,
                    output=True,
                )
                try:
                    stream.write(samples)
                finally:
                    stream.stop_stream()
                    stream.close()
            finally:
                pa.terminate()
        except Exception as e:
            logger.debug("Audio feedback error: %s", e)
