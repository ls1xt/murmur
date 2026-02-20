"""
System-wide dictation tool -- main entry point.

Wires together hotkey detection, speech-to-text streaming, and text injection
to provide push-to-talk (or toggle) dictation into any application.
"""

from __future__ import annotations

import argparse
import contextlib
import contextvars
import dataclasses
import json
import logging
import os
import signal
import subprocess
import sys
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

        self.hotkey: HotkeyListener = create_hotkey_listener(config.hotkey)
        self.transcriber: Transcriber = create_transcriber(config.transcriber)
        self.injector: TextInjector = create_injector(config.injector)
        self.feedback = AudioFeedback(
            enabled=config.feedback.audio_enabled,
            start_hz=config.feedback.start_hz,
            stop_hz=config.feedback.stop_hz,
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
        with self._lock:
            if self.transcriber.is_streaming:
                return  # already recording
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
            if not self.transcriber.is_streaming:
                return  # already stopped
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
        if self.transcriber.is_streaming:
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


def _setup_logging(config: DictationConfig) -> None:
    """Configure logging from config."""
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-7s] [s=%(session)d] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    _filter = _SessionFilter()
    for handler in logging.root.handlers:
        handler.addFilter(_filter)


def _get_dotted(obj: object, key: str) -> object:
    """Get a value from a nested dataclass using dot notation."""
    parts = key.split(".")
    current: object = obj
    for part in parts:
        current = getattr(current, part)
    return current


def _set_dotted(obj: object, key: str, value: str) -> None:
    """Set a value on a nested dataclass using dot notation."""
    parts = key.split(".")
    current: object = obj
    for part in parts[:-1]:
        current = getattr(current, part)
    # Get the current field value to determine its type
    field_name = parts[-1]
    current_val = getattr(current, field_name)
    # Try to cast value to the same type as the current field
    if isinstance(current_val, bool):
        typed_value: object = value.lower() in ("true", "1", "yes")
    elif isinstance(current_val, int):
        typed_value = int(value)
    elif isinstance(current_val, float):
        typed_value = float(value)
    elif isinstance(current_val, list):
        typed_value = [v.strip() for v in value.split(",") if v.strip()]
    else:
        typed_value = value
    setattr(current, field_name, typed_value)


def _cmd_config(args: argparse.Namespace) -> None:
    """Handle: murmur config [--key KEY] [--value VALUE]"""
    config = DictationConfig.load()

    if args.key is None:
        # Print full config as JSON
        print(json.dumps(dataclasses.asdict(config), indent=2))
        return

    if args.value is None:
        # Print specific key value
        try:
            val = _get_dotted(config, args.key)
            print(val)
        except AttributeError:
            fatal(f"Unknown config key: {args.key}")
        return

    # Set key to value
    try:
        _set_dotted(config, args.key, args.value)
        config.save()
        print(f"Saved: {args.key} = {args.value}")
    except AttributeError:
        fatal(f"Unknown config key: {args.key}")


def _cmd_list_mics(_args: argparse.Namespace) -> None:
    """Handle: murmur list-mics"""
    from typing import Any as _Any

    import sounddevice as _sd  # type: ignore[import-untyped]

    devices: _Any = _sd.query_devices()
    print("Available input devices:")
    print(f"  {'IDX':>3}  {'NAME':<40}  CHANNELS  RATE")
    print(f"  {'-' * 3}  {'-' * 40}  {'-' * 8}  {'-' * 8}")
    default_input = (
        _sd.default.device[0]
        if isinstance(_sd.default.device, (list, tuple))
        else _sd.default.device
    )
    for i, dev in enumerate(devices):
        if dev.get("max_input_channels", 0) > 0:
            marker = " *" if i == default_input else "  "
            print(
                f"{marker}{i:>3}  {dev['name']:<40}  "
                f"{dev['max_input_channels']:>8}  "
                f"{int(dev.get('default_samplerate', 0)):>8}"
            )
    print("\n* = current default")
    print("\nTo use a specific device:")
    print("  murmur config --key transcriber.mic_device --value <index_or_name>")


