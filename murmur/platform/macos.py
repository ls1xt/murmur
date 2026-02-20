"""macOS permission detection helpers for the murmur daemon.

These functions are called at daemon startup on darwin to provide
actionable fatal errors before pynput or PyAudio silently fail.
Mirrors the existing ydotoold startup check on Linux -- same pattern,
macOS-specific implementation.

All macOS framework imports are guarded inside try/except ImportError so
this module is safely importable on Linux (e.g. in tests) without crashing.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def check_accessibility() -> bool:
    """Return True if this process has macOS Accessibility permission.

    Accessibility permission is required by pynput keyboard.Listener for
    global key event monitoring. If pyobjc is not installed, returns True
    (cannot check; pynput will fail at runtime if permission is missing).
    """
    try:
        from ApplicationServices import AXIsProcessTrusted  # type: ignore[import]

        return bool(AXIsProcessTrusted())
    except ImportError:
        logger.warning(
            "pyobjc-framework-ApplicationServices not available; "
            "cannot verify Accessibility permission"
        )
        return True


def check_microphone() -> bool:
    """Return True if this process has macOS Microphone permission.

    Microphone permission is required by PyAudio for audio capture.
    Returns True if pyobjc AVFoundation is not available (cannot check).
    If status is notDetermined (0), logs a warning and returns True to
    allow PyAudio to trigger the system permission dialog on first use.
    Fatal-callers should only exit on denied (2) or restricted (1).
    """
    try:
        import AVFoundation  # type: ignore[import]

        status = int(
            AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                AVFoundation.AVMediaTypeAudio
            )
        )
        # 0=notDetermined, 1=restricted, 2=denied, 3=authorized
        if status == 3:
            return True
        if status == 0:
            logger.warning(
                "Microphone permission not yet determined; "
                "PyAudio will trigger the system dialog on first use"
            )
            return True
        return False  # 1=restricted or 2=denied
    except ImportError:
        logger.warning(
            "pyobjc-framework-AVFoundation not available; "
            "cannot verify Microphone permission"
        )
        return True
