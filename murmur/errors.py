"""
Fatal error handling for the murmur daemon.

Provides consistent error exit behavior: log to stderr, send desktop
notification via notify-send, and terminate the process.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import subprocess
import sys

logger = logging.getLogger(__name__)


def _notify(message: str) -> None:
    """Send a desktop notification via notify-send (best-effort)."""
    with contextlib.suppress(FileNotFoundError, subprocess.TimeoutExpired):
        subprocess.run(
            ["notify-send", "--urgency=critical", "Murmur", message],
            timeout=5,
            capture_output=True,
        )


def fatal(message: str) -> None:
    """Log error, send desktop notification, and exit the process.

    Use from the main thread. For background threads, use
    ``fatal_from_thread`` instead (``sys.exit`` only raises
    ``SystemExit`` in the calling thread).
    """
    logger.error(message)
    print(f"murmur: {message}", file=sys.stderr)
    _notify(message)
    sys.exit(1)


def fatal_from_thread(message: str) -> None:
    """Log error, send desktop notification, and signal the main thread to exit.

    Uses ``os.kill(SIGTERM)`` so the main thread's signal handler runs,
    giving it a chance to clean up before the process terminates.
    """
    logger.error(message)
    print(f"murmur: {message}", file=sys.stderr)
    _notify(message)
    os.kill(os.getpid(), signal.SIGTERM)
