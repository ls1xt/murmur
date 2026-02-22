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


@pytest.mark.linux_only
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


@pytest.mark.linux_only
class TestInjectRawAndBackspaces:
    """Test inject_raw and inject_backspaces methods."""

    def test_inject_raw_calls_ydotool(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.inject_raw("hello")

        mock_run.assert_called_once()
        args: list[str] = mock_run.call_args[0][0]
        assert "ydotool" in args[0]
        assert "type" in args
        assert "--clearmodifiers" in args
        assert "hello" in args

    def test_inject_raw_no_trailing_space(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(trailing_space=True)
        injector.inject_raw("hello")

        args: list[str] = mock_run.call_args[0][0]
        # inject_raw should NOT add trailing space
        assert "hello" in args
        assert "hello " not in args

    def test_inject_raw_empty_noop(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.inject_raw("")

        mock_run.assert_not_called()

    def test_inject_backspaces_calls_ydotool_key(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.inject_backspaces(3)

        mock_run.assert_called_once()
        args: list[str] = mock_run.call_args[0][0]
        assert "key" in args
        # 3 backspaces = 3 pairs of 14:1/14:0
        assert args.count("14:1") == 3
        assert args.count("14:0") == 3

    def test_inject_backspaces_zero_noop(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.inject_backspaces(0)

        mock_run.assert_not_called()

    def test_inject_backspaces_negative_noop(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.inject_backspaces(-1)

        mock_run.assert_not_called()


@pytest.mark.linux_only
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


@pytest.mark.linux_only
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


@pytest.mark.linux_only
class TestInjectRawStrategyRouting:
    """Test that inject_raw routes through the configured strategy."""

    def test_inject_raw_non_ascii_uses_clipboard_in_fallback(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(inject_strategy="clipboard-fallback")
        injector.inject_raw("café")  # non-ASCII

        # Should use clipboard: wl-copy + ydotool key
        assert mock_run.call_count == 2
        wl_copy_args: list[str] = mock_run.call_args_list[0][0][0]
        assert "wl-copy" in wl_copy_args[0]
        assert "café" in wl_copy_args

    def test_inject_raw_clipboard_strategy_always_uses_clipboard(
        self, mocker: Any
    ) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(inject_strategy="clipboard")
        injector.inject_raw("hello")  # ASCII

        # Clipboard strategy: always wl-copy + ydotool key
        assert mock_run.call_count == 2
        wl_copy_args: list[str] = mock_run.call_args_list[0][0][0]
        assert "wl-copy" in wl_copy_args[0]


class TestSanitizeText:
    """Test _sanitize_text strips control characters."""

    def test_clean_text_unchanged(self) -> None:
        from murmur.injector.ydotool import _sanitize_text

        assert _sanitize_text("Hello, world!") == "Hello, world!"

    def test_newline_stripped(self) -> None:
        from murmur.injector.ydotool import _sanitize_text

        assert _sanitize_text("hello\nworld") == "helloworld"

    def test_carriage_return_stripped(self) -> None:
        from murmur.injector.ydotool import _sanitize_text

        assert _sanitize_text("hello\r\nworld") == "helloworld"

    def test_tab_stripped(self) -> None:
        from murmur.injector.ydotool import _sanitize_text

        assert _sanitize_text("hello\tworld") == "helloworld"

    def test_null_byte_stripped(self) -> None:
        from murmur.injector.ydotool import _sanitize_text

        assert _sanitize_text("hel\x00lo") == "hello"

    def test_spaces_preserved(self) -> None:
        from murmur.injector.ydotool import _sanitize_text

        assert _sanitize_text("hello world") == "hello world"

    def test_unicode_letters_preserved(self) -> None:
        from murmur.injector.ydotool import _sanitize_text

        assert _sanitize_text("café résumé") == "café résumé"

    def test_inject_strips_control_chars(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector(inject_strategy="ydotool", trailing_space=False)
        injector.inject("hello\nworld")  # newline should be stripped

        args: list[str] = mock_run.call_args[0][0]
        injected_text = args[-1]
        assert "\n" not in injected_text
        assert injected_text == "helloworld"


@pytest.mark.linux_only
class TestCopyToClipboard:
    """Test copy_to_clipboard method."""

    def test_copy_to_clipboard_calls_wl_copy(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.copy_to_clipboard("Hello world")

        mock_run.assert_called_once()
        args: list[str] = mock_run.call_args[0][0]
        assert "wl-copy" in args[0]
        assert "Hello world" in args

    def test_copy_to_clipboard_no_inject(self, mocker: Any) -> None:
        """copy_to_clipboard must NOT simulate a Ctrl+V paste."""
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        mock_run.return_value = MagicMock(returncode=0)
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.copy_to_clipboard("Hello world")

        # Only one call: wl-copy (no ydotool key for Ctrl+V)
        assert mock_run.call_count == 1

    def test_copy_to_clipboard_empty_noop(self, mocker: Any) -> None:
        mock_run = mocker.patch("murmur.injector.ydotool.subprocess.run")
        _mock_which(mocker)

        injector = YdotoolInjector()
        injector.copy_to_clipboard("")

        mock_run.assert_not_called()

    def test_copy_to_clipboard_no_wl_copy_logs_error(self, mocker: Any) -> None:
        mocker.patch("murmur.injector.ydotool.shutil.which", return_value=None)
        mock_log = mocker.patch("murmur.injector.ydotool.logger")

        injector = YdotoolInjector()
        injector.copy_to_clipboard("hello")

        mock_log.error.assert_called_once()


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
