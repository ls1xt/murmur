"""Abstract base class for hotkey listeners."""

from abc import ABC, abstractmethod
from collections.abc import Callable


class HotkeyListener(ABC):
    """Base class for hotkey detection backends."""

    def __init__(self) -> None:
        self._on_activate: Callable[[str], None] | None = None
        self._on_deactivate: Callable[[], None] | None = None

    def set_callbacks(
        self,
        on_activate: Callable[[str], None],
        on_deactivate: Callable[[], None],
    ) -> None:
        """Register activation/deactivation callbacks.

        The on_activate callback receives the action name (e.g. "push_to_talk",
        "copy_to_clipboard") so the caller can behave differently per action.
        """
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

    def _dispatch_action(self, action: str) -> None:
        """Dispatch a hotkey press by action name."""
        if action in ("push_to_talk", "toggle_start", "copy_to_clipboard"):
            if self._on_activate:
                self._on_activate(action)
        elif action == "toggle_stop" and self._on_deactivate:
            self._on_deactivate()

    def _dispatch_release(self, action: str) -> None:
        """Dispatch a hotkey release by action name."""
        if action in ("push_to_talk", "copy_to_clipboard") and self._on_deactivate:
            self._on_deactivate()
        # toggle_start and toggle_stop releases are no-ops
