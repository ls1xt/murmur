"""Tests for the Notifier desktop notification module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from murmur.feedback.notify import Notifier


class TestNotifierError:
    """Test error notification behavior."""

    @patch("murmur.feedback.notify.subprocess.run")
    def test_error_sends_critical_notification(self, mock_run: Any) -> None:
        notifier = Notifier(level="errors")
        notifier.error("ydotoold not running")
        assert mock_run.call_count == 1
        cmd: list[str] = mock_run.call_args[0][0]
        assert "--urgency=critical" in cmd
        assert "Murmur" in cmd
        assert "ydotoold not running" in cmd

    @patch("murmur.feedback.notify.subprocess.run")
    def test_error_suppressed_when_off(self, mock_run: Any) -> None:
        notifier = Notifier(level="off")
        notifier.error("some error")
        assert isinstance(mock_run, MagicMock)
        mock_run.assert_not_called()

    @patch("murmur.feedback.notify.subprocess.run")
    def test_error_sends_when_verbose(self, mock_run: Any) -> None:
        notifier = Notifier(level="verbose")
        notifier.error("critical error")
        assert mock_run.call_count == 1


class TestNotifierInfo:
    """Test informational notification behavior."""

    @patch("murmur.feedback.notify.subprocess.run")
    def test_info_sends_when_verbose(self, mock_run: Any) -> None:
        notifier = Notifier(level="verbose")
        notifier.info("Recording started")
        assert mock_run.call_count == 1
        cmd: list[str] = mock_run.call_args[0][0]
        assert "--urgency=normal" in cmd

    @patch("murmur.feedback.notify.subprocess.run")
    def test_info_suppressed_when_errors(self, mock_run: Any) -> None:
        notifier = Notifier(level="errors")
        notifier.info("Recording started")
        assert isinstance(mock_run, MagicMock)
        mock_run.assert_not_called()

    @patch("murmur.feedback.notify.subprocess.run")
    def test_info_suppressed_when_off(self, mock_run: Any) -> None:
        notifier = Notifier(level="off")
        notifier.info("Recording started")
        assert isinstance(mock_run, MagicMock)
        mock_run.assert_not_called()

    @patch("murmur.feedback.notify.subprocess.run")
    def test_expire_time_on_info(self, mock_run: Any) -> None:
        notifier = Notifier(level="verbose")
        notifier.info("Murmur started")
        cmd: list[str] = mock_run.call_args[0][0]
        assert "--expire-time=5000" in cmd


class TestNotifierResilience:
    """Test graceful handling of missing notify-send."""

    @patch(
        "murmur.feedback.notify.subprocess.run",
        side_effect=FileNotFoundError("notify-send not found"),
    )
    def test_missing_notify_send_no_crash(self, mock_run: Any) -> None:
        notifier = Notifier(level="errors")
        # Should not raise
        notifier.error("test error")
