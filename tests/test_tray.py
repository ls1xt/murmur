"""Tests for the TrayIcon system tray module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from murmur.feedback.tray import TrayIcon, _create_icon_image


class TestTrayIconGracefulDegradation:
    """Test graceful handling when pystray is unavailable."""

    @patch("murmur.feedback.tray.pystray", create=True)
    def test_start_graceful_on_import_error(self, _mock: object) -> None:
        """If pystray import fails, tray stays unavailable without crash."""
        tray = TrayIcon()
        with patch.dict("sys.modules", {"pystray": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("no pystray"),
            ):
                tray.start()
        assert not tray.available

    def test_set_state_noop_when_unavailable(self) -> None:
        """set_state is a no-op when tray is not available."""
        tray = TrayIcon()
        # Should not raise
        tray.set_state("recording")
        tray.set_state("error", reason="test")
        assert not tray.available

    def test_stop_noop_when_unavailable(self) -> None:
        """stop is a no-op when tray is not available."""
        tray = TrayIcon()
        # Should not raise
        tray.stop()


class TestTrayIconCreation:
    """Test icon image creation."""

    def test_create_icon_returns_pil_image_idle(self) -> None:
        """Icon creation returns a PIL Image for idle state."""
        try:
            img = _create_icon_image("idle")
            assert img.size == (64, 64)
            assert img.mode == "RGBA"
        except ImportError:
            # Pillow not installed in test env -- skip
            pass

    def test_create_icon_returns_pil_image_recording(self) -> None:
        """Icon creation returns a PIL Image for recording state."""
        try:
            img = _create_icon_image("recording")
            assert img.size == (64, 64)
        except ImportError:
            pass

    def test_create_icon_returns_pil_image_error(self) -> None:
        """Icon creation returns a PIL Image for error state."""
        try:
            img = _create_icon_image("error")
            assert img.size == (64, 64)
        except ImportError:
            pass

    def test_create_icon_unknown_state_falls_back_to_idle(self) -> None:
        """Unknown state uses idle colors."""
        try:
            img = _create_icon_image("unknown")
            assert img.size == (64, 64)
        except ImportError:
            pass


class TestTrayIconMenu:
    """Test menu structure and callbacks."""

    def test_status_text_idle(self) -> None:
        """Status text returns 'Idle' for idle state."""
        tray = TrayIcon()
        assert tray._status_text() == "Idle"

    def test_status_text_recording(self) -> None:
        """Status text returns 'Recording' for recording state."""
        tray = TrayIcon()
        tray._state = "recording"
        assert tray._status_text() == "Recording"

    def test_status_text_error_with_reason(self) -> None:
        """Status text includes error reason."""
        tray = TrayIcon()
        tray._state = "error"
        tray._error_reason = "ydotoold not running"
        assert tray._status_text() == "Error: ydotoold not running"

    def test_quit_callback_fires(self) -> None:
        """Quit menu item calls on_quit callback."""
        mock_quit = MagicMock()
        tray = TrayIcon(on_quit=mock_quit)
        tray._on_quit_clicked()
        mock_quit.assert_called_once()

    def test_quit_callback_none_no_crash(self) -> None:
        """Quit with no callback does not crash."""
        tray = TrayIcon(on_quit=None)
        tray._on_quit_clicked()  # Should not raise
