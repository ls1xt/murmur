"""Abstract base class for hotkey listeners."""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

from murmur.config import HotkeyBinding

logger = logging.getLogger(__name__)


class HotkeyListener(ABC):
    """Base class for hotkey detection backends."""

    def __init__(self) -> None:
        self.on_activate: Callable[[HotkeyBinding], None] | None = None
        self.on_deactivate: Callable[[], None] | None = None

    def set_callbacks(
        self,
        on_activate: Callable[[HotkeyBinding], None],
        on_deactivate: Callable[[], None],
    ) -> None:
        """Register activation/deactivation callbacks.

        The on_activate callback receives the full HotkeyBinding so the caller
        can behave differently per action and access binding-level settings
        (language, inject_to, append_enter, etc.).
        """
        self.on_activate = on_activate
        self.on_deactivate = on_deactivate

    @abstractmethod
    def start(self) -> None:
        """Start listening for the hotkey."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop listening and release resources."""
        ...

    def dispatch_action(self, binding: HotkeyBinding) -> None:
        """Dispatch a hotkey press for the given binding."""
        if binding.action in ("push_to_talk", "toggle", "copy_to_clipboard"):
            if self.on_activate:
                self.on_activate(binding)

    def dispatch_release(self, binding: HotkeyBinding) -> None:
        """Dispatch a hotkey release for the given binding."""
        if binding.action in ("push_to_talk", "copy_to_clipboard") and self.on_deactivate:
            self.on_deactivate()
        # toggle release is a no-op; the toggle logic lives in the app layer
