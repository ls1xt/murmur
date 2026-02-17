"""
System-wide dictation tool -- main entry point.

Wires together hotkey detection, speech-to-text streaming, and text injection
to provide push-to-talk (or toggle) dictation into any application.
"""

from __future__ import annotations

import logging
import signal
import sys
import threading
import types

from murmur.config import DictationConfig
from murmur.feedback.audio import AudioFeedback
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

        self.hotkey: HotkeyListener = create_hotkey_listener(config.hotkey)
        self.transcriber: Transcriber = create_transcriber(config.transcriber)
        self.injector: TextInjector = create_injector(config.injector)
        self.feedback = AudioFeedback(enabled=config.feedback.audio_enabled)

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
        logger.info("Recording started")
        self.feedback.play_start()
        threading.Thread(target=self.transcriber.start, daemon=True).start()

    def _on_deactivate(self) -> None:
        """Called when the hotkey is deactivated (stop recording)."""
        logger.info("Recording stopped")
        self.feedback.play_stop()
        threading.Thread(target=self.transcriber.stop, daemon=True).start()

    def _on_partial_transcript(self, text: str) -> None:
        """Called with intermediate (partial) transcript text."""
        logger.debug("Partial: %s", text)

    def _on_final_transcript(self, text: str) -> None:
        """Called with finalized turn text -- inject it into the active app."""
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

    def run(self) -> None:
        """Start the dictation app. Blocks until interrupted."""
        self._running = True

        if not self.injector.is_available():
            logger.error(
                "Text injector backend is not available. "
                "See setup instructions in the README."
            )
            sys.exit(1)

        mode = self.config.hotkey.mode
        trigger_desc = (
            f"{'+'.join(self.config.hotkey.modifiers)}+{self.config.hotkey.trigger}"
        )
        print(f"\n{'=' * 60}")
        print("  Dictation Tool Ready")
        print(f"  Hotkey:  {trigger_desc}")
        print(f"  Mode:    {mode}")
        print(f"  Engine:  {self.config.transcriber.backend}")
        print(f"  Inject:  {self.config.injector.backend}")
        print(f"{'=' * 60}")
        if mode == "push_to_talk":
            print(f"  Hold {trigger_desc} to dictate.")
        else:
            print(f"  Press {trigger_desc} to start/stop dictation.")
        print("  Press Ctrl+C to quit.\n")

        self.hotkey.start()

        stop_event = threading.Event()

        def _signal_handler(signum: int, frame: types.FrameType | None) -> None:
            print("\nShutting down...")
            stop_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        stop_event.wait()
        self.shutdown()

    def shutdown(self) -> None:
        """Clean up all resources."""
        self._running = False
        logger.info("Shutting down...")

        if self.transcriber.is_streaming:
            self.transcriber.stop()

        self.hotkey.stop()
        logger.info("Goodbye!")


def main() -> None:
    """Entry point for the dictation daemon."""
    config = DictationConfig.load()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if not config.transcriber.api_key:
        print("Error: ASSEMBLYAI_API_KEY environment variable is required.")
        print("  export ASSEMBLYAI_API_KEY=your_key_here")
        print("  Get a free key at: https://www.assemblyai.com/")
        sys.exit(1)

    app = DictationApp(config)
    app.run()