def _cmd_record(args: argparse.Namespace) -> None:
    """Handle: murmur record [--inject ...] [--notify ...] [--inject-partials]"""
    config = DictationConfig.load()

    if hasattr(args, "inject") and args.inject is not None:
        config.injector.inject_strategy = args.inject

    if hasattr(args, "notify") and args.notify is not None:
        config.notify.level = args.notify

    if hasattr(args, "inject_partials") and args.inject_partials is not None:
        config.transcriber.inject_partials = args.inject_partials

    _setup_logging(config)

    if not config.transcriber.api_key:
        # Try setup wizard
        msg = (
            "API key not set. Run: "
            "murmur config --key transcriber.api_key --value YOUR_KEY"
        )
        try:
            from murmur.setup_wizard import prompt_setup  # type: ignore[import-not-found]  # noqa: I001

            if not prompt_setup(config):  # type: ignore[no-untyped-call]
                fatal(msg)
        except ImportError:
            fatal(msg)

    app = DictationApp(config)
    app.run()


def _cmd_daemon(args: argparse.Namespace) -> None:
    """Handle: murmur daemon {start|stop|status|enable}"""
    action: str = args.action

    if action == "start":
        _cmd_record(args)

    elif action == "stop":
        result = subprocess.run(
            ["pgrep", "-f", "murmur daemon start"],
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            # Also check for 'murmur record'
            result = subprocess.run(
                ["pgrep", "-f", "murmur record"],
                capture_output=True,
                text=True,
            )
        if result.stdout.strip():
            pids = result.stdout.strip().split()
            for pid in pids:
                with contextlib.suppress(ProcessLookupError):
                    os.kill(int(pid), signal.SIGTERM)
            print("Daemon stopped.")
        else:
            print("No daemon running.")

    elif action == "status":
        result = subprocess.run(
            ["pgrep", "-f", "murmur daemon start"],
            capture_output=True,
            text=True,
        )
        if not result.stdout.strip():
            result = subprocess.run(
                ["pgrep", "-f", "murmur record"],
                capture_output=True,
                text=True,
            )
        if result.stdout.strip():
            pid = result.stdout.strip().split()[0]
            print(f"Daemon running (PID={pid})")
        else:
            print("Daemon not running")

    elif action == "enable":
        # Look for install-service.sh relative to the package
        import importlib.util

        spec = importlib.util.find_spec("murmur")
        install_script: str | None = None
        if spec and spec.origin:
            pkg_dir = os.path.dirname(spec.origin)
            candidate = os.path.join(os.path.dirname(pkg_dir), "install-service.sh")
            if os.path.exists(candidate):
                install_script = candidate

        if install_script:
            subprocess.run(["bash", install_script], check=True)
        else:
            print("Service installer not found.")
            print("To enable auto-start manually:")
            if sys.platform == "darwin":
                print("  Copy the LaunchAgent plist to ~/Library/LaunchAgents/")
                print(
                    "  Then: launchctl load "
                    "~/Library/LaunchAgents/com.murmur.dictation.plist"
                )
            else:
                print("  Copy murmur.service to ~/.config/systemd/user/")
                print("  Then: systemctl --user enable --now murmur")


def main() -> None:
    """Entry point for the murmur CLI."""
    parser = argparse.ArgumentParser(
        prog="murmur",
        description="System-wide voice dictation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # murmur config [--key KEY] [--value VALUE]
    config_parser = subparsers.add_parser("config", help="View or set configuration")
    config_parser.add_argument(
        "--key",
        help="Dot-separated config key (e.g. transcriber.api_key)",
    )
    config_parser.add_argument(
        "--value",
        help="Value to set for the given key",
    )

    # murmur record
    # murmur list-mics
    subparsers.add_parser("list-mics", help="List available microphone input devices")

    record_parser = subparsers.add_parser(
        "record", help="Single dictation session (run once and exit)"
    )
    record_parser.add_argument(
        "--inject",
        choices=["ydotool", "clipboard-fallback", "clipboard"],
        default=None,
    )
    record_parser.add_argument(
        "--notify",
        choices=["off", "errors", "verbose"],
        default=None,
    )
    record_parser.add_argument(
        "--inject-partials",
        dest="inject_partials",
        action="store_true",
        default=None,
    )
    record_parser.add_argument(
        "--no-inject-partials",
        dest="inject_partials",
        action="store_false",
    )

    # murmur daemon {start|stop|status|enable}
    daemon_parser = subparsers.add_parser("daemon", help="Manage background service")
    daemon_parser.add_argument(
        "action",
        choices=["start", "stop", "status", "enable"],
        help="start: run daemon; stop: send SIGTERM; status: check; enable: install",
    )

    args = parser.parse_args()

    if args.command == "config":
        _cmd_config(args)
    elif args.command == "record":
        _cmd_record(args)
    elif args.command == "daemon":
        _cmd_daemon(args)
    elif args.command == "list-mics":
        _cmd_list_mics(args)
