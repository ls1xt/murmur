"""Abstract base class for speech-to-text transcribers."""

from abc import ABC, abstractmethod
from collections.abc import Callable


class Transcriber(ABC):
    """Base class for streaming speech-to-text backends."""

    def __init__(self) -> None:
        self._is_streaming = False
        self._on_partial: Callable[[str], None] | None = None
        self._on_final: Callable[[str], None] | None = None
        self._on_error: Callable[[Exception], None] | None = None

    def set_callbacks(
        self,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        """Register transcript event callbacks."""
        self._on_partial = on_partial
        self._on_final = on_final
        self._on_error = on_error

    @property
    def is_streaming(self) -> bool:
        """Whether the transcriber is currently streaming audio."""
        return self._is_streaming

    @abstractmethod
    def start(self) -> None:
        """Start streaming audio and transcribing."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop streaming and disconnect."""
        ...
