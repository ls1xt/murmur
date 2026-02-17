"""Tests for murmur.errors module."""

from __future__ import annotations

import signal
from typing import Any
from unittest.mock import MagicMock

import pytest

from murmur.errors import fatal, fatal_from_thread


class TestFatal:
    """Test fatal() error exit behavior."""

    def test_exits_with_code_1(self, mocker: Any) -> None:
        mocker.patch("murmur.errors.subprocess.run")
        with pytest.raises(SystemExit, match="1"):
            fatal("test error")

    def test_prints_to_stderr(self, mocker: Any, capsys: Any) -> None:
        mocker.patch("murmur.errors.subprocess.run")
        with pytest.raises(SystemExit):
            fatal("something broke")
        captured = capsys.readouterr()
        assert "murmur: something broke" in captured.err

    def test_calls_notify_send(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.errors.subprocess.run")
        with pytest.raises(SystemExit):
            fatal("notify test")
        mock_run.assert_called_once()
        args: list[str] = mock_run.call_args[0][0]
        assert args[0] == "notify-send"
        assert "--urgency=critical" in args
        assert "Murmur" in args
        assert "notify test" in args

    def test_handles_missing_notify_send(self, mocker: Any) -> None:
        mocker.patch("murmur.errors.subprocess.run", side_effect=FileNotFoundError)
        with pytest.raises(SystemExit, match="1"):
            fatal("no notify-send")

    def test_handles_notify_send_timeout(self, mocker: Any) -> None:
        import subprocess

        mocker.patch(
            "murmur.errors.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="notify-send", timeout=5),
        )
        with pytest.raises(SystemExit, match="1"):
            fatal("timed out")


class TestFatalFromThread:
    """Test fatal_from_thread() behavior for background threads."""

    def test_sends_sigterm(self, mocker: Any) -> None:
        mocker.patch("murmur.errors.subprocess.run")
        mock_kill = mocker.patch("murmur.errors.os.kill")
        fatal_from_thread("thread error")
        mock_kill.assert_called_once_with(mocker.ANY, signal.SIGTERM)

    def test_prints_to_stderr(self, mocker: Any, capsys: Any) -> None:
        mocker.patch("murmur.errors.subprocess.run")
        mocker.patch("murmur.errors.os.kill")
        fatal_from_thread("thread broke")
        captured = capsys.readouterr()
        assert "murmur: thread broke" in captured.err

    def test_calls_notify_send(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.errors.subprocess.run")
        mocker.patch("murmur.errors.os.kill")
        fatal_from_thread("thread notify")
        mock_run.assert_called_once()
        args: list[str] = mock_run.call_args[0][0]
        assert "notify-send" in args[0]


class TestStartupValidation:
    """Test startup exits for missing prerequisites."""

    def test_exits_when_ydotoold_not_running(self, mocker: Any) -> None:
        from murmur.config import DictationConfig

        mocker.patch(
            "murmur.injector.ydotool.shutil.which",
            return_value="/usr/bin/ydotool",
        )
        mock_pgrep = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_pgrep.return_value = MagicMock(returncode=1)  # ydotoold not running

        config = DictationConfig()
        config.transcriber.api_key = "test_key"

        # Mock transcriber to avoid SDK issues
        mocker.patch("murmur.transcriber.assemblyai._v3")
        mocker.patch("murmur.main.create_hotkey_listener")
        mocker.patch("murmur.main.AudioFeedback")

        from murmur.main import DictationApp

        app = DictationApp(config)
        with pytest.raises(SystemExit, match="1"):
            app.run()

    def test_exits_when_api_key_missing(self, mocker: Any) -> None:
        mocker.patch("murmur.errors.subprocess.run")
        mocker.patch.dict("os.environ", {"ASSEMBLYAI_API_KEY": ""}, clear=False)
        mocker.patch("sys.argv", ["murmur"])

        from murmur.config import DictationConfig
        from murmur.main import main

        mock_config = DictationConfig()
        mock_config.transcriber.api_key = ""
        mocker.patch.object(DictationConfig, "load", return_value=mock_config)

        with pytest.raises(SystemExit, match="1"):
            main()
