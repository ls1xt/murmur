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

from murmur.app import DictationApp
from murmur.config import DictationConfig, FeedbackConfig, HotkeyBinding, TrayConfig
from murmur.main import main


def _make_app(mocker: Any) -> tuple[DictationApp, MagicMock, MagicMock, MagicMock]:
    """Build a DictationApp with all hardware backends mocked out.

    Returns (app, mock_transcriber, mock_injector, mock_hotkey).
    """
    config = DictationConfig()
    config.transcriber.api_key = "fake_key"
    config.transcriber.inject_partials = True  # enable partial injection for tests
    config.feedback = FeedbackConfig(audio_enabled=False)
    config.tray = TrayConfig(enabled=False)
    config.hotkey.push_to_talk_debounce_ms = 0  # disable debounce in tests

    mock_transcriber = MagicMock()
    mock_transcriber.is_streaming = False
    mock_injector = MagicMock()
    mock_injector.is_available.return_value = True
    mock_hotkey = MagicMock()

    mocker.patch("murmur.app.create_transcriber", return_value=mock_transcriber)
    mocker.patch("murmur.app.create_injector", return_value=mock_injector)
    mocker.patch("murmur.app.create_hotkey_listener", return_value=mock_hotkey)

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
        mocker.patch("murmur.config.DictationConfig.load", return_value=config)
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
        mocker.patch("murmur.config.DictationConfig.load", return_value=config)
        _run_main(["config", "--key", "transcriber.api_key"], mocker)
        main()
        captured = capsys.readouterr()
        assert "my_test_key" in captured.out

    def test_config_set_key(self, mocker: Any, capsys: Any) -> None:
        """murmur config --key K --value V saves config and prints confirmation."""
        config = DictationConfig()
        mocker.patch("murmur.config.DictationConfig.load", return_value=config)
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
        mocker.patch("murmur.config.DictationConfig.load", return_value=config)
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
        mocker.patch("murmur.config.DictationConfig.load", return_value=config)
        mocker.patch("murmur.app.create_transcriber", return_value=MagicMock())
        mocker.patch("murmur.app.create_injector", return_value=MagicMock())
        mocker.patch("murmur.app.create_hotkey_listener", return_value=MagicMock())
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
        mocker.patch("murmur.config.DictationConfig.load", return_value=config)
        mocker.patch("murmur.app.create_transcriber", return_value=MagicMock())
        mocker.patch("murmur.app.create_injector", return_value=MagicMock())
        mocker.patch("murmur.app.create_hotkey_listener", return_value=MagicMock())
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
        mocker.patch("subprocess.run", return_value=mock_result)
        _run_main(["daemon", "status"], mocker)
        main()
        captured = capsys.readouterr()
        assert "not running" in captured.out.lower()

    def test_daemon_status_running(self, mocker: Any, capsys: Any) -> None:
        """murmur daemon status prints PID when daemon is found."""
        mock_result = MagicMock()
        mock_result.stdout = "12345\n"
        mocker.patch("subprocess.run", return_value=mock_result)
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
        mocker.patch("murmur.config.DictationConfig.load", return_value=config)
        mocker.patch("murmur.app.create_transcriber", return_value=MagicMock())
        mocker.patch("murmur.app.create_injector", return_value=MagicMock())
        mocker.patch("murmur.app.create_hotkey_listener", return_value=MagicMock())
        mock_run = mocker.patch.object(DictationApp, "run")
        _run_main(["daemon", "start"], mocker)
        main()
        mock_run.assert_called_once()


# ─── DictationApp lifecycle ───────────────────────────────────────────────────


