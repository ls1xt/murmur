"""Audio feedback -- start/stop beeps via PyAudio."""

from __future__ import annotations

import logging
import math
import struct
import threading
from typing import Any

logger = logging.getLogger(__name__)

_pyaudio_module: Any = None

try:
    import pyaudio as _pa  # type: ignore[import-untyped]
    _pyaudio_module = _pa
except ImportError:
    pass

# Single persistent PortAudio context for the process lifetime.
# Re-initializing Pa_Initialize/Pa_Terminate repeatedly after a prior
# terminate leaves ALSA in a bad state on systems with broken ALSA configs,
# causing a segfault on the second init. One instance, kept alive, avoids this.
_pa_instance: Any = None
_pa_lock = threading.Lock()


def _get_pa() -> Any:
    """Return the shared PyAudio instance, initializing it once if needed."""
    global _pa_instance  # noqa: PLW0603
    if _pa_instance is not None:
        return _pa_instance
    if _pyaudio_module is None:
        return None
    try:
        _pa_instance = _pyaudio_module.PyAudio()
    except Exception as e:
        logger.debug("PyAudio init failed: %s", e)
    return _pa_instance


class AudioFeedback:
    """Generates PCM sine tone beeps for start/stop feedback."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled and _pyaudio_module is not None

    def play_start(self) -> None:
        """Play a short beep indicating recording started (440 Hz)."""
        if not self._enabled:
            return
        threading.Thread(target=self._play_tone, args=(440, 0.1), daemon=True).start()

    def play_stop(self) -> None:
        """Play a short beep indicating recording stopped (880 Hz).

        Blocking: completes before returning so the caller can safely tear
        down the MicrophoneStream without a concurrent PortAudio race.
        """
        if not self._enabled:
            return
        self._play_tone(880, 0.1)

    @staticmethod
    def _play_tone(frequency: float, duration: float) -> None:
        """Generate and play a sine wave tone using the shared PyAudio instance."""
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

        with _pa_lock:
            pa = _get_pa()
            if pa is None:
                return
            try:
                stream: Any = pa.open(
                    format=_pyaudio_module.paInt16,
                    channels=1,
                    rate=sample_rate,
                    output=True,
                )
                try:
                    stream.write(samples)
                finally:
                    stream.stop_stream()
                    stream.close()
            except Exception as e:
                logger.debug("Audio feedback error: %s", e)
