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

from murmur.config import (
    CONFIG_FILE,
    ClipboardDestination,
    DictationConfig,
    HotkeyBinding,
    TmuxDestination,
)
from murmur.errors import fatal
from murmur.feedback.audio import AudioFeedback
from murmur.feedback.notify import Notifier
from murmur.feedback.tray import TrayIcon
from murmur.hotkey import create_hotkey_listener
from murmur.hotkey.base import HotkeyListener
from murmur.injector import create_injector
from murmur.injector.base import TextInjector
from murmur.injector.tmux import TmuxUnavailableError
from murmur.transcriber import create_transcriber
from murmur.transcriber.base import Transcriber

logger = logging.getLogger(__name__)

_session_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "murmur_session", default=0
)


class SessionFilter(logging.Filter):  # pyright: ignore[reportUnusedClass]
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
        self._clipboard_mode: bool = False  # True when destination == clipboard
        self._clipboard_buffer: list[str] = []  # accumulates turns in clipboard mode
        self._session_id: int = 0  # current session index; set before each start
        self._recording_active: bool = (
            False  # set synchronously in on_activate/on_deactivate
        )
        self._last_deactivate_time: float = 0.0  # monotonic time of last deactivation
        self._recording_start_time: float = 0.0  # monotonic time of last activation

        # Config hot-reload: track mtime so we can reload on next activation
        try:
            self._config_mtime: float = CONFIG_FILE.stat().st_mtime
        except OSError:
            self._config_mtime = 0.0

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
            on_activate=self.on_tray_activate,
        )

        # Per-binding injectors: tmux bindings get their own TmuxInjector;
        # all others share the default self.injector.
        self._binding_injectors: dict[int, TextInjector] = (
            self._build_binding_injectors()
        )
        self._active_injector: TextInjector = self.injector
        self._active_binding: HotkeyBinding | None = None

        self.hotkey.set_callbacks(
            on_activate=self.on_activate,
            on_deactivate=self.on_deactivate,
        )
        self.transcriber.set_callbacks(
            on_partial=self.on_partial_transcript,
            on_final=self.on_final_transcript,
            on_error=self.on_transcriber_error,
        )

    @property
    def recording_active(self) -> bool:
        """Whether recording is currently active."""
        return self._recording_active

    @recording_active.setter
    def recording_active(self, value: bool) -> None:
        """Set whether recording is currently active."""
        self._recording_active = value

    @property
    def clipboard_mode(self) -> bool:
        """Whether clipboard mode is currently active."""
        return self._clipboard_mode

    @clipboard_mode.setter
    def clipboard_mode(self, value: bool) -> None:
        """Set whether clipboard mode is currently active."""
        self._clipboard_mode = value

    @property
    def active_injector(self) -> TextInjector:
        """The currently active text injector."""
        return self._active_injector

    @active_injector.setter
    def active_injector(self, value: TextInjector) -> None:
        """Set the currently active text injector."""
        self._active_injector = value

    @property
    def active_binding(self) -> HotkeyBinding | None:
        """The currently active hotkey binding."""
        return self._active_binding

    @active_binding.setter
    def active_binding(self, value: HotkeyBinding | None) -> None:
        """Set the currently active hotkey binding."""
        self._active_binding = value

    @property
    def config_mtime(self) -> float:
        """The modification time of the config file."""
        return self._config_mtime

    @config_mtime.setter
    def config_mtime(self, value: float) -> None:
        """Set the modification time of the config file."""
        self._config_mtime = value

    @property
    def last_partial(self) -> str:
        """The last partial transcript received."""
        return self._last_partial

    @last_partial.setter
    def last_partial(self, value: str) -> None:
        """Set the last partial transcript received."""
        self._last_partial = value

    @property
    def clipboard_buffer(self) -> list[str]:
        """The buffered text in clipboard mode."""
        return self._clipboard_buffer

    @clipboard_buffer.setter
    def clipboard_buffer(self, value: list[str]) -> None:
        """Set the buffered text in clipboard mode."""
        self._clipboard_buffer = value

    def _build_binding_injectors(self) -> dict[int, TextInjector]:
        """Build a per-binding injector map.

        Bindings with a ``TmuxDestination`` get a dedicated
        ``TmuxInjector`` targeting the destination's pane address; all others
        map to the shared default injector.
        """
        from murmur.injector.tmux import TmuxInjector

        injectors: dict[int, TextInjector] = {}
        for binding in self.config.hotkey.bindings:
            if isinstance(binding.destination, TmuxDestination):
                injectors[id(binding)] = TmuxInjector(
                    target=binding.destination.target,
                    trailing_space=self.config.injector.trailing_space,
                )
            else:
                injectors[id(binding)] = self.injector
        return injectors

    def maybe_reload_config(self) -> None:
        """Reload config from disk if the file has been modified since last check."""
        try:
            mtime = CONFIG_FILE.stat().st_mtime
            if mtime == self._config_mtime:
                return
            self._config_mtime = mtime
        except OSError:
            return
        try:
            new_config = DictationConfig.load()
        except Exception as e:
            logger.warning("Config reload failed: %s", e)
            return
        logger.info("Config changed on disk, reloading...")
        self.config = new_config
        # Rebuild binding injectors with new config
        self._binding_injectors = self._build_binding_injectors()
        # Restart hotkey listener with new bindings
        self.hotkey.stop()
        self.hotkey = create_hotkey_listener(new_config.hotkey)
        self.hotkey.set_callbacks(
            on_activate=self.on_activate,
            on_deactivate=self.on_deactivate,
        )
        self.hotkey.start()

    def on_activate(self, binding: HotkeyBinding, trigger: str = "hotkey") -> None:
        """Called when the hotkey is activated (start recording).

        ``binding`` is the full HotkeyBinding that was triggered.
        ``binding.mode`` is ``"push_to_talk"`` or ``"toggle"``.
        ``binding.destination`` is a ``TypeDestination``, ``ClipboardDestination``, or ``TmuxDestination``.
        ``trigger`` is "hotkey" or "tray" and indicates what triggered recording.
        """
        self.maybe_reload_config()

        if binding.mode == "toggle":
            with self._lock:
                should_stop = self._recording_active
            if should_stop:
                self.on_deactivate()
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
            self._recording_start_time = time.monotonic()
            self._recording_active = True
            self._clipboard_mode = isinstance(binding.destination, ClipboardDestination)
            self._clipboard_buffer = []
            self._session_id += 1
            self._active_binding = binding
            self._active_injector = self._binding_injectors.get(
                id(binding), self.injector
            )
        _session_var.set(self._session_id)
        from murmur.language import resolve_language

        lang = resolve_language(binding.language)
        logger.info(
            "Recording started (trigger=%s mode=%s destination=%s language=%s)",
            trigger,
            binding.mode,
            binding.destination,
            lang or self.config.transcriber.language,
        )
        self.feedback.play_start()
        self.notifier.info("Recording started")
        self.tray.set_state("recording")
        threading.Thread(
            target=self.transcriber.start, args=(lang,), daemon=True
        ).start()

    def on_deactivate(self) -> None:
        """Called when the hotkey is deactivated (stop recording)."""
        with self._lock:
            if not self._recording_active:
                return  # already stopped
            # Guard: for toggle mode, ignore deactivations within 200 ms of
            # starting.  This prevents stop_on_keypress from firing on a key
            # pressed at the same moment as (or just after) the toggle hotkey
            # that activated recording.  push_to_talk is unaffected — the user
            # may legitimately release the key very quickly.
            if (
                self._active_binding is not None
                and self._active_binding.mode == "toggle"
            ):
                elapsed = time.monotonic() - self._recording_start_time
                if elapsed < 0.200:
                    logger.debug(
                        "Ignoring deactivate: toggle recording too recent "
                        "(%.0f ms elapsed, min 200 ms)",
                        elapsed * 1000,
                    )
                    return
            self._recording_active = False
            self._last_deactivate_time = time.monotonic()
        logger.info("Recording stopped")
        self.feedback.play_stop()
        self.notifier.info("Recording stopped")
        self.tray.set_state("idle")
        self._last_partial = ""
        threading.Thread(target=self.stop_and_deliver, daemon=True).start()

    def stop_and_deliver(self) -> None:
        """Stop the transcriber, then deliver clipboard if in clipboard mode.

        Runs in a background thread.  Calling transcriber.stop() joins the
        SDK stream thread, so by the time stop() returns all final-transcript
        callbacks have already fired and _clipboard_buffer is complete.
        """
        clipboard_mode = self._clipboard_mode
        active_binding = self._active_binding
        active_injector = self._active_injector
        self.transcriber.stop()
        if not clipboard_mode:
            # Append Enter if requested by this binding
            if active_binding is not None and active_binding.append_enter:
                try:
                    active_injector.inject_return()
                except Exception as e:
                    logger.error("inject_return failed: %s", e)
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

    def on_partial_transcript(self, text: str) -> None:
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
                    self._active_injector.inject_raw(suffix)
                else:
                    logger.debug("Partial unchanged, no delta to inject")
            else:
                logger.info(
                    "Partial diverged: backspace %d chars, inject %r",
                    len(self._last_partial),
                    text[:80],
                )
                if self._last_partial:
                    self._active_injector.inject_backspaces(len(self._last_partial))
                self._active_injector.inject_raw(text)
            self._last_partial = text

    def on_final_transcript(self, text: str) -> None:
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
                self._active_injector.inject_backspaces(len(self._last_partial))
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
                self._active_injector.inject(text)
            except TmuxUnavailableError:
                logger.warning("tmux pane unavailable; falling back to clipboard")
                self.injector.copy_to_clipboard(text)
                self.notifier.error("tmux unavailable — text copied to clipboard")
            except Exception as e:
                logger.error("Text injection failed: %s", e)

    def on_transcriber_error(self, error: Exception) -> None:
        """Called when the transcriber encounters an error."""
        _session_var.set(self._session_id)  # propagate session to SDK thread
        logger.error("Transcription error: %s", error)
        self.notifier.error(str(error))
        self.tray.set_state("error", reason=str(error))
        # Reset recording state so the daemon stays functional after a
        # non-fatal transcriber error (e.g. too-short audio rejected by API).
        with self._lock:
            if self._recording_active:
                self._recording_active = False
                self._last_deactivate_time = time.monotonic()
                logger.info("Recording state reset after transcriber error")

    def run(self) -> None:
        """Start the dictation app. Blocks until interrupted."""
        self._running = True

        # Pre-warm the WebSocket connection to AssemblyAI in the background.
        # Connects, waits for the Begin event (API key verified), then
        # disconnects immediately.  Costs ~$0.000042 but ensures the first real
        # recording session connects in <1s instead of ~3s cold.
        threading.Thread(
            target=self.transcriber.test_connection,
            daemon=True,
            name="aai-connection-test",
        ).start()

        if sys.platform == "darwin":
            from murmur.platform.macos import check_accessibility, check_microphone

            if not check_accessibility():
                fatal(
                    "Accessibility permission required for keyboard monitoring.\n"
                    "Go to System Settings -> Privacy & Security -> Accessibility\n"
                    "and enable Terminal (or your Python interpreter)."
                )
            if not check_microphone():
                fatal(
                    "Microphone permission required for audio capture.\n"
                    "Go to System Settings -> Privacy & Security -> Microphone\n"
                    "and enable Terminal (or your Python interpreter)."
                )
        elif not self.injector.is_available():
            fatal(
                "ydotoold is not running. Start it with: systemctl --user start ydotool"
            )

        # Warn (non-fatal) about tmux bindings whose pane isn't available yet
        for binding in self.config.hotkey.bindings:
            if isinstance(binding.destination, TmuxDestination):
                inj = self._binding_injectors.get(id(binding))
                if inj is not None and not inj.is_available():
                    logger.warning(
                        "tmux pane %r not found — text will fall back to clipboard "
                        "until the session exists.",
                        str(binding.destination),
                    )

        if sys.platform == "darwin":
            _fkey = {f"KEY_F{i}" for i in range(1, 25)}
            for b in self.config.hotkey.bindings:
                if (
                    b.mode == "push_to_talk"
                    and b.trigger not in _fkey
                    and not b.suppress
                ):
                    logger.warning(
                        "Binding %s (mode=%s) has suppress=false on macOS: "
                        "the key character will type into the active app while held. "
                        'Set "suppress": true to prevent this.',
                        b.trigger,
                        b.mode,
                    )

        print(f"\n{'=' * 60}")
        print("  Dictation Tool Ready")
        print(f"  Engine:  {self.config.transcriber.backend}")
        print(f"  Inject:  {self.config.injector.backend}")
        print(f"{'=' * 60}")
        for binding in self.config.hotkey.bindings:
            combo = (
                "+".join(binding.modifiers + [binding.trigger])
                if binding.modifiers
                else binding.trigger
            )
            dest_label = str(binding.destination)
            parts = [f"{binding.mode.replace('_', ' ').title()} → {dest_label}"]
            if binding.language:
                parts.append(f"lang={binding.language}")
            if binding.append_enter:
                parts.append("+Enter")
            print(f"  {combo}  ->  {', '.join(parts)}")
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

    def on_tray_activate(self) -> None:
        """Handle tray icon left-click: toggle recording on/off."""
        with self._lock:
            active = self._recording_active
        if active:
            self.on_deactivate()
        else:
            # Use first push_to_talk binding, or a synthetic default
            binding = next(
                (b for b in self.config.hotkey.bindings if b.mode == "push_to_talk"),
                HotkeyBinding(mode="push_to_talk"),
            )
            self.on_activate(binding, trigger="tray")

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
