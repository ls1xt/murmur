"""
DictationApp -- core application logic for the murmur dictation tool.

Wires together hotkey detection, speech-to-text streaming, and text injection
to provide push-to-talk (or toggle) dictation into any application.
"""

from __future__ import annotations

import contextvars
import logging
import signal
import sys
import threading
import time
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

_session_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "murmur_session", default=0
)


class _SessionFilter(logging.Filter):
    """Injects ``session`` into every LogRecord from any thread."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.session = _session_var.get()  # type: ignore[attr-defined]
        return True


class DictationApp:
    """
    Main application: orchestrates hotkey -> transcriber -> injector pipeline.

    Lifecycle:
        1. User presses hotkey -> start transcriber (mic + AssemblyAI stream)
        2. AssemblyAI sends transcript turns -> inject text via ydotool
        3. User releases hotkey -> stop transcriber

    Two activation modes are supported via different hotkey actions:
        - ``push_to_talk``: hold key to record, release to inject into app.
        - ``copy_to_clipboard``: hold key to record, release to copy to clipboard.
    """

    def __init__(self, config: DictationConfig) -> None:
        self.config = config
        self._running = False
        self._lock = threading.Lock()
        self._inject_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._last_partial: str = ""
        self._clipboard_mode: bool = False  # True when action == copy_to_clipboard
        self._clipboard_buffer: list[str] = []  # accumulates turns in clipboard mode
        self._session_id: int = 0  # current session index; set before each start
        self._recording_active: bool = False  # set synchronously in _on_activate/_on_deactivate
        self._last_deactivate_time: float = 0.0  # monotonic time of last deactivation

        self.hotkey: HotkeyListener = create_hotkey_listener(config.hotkey)
        self.transcriber: Transcriber = create_transcriber(config.transcriber)
        self.injector: TextInjector = create_injector(config.injector)
        self.feedback = AudioFeedback(
            enabled=config.feedback.audio_enabled,
            start_hz=config.feedback.start_hz,
            stop_hz=config.feedback.stop_hz,
            amplitude=config.feedback.amplitude,
            start_duration_ms=config.feedback.start_duration_ms,
            stop_duration_ms=config.feedback.stop_duration_ms,
        )
        self.notifier = Notifier(level=config.notify.level)
        self.tray = TrayIcon(
            on_quit=self._request_shutdown,
            on_activate=self._on_tray_activate,
        )

        self.hotkey.set_callbacks(
            on_activate=self._on_activate,
            on_deactivate=self._on_deactivate,
        )
        self.transcriber.set_callbacks(
            on_partial=self._on_partial_transcript,
            on_final=self._on_final_transcript,
            on_error=self._on_transcriber_error,
        )

    def _on_activate(self, action: str, trigger: str = "hotkey") -> None:
        """Called when the hotkey is activated (start recording).

        ``action`` is one of "push_to_talk", "toggle_start", or
        "copy_to_clipboard" and determines what happens to the transcript.
        ``trigger`` is "hotkey" or "tray" and indicates what triggered recording.
        """
        if action == "toggle":
            with self._lock:
                should_stop = self._recording_active
            if should_stop:
                self._on_deactivate()
                return
        debounce_s = self.config.hotkey.push_to_talk_debounce_ms / 1000.0
        with self._lock:
            if self._recording_active:
                return  # already recording
            # Debounce: ignore activations fired within push_to_talk_debounce_ms of
            # the last deactivation.  On macOS, Ctrl+Option+Space generates phantom
            # key events that produce a second Space press immediately after release,
            # causing runaway start/stop cycles without this guard.
            if time.monotonic() - self._last_deactivate_time < debounce_s:
                return
            self._recording_active = True
            self._clipboard_mode = action == "copy_to_clipboard"
            self._clipboard_buffer = []
            self._session_id += 1
        _session_var.set(self._session_id)
        logger.info("Recording started (trigger=%s action=%s)", trigger, action)
        self.feedback.play_start()
        self.notifier.info("Recording started")
        self.tray.set_state("recording")
        threading.Thread(target=self.transcriber.start, daemon=True).start()

    def _on_deactivate(self) -> None:
        """Called when the hotkey is deactivated (stop recording)."""
        with self._lock:
            if not self._recording_active:
                return  # already stopped
            self._recording_active = False
            self._last_deactivate_time = time.monotonic()
        logger.info("Recording stopped")
        self.feedback.play_stop()
        self.notifier.info("Recording stopped")
        self.tray.set_state("idle")
        self._last_partial = ""
        threading.Thread(target=self._stop_and_deliver, daemon=True).start()

    def _stop_and_deliver(self) -> None:
        """Stop the transcriber, then deliver clipboard if in clipboard mode.

        Runs in a background thread.  Calling transcriber.stop() joins the
        SDK stream thread, so by the time stop() returns all final-transcript
        callbacks have already fired and _clipboard_buffer is complete.
        """
        clipboard_mode = self._clipboard_mode
        self.transcriber.stop()
        if not clipboard_mode:
            return
        with self._inject_lock:
            full_text = " ".join(self._clipboard_buffer).strip()
            self._clipboard_buffer = []
        if full_text:
            logger.info(
                "Clipboard mode: copying full session to clipboard (%d chars)",
                len(full_text),
            )
            self.injector.copy_to_clipboard(full_text)
            self.notifier.info("Copied to clipboard")
        else:
            logger.info("Clipboard mode: no text to copy")

    def _on_partial_transcript(self, text: str) -> None:
        """Called with intermediate (partial) transcript text.

        Skipped entirely when inject_partials=False (default) or in
        copy_to_clipboard mode -- only finalised turns are injected.

        When inject_partials=True, injects the delta between the previous
        partial and the new one. When AssemblyAI appends words, only the new
        suffix is injected. When text diverges, the old partial is backspaced
        and new text typed.
        """
        _session_var.set(self._session_id)  # propagate session to SDK thread
        if not text:
            return
        if self._clipboard_mode:
            return  # Don't inject partials in clipboard mode
        if not self.config.transcriber.inject_partials:
            return  # Only inject on final turns
        logger.info(
            "Partial transcript received: %r (last_partial=%r)",
            text[:120],
            self._last_partial[:80],
        )
        with self._inject_lock:
            if text.startswith(self._last_partial):
                suffix = text[len(self._last_partial) :]
                if suffix:
                    logger.info("Injecting delta suffix: %r", suffix[:80])
                    self.injector.inject_raw(suffix)
                else:
                    logger.debug("Partial unchanged, no delta to inject")
            else:
                logger.info(
                    "Partial diverged: backspace %d chars, inject %r",
                    len(self._last_partial),
                    text[:80],
                )
                if self._last_partial:
                    self.injector.inject_backspaces(len(self._last_partial))
                self.injector.inject_raw(text)
            self._last_partial = text

    def _on_final_transcript(self, text: str) -> None:
        """Called with finalized turn text.

        In copy_to_clipboard mode: copies the transcript to the system
        clipboard via wl-copy instead of injecting it.

        In normal mode: backspaces the partial text first, then injects the
        final formatted text.  Serialized via _inject_lock to prevent races
        with partials.
        """
        _session_var.set(self._session_id)  # propagate session to SDK thread
        logger.info(
            "Final transcript received: %r (last_partial=%r)",
            text[:120],
            self._last_partial[:80],
        )
        with self._inject_lock:
            if self._last_partial:
                logger.info(
                    "Backspacing %d partial chars before final inject",
                    len(self._last_partial),
                )
                self.injector.inject_backspaces(len(self._last_partial))
                self._last_partial = ""
            if not text.strip():
                logger.info("Final text was empty/whitespace, skipping")
                return
            if self._clipboard_mode:
                logger.info("Clipboard mode: buffering turn %r", text[:80])
                self._clipboard_buffer.append(text)
                return
            logger.info("Injecting final: %s", text)
            try:
                self.injector.inject(text)
            except Exception as e:
                logger.error("Text injection failed: %s", e)

    def _on_transcriber_error(self, error: Exception) -> None:
        """Called when the transcriber encounters an error."""
        _session_var.set(self._session_id)  # propagate session to SDK thread
        logger.error("Transcription error: %s", error)
        self.notifier.error(str(error))
        self.tray.set_state("error", reason=str(error))

    def run(self) -> None:
        """Start the dictation app. Blocks until interrupted."""
        self._running = True

        if sys.platform == "darwin":
            from murmur.platform.macos import check_accessibility, check_microphone

            if not check_accessibility():
                fatal(
                    "Accessibility permission required for keyboard monitoring.\n"
                    "Go to System Settings → Privacy & Security → Accessibility\n"
                    "and enable Terminal (or your Python interpreter)."
                )
            if not check_microphone():
                fatal(
                    "Microphone permission required for audio capture.\n"
                    "Go to System Settings → Privacy & Security → Microphone\n"
                    "and enable Terminal (or your Python interpreter)."
                )
        elif not self.injector.is_available():
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
            if binding.action == "tmux_send_keys":
                label = f"Tmux send {binding.tmux_keys!r} -> {binding.tmux_target}"
            else:
                label = binding.action.replace("_", " ").title()
            print(f"  {combo}  ->  {label}")
        print("  Press Ctrl+C to quit.\n")

        self.notifier.info("Murmur started")

        def _signal_handler(signum: int, frame: types.FrameType | None) -> None:
            print("\nShutting down...")
            self._stop_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        if sys.platform == "darwin" and self.config.tray.enabled:
            # pystray's Darwin backend calls NSApp.run() which must run on the
            # main thread.  Use run_blocking() so the tray event loop owns the
            # main thread while everything else runs in setup_fn's thread.
            def _darwin_setup() -> None:
                self.hotkey.start()
                self._stop_event.wait()

            self.tray.run_blocking(_darwin_setup)
        else:
            if self.config.tray.enabled:
                self.tray.start()
            self.hotkey.start()
            self._stop_event.wait()

        self.shutdown()

    def _on_tray_activate(self) -> None:
        """Handle tray icon left-click: toggle recording on/off."""
        with self._lock:
            active = self._recording_active
        if active:
            self._on_deactivate()
        else:
            self._on_activate("push_to_talk", trigger="tray")

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
