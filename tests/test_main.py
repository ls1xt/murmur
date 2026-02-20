"""Tests for murmur CLI subcommands and DictationApp orchestration.

Tests the full activate → transcribe → deactivate cycle using mocked
backends, and all subcommand paths (config, record, daemon).
"""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import MagicMock

import pytest

from murmur.config import DictationConfig, FeedbackConfig, TrayConfig
from murmur.main import DictationApp, main


def _make_app(mocker: Any) -> tuple[DictationApp, MagicMock, MagicMock, MagicMock]:
    """Build a DictationApp with all hardware backends mocked out.

    Returns (app, mock_transcriber, mock_injector, mock_hotkey).
    """
    config = DictationConfig()
    config.transcriber.api_key = "fake_key"
    config.feedback = FeedbackConfig(audio_enabled=False)
    config.tray = TrayConfig(enabled=False)

    mock_transcriber = MagicMock()
    mock_transcriber.is_streaming = False
    mock_injector = MagicMock()
    mock_injector.is_available.return_value = True
    mock_hotkey = MagicMock()

    mocker.patch("murmur.main.create_transcriber", return_value=mock_transcriber)
    mocker.patch("murmur.main.create_injector", return_value=mock_injector)
    mocker.patch("murmur.main.create_hotkey_listener", return_value=mock_hotkey)

    app = DictationApp(config)
    return app, mock_transcriber, mock_injector, mock_hotkey


def _run_main(args: list[str], mocker: Any) -> None:
    """Run main() with the given argv args (excluding prog name)."""
    mocker.patch("sys.argv", ["murmur"] + args)


# ─── Config subcommand ────────────────────────────────────────────────────────


class TestConfigSubcommand:
    def test_config_no_args_prints_json(self, mocker: Any, capsys: Any) -> None:
        """murmur config prints full config as valid JSON."""
        config = DictationConfig()
        mocker.patch("murmur.main.DictationConfig.load", return_value=config)
        _run_main(["config"], mocker)
        main()
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "transcriber" in parsed
        assert "hotkey" in parsed

    def test_config_get_key(self, mocker: Any, capsys: Any) -> None:
        """murmur config --key transcriber.api_key prints the value."""
        config = DictationConfig()
        config.transcriber.api_key = "my_test_key"
        mocker.patch("murmur.main.DictationConfig.load", return_value=config)
        _run_main(["config", "--key", "transcriber.api_key"], mocker)
        main()
        captured = capsys.readouterr()
        assert "my_test_key" in captured.out

    def test_config_set_key(self, mocker: Any, capsys: Any) -> None:
        """murmur config --key K --value V saves config and prints confirmation."""
        config = DictationConfig()
        mocker.patch("murmur.main.DictationConfig.load", return_value=config)
        mock_save = mocker.patch.object(config, "save")
        _run_main(
            ["config", "--key", "transcriber.api_key", "--value", "new_key"],
            mocker,
        )
        main()
        mock_save.assert_called_once()
        captured = capsys.readouterr()
        assert "Saved" in captured.out
        assert "transcriber.api_key" in captured.out


# ─── Record subcommand ────────────────────────────────────────────────────────


class TestRecordSubcommand:
    def test_record_no_api_key_exits(self, mocker: Any) -> None:
        """murmur record with no API key raises SystemExit."""
        config = DictationConfig()
        config.transcriber.api_key = ""
        mocker.patch("murmur.main.DictationConfig.load", return_value=config)
        # Suppress setup_wizard import
        mocker.patch.dict(
            "sys.modules",
            {"murmur.setup_wizard": None},  # type: ignore[dict-item]
        )
        _run_main(["record"], mocker)
        with pytest.raises(SystemExit):
            main()

    def test_record_with_api_key_runs_app(self, mocker: Any) -> None:
        """murmur record with a valid API key launches DictationApp.run()."""
        config = DictationConfig()
        config.transcriber.api_key = "valid_key"
        config.feedback = FeedbackConfig(audio_enabled=False)
        config.tray = TrayConfig(enabled=False)
        mocker.patch("murmur.main.DictationConfig.load", return_value=config)
        mocker.patch("murmur.main.create_transcriber", return_value=MagicMock())
        mocker.patch("murmur.main.create_injector", return_value=MagicMock())
        mocker.patch("murmur.main.create_hotkey_listener", return_value=MagicMock())
        mock_run = mocker.patch.object(DictationApp, "run")
        _run_main(["record"], mocker)
        main()
        mock_run.assert_called_once()

    def test_record_inject_flag_overrides_config(self, mocker: Any) -> None:
        """murmur record --inject clipboard overrides injector strategy."""
        config = DictationConfig()
        config.transcriber.api_key = "valid_key"
        config.feedback = FeedbackConfig(audio_enabled=False)
        config.tray = TrayConfig(enabled=False)
        mocker.patch("murmur.main.DictationConfig.load", return_value=config)
        mocker.patch("murmur.main.create_transcriber", return_value=MagicMock())
        mocker.patch("murmur.main.create_injector", return_value=MagicMock())
        mocker.patch("murmur.main.create_hotkey_listener", return_value=MagicMock())
        mocker.patch.object(DictationApp, "run")
        _run_main(["record", "--inject", "clipboard"], mocker)
        main()
        assert config.injector.inject_strategy == "clipboard"


# ─── Daemon subcommand ────────────────────────────────────────────────────────


