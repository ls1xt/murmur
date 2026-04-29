"""
CGEvent-based text injector for macOS.

Posts key events at ``kCGSessionEventTap`` (pipeline level 1).  pynput's
Listener is also at level 1 and does see injected events (``injected=True``).
The ``_is_injecting`` flag in ``PynputHotkeyListener`` suppresses
``stop_on_keypress`` while injection is active — that is the correct guard.

Injecting at ``kCGAnnotatedSessionEventTap`` (level 2) was tried but caused
double-delivery in browser text fields (each character appeared twice), so
level 1 is used instead.

Character encoding: uses ``CGEventKeyboardSetUnicodeString`` to inject Unicode
directly without mapping characters to virtual keycodes.  Works for all BMP
characters and emoji.  The virtual keycode is set to 0 -- apps that dispatch
on keycode rather than character (e.g. keyboard-shortcut handlers) will not
be triggered.

Backspace injection uses the real virtual keycode (0x33 = kVK_Delete) so
that apps that map backspace by keycode receive it correctly.

Requires ``pyobjc-framework-Quartz`` (already a murmur dependency on macOS).
"""

from __future__ import annotations

import logging
import subprocess
import time
import unicodedata
from typing import TYPE_CHECKING, Any

from murmur.injector.base import TextInjector

if TYPE_CHECKING:
    pass  # Quartz doesn't expose typed stubs, use Any

logger = logging.getLogger(__name__)

# kVK_Delete (backspace) -- the physical key to the left of Return.
# Value 0x33 is fixed in the macOS keyboard layout and does not change.
_VK_DELETE: int = 0x33

# kVK_Return -- the main Return/Enter key.
# Value 0x24 is fixed in the macOS keyboard layout and does not change.
_VK_RETURN: int = 0x24


def _sanitize_text(text: str) -> str:
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


class CGEventInjector(TextInjector):
    """Injects text via CGEvent at kCGSessionEventTap (pipeline level 1).

    Posts key-down/key-up pairs for each character using
    ``CGEventKeyboardSetUnicodeString``.  pynput's listener sees these events
    but ``PynputHotkeyListener`` suppresses ``stop_on_keypress`` via the
    ``_is_injecting`` flag while injection is in progress.

    Requires Accessibility permission (System Preferences > Privacy &
    Security > Accessibility) -- same requirement as pynput injection.
    """

    def __init__(
        self,
        trailing_space: bool = True,
        key_delay: int = 0,
    ) -> None:
        self._trailing_space = trailing_space
        self._key_delay_s: float = key_delay / 1000.0
        # Lazily created on first use: CGEventSourceCreate must not be called
        # before NSApp/TSM finishes initializing on the main thread, otherwise
        # pynput's listener thread calling UCKeyTranslate → TSM may abort with
        # "_HaveOnlyOneKeyboardInputSource" assertion failure.
        self._source: Any = None

    def is_available(self) -> bool:
        """Check if Quartz and Accessibility are available."""
        try:
            from Quartz import (  # pyright: ignore[reportMissingImports]
                CGEventCreateKeyboardEvent,  # noqa: F401  # pyright: ignore[reportUnusedImport]
            )
        except ImportError:
            return False
        try:
            from ApplicationServices import (  # pyright: ignore[reportMissingImports]
                AXIsProcessTrusted,
            )

            return bool(AXIsProcessTrusted())
        except ImportError:
            return True

    def inject(self, text: str) -> None:
        """Inject text with optional trailing space."""
        if not text:
            return
        text = _sanitize_text(text)
        if not text:
            return
        if self._trailing_space:
            text = text + " "
        logger.debug("Injecting: %r", text[:80])
        self._type(text)

    def inject_raw(self, text: str) -> None:
        """Inject text without trailing space (used for partial transcripts)."""
        if not text:
            return
        text = _sanitize_text(text)
        if not text:
            return
        logger.debug("Injecting raw partial: %r", text[:80])
        self._type(text)

    def inject_backspaces(self, count: int) -> None:
        """Inject N backspace keypresses using the real kVK_Delete keycode."""
        if count <= 0:
            return
        from Quartz import (  # pyright: ignore[reportMissingImports]
            CGEventCreateKeyboardEvent,
            CGEventPost,
            kCGSessionEventTap,
        )

        source = self._get_source()
        logger.debug("Injecting %d backspaces", count)
        for _ in range(count):
            e_dn = CGEventCreateKeyboardEvent(source, _VK_DELETE, True)
            CGEventPost(kCGSessionEventTap, e_dn)
            e_up = CGEventCreateKeyboardEvent(source, _VK_DELETE, False)
            CGEventPost(kCGSessionEventTap, e_up)
            if self._key_delay_s > 0:
                time.sleep(self._key_delay_s)

    def inject_return(self) -> None:
        """Inject a Return/Enter keypress using the real kVK_Return keycode."""
        from Quartz import (  # pyright: ignore[reportMissingImports]
            CGEventCreateKeyboardEvent,
            CGEventPost,
            kCGSessionEventTap,
        )

        source = self._get_source()
        e_dn = CGEventCreateKeyboardEvent(source, _VK_RETURN, True)
        CGEventPost(kCGSessionEventTap, e_dn)
        e_up = CGEventCreateKeyboardEvent(source, _VK_RETURN, False)
        CGEventPost(kCGSessionEventTap, e_up)

    def copy_to_clipboard(self, text: str) -> None:
        """Copy text to the macOS clipboard via pbcopy (no paste keystroke)."""
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

    def _get_source(self) -> Any:
        """Return (lazily creating) the private CGEventSource.

        Deferred until first injection so that CGEventSourceCreate is called
        after NSApp and TSM are fully initialized on the main thread.
        """
        if self._source is None:
            from Quartz import (  # pyright: ignore[reportMissingImports]
                CGEventSourceCreate,
                kCGEventSourceStatePrivate,
            )

            self._source = CGEventSourceCreate(kCGEventSourceStatePrivate)  # type: ignore[assignment]
        return self._source  # type: ignore[return-value]

    def _type(self, text: str) -> None:
        """Post key-down/key-up pairs for each character at annotated-session level.

        Uses CGEventKeyboardSetUnicodeString (vk=0) so that apps receive the
        exact Unicode character regardless of keyboard layout.  Electron,
        terminal emulators, and native Cocoa apps all read the unicode string
        from the NSEvent generated from this CGEvent.
        """
        from Quartz import (  # pyright: ignore[reportMissingImports]
            CGEventCreateKeyboardEvent,
            CGEventKeyboardSetUnicodeString,
            CGEventPost,
            kCGSessionEventTap,
        )

        source = self._get_source()
        for char in text:
            e_dn = CGEventCreateKeyboardEvent(source, 0, True)
            CGEventKeyboardSetUnicodeString(e_dn, 1, char)
            CGEventPost(kCGSessionEventTap, e_dn)

            e_up = CGEventCreateKeyboardEvent(source, 0, False)
            CGEventKeyboardSetUnicodeString(e_up, 1, char)
            CGEventPost(kCGSessionEventTap, e_up)

            if self._key_delay_s > 0:
                time.sleep(self._key_delay_s)
