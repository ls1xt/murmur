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
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import Literal

from tap import Tap

from murmur.app import DictationApp, SessionFilter
from murmur.config import ConfigError, KEYTERMS_MAX, KEYTERMS_MAX_LEN, DictationConfig
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


def _parse_keyterms_file(path: str) -> list[str]:
    """Extract keyterms from a file containing a ``## Murmur Keyterms`` section.

    Looks for a heading whose text matches "murmur keyterms" (case-insensitive)
    and collects all terms until the next heading or end of file.

    Supported term formats within the section:
    - Comma-separated values on any line
    - Markdown bullet points (``- term`` or ``* term``)
    - Backtick-quoted terms (```term```)

    HTML comments (``<!-- ... -->``) are stripped before parsing.
    """
    try:
        content = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        fatal(f"File not found: {path}")
    except OSError as e:
        fatal(f"Cannot read {path!r}: {e}")

    lines = content.splitlines()
    section_start: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^#{1,6}\s+.*murmur\s+keyterms", line.strip(), re.IGNORECASE):
            section_start = i + 1
            break

    if section_start is None:
        return []

    section_lines: list[str] = []
    for line in lines[section_start:]:
        if re.match(r"^#{1,6}\s+", line):
            break
        section_lines.append(line)

    # Strip HTML comments
    section_text = re.sub(r"<!--.*?-->", "", "\n".join(section_lines), flags=re.DOTALL)

    terms: list[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "*", "•")):
            # Bullet: "- term" or "- term1, term2"
            rest = stripped[1:].strip()
            terms.extend(t.strip() for t in rest.split(",") if t.strip())
        else:
            # Check for backtick-quoted terms first
            backtick = re.findall(r"`([^`]+)`", stripped)
            if backtick:
                terms.extend(t.strip() for t in backtick if t.strip())
            else:
                # Plain comma-separated
                terms.extend(t.strip() for t in stripped.split(",") if t.strip())

    return terms


class _KeytermsArgs(Tap):
    action: Literal["list", "import", "add", "clear"]  # keyterms action
    file: str = "CLAUDE.md"  # file to import from (for 'import')
    terms: str = ""  # comma-separated terms to add (for 'add')
    replace: bool = False  # replace existing instead of merging

    def configure(self) -> None:
        self.add_argument("action", help="Keyterms action: list, import, add, clear")
        self.set_defaults(func=_cmd_keyterms)


class _MurmurArgs(Tap):
    def configure(self) -> None:
        self.add_subparsers(dest="subcommand", help="sub-command help")
        self.add_subparser("config", _ConfigArgs, help="View or set configuration")
        self.add_subparser(
            "list-mics", _ListMicsArgs, help="List available microphone devices"
        )
        self.add_subparser("record", _RecordArgs, help="Single dictation session")
        self.add_subparser("daemon", _DaemonArgs, help="Manage background service")
        self.add_subparser(
            "keyterms", _KeytermsArgs, help="Manage transcription keyterms"
        )


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


def _cmd_keyterms(args: _KeytermsArgs) -> None:
    """Handle: murmur keyterms {list|import|add|clear}"""
    config = DictationConfig.load()
    action = args.action

    if action == "list":
        terms = config.transcriber.keyterms_prompt
        if not terms:
            print("No keyterms configured.")
            print("  murmur keyterms add --terms 'ScyllaDB,PyO3'")
            print(
                "  murmur keyterms import              # reads ## Murmur Keyterms from CLAUDE.md"
            )
            return
        print(f"Keyterms ({len(terms)}/{KEYTERMS_MAX}):")
        for i, term in enumerate(terms, 1):
            flag = (
                f"  [>{KEYTERMS_MAX_LEN} chars, will be dropped]"
                if len(term) > KEYTERMS_MAX_LEN
                else ""
            )
            print(f"  {i:3d}. {term}{flag}")

    elif action == "import":
        new_terms = _parse_keyterms_file(args.file)
        if not new_terms:
            print(f"No keyterms found in {args.file!r}.")
            print("Add a section to that file like:")
            print("")
            print("  ## Murmur Keyterms")
            print("  ScyllaDB, PyO3, my-project-name")
            return

        existing = list(config.transcriber.keyterms_prompt)
        if args.replace:
            merged = list(dict.fromkeys(new_terms))  # deduplicate, preserve order
        else:
            seen = set(existing)
            merged = existing + [t for t in new_terms if t not in seen]

        if len(merged) > KEYTERMS_MAX:
            print(
                f"Warning: {len(merged)} terms exceed limit of {KEYTERMS_MAX}; truncating."
            )
            merged = merged[:KEYTERMS_MAX]

        config.transcriber.keyterms_prompt = merged
        config.save()

        added = len(merged) - (0 if args.replace else len(existing))
        action_word = "Imported" if args.replace else "Merged"
        print(
            f"{action_word} {len(new_terms)} terms from {args.file!r} (+{added} new, {len(merged)} total)."
        )

    elif action == "add":
        if not args.terms:
            fatal("Provide terms with --terms 'term1,term2,...'")
        new_terms = [t.strip() for t in args.terms.split(",") if t.strip()]
        existing = list(config.transcriber.keyterms_prompt)
        if args.replace:
            merged = list(dict.fromkeys(new_terms))
        else:
            seen = set(existing)
            merged = existing + [t for t in new_terms if t not in seen]

        if len(merged) > KEYTERMS_MAX:
            print(
                f"Warning: {len(merged)} terms exceed limit of {KEYTERMS_MAX}; truncating."
            )
            merged = merged[:KEYTERMS_MAX]

        config.transcriber.keyterms_prompt = merged
        config.save()
        added = len(merged) - (0 if args.replace else len(existing))
        print(f"Added {added} term(s). Total: {len(merged)}/{KEYTERMS_MAX}.")

    elif action == "clear":
        config.transcriber.keyterms_prompt = []
        config.save()
        print("Keyterms cleared.")


def main() -> None:
    """Entry point for the murmur CLI."""
    args = _MurmurArgs(description="System-wide voice dictation").parse_args()
    func = getattr(args, "func", None)
    if func is None:
        fatal("No subcommand provided. Use --help for usage information.")
    func(args)
