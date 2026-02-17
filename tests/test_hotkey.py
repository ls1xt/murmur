"""Tests for murmur.hotkey module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from murmur.hotkey.base import HotkeyListener


class TestHotkeyListenerBase:
    """Test the HotkeyListener ABC mode logic."""

    def _make_listener(self, mode: str = "push_to_talk") -> HotkeyListener:
        """Create a concrete HotkeyListener subclass for testing."""

        class StubListener(HotkeyListener):
            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

        return StubListener(mode=mode)

    def test_push_to_talk_activate_on_press(self) -> None:
        listener = self._make_listener("push_to_talk")
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        listener._handle_hotkey_press()
        on_activate.assert_called_once()
        on_deactivate.assert_not_called()

    def test_push_to_talk_deactivate_on_release(self) -> None:
        listener = self._make_listener("push_to_talk")
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        listener._handle_hotkey_release()
        on_deactivate.assert_called_once()
        on_activate.assert_not_called()

    def test_toggle_mode_alternates(self) -> None:
        listener = self._make_listener("toggle")
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        # First press -> activate
        listener._handle_hotkey_press()
        assert on_activate.call_count == 1
        assert on_deactivate.call_count == 0

        # Second press -> deactivate
        listener._handle_hotkey_press()
        assert on_activate.call_count == 1
        assert on_deactivate.call_count == 1

        # Third press -> activate again
        listener._handle_hotkey_press()
        assert on_activate.call_count == 2
        assert on_deactivate.call_count == 1

    def test_toggle_mode_release_is_noop(self) -> None:
        listener = self._make_listener("toggle")
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        listener._handle_hotkey_release()
        on_activate.assert_not_called()
        on_deactivate.assert_not_called()

    def test_no_callbacks_does_not_crash(self) -> None:
        listener = self._make_listener("push_to_talk")
        # No callbacks set -- should not raise
        listener._handle_hotkey_press()
        listener._handle_hotkey_release()


class TestEvdevHotkeyListener:
    """Test EvdevHotkeyListener with mocked evdev."""

    def test_push_to_talk_activates_on_combo(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener, _ecodes_dict

        on_activate = MagicMock()
        on_deactivate = MagicMock()

        listener = EvdevHotkeyListener(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
            trigger="KEY_SPACE",
            mode="push_to_talk",
        )
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        # Pre-set modifiers as held
        ctrl_code: int = _ecodes_dict["KEY_LEFTCTRL"]
        shift_code: int = _ecodes_dict["KEY_LEFTSHIFT"]
        space_code: int = _ecodes_dict["KEY_SPACE"]

        listener._held_keys.add(ctrl_code)
        listener._held_keys.add(shift_code)

        # Simulate space down (keystate=1)
        event = MagicMock()
        event.code = space_code
        key_event = MagicMock()
        key_event.keystate = 1
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_event)

        listener._handle_key_event(event)
        on_activate.assert_called_once()

    def test_push_to_talk_deactivates_on_release(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener, _ecodes_dict

        on_activate = MagicMock()
        on_deactivate = MagicMock()

        listener = EvdevHotkeyListener(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
            trigger="KEY_SPACE",
            mode="push_to_talk",
        )
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        space_code: int = _ecodes_dict["KEY_SPACE"]

        # Simulate space up (keystate=0)
        event = MagicMock()
        event.code = space_code
        key_event = MagicMock()
        key_event.keystate = 0
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_event)

        listener._handle_key_event(event)
        on_deactivate.assert_called_once()

    def test_trigger_without_modifiers_no_activate(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener, _ecodes_dict

        on_activate = MagicMock()

        listener = EvdevHotkeyListener(
            modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
            trigger="KEY_SPACE",
            mode="push_to_talk",
        )
        listener.set_callbacks(on_activate=on_activate, on_deactivate=MagicMock())

        space_code: int = _ecodes_dict["KEY_SPACE"]

        # Simulate space down without modifiers
        event = MagicMock()
        event.code = space_code
        key_event = MagicMock()
        key_event.keystate = 1
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_event)

        listener._handle_key_event(event)
        on_activate.assert_not_called()

    def test_invalid_key_name_raises(self) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener

        with pytest.raises(ValueError, match="Unknown evdev key name"):
            EvdevHotkeyListener(
                modifiers=["KEY_NONEXISTENT"],
                trigger="KEY_SPACE",
            )

    def test_invalid_trigger_name_raises(self) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener

        with pytest.raises(ValueError, match="Unknown evdev key name"):
            EvdevHotkeyListener(
                modifiers=["KEY_LEFTCTRL"],
                trigger="KEY_BOGUS",
            )

    def test_find_keyboard_devices(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import _EV_KEY, _KEY_A, _KEY_Z, find_keyboard_devices

        mock_dev = MagicMock()
        mock_dev.name = "Test Keyboard"
        mock_dev.capabilities.return_value = {
            _EV_KEY: [_KEY_A, _KEY_Z, 1, 2, 3],
        }
        mock_dev.close = MagicMock()

        mocker.patch(
            "murmur.hotkey.evdev._list_devices",
            return_value=["/dev/input/event0"],
        )
        mocker.patch(
            "murmur.hotkey.evdev._open_device",
            return_value=mock_dev,
        )

        result = find_keyboard_devices()
        assert result == ["/dev/input/event0"]
        mock_dev.close.assert_called_once()

    @pytest.mark.hardware()
    def test_real_keyboard_detection(self) -> None:
        """Integration test: detect real keyboard (requires hardware)."""
        from murmur.hotkey.evdev import find_keyboard_devices

        devices = find_keyboard_devices()
        assert len(devices) > 0, "No keyboard devices detected"
