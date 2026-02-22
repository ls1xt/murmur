"""Abstract base class for speech-to-text transcribers."""

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

TranscriptionCallback = Callable[[str], None]


class Transcriber(ABC):
    """Base class for streaming speech-to-text backends."""

    def __init__(self) -> None:
        self._streaming_lock = threading.Lock()
        self._streaming: bool = False
        self.on_partial: TranscriptionCallback | None = None
        self.on_final: TranscriptionCallback | None = None
        self.on_error: Callable[[Exception], None] | None = None

    @property
    def _is_streaming(self) -> bool:
        with self._streaming_lock:
            return self._streaming

    @_is_streaming.setter
    def _is_streaming(self, value: bool) -> None:
        with self._streaming_lock:
            self._streaming = value

    def set_callbacks(
        self,
        on_partial: TranscriptionCallback,
        on_final: TranscriptionCallback,
        on_error: Callable[[Exception], None],
    ) -> None:
        """Register transcript event callbacks."""
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error

    @property
    def is_streaming(self) -> bool:
        """Whether the transcriber is currently streaming audio."""
        return self._is_streaming

    @abstractmethod
    def start(self, language: str | None = None) -> None:
        """Start streaming audio and transcribing."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop streaming and disconnect."""
        ...

    def test_connection(self) -> None:
        """Optional startup connection test. Override in backends that support it."""
