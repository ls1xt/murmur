"""tmux send-keys based text injector."""

from __future__ import annotations

import logging
import subprocess

from murmur.injector.base import TextInjector

logger = logging.getLogger(__name__)


class TmuxUnavailableError(RuntimeError):
    """Raised when the target tmux pane is not reachable."""


class TmuxInjector(TextInjector):
    """Injects text into a specific tmux pane via `tmux send-keys`.

    Created per-binding since each tmux binding has its own fixed target pane.
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
            result = subprocess.run(cmd, check=False, capture_output=True, timeout=5)
        except FileNotFoundError as e:
            raise TmuxUnavailableError(
                f"tmux binary not found; cannot inject into pane {self._target!r}"
            ) from e
        if result.returncode != 0:
            raise TmuxUnavailableError(
                f"tmux command failed for pane {self._target!r} "
                f"(exit {result.returncode}): {result.stderr.decode(errors='replace').strip()}"
            )
