"""Tests for the TrayIcon system tray module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from murmur.feedback.tray import TrayIcon, create_icon_image
from murmur.feedback.tray_pystray import PystrayTray


class TestTrayIconGracefulDegradation:
    """Test graceful handling when pystray is unavailable."""

    @patch("murmur.feedback.tray.TrayIcon.is_sway", return_value=False)
    def test_start_graceful_on_import_error(self, _mock_sway: object) -> None:
        """If pystray backend raises, tray stays unavailable without crash."""
        tray = TrayIcon()
        with patch("murmur.feedback.tray_pystray.PystrayTray") as MockPystray:
            MockPystray.side_effect = Exception("no pystray")
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
            img = create_icon_image("idle")
            assert img.size == (64, 64)
            assert img.mode == "RGBA"
        except ImportError:
            # Pillow not installed in test env -- skip
            pass

    def test_create_icon_returns_pil_image_recording(self) -> None:
        """Icon creation returns a PIL Image for recording state."""
        try:
            img = create_icon_image("recording")
            assert img.size == (64, 64)
        except ImportError:
            pass

    def test_create_icon_returns_pil_image_error(self) -> None:
        """Icon creation returns a PIL Image for error state."""
        try:
            img = create_icon_image("error")
            assert img.size == (64, 64)
        except ImportError:
            pass

    def test_create_icon_unknown_state_falls_back_to_idle(self) -> None:
        """Unknown state uses idle colors."""
        try:
            img = create_icon_image("unknown")  # type: ignore[arg-type]
            assert img.size == (64, 64)
        except ImportError:
            pass


class TestTrayIconMenu:
    """Test menu structure and callbacks."""

    def test_status_text_idle(self) -> None:
        """Status text returns 'Idle' for idle state."""
        tray = PystrayTray()
        assert tray.status_text() == "Idle"

    def test_status_text_recording(self) -> None:
        """Status text returns 'Recording' for recording state."""
        tray = PystrayTray()
        tray.state = "recording"
        assert tray.status_text() == "Recording"

    def test_status_text_error_with_reason(self) -> None:
        """Status text includes error reason."""
        tray = PystrayTray()
        tray.state = "error"
        tray.error_reason = "ydotoold not running"
        assert tray.status_text() == "Error: ydotoold not running"

    def test_quit_callback_fires(self) -> None:
        """Quit menu item calls on_quit callback."""
        mock_quit = MagicMock()
        tray = PystrayTray(on_quit=mock_quit)
        tray.on_quit_clicked()
        mock_quit.assert_called_once()

    def test_quit_callback_none_no_crash(self) -> None:
        """Quit with no callback does not crash."""
        tray = PystrayTray(on_quit=None)
        tray.on_quit_clicked()  # Should not raise


class TestTrayIconSniDetection:
    """Test SNI/Sway detection."""

    def test_is_sway_with_swaysock(self) -> None:
        """is_sway returns True when SWAYSOCK is set."""
        with patch.dict("os.environ", {"SWAYSOCK": "/run/user/1000/sway"}):
            assert TrayIcon.is_sway() is True

    def test_is_sway_without_swaysock(self) -> None:
        """is_sway returns False when SWAYSOCK is not set."""
        with patch.dict("os.environ", {}, clear=True):
            assert TrayIcon.is_sway() is False

    @patch("murmur.feedback.tray.TrayIcon.is_sway", return_value=True)
    def test_sway_routes_to_sni(self, _mock: object) -> None:
        """On Sway, start() calls _start_sni instead of pystray."""
        tray = TrayIcon()
        with patch.object(tray, "_start_sni") as mock_sni:
            tray.start()
            mock_sni.assert_called_once()

    def test_sni_set_state_delegates(self) -> None:
        """set_state delegates to backend when available."""
        tray = TrayIcon()
        tray.available = True
        mock_backend = MagicMock()
        tray.backend = mock_backend

        tray.set_state("recording")
        mock_backend.set_state.assert_called_once_with("recording", "")

    def test_sni_stop_delegates(self) -> None:
        """stop delegates to backend."""
        tray = TrayIcon()
        mock_backend = MagicMock()
        tray.backend = mock_backend

        tray.stop()
        mock_backend.stop.assert_called_once()
