"""Abstract base class for text injectors."""

from abc import ABC, abstractmethod


class TextInjector(ABC):
    """Base class for text injection backends."""

    @abstractmethod
    def inject(self, text: str) -> None:
        """Inject text into the currently focused application."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the injection backend is available and ready."""
        ...
