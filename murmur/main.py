"""
System-wide dictation tool -- main entry point.

Wires together hotkey detection, speech-to-text streaming, and text injection
to provide push-to-talk (or toggle) dictation into any application.
"""

import contextlib
import dataclasses
import json
import logging
import os
import signal
import subprocess
import sys
from typing import Literal

from tap import Tap

from murmur.app import DictationApp, SessionFilter
from murmur.config import ConfigError, DictationConfig
from murmur.errors import fatal


def _setup_logging(config: DictationConfig) -> None:
    """Configure logging from config."""
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)-7s] [s=%(session)d] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    _filter = SessionFilter()
    for handler in logging.root.handlers:
        handler.addFilter(_filter)
    # websockets logs raw binary frames at DEBUG -- suppress to WARNING
    # to keep logs readable. Set MURMUR_LOG_LEVEL=WEBSOCKETS_DEBUG to restore.
    if config.log_level.upper() not in ("WEBSOCKETS_DEBUG",):
        logging.getLogger("websockets").setLevel(logging.WARNING)


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


class _ConfigArgs(Tap):
    key: str | None = None  # dot-separated config key (e.g. transcriber.api_key)
    value: str | None = None  # value to set for the given key

    def configure(self) -> None:
        self.set_defaults(func=_cmd_config)


class _ListMicsArgs(Tap):
    def configure(self) -> None:
        self.set_defaults(func=_cmd_list_mics)


class _RecordArgs(Tap):
    inject: Literal["ydotool", "clipboard-fallback", "clipboard"] | None = (
        None  # injection backend override
    )
    notify: Literal["off", "errors", "verbose"] | None = (
        None  # notification level override
    )
    inject_partials: bool | None = None  # whether to inject partial transcriptions

    def configure(self) -> None:
        self.set_defaults(func=_cmd_record)


class _DaemonArgs(Tap):
    action: Literal["start", "stop", "status", "enable"]  # daemon action

    def configure(self) -> None:
        self.add_argument("action", help="Daemon action: start, stop, status, enable")
        self.set_defaults(func=_cmd_daemon)


class _MurmurArgs(Tap):
    def configure(self) -> None:
        self.add_subparsers(dest="subcommand", help="sub-command help")
        self.add_subparser("config", _ConfigArgs, help="View or set configuration")
        self.add_subparser(
            "list-mics", _ListMicsArgs, help="List available microphone devices"
        )
        self.add_subparser("record", _RecordArgs, help="Single dictation session")
        self.add_subparser("daemon", _DaemonArgs, help="Manage background service")


def _cmd_config(args: _ConfigArgs) -> None:
    """Handle: murmur config [--key KEY] [--value VALUE]"""
    try:
        config = DictationConfig.load()
    except ConfigError as e:
        fatal(str(e))

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


def _cmd_list_mics(_args: _ListMicsArgs) -> None:
    """Handle: murmur list-mics"""
    from typing import Any as _Any

    import sounddevice as _sd

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


def _cmd_record(args: _RecordArgs) -> None:
    """Handle: murmur record [--inject ...] [--notify ...] [--inject-partials]"""
    try:
        config = DictationConfig.load()
    except ConfigError as e:
        fatal(str(e))

    if args.inject is not None:
        config.injector.inject_strategy = args.inject

    if args.notify is not None:
        config.notify.level = args.notify

    if args.inject_partials is not None:
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


def _cmd_daemon(args: _DaemonArgs) -> None:
    """Handle: murmur daemon {start|stop|status|enable}"""
    action: str = args.action

    if action == "start":
        _cmd_record(_RecordArgs().parse_args([]))

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
    args = _MurmurArgs(description="System-wide voice dictation").parse_args()
    func = getattr(args, "func", None)
    if func is None:
        fatal("No subcommand provided. Use --help for usage information.")
    func(args)
