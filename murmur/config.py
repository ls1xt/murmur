"""
Configuration for the dictation tool.
Loads from environment variables and/or a config file.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal, cast

logger = logging.getLogger(__name__)

CONFIG_DIR: Final[Path] = Path.home() / ".config" / "murmur"
CONFIG_FILE: Final[Path] = CONFIG_DIR / "config.json"


class ConfigError(Exception):
    """Raised when the config file exists but cannot be loaded."""


@dataclass(frozen=True)
class TypeDestination:
    """Send transcribed text to the focused application via keystroke injection."""

    kind: Literal["type"] = "type"

    def __str__(self) -> str:
        return "type"


@dataclass(frozen=True)
class ClipboardDestination:
    """Copy transcribed text to the system clipboard."""

    kind: Literal["clipboard"] = "clipboard"

    def __str__(self) -> str:
        return "clipboard"


@dataclass(frozen=True)
class TmuxDestination:
    """Send transcribed text to a specific tmux pane."""

    target: str  # pane address, e.g. "todo:0.0"
    kind: Literal["tmux"] = "tmux"

    def __str__(self) -> str:
        return f"tmux:{self.target}"


Destination = TypeDestination | ClipboardDestination | TmuxDestination


@dataclass
class HotkeyBinding:
    """A single hotkey binding mapping a key combination to an action.

    Fields:
        modifiers: List of modifier key names (e.g. ``["KEY_LEFTCTRL", "KEY_LEFTMETA"]``).
        trigger: The key name that triggers the action (e.g. ``"KEY_SPACE"``).
        mode: Activation mode.  ``"push_to_talk"`` records while the key is
            held and stops on release.  ``"toggle"`` starts recording on the
            first press and stops on a second press.
        destination: Where the transcribed text is sent.  ``TypeDestination``
            types the text into the currently focused application using
            keystroke injection.  ``ClipboardDestination`` copies the full
            session text to the system clipboard on completion.
            ``TmuxDestination`` sends text to a specific tmux pane; the pane
            address is encoded as ``"tmux:SESSION:WINDOW.PANE"``
            (e.g. ``"tmux:todo:0.0"``).
        language: Per-binding language override.  An ISO 639-1 code or
            AssemblyAI regional variant (e.g. ``"de"``, ``"en_au"``).  When
            ``None``, the global transcriber language is used.
        append_enter: When ``True``, a Return key press is sent after the
            transcription is injected at the end of each session.
        suppress: When ``True``, installs an active CGEventTap to swallow the
            key event so it does not reach other applications.
    """

    modifiers: list[str] = field(
        default_factory=lambda: ["KEY_LEFTCTRL", "KEY_LEFTALT"]
    )
    trigger: str = "KEY_SPACE"
    mode: Literal["push_to_talk", "toggle"] = "push_to_talk"
    destination: Destination = field(default_factory=TypeDestination)
    language: str | None = None
    append_enter: bool = False
    # suppress=True installs an active CGEventTap to swallow the key event
    suppress: bool = False


def _default_bindings() -> list[HotkeyBinding]:
    """Create the default hotkey configuration.

    On macOS, Cmd (KEY_LEFTMETA) is used instead of Alt (KEY_LEFTALT) because
    macOS Option/Alt transforms key characters at the OS level (e.g. Alt+M →
    'µ'), breaking hotkeys on non-US keyboard layouts.  Cmd never transforms
    characters, so Ctrl+Cmd+key works on any layout.
    """
    import sys

    meta = "KEY_LEFTMETA" if sys.platform == "darwin" else "KEY_LEFTALT"
    return [
        HotkeyBinding(
            modifiers=[],
            trigger="KEY_F12",
            mode="push_to_talk",
            destination=TypeDestination(),
            suppress=True,
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", meta],
            trigger="KEY_M",
            mode="toggle",
            destination=TypeDestination(),
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", meta],
            trigger="KEY_C",
            mode="push_to_talk",
            destination=ClipboardDestination(),
        ),
        HotkeyBinding(
            modifiers=["KEY_LEFTCTRL", meta],
            trigger="KEY_V",
            mode="toggle",
            destination=ClipboardDestination(),
        ),
    ]


@dataclass
class HotkeyConfig:
    """Hotkey detection settings."""

    bindings: list[HotkeyBinding] = field(default_factory=_default_bindings)
    backend: Literal["auto", "evdev", "pynput"] = "auto"
    evdev_device: str | None = None
    push_to_talk_debounce_ms: int = 300
    stop_on_keypress: bool = True


KEYTERMS_MAX = 100
KEYTERMS_MAX_LEN = 50


@dataclass
class TranscriberConfig:
    """Speech-to-text engine settings."""

    backend: Literal["assemblyai"] = "assemblyai"
    api_key: str = ""
    sample_rate: int = 16_000
    format_turns: bool = True
    language: str = "en"
    end_of_turn_confidence_threshold: float = 0.4
    min_end_of_turn_silence_when_confident: int = 400
    max_turn_silence: int = 1280
    keyterms_prompt: list[str] = field(default_factory=list[str])
    keyterms: list[str] = field(default_factory=list[str])
    inject_partials: bool = False
    reconnect_attempts: int = 5
    reconnect_delay_ms: int = 1000
    mic_device: str | int | None = None

    def validate(self) -> None:
        """Warn about keyterms that violate AssemblyAI's API limits.

        AssemblyAI enforces: max 100 keyterms, each ≤50 characters.
        Violations are logged at WARNING level so they surface at startup
        rather than at connection time (where they cause a cryptic 1011 error).
        """
        terms = self.keyterms_prompt
        if not terms:
            return
        seen: set[str] = set()
        dupes: list[str] = []
        too_long: list[str] = []
        for t in terms:
            if t in seen:
                dupes.append(t)
            else:
                seen.add(t)
            if len(t) > KEYTERMS_MAX_LEN:
                too_long.append(t)
        unique_count = len(seen)
        if dupes:
            logger.warning(
                "Config: duplicate keyterms will be dropped at connect time: %s", dupes
            )
        if too_long:
            logger.warning(
                "Config: keyterms exceed %d-char limit and will be dropped: %s",
                KEYTERMS_MAX_LEN,
                too_long,
            )
        if unique_count > KEYTERMS_MAX:
            logger.warning(
                "Config: %d keyterms exceeds AssemblyAI limit of %d; "
                "the last %d will be dropped at connect time. "
                "Trim your keyterms_prompt list.",
                unique_count,
                KEYTERMS_MAX,
                unique_count - KEYTERMS_MAX,
            )


@dataclass
class InjectorConfig:
    """Text injection settings."""

    backend: Literal["auto", "pynput", "ydotool", "cgevent", "tmux"] = "auto"
    ydotool_path: str = "ydotool"
    trailing_space: bool = True
    key_delay: int = 1
    inject_strategy: Literal["clipboard", "clipboard-fallback", "ydotool"] = "ydotool"


@dataclass
class FeedbackConfig:
    """User feedback settings."""

    audio_enabled: bool = True
    start_hz: float = 440.0
    stop_hz: float = 880.0
    visual_enabled: bool = False
    start_duration_ms: int = 100
    stop_duration_ms: int = 100
    amplitude: float = 0.3


@dataclass
class NotifyConfig:
    """Desktop notification settings."""

    level: Literal["off", "errors", "verbose"] = "errors"


@dataclass
class TrayConfig:
    """System tray icon settings."""

    enabled: bool = True


def _parse_destination(bd: dict[str, Any]) -> Destination | None:
    """Parse destination from a binding dict, handling all migration paths.

    Accepted formats:
    - New:      ``destination: "type"`` / ``"clipboard"`` / ``"tmux:SESSION:WINDOW.PANE"``
    - Old:      ``destination: "tmux"`` + ``inject_to: "SESSION:WINDOW.PANE"``
    - Oldest:   ``inject_to: "tmux:SESSION:WINDOW.PANE"`` (no destination field)
    - Migration: ``destination: "direct_inject"`` → TypeDestination
    - Saved:    ``destination: {"kind": "type"}`` (dataclasses.asdict() output) → TypeDestination
    """
    raw_value = bd.get("destination", "type")
    # Handle destinations saved by config.save() as dataclass dicts
    # (e.g. {"kind": "type"}, {"kind": "clipboard"}, {"kind": "tmux", "target": "..."})
    if isinstance(raw_value, dict):
        kind = raw_value.get("kind", "type")
        if kind == "tmux":
            target = raw_value.get("target", "")
            if target:
                return TmuxDestination(target=target)
            logger.error(
                "Binding destination dict has kind='tmux' but no target. Binding skipped."
            )
            return None
        elif kind == "clipboard":
            return ClipboardDestination()
        else:
            return TypeDestination()
    raw_dest = str(raw_value)
    raw_inject_to: str | None = str(bd["inject_to"]) if "inject_to" in bd else None

    # Migrate legacy "direct_inject" value
    if raw_dest == "direct_inject":
        raw_dest = "type"

    if raw_dest.startswith("tmux:"):
        # New format: destination = "tmux:SESSION:WINDOW.PANE"
        return TmuxDestination(target=raw_dest[len("tmux:") :])

    if raw_dest == "tmux":
        # Old format: destination="tmux" + inject_to="SESSION:WINDOW.PANE"
        if raw_inject_to is None:
            logger.error(
                "Binding has destination='tmux' but no inject_to pane address. "
                "Use destination='tmux:SESSION:WINDOW.PANE'. Binding skipped."
            )
            return None
        # Handle very old inject_to="tmux:SESSION:..." format
        target = (
            raw_inject_to.removeprefix("tmux:")
            if raw_inject_to.startswith("tmux:")
            else raw_inject_to
        )
        return TmuxDestination(target=target)

    # Very old format: inject_to="tmux:SESSION:..." with no destination field
    if raw_inject_to is not None and raw_inject_to.startswith("tmux:"):
        return TmuxDestination(target=raw_inject_to.removeprefix("tmux:"))

    if raw_dest == "clipboard":
        return ClipboardDestination()

    if raw_dest != "type":
        logger.warning("Unknown destination %r; defaulting to 'type'", raw_dest)
    return TypeDestination()


def _apply_section(data: dict[str, Any], key: str, target: object) -> None:
    """Apply a JSON dict section to a dataclass instance.

    Uses setattr for JSON deserialization -- type safety is enforced
    by the dataclass field types at runtime.
    """
    if key not in data:
        return
    section: Any = data[key]
    if not isinstance(section, dict):
        return
    # section is dict[Unknown, Unknown] after isinstance narrowing of Any.
    # Explicit Any cast bypasses strict-mode tracking of untyped JSON values.
    raw_section: Any = section  # type: ignore[reportUnknownVariableType]
    items: list[tuple[str, Any]] = list(raw_section.items())
    for name, value in items:
        if hasattr(target, name):
            setattr(target, name, value)


@dataclass
class DictationConfig:
    """Top-level configuration."""

    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    transcriber: TranscriberConfig = field(default_factory=TranscriberConfig)
    injector: InjectorConfig = field(default_factory=InjectorConfig)
    feedback: FeedbackConfig = field(default_factory=FeedbackConfig)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    tray: TrayConfig = field(default_factory=TrayConfig)
    log_level: str = "INFO"

    @classmethod
    def load(cls) -> DictationConfig:
        """Load config from file + environment overrides."""
        config = cls()

        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    data: dict[str, Any] = json.load(f)
                config = cls.from_dict(data)
                logger.info("Loaded config from %s", CONFIG_FILE)
            except Exception as e:
                raise ConfigError(
                    f"Failed to load config file {CONFIG_FILE}: {e}"
                ) from e

        if api_key := os.environ.get("ASSEMBLYAI_API_KEY"):
            config.transcriber.api_key = api_key

        if log_level := os.environ.get("MURMUR_LOG_LEVEL") or os.environ.get(
            "DICTATION_LOG_LEVEL"
        ):
            config.log_level = log_level

        if backend := os.environ.get("DICTATION_HOTKEY_BACKEND"):
            # cast: env var is user-supplied; runtime value must match Literal
            config.hotkey.backend = cast(Literal["auto", "evdev", "pynput"], backend)

        if backend := os.environ.get("DICTATION_INJECTOR_BACKEND"):
            # cast: env var is user-supplied; runtime value must match Literal
            config.injector.backend = cast(
                Literal["auto", "pynput", "ydotool", "cgevent", "tmux"], backend
            )

        if strategy := os.environ.get("MURMUR_INJECT_STRATEGY"):
            # cast: env var is user-supplied; runtime value must match Literal
            config.injector.inject_strategy = cast(
                Literal["clipboard", "clipboard-fallback", "ydotool"], strategy
            )

        if notify_level := os.environ.get("MURMUR_NOTIFY_LEVEL"):
            # cast: env var is user-supplied; runtime value must match Literal
            config.notify.level = cast(
                Literal["off", "errors", "verbose"], notify_level
            )

        if mic_device := os.environ.get("MURMUR_MIC_DEVICE"):
            config.transcriber.mic_device = (
                int(mic_device) if mic_device.isdigit() else mic_device
            )

        config.transcriber.validate()

        # On macOS, normalize KEY_LEFTALT/KEY_RIGHTALT → KEY_LEFTMETA/KEY_RIGHTMETA
        # in all binding modifier lists.  This lets users write Linux-style configs
        # and have them work correctly on macOS, where Option/Alt transforms key
        # characters at the OS level but Cmd does not.
        import sys

        if sys.platform == "darwin":
            _alt_to_meta = {
                "KEY_LEFTALT": "KEY_LEFTMETA",
                "KEY_RIGHTALT": "KEY_RIGHTMETA",
            }
            for binding in config.hotkey.bindings:
                binding.modifiers = [
                    _alt_to_meta.get(mod, mod) for mod in binding.modifiers
                ]

        return config

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DictationConfig:
        """Construct config from a dict (loaded from JSON).

        Uses setattr for JSON deserialization -- type safety is enforced
        by the dataclass field types at runtime.

        """
        config = cls()
        hotkey_data: Any = data.get("hotkey")
        if isinstance(hotkey_data, dict):
            raw_hotkey: dict[str, Any] = hotkey_data  # type: ignore[reportUnknownVariableType]
            if "bindings" in raw_hotkey:
                bindings_raw: Any = raw_hotkey["bindings"]
                if isinstance(bindings_raw, list):
                    bindings: list[HotkeyBinding] = []
                    for b in bindings_raw:  # type: ignore[reportUnknownVariableType]
                        if isinstance(b, dict):
                            # cast: b is dict from JSON; keys are strings, values are Any
                            bd: dict[str, Any] = cast(dict[str, Any], b)
                            binding = HotkeyBinding()
                            if "modifiers" in bd:
                                binding.modifiers = bd["modifiers"]
                            if "trigger" in bd:
                                binding.trigger = bd["trigger"]
                            if "mode" in bd:
                                binding.mode = cast(
                                    Literal["push_to_talk", "toggle"],
                                    bd["mode"],
                                )
                            dest = _parse_destination(bd)
                            if dest is None:
                                continue  # invalid binding, skip it
                            binding.destination = dest
                            if "language" in bd:
                                raw_lang: Any = bd["language"]
                                binding.language = (
                                    str(raw_lang) if raw_lang is not None else None
                                )
                            if "append_enter" in bd:
                                binding.append_enter = bool(bd["append_enter"])
                            if "suppress" in bd:
                                binding.suppress = bool(bd["suppress"])
                            bindings.append(binding)
                    if bindings:
                        config.hotkey.bindings = bindings
            # Apply remaining hotkey fields (backend, evdev_device, debounce)
            if "backend" in raw_hotkey:
                # cast: JSON value must match Literal at runtime
                config.hotkey.backend = cast(
                    Literal["auto", "evdev", "pynput"], raw_hotkey["backend"]
                )
            if "evdev_device" in raw_hotkey:
                config.hotkey.evdev_device = raw_hotkey["evdev_device"]
            if "push_to_talk_debounce_ms" in raw_hotkey:
                config.hotkey.push_to_talk_debounce_ms = int(
                    raw_hotkey["push_to_talk_debounce_ms"]
                )
            if "stop_on_keypress" in raw_hotkey:
                config.hotkey.stop_on_keypress = bool(raw_hotkey["stop_on_keypress"])
        _apply_section(data, "transcriber", config.transcriber)
        _apply_section(data, "injector", config.injector)
        _apply_section(data, "feedback", config.feedback)
        _apply_section(data, "notify", config.notify)
        _apply_section(data, "tray", config.tray)
        if "log_level" in data:
            config.log_level = str(data["log_level"])
        return config

    def save(self) -> None:
        """Save current config to file."""
        import dataclasses

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(dataclasses.asdict(self), f, indent=2)
        logger.info("Saved config to %s", CONFIG_FILE)
