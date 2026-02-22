"""tmux send-keys based text injector."""

from __future__ import annotations

import logging
import subprocess

from murmur.injector.base import TextInjector

logger = logging.getLogger(__name__)


class TmuxInjector(TextInjector):
    """Injects text into a specific tmux pane via `tmux send-keys`.

    Created per-binding (not via the create_injector factory) since each
    binding that uses inject_to="tmux:..." has its own fixed target pane.
    """

    def __init__(self, target: str, trailing_space: bool = True) -> None:
        self._target = target
        self._trailing_space = trailing_space

    def inject(self, text: str) -> None:
        if not text:
            return
        if self._trailing_space:
            text = text + " "
        self._send(text)

    def inject_raw(self, text: str) -> None:
        if not text:
            return
        self._send(text)

    def inject_backspaces(self, count: int) -> None:
        # Cannot meaningfully backspace in a tmux pane
        pass

    def inject_return(self) -> None:
        self._run(["tmux", "send-keys", "-t", self._target, "", "Enter"])

    def copy_to_clipboard(self, text: str) -> None:
        # Not supported for tmux injection
        pass

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self._target],
                capture_output=True,
                timeout=2,
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    def _send(self, text: str) -> None:
        self._run(["tmux", "send-keys", "-t", self._target, text])

    def _run(self, cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=False, capture_output=True, timeout=5)
        except FileNotFoundError:
            logger.error("tmux not found; cannot inject into pane %r", self._target)
        except OSError as e:
            logger.error("tmux send-keys failed for %r: %s", self._target, e)