class TestDaemonSubcommand:
    def test_daemon_status_not_running(self, mocker: Any, capsys: Any) -> None:
        """murmur daemon status prints 'not running' when no daemon is found."""
        # pgrep returns empty output for both checks
        mock_result = MagicMock()
        mock_result.stdout = ""
        mocker.patch("murmur.main.subprocess.run", return_value=mock_result)
        _run_main(["daemon", "status"], mocker)
        main()
        captured = capsys.readouterr()
        assert "not running" in captured.out.lower()

    def test_daemon_status_running(self, mocker: Any, capsys: Any) -> None:
        """murmur daemon status prints PID when daemon is found."""
        mock_result = MagicMock()
        mock_result.stdout = "12345\n"
        mocker.patch("murmur.main.subprocess.run", return_value=mock_result)
        _run_main(["daemon", "status"], mocker)
        main()
        captured = capsys.readouterr()
        assert "12345" in captured.out

    def test_daemon_start_calls_record(self, mocker: Any) -> None:
        """murmur daemon start delegates to _cmd_record."""
        config = DictationConfig()
        config.transcriber.api_key = "valid_key"
        config.feedback = FeedbackConfig(audio_enabled=False)
        config.tray = TrayConfig(enabled=False)
        mocker.patch("murmur.main.DictationConfig.load", return_value=config)
        mocker.patch("murmur.main.create_transcriber", return_value=MagicMock())
        mocker.patch("murmur.main.create_injector", return_value=MagicMock())
        mocker.patch("murmur.main.create_hotkey_listener", return_value=MagicMock())
        mock_run = mocker.patch.object(DictationApp, "run")
        _run_main(["daemon", "start"], mocker)
        main()
        mock_run.assert_called_once()


# ─── DictationApp lifecycle ───────────────────────────────────────────────────


class TestDictationAppLifecycle:
    def test_activate_starts_transcription(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        app._on_activate("push_to_talk")

        time.sleep(0.05)
        transcriber.start.assert_called_once()

    def test_deactivate_stops_transcription(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = True
        app._on_deactivate()

        time.sleep(0.05)
        transcriber.stop.assert_called_once()

    def test_activate_noop_when_already_streaming(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = True
        app._on_activate("push_to_talk")

        time.sleep(0.05)
        transcriber.start.assert_not_called()

    def test_deactivate_noop_when_not_streaming(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = False
        app._on_deactivate()

        time.sleep(0.05)
        transcriber.stop.assert_not_called()

    def test_final_transcript_injects_text(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_final_transcript("Hello world.")

        injector.inject.assert_called_once_with("Hello world.")

    def test_final_transcript_backspaces_partial_first(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._last_partial = "Hello"
        app._on_final_transcript("Hello world.")

        injector.inject_backspaces.assert_called_once_with(5)
        injector.inject.assert_called_once_with("Hello world.")
        assert app._last_partial == ""

    def test_blank_transcript_not_injected(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_final_transcript("   ")

        injector.inject.assert_not_called()

    def test_partial_transcript_inject_raw(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("Hello")
        injector.inject_raw.assert_called_once_with("Hello")
        assert app._last_partial == "Hello"

    def test_partial_transcript_delta_suffix(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("Hello")
        app._on_partial_transcript("Hello world")

        assert injector.inject_raw.call_count == 2
        assert injector.inject_raw.call_args_list[1][0][0] == " world"

    def test_partial_transcript_diverged(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("Hello")
        injector.inject_raw.reset_mock()

        app._on_partial_transcript("Hey there")
        injector.inject_backspaces.assert_called_once_with(5)
        injector.inject_raw.assert_called_once_with("Hey there")

    def test_partial_empty_is_noop(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._on_partial_transcript("")
        injector.inject_raw.assert_not_called()

    def test_sequential_recordings(self, mocker: Any) -> None:
        """Three activate/deactivate cycles must all complete without error."""
        app, transcriber, _, _ = _make_app(mocker)

        for _ in range(3):
            transcriber.is_streaming = False
            app._on_activate("push_to_talk")
            time.sleep(0.05)

            transcriber.is_streaming = True
            app._on_deactivate()
            time.sleep(0.05)

            transcriber.is_streaming = False

        assert transcriber.start.call_count == 3
        assert transcriber.stop.call_count == 3

    def test_transcriber_error_updates_state(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)
        mock_set_state = mocker.patch.object(app.tray, "set_state")

        app._on_transcriber_error(RuntimeError("boom"))

        mock_set_state.assert_called_once_with("error", reason="boom")

    def test_shutdown_stops_hotkey_and_transcriber(self, mocker: Any) -> None:
        app, transcriber, _, hotkey = _make_app(mocker)

        transcriber.is_streaming = True
        app.shutdown()

        transcriber.stop.assert_called_once()
        hotkey.stop.assert_called_once()


class TestClipboardMode:
    """Test copy_to_clipboard hotkey action behaviour."""

    def test_activate_clipboard_sets_flag(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)

        app._on_activate("copy_to_clipboard")
        assert app._clipboard_mode is True

    def test_activate_push_to_talk_clears_flag(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_activate("push_to_talk")
        assert app._clipboard_mode is False

    def test_partial_skipped_in_clipboard_mode(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_partial_transcript("Hello world")

        injector.inject_raw.assert_not_called()
        injector.inject_backspaces.assert_not_called()

    def test_final_copies_to_clipboard(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_final_transcript("Hello world.")

        injector.copy_to_clipboard.assert_called_once_with("Hello world.")
        injector.inject.assert_not_called()

    def test_final_clipboard_resets_flag(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_final_transcript("Hello world.")

        assert app._clipboard_mode is False

    def test_final_blank_in_clipboard_mode_skips_copy(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app._clipboard_mode = True
        app._on_final_transcript("   ")

        injector.copy_to_clipboard.assert_not_called()

    def test_tray_activate_uses_push_to_talk(self, mocker: Any) -> None:
        """Tray left-click always uses push_to_talk, not clipboard mode."""
        app, transcriber, _, _ = _make_app(mocker)

        transcriber.is_streaming = False
        app._on_tray_activate()

        assert app._clipboard_mode is False
