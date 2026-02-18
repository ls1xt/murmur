"""Audio feedback -- start/stop beeps via sounddevice."""

from __future__ import annotations

import logging
import math
import struct
import threading
from typing import Any

import sounddevice as _sd  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class AudioFeedback:
    """Generates PCM sine tone beeps for start/stop feedback."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    def play_start(self) -> None:
        """Play a short beep indicating recording started (440 Hz)."""
        if not self._enabled:
            return
        threading.Thread(target=self._play_tone, args=(440, 0.1), daemon=True).start()

    def play_stop(self) -> None:
        """Play a short beep indicating recording stopped (880 Hz).

        Blocking: completes before returning so the caller can safely tear
        down the mic stream without a concurrent audio race.
        """
        if not self._enabled:
            return
        self._play_tone(880, 0.1)

    @staticmethod
    def _play_tone(frequency: float, duration: float) -> None:
        """Generate and play a sine wave tone via sounddevice."""
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
