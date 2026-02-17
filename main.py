#!/usr/bin/env python3
"""
System-wide dictation tool — main entry point.

Wires together hotkey detection, speech-to-text streaming, and text injection
to provide push-to-talk (or toggle) dictation into any application.

Usage:
    ASSEMBLYAI_API_KEY=your_key python -m dictation
    # or
    ASSEMBLYAI_API_KEY=your_key python main.py

Then press Ctrl+Shift+Space to dictate. Text appears at your cursor.
"""

import logging
import signal
import sys
import threading

from dictation.config import DictationConfig
from dictation.hotkey import create_hotkey_listener
from dictation.hotkey.base import HotkeyListener
from dictation.transcriber import create_transcriber
from dictation.transcriber.base import Transcriber
from dictation.injector import create_injector
from dictation.injector.base import TextInjector
from dictation.feedback import AudioFeedback

logger = logging.getLogger(__name__)


class DictationApp:
    """
    Main application: orchestrates hotkey → transcriber → injector pipeline.

    Lifecycle:
        1. User presses hotkey → start transcriber (mic + AssemblyAI stream)
        2. AssemblyAI sends transcript turns → inject text via ydotool
        3. User releases hotkey → stop transcriber
    """

    def __init__(self, config: DictationConfig):
        self.config = config
        self._running = False
        self._lock = threading.Lock()

        # Create components
        self.hotkey: HotkeyListener = create_hotkey_listener(config.hotkey)
        self.transcriber: Transcriber = create_transcriber(config.transcriber)
        self.injector: TextInjector = create_injector(config.injector)
        self.feedback = AudioFeedback(enabled=config.feedback.audio_enabled)

        # Wire callbacks
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
        logger.info("🎙️  Recording started")
        self.feedback.play_start()
        # Start transcriber in a background thread to avoid blocking the hotkey listener
        threading.Thread(target=self.transcriber.start, daemon=True).start()

    def _on_deactivate(self) -> None:
        """Called when the hotkey is deactivated (stop recording)."""
        logger.info("⏹️  Recording stopped")
        self.feedback.play_stop()
        # Stop transcriber in a background thread
        threading.Thread(target=self.transcriber.stop, daemon=True).start()

    def _on_partial_transcript(self, text: str) -> None:
        """Called with intermediate (partial) transcript text."""
        # For now, just log it. Could be used for a live preview overlay.
        logger.debug("Partial: %s", text)

    def _on_final_transcript(self, text: str) -> None:
        """Called with finalized turn text — inject it into the active app."""
        if not text.strip():
            return

        logger.info("📝 Injecting: %s", text)
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

        # Verify injector is available
        if not self.injector.is_available():
            logger.error(
                "Text injector backend is not available. "
                "See setup instructions in the README."
            )
            sys.exit(1)

        # Print startup info
        mode = self.config.hotkey.mode
        trigger_desc = (
            f"{'+'.join(self.config.hotkey.modifiers)}+{self.config.hotkey.trigger}"
        )
        print(f"\n{'='*60}")
        print(f"  🎤 Dictation Tool Ready")
        print(f"  Hotkey:  {trigger_desc}")
        print(f"  Mode:    {mode}")
        print(f"  Engine:  {self.config.transcriber.backend}")
        print(f"  Inject:  {self.config.injector.backend}")
        print(f"{'='*60}")
        if mode == "push_to_talk":
            print(f"  Hold {trigger_desc} to dictate.")
        else:
            print(f"  Press {trigger_desc} to start/stop dictation.")
        print(f"  Press Ctrl+C to quit.\n")

        # Start hotkey listener (blocks in background thread)
        self.hotkey.start()

        # Keep main thread alive until Ctrl+C
        stop_event = threading.Event()

        def _signal_handler(signum, frame):
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


def main():
    # Load configuration
    config = DictationConfig.load()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-7s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Validate critical config
    if not config.transcriber.api_key:
        print("Error: ASSEMBLYAI_API_KEY environment variable is required.")
        print("  export ASSEMBLYAI_API_KEY=your_key_here")
        print("  Get a free key at: https://www.assemblyai.com/")
        sys.exit(1)

    # Run
    app = DictationApp(config)
    app.run()


if __name__ == "__main__":
    main()
