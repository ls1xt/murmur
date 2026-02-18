"""
System-wide dictation tool -- main entry point.

Wires together hotkey detection, speech-to-text streaming, and text injection
to provide push-to-talk (or toggle) dictation into any application.
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import types

from murmur.config import DictationConfig
from murmur.errors import fatal
from murmur.feedback.audio import AudioFeedback
from murmur.feedback.notify import Notifier
from murmur.feedback.tray import TrayIcon
from murmur.hotkey import create_hotkey_listener
from murmur.hotkey.base import HotkeyListener
from murmur.injector import create_injector
from murmur.injector.base import TextInjector
from murmur.transcriber import create_transcriber
from murmur.transcriber.base import Transcriber

logger = logging.getLogger(__name__)


class DictationApp:
    """
    Main application: orchestrates hotkey -> transcriber -> injector pipeline.

    Lifecycle:
        1. User presses hotkey -> start transcriber (mic + AssemblyAI stream)
        2. AssemblyAI sends transcript turns -> inject text via ydotool
        3. User releases hotkey -> stop transcriber
    """

    def __init__(self, config: DictationConfig) -> None:
        self.config = config
        self._running = False
        self._lock = threading.Lock()
        self._inject_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_partial: str = ""

        self.hotkey: HotkeyListener = create_hotkey_listener(config.hotkey)
        self.transcriber: Transcriber = create_transcriber(config.transcriber)
        self.injector: TextInjector = create_injector(config.injector)
        self.feedback = AudioFeedback(enabled=config.feedback.audio_enabled)
        self.notifier = Notifier(level=config.notify.level)
        self.tray = TrayIcon(on_quit=self._request_shutdown)

        self.hotkey.set_callbacks(
            on_activate=self._on_activate,
            on_deactivate=self._on_deactivate,
        )
        self.transcriber.set_callbacks(
            on_partial=self._on_partial_transcript,
            on_final=self._on_final_transcript,
            on_error=self._on_transcriber_error,
        )

    def _on_activate(self) -> None:
        """Called when the hotkey is activated (start recording)."""
        with self._lock:
            if self.transcriber.is_streaming:
                return  # already recording
        logger.info("Recording started")
        self.feedback.play_start()
        self.notifier.info("Recording started")
        self.tray.set_state("recording")
        threading.Thread(target=self.transcriber.start, daemon=True).start()

    def _on_deactivate(self) -> None:
        """Called when the hotkey is deactivated (stop recording)."""
        with self._lock:
            if not self.transcriber.is_streaming:
                return  # already stopped
        logger.info("Recording stopped")
        self.feedback.play_stop()
        self.notifier.info("Recording stopped")
        self.tray.set_state("idle")
        self._last_partial = ""
        threading.Thread(target=self.transcriber.stop, daemon=True).start()

    def _on_partial_transcript(self, text: str) -> None:
        """Called with intermediate (partial) transcript text.

        Injects the delta between the previous partial and the new one.
        When AssemblyAI appends words, only the new suffix is injected.
        When text diverges, the old partial is backspaced and new text typed.
        """
        logger.debug("Partial: %s", text)
        if not text:
            return
        with self._inject_lock:
            if text.startswith(self._last_partial):
                # Common case: AssemblyAI appended words
                suffix = text[len(self._last_partial) :]
                if suffix:
                    self.injector.inject_raw(suffix)
            else:
                # Diverged: backspace the old partial, type new text
                if self._last_partial:
                    self.injector.inject_backspaces(
                        len(self._last_partial)
                    )
                self.injector.inject_raw(text)
            self._last_partial = text

    def _on_final_transcript(self, text: str) -> None:
        """Called with finalized turn text -- inject it into the active app.

        Backspaces the partial text first, then injects the final formatted
        text. Serialized via _inject_lock to prevent races with partials.
        """
        with self._inject_lock:
            # Backspace the partial first
            if self._last_partial:
                self.injector.inject_backspaces(
                    len(self._last_partial)
                )
                self._last_partial = ""
            if not text.strip():
                return
            logger.info("Injecting: %s", text)
            try:
                self.injector.inject(text)
            except Exception as e:
                logger.error("Text injection failed: %s", e)

    def _on_transcriber_error(self, error: Exception) -> None:
        """Called when the transcriber encounters an error."""
        logger.error("Transcription error: %s", error)
        self.notifier.error(str(error))
        self.tray.set_state("error", reason=str(error))

    def run(self) -> None:
        """Start the dictation app. Blocks until interrupted."""
        self._running = True

        if not self.injector.is_available():
            fatal(
                "ydotoold is not running. Start it with: systemctl --user start ydotool"
            )

        print(f"\n{'=' * 60}")
        print("  Dictation Tool Ready")
        print(f"  Engine:  {self.config.transcriber.backend}")
        print(f"  Inject:  {self.config.injector.backend}")
        print(f"{'=' * 60}")
        for binding in self.config.hotkey.bindings:
            combo = f"{'+'.join(binding.modifiers)}+{binding.trigger}"
            label = binding.action.replace("_", " ").title()
            print(f"  {combo}  ->  {label}")
        print("  Press Ctrl+C to quit.\n")

        self.notifier.info("Murmur started")

        if self.config.tray.enabled:
            self.tray.start()

        self.hotkey.start()

        def _signal_handler(signum: int, frame: types.FrameType | None) -> None:
            print("\nShutting down...")
            self._stop_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        self._stop_event.wait()
        self.shutdown()

    def _request_shutdown(self) -> None:
        """Request daemon shutdown (e.g., from tray Quit menu)."""
        self._stop_event.set()

    def shutdown(self) -> None:
        """Clean up all resources."""
        self._running = False
        logger.info("Shutting down...")

        self.tray.stop()

        if self.transcriber.is_streaming:
            self.transcriber.stop()

        self.hotkey.stop()
        logger.info("Goodbye!")


def main() -> None:
    """Entry point for the dictation daemon."""
    parser = argparse.ArgumentParser(description="Murmur voice dictation daemon")
    parser.add_argument(
        "--inject",
        choices=["ydotool", "clipboard-fallback", "clipboard"],
        default=None,
        help="Text injection strategy (default: clipboard-fallback)",
    )
    parser.add_argument(
        "--notify",
        choices=["off", "errors", "verbose"],
        default=None,
        help="Notification verbosity (default: errors)",
    )
    args = parser.parse_args()

    config = DictationConfig.load()

    if args.inject is not None:
        config.injector.inject_strategy = args.inject

    if args.notify is not None:
        config.notify.level = args.notify

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not config.transcriber.api_key:
        fatal("ASSEMBLYAI_API_KEY not set. Get a key at: https://www.assemblyai.com/")

    app = DictationApp(config)
    app.run()
