"""Abstract base class for hotkey listeners."""

import logging
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable

logger = logging.getLogger(__name__)


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

    def _dispatch_action(
        self, action: str, tmux_target: str = "", tmux_keys: str = ""
    ) -> None:
        """Dispatch a hotkey press by action name."""
        if action == "tmux_send_keys":
            if tmux_target and tmux_keys:
                logger.info(
                    "tmux send-keys: target=%r keys=%r", tmux_target, tmux_keys
                )
                try:
                    subprocess.run(
                        ["tmux", "send-keys", "-t", tmux_target, tmux_keys],
                        check=False,
                        capture_output=True,
                    )
                except FileNotFoundError:
                    logger.error("tmux not found; cannot send keys to pane")
                except OSError as e:
                    logger.error("tmux send-keys failed: %s", e)
            else:
                logger.warning(
                    "tmux_send_keys binding missing tmux_target or tmux_keys"
                )
        elif action in ("push_to_talk", "toggle_start", "copy_to_clipboard"):
            if self._on_activate:
                self._on_activate(action)
        elif action == "toggle_stop" and self._on_deactivate:
            self._on_deactivate()

    def _dispatch_release(self, action: str) -> None:
        """Dispatch a hotkey release by action name."""
        if action in ("push_to_talk", "copy_to_clipboard") and self._on_deactivate:
            self._on_deactivate()
        # toggle_start and toggle_stop releases are no-ops
