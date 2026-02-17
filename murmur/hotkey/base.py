"""Abstract base class for hotkey listeners."""

from abc import ABC, abstractmethod
from collections.abc import Callable


class HotkeyListener(ABC):
    """Base class for hotkey detection backends."""

    def __init__(self, mode: str = "push_to_talk") -> None:
        self.mode = mode
        self._on_activate: Callable[[], None] | None = None
        self._on_deactivate: Callable[[], None] | None = None
        self._active: bool = False

    def set_callbacks(
        self,
        on_activate: Callable[[], None],
        on_deactivate: Callable[[], None],
    ) -> None:
        """Register activation/deactivation callbacks."""
        self._on_activate = on_activate
        self._on_deactivate = on_deactivate

    @abstractmethod
    def start(self) -> None:
        """Start listening for the hotkey."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop listening and release resources."""
        ...

    def _handle_hotkey_press(self) -> None:
        """Handle a hotkey press event (mode-aware)."""
        if self.mode == "push_to_talk":
            if self._on_activate:
                self._on_activate()
        elif self.mode == "toggle":
            if self._active:
                self._active = False
                if self._on_deactivate:
                    self._on_deactivate()
            else:
                self._active = True
                if self._on_activate:
                    self._on_activate()

    def _handle_hotkey_release(self) -> None:
        """Handle a hotkey release event (mode-aware)."""
        if self.mode == "push_to_talk" and self._on_deactivate:
            self._on_deactivate()
