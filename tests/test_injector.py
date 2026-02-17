"""Tests for murmur.injector module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from murmur.config import InjectorConfig
from murmur.injector.ydotool import YdotoolInjector


class TestYdotoolInjector:
    """Test YdotoolInjector with mocked subprocess."""

    def test_inject_calls_ydotool(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        mocker.patch(
            "murmur.injector.ydotool.shutil.which", return_value="/usr/bin/ydotool"
        )

        injector = YdotoolInjector(trailing_space=True)
        injector.inject("hello")

        mock_run.assert_called_once()
        args: list[str] = mock_run.call_args[0][0]
        assert "ydotool" in args[0]
        assert "type" in args
        assert "--clearmodifiers" in args
        assert "hello " in args  # trailing space

    def test_inject_without_trailing_space(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        mocker.patch(
            "murmur.injector.ydotool.shutil.which", return_value="/usr/bin/ydotool"
        )

        injector = YdotoolInjector(trailing_space=False)
        injector.inject("hello")

        args: list[str] = mock_run.call_args[0][0]
        assert "hello" in args
        assert "hello " not in args

    def test_inject_with_key_delay(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        mocker.patch(
            "murmur.injector.ydotool.shutil.which", return_value="/usr/bin/ydotool"
        )

        injector = YdotoolInjector(key_delay=50, trailing_space=False)
        injector.inject("test")

        args: list[str] = mock_run.call_args[0][0]
        assert "--key-delay" in args
        assert "50" in args

    def test_inject_empty_string_noop(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mocker.patch(
            "murmur.injector.ydotool.shutil.which", return_value="/usr/bin/ydotool"
        )

        injector = YdotoolInjector()
        injector.inject("")

        mock_run.assert_not_called()

    def test_is_available_true(self, mocker: Any) -> None:
        mocker.patch(
            "murmur.injector.ydotool.shutil.which", return_value="/usr/bin/ydotool"
        )
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        injector = YdotoolInjector()
        assert injector.is_available() is True

    def test_is_available_false_no_ydotool(self, mocker: Any) -> None:
        mocker.patch("murmur.injector.ydotool.shutil.which", return_value=None)

        injector = YdotoolInjector()
        assert injector.is_available() is False

    def test_is_available_false_no_daemon(self, mocker: Any) -> None:
        mocker.patch(
            "murmur.injector.ydotool.shutil.which", return_value="/usr/bin/ydotool"
        )
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=1)

        injector = YdotoolInjector()
        assert injector.is_available() is False


class TestInjectorFactory:
    """Test the injector factory function."""

    def test_unknown_backend_raises(self) -> None:
        from murmur.injector import create_injector

        config = InjectorConfig(backend="nonexistent")
        with pytest.raises(ValueError, match="Unknown injector backend"):
            create_injector(config)

    def test_ydotool_backend(self, mocker: Any) -> None:
        from murmur.injector import create_injector

        mocker.patch(
            "murmur.injector.ydotool.shutil.which", return_value="/usr/bin/ydotool"
        )
        config = InjectorConfig(backend="ydotool")
        injector = create_injector(config)
        assert isinstance(injector, YdotoolInjector)
