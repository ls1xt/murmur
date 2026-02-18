"""Abstract base class for text injectors."""

from abc import ABC, abstractmethod


class TextInjector(ABC):
    """Base class for text injection backends."""

    @abstractmethod
    def inject(self, text: str) -> None:
        """Inject text into the currently focused application."""
        ...

    @abstractmethod
    def inject_raw(self, text: str) -> None:
        """Inject text without trailing space.

        Used for partial transcripts that are mid-sentence.
        Respects the configured injection strategy (same as inject()).
        """
        ...

    @abstractmethod
    def inject_backspaces(self, count: int) -> None:
        """Inject N backspace keypresses to erase previously-injected text."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the injection backend is available and ready."""
        ...

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to the system clipboard without injecting into an app.

        Default implementation does nothing.  Backends that support clipboard
        access (e.g. ydotool with wl-copy) should override this.
        """