class TestDictationAppLifecycle:
    def test_activate_starts_transcription(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        app.on_activate(HotkeyBinding(mode="push_to_talk"))

        time.sleep(0.05)
        transcriber.start.assert_called_once()

    def test_deactivate_stops_transcription(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        app.recording_active = True
        transcriber.is_streaming = True
        app.on_deactivate()  # private callback, keep as-is

        time.sleep(0.05)
        transcriber.stop.assert_called_once()

    def test_activate_noop_when_already_recording(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        # Simulate recording already active
        app.recording_active = True
        app.on_activate(HotkeyBinding(mode="push_to_talk"))

        time.sleep(0.05)
        transcriber.start.assert_not_called()

    def test_deactivate_noop_when_not_recording(self, mocker: Any) -> None:
        app, transcriber, _, _ = _make_app(mocker)

        # _recording_active starts False
        app.on_deactivate()

        time.sleep(0.05)
        transcriber.stop.assert_not_called()

    def test_final_transcript_injects_text(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.on_final_transcript("Hello world.")

        injector.inject.assert_called_once_with("Hello world.")

    def test_final_transcript_backspaces_partial_first(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.last_partial = "Hello"
        app.on_final_transcript("Hello world.")

        injector.inject_backspaces.assert_called_once_with(5)
        injector.inject.assert_called_once_with("Hello world.")
        assert app.last_partial == ""

    def test_blank_transcript_not_injected(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.on_final_transcript("   ")

        injector.inject.assert_not_called()

    def test_partial_transcript_inject_raw(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.on_partial_transcript("Hello")
        injector.inject_raw.assert_called_once_with("Hello")
        assert app.last_partial == "Hello"

    def test_partial_transcript_delta_suffix(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.on_partial_transcript("Hello")
        app.on_partial_transcript("Hello world")

        assert injector.inject_raw.call_count == 2
        assert injector.inject_raw.call_args_list[1][0][0] == " world"

    def test_partial_transcript_diverged(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.on_partial_transcript("Hello")
        injector.inject_raw.reset_mock()

        app.on_partial_transcript("Hey there")
        injector.inject_backspaces.assert_called_once_with(5)
        injector.inject_raw.assert_called_once_with("Hey there")

    def test_partial_empty_is_noop(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.on_partial_transcript("")
        injector.inject_raw.assert_not_called()

    def test_sequential_recordings(self, mocker: Any) -> None:
        """Three activate/deactivate cycles must all complete without error."""
        app, transcriber, _, _ = _make_app(mocker)

        for _ in range(3):
            app.recording_active = False
            app.on_activate(HotkeyBinding(mode="push_to_talk"))
            time.sleep(0.05)

            app.recording_active = True
            app.on_deactivate()
            time.sleep(0.05)

            transcriber.is_streaming = False

        assert transcriber.start.call_count == 3
        assert transcriber.stop.call_count == 3

    def test_transcriber_error_updates_state(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)
        mock_set_state = mocker.patch.object(app.tray, "set_state")

        app.on_transcriber_error(RuntimeError("boom"))

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

        app.on_activate(HotkeyBinding(mode="push_to_talk", destination="clipboard"))
        assert app.clipboard_mode is True

    def test_activate_push_to_talk_clears_flag(self, mocker: Any) -> None:
        app, _, _, _ = _make_app(mocker)

        app.clipboard_mode = True
        app.recording_active = False
        app.on_activate(HotkeyBinding(mode="push_to_talk"))
        assert app.clipboard_mode is False

    def test_partial_skipped_in_clipboard_mode(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.clipboard_mode = True
        app.on_partial_transcript("Hello world")

        injector.inject_raw.assert_not_called()
        injector.inject_backspaces.assert_not_called()

    def test_final_buffers_in_clipboard_mode(self, mocker: Any) -> None:
        """In clipboard mode, _on_final_transcript buffers text, not injects."""
        app, _, injector, _ = _make_app(mocker)

        app.clipboard_mode = True
        app.on_final_transcript("Hello world.")

        # Text is buffered, not injected or copied to clipboard directly
        assert "Hello world." in app.clipboard_buffer
        injector.inject.assert_not_called()
        injector.copy_to_clipboard.assert_not_called()

    def test_final_blank_in_clipboard_mode_skips_buffer(self, mocker: Any) -> None:
        app, _, injector, _ = _make_app(mocker)

        app.clipboard_mode = True
        app.on_final_transcript("   ")

        assert len(app.clipboard_buffer) == 0
        injector.copy_to_clipboard.assert_not_called()

    def test_tray_activate_uses_push_to_talk(self, mocker: Any) -> None:
        """Tray left-click always uses push_to_talk, not clipboard mode."""
        app, _transcriber, _, _ = _make_app(mocker)

        app.recording_active = False
        app.on_tray_activate()

        assert app.clipboard_mode is False


class TestAppendEnter:
    """Test append_enter binding option."""

    def test_append_enter_calls_inject_return(self, mocker: Any) -> None:
        """When binding.append_enter=True, inject_return is called after transcription."""
        app, transcriber, injector, _ = _make_app(mocker)

        binding = HotkeyBinding(mode="push_to_talk", append_enter=True)
        app.on_activate(binding)
        time.sleep(0.05)

        # Manually set active binding state as activate would have done
        app.active_binding = binding
        app.active_injector = injector

        # Simulate stop and deliver
        app.clipboard_mode = False
        transcriber.stop.return_value = None
        app.stop_and_deliver()

        injector.inject_return.assert_called_once()

    def test_no_append_enter_does_not_call_inject_return(self, mocker: Any) -> None:
        """When binding.append_enter=False, inject_return is not called."""
        app, transcriber, injector, _ = _make_app(mocker)

        binding = HotkeyBinding(mode="push_to_talk", append_enter=False)
        app.active_binding = binding
        app.active_injector = injector
        app.clipboard_mode = False
        transcriber.stop.return_value = None
        app.stop_and_deliver()

        injector.inject_return.assert_not_called()


class TestConfigReload:
    """Test config hot-reload on activation."""

    def test_maybe_reload_config_no_change(self, mocker: Any) -> None:
        """No reload when mtime has not changed."""
        app, _, _, _ = _make_app(mocker)

        # stat returns same mtime — no reload expected
        mock_stat = MagicMock()
        mock_stat.st_mtime = app.config_mtime
        mocker.patch("pathlib.Path.stat", return_value=mock_stat)

        mock_load = mocker.patch.object(DictationConfig, "load")
        app.maybe_reload_config()

        mock_load.assert_not_called()

    def test_maybe_reload_config_oserror_skips(self, mocker: Any) -> None:
        """OSError when stat-ing config file is silently ignored."""
        app, _, _, _ = _make_app(mocker)

        mocker.patch("pathlib.Path.stat", side_effect=OSError("no file"))
        mock_load = mocker.patch.object(DictationConfig, "load")
        app.maybe_reload_config()

        mock_load.assert_not_called()

    def test_maybe_reload_config_load_failure_logs_warning(self, mocker: Any) -> None:
        """Failed config reload logs a warning and does not crash."""
        app, _, _, _ = _make_app(mocker)

        # Simulate mtime change
        mock_stat = MagicMock()
        mock_stat.st_mtime = app.config_mtime + 1.0
        mocker.patch("pathlib.Path.stat", return_value=mock_stat)
        mocker.patch.object(DictationConfig, "load", side_effect=ValueError("bad json"))

        mock_logger = mocker.patch("murmur.app.logger")
        app.maybe_reload_config()

        mock_logger.warning.assert_called_once()
