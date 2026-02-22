"""
pynput-based text injector -- works on macOS.

Uses pynput's keyboard Controller to simulate typing, and pbcopy + Cmd+V
for clipboard-based injection of non-ASCII text. Supports three injection
strategies:

- ``pynput``: Direct ``Controller.type()`` (fast, any Unicode pynput supports).
- ``clipboard``: Always ``pbcopy`` + Cmd+V (handles all Unicode).
- ``clipboard-fallback``: pynput type for ASCII, clipboard for non-ASCII.
"""

from __future__ import annotations

import logging
import subprocess
import time
import unicodedata

from pynput import keyboard

from murmur.injector.base import InjectStrategy, TextInjector

logger = logging.getLogger(__name__)


def sanitize_text(text: str) -> str:
    """Strip control characters before injection.

    Control characters (newline, carriage return, tab, NUL, ...) can cause
    dangerous effects when injected into terminal applications -- for example,
    a newline would submit the current input buffer.  Only printable Unicode
    characters (general category != C*) are kept.
    """
    clean = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    removed = len(text) - len(clean)
    if removed:
        logger.warning("Sanitized %d control character(s) from injection text", removed)
    return clean


class PynputInjector(TextInjector):
    """Injects text using pynput with configurable strategy.

    Designed for macOS where pynput.keyboard.Controller provides the
    most native typing experience. Requires Accessibility permissions
    (System Preferences > Privacy & Security > Accessibility).
    """

    def __init__(
        self,
        trailing_space: bool = True,
        inject_strategy: InjectStrategy = "clipboard-fallback",
        key_delay: int = 0,
    ) -> None:
        self._trailing_space = trailing_space
        self._inject_strategy = inject_strategy
        self._key_delay_s: float = key_delay / 1000.0
        self._controller = keyboard.Controller()

    def is_available(self) -> bool:
        """Check if pynput can inject text (Accessibility permission on macOS)."""
        try:
            from ApplicationServices import (  # pyright: ignore[reportMissingImports]
                AXIsProcessTrusted,
            )

            return bool(AXIsProcessTrusted())
        except ImportError:
            # Cannot verify without pyobjc; assume available
            return True

    def inject(self, text: str) -> None:
        """Inject text using the configured strategy."""
        if not text:
            return

        text = sanitize_text(text)
        if not text:
            return

        if self._trailing_space:
            text = text + " "

        self._dispatch(text)

    def inject_raw(self, text: str) -> None:
        """Inject text without trailing space, routing through the configured strategy.

        Used for partial transcripts that are mid-sentence. Routes through the
        same strategy as inject() to ensure non-ASCII characters are handled
        consistently -- which keeps the injected character count in sync with
        len(text) used by inject_backspaces().
        """
        if not text:
            return

        text = sanitize_text(text)
        if not text:
            return

        logger.debug("Injecting raw partial: %r", text[:80])

        self._dispatch(text)

    def _dispatch(self, text: str) -> None:
        """Dispatch text to the configured injection strategy."""
        if self._inject_strategy == "clipboard":
            self._inject_via_clipboard(text)
        elif self._inject_strategy == "clipboard-fallback":
            if text.isascii():
                self._type(text)
            else:
                self._inject_via_clipboard(text)
        else:
            # "pynput" strategy
            self._type(text)

    def inject_backspaces(self, count: int) -> None:
        """Inject N backspace keypresses to erase previously-injected text."""
        if count <= 0:
            return

        logger.debug("Injecting %d backspaces", count)
        for _ in range(count):
            self._controller.press(keyboard.Key.backspace)
            self._controller.release(keyboard.Key.backspace)

    def inject_return(self) -> None:
        """Press and release the Return/Enter key."""
        self._controller.press(keyboard.Key.enter)
        self._controller.release(keyboard.Key.enter)

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to the macOS clipboard via pbcopy (no paste keystroke).

        This is clipboard-only -- it does not inject into any application.
        """
        if not text:
            return

        logger.debug("Copying to clipboard: %r", text[:80])
        proc = subprocess.run(
            ["pbcopy"],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=5,
        )
        if proc.returncode != 0:
            logger.error("pbcopy failed (rc=%d)", proc.returncode)

    def _type(self, text: str) -> None:
        """Type text character by character with optional inter-keystroke delay.

        When ``key_delay`` is 0 (default), delegates directly to
        ``controller.type()`` which posts all CGEvents in a tight loop.
        When ``key_delay > 0``, sleeps between characters to give the target
        application's event loop time to advance the cursor between each
        keystroke -- useful when the app batches key events and the cursor
        lags behind rapid typing.
        """
        if self._key_delay_s <= 0:
            self._controller.type(text)
        else:
            for char in text:
                self._controller.type(char)
                time.sleep(self._key_delay_s)

    def _inject_via_clipboard(self, text: str) -> None:
        """Inject text via clipboard: pbcopy + Cmd+V."""
        proc = subprocess.run(
            ["pbcopy"],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=5,
        )
        if proc.returncode != 0:
            logger.error(
                "pbcopy failed (rc=%d): %s",
                proc.returncode,
                proc.stderr.decode(errors="replace").strip(),
            )
            return

        logger.debug("Pasting via Cmd+V")
        with self._controller.pressed(keyboard.Key.cmd):
            self._controller.tap(keyboard.KeyCode.from_char("v"))
