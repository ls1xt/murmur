"""Tests for murmur.injector module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from murmur.config import InjectorConfig
from murmur.injector.ydotool import YdotoolInjector


def _mock_which(mocker: Any) -> Any:
    """Mock shutil.which to return paths for ydotool and wl-copy."""

    def which_side_effect(name: str) -> str | None:
        paths: dict[str, str] = {
            "ydotool": "/usr/bin/ydotool",
            "wl-copy": "/usr/bin/wl-copy",
        }
        return paths.get(name)

    return mocker.patch(
        "murmur.injector.ydotool.shutil.which",
        side_effect=which_side_effect,
    )


class TestYdotoolInjector:
    """Test YdotoolInjector with mocked subprocess."""

    def test_inject_calls_ydotool(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(trailing_space=True, inject_strategy="ydotool")
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
        _mock_which(mocker)

        injector = YdotoolInjector(trailing_space=False, inject_strategy="ydotool")
        injector.inject("hello")

        args: list[str] = mock_run.call_args[0][0]
        assert "hello" in args
        assert "hello " not in args

    def test_inject_with_key_delay(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(
            key_delay=50, trailing_space=False, inject_strategy="ydotool"
        )
        injector.inject("test")

        args: list[str] = mock_run.call_args[0][0]
        assert "--key-delay" in args
        assert "50" in args

    def test_inject_empty_string_noop(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.inject("")

        mock_run.assert_not_called()

    def test_is_available_true(self, mocker: Any) -> None:
        _mock_which(mocker)
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)

        injector = YdotoolInjector()
        assert injector.is_available() is True

    def test_is_available_false_no_ydotool(self, mocker: Any) -> None:
        mocker.patch("murmur.injector.ydotool.shutil.which", return_value=None)

        injector = YdotoolInjector()
        assert injector.is_available() is False

    def test_is_available_false_no_daemon(self, mocker: Any) -> None:
        _mock_which(mocker)
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=1)

        injector = YdotoolInjector()
        assert injector.is_available() is False


class TestClipboardStrategy:
    """Test clipboard injection strategy."""

    def test_clipboard_strategy_uses_wl_copy(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(inject_strategy="clipboard", trailing_space=False)
        injector.inject("hello world")

        # Should have two calls: wl-copy and ydotool key
        assert mock_run.call_count == 2

        # First call: wl-copy
        wl_copy_args: list[str] = mock_run.call_args_list[0][0][0]
        assert "wl-copy" in wl_copy_args[0]
        assert "hello world" in wl_copy_args

        # Second call: ydotool key (Ctrl+V)
        key_args: list[str] = mock_run.call_args_list[1][0][0]
        assert "key" in key_args
        assert "29:1" in key_args  # Ctrl down
        assert "47:1" in key_args  # V down

    def test_clipboard_strategy_all_text(self, mocker: Any) -> None:
        """Clipboard strategy sends ALL text through clipboard, even ASCII."""
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(inject_strategy="clipboard", trailing_space=False)
        injector.inject("plain ascii")

        # Still uses clipboard for ASCII text
        assert mock_run.call_count == 2
        wl_copy_args: list[str] = mock_run.call_args_list[0][0][0]
        assert "wl-copy" in wl_copy_args[0]

    def test_clipboard_missing_wl_copy_calls_fatal(self, mocker: Any) -> None:
        mocker.patch("murmur.injector.ydotool.subprocess.run")
        mocker.patch("murmur.injector.ydotool.shutil.which", return_value=None)
        mock_fatal = mocker.patch("murmur.errors.fatal")

        injector = YdotoolInjector(inject_strategy="clipboard")
        injector._wl_copy_path = None
        injector._resolved_path = "/usr/bin/ydotool"
        injector.inject("test")

        mock_fatal.assert_called_once()
        call_msg: str = mock_fatal.call_args[0][0]
        assert "wl-copy" in call_msg


class TestClipboardFallbackStrategy:
    """Test clipboard-fallback injection strategy."""

    def test_ascii_uses_ydotool_type(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(
            inject_strategy="clipboard-fallback", trailing_space=False
        )
        injector.inject("hello world")

        # Should only call ydotool type, not wl-copy
        mock_run.assert_called_once()
        args: list[str] = mock_run.call_args[0][0]
        assert "type" in args

    def test_non_ascii_uses_clipboard(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(
            inject_strategy="clipboard-fallback", trailing_space=False
        )
        # Curly quote and em-dash: non-ASCII
        injector.inject("Hello\u2019s world\u2014nice")

        # Should use clipboard path (wl-copy + ydotool key)
        assert mock_run.call_count == 2
        wl_copy_args: list[str] = mock_run.call_args_list[0][0][0]
        assert "wl-copy" in wl_copy_args[0]

    def test_accented_chars_use_clipboard(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(
            inject_strategy="clipboard-fallback", trailing_space=False
        )
        injector.inject("caf\u00e9")

        # non-ASCII -> clipboard
        assert mock_run.call_count == 2
        wl_copy_args: list[str] = mock_run.call_args_list[0][0][0]
        assert "wl-copy" in wl_copy_args[0]


class TestInjectorFactory:
    """Test the injector factory function."""

    def test_unknown_backend_raises(self) -> None:
        from murmur.injector import create_injector

        config = InjectorConfig(backend="nonexistent")
        with pytest.raises(ValueError, match="Unknown injector backend"):
            create_injector(config)

    def test_ydotool_backend(self, mocker: Any) -> None:
        from murmur.injector import create_injector

        _mock_which(mocker)
        config = InjectorConfig(backend="ydotool")
        injector = create_injector(config)
        assert isinstance(injector, YdotoolInjector)

    def test_factory_passes_inject_strategy(self, mocker: Any) -> None:
        from murmur.injector import create_injector

        _mock_which(mocker)
        config = InjectorConfig(backend="ydotool", inject_strategy="clipboard")
        injector = create_injector(config)
        assert isinstance(injector, YdotoolInjector)
        assert injector._inject_strategy == "clipboard"
