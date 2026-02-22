"""Tests for murmur.hotkey module."""

from __future__ import annotations

import time
from typing import Any, Literal
from unittest.mock import MagicMock

import pytest

from murmur.config import HotkeyBinding
from murmur.hotkey.base import HotkeyListener


class TestHotkeyListenerBase:
    """Test the HotkeyListener ABC action-based dispatch."""

    def _make_listener(self) -> HotkeyListener:
        """Create a concrete HotkeyListener subclass for testing."""

        class StubListener(HotkeyListener):
            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

        return StubListener()

    def _binding(self, action: Literal["push_to_talk", "toggle", "copy_to_clipboard"]) -> HotkeyBinding:
        """Create a HotkeyBinding with the given action for dispatch tests."""
        return HotkeyBinding(
            modifiers=["KEY_LEFTCTRL"],
            trigger="KEY_SPACE",
            action=action,
        )

    def test_push_to_talk_activate_on_dispatch(self) -> None:
        listener = self._make_listener()
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        binding = self._binding("push_to_talk")
        listener.dispatch_action(binding)
        on_activate.assert_called_once_with(binding)
        on_deactivate.assert_not_called()

    def test_push_to_talk_deactivate_on_release(self) -> None:
        listener = self._make_listener()
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        binding = self._binding("push_to_talk")
        listener.dispatch_release(binding)
        on_deactivate.assert_called_once()
        on_activate.assert_not_called()

    def test_toggle_activates(self) -> None:
        listener = self._make_listener()
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        binding = self._binding("toggle")
        listener.dispatch_action(binding)
        on_activate.assert_called_once_with(binding)
        on_deactivate.assert_not_called()

    def test_toggle_release_is_noop(self) -> None:
        listener = self._make_listener()
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        binding = self._binding("toggle")
        listener.dispatch_release(binding)
        on_activate.assert_not_called()
        on_deactivate.assert_not_called()

    def test_no_callbacks_does_not_crash(self) -> None:
        listener = self._make_listener()
        # No callbacks set -- should not raise
        binding = self._binding("push_to_talk")
        listener.dispatch_action(binding)
        listener.dispatch_release(binding)

    def test_copy_to_clipboard_activate_on_dispatch(self) -> None:
        listener = self._make_listener()
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        binding = self._binding("copy_to_clipboard")
        listener.dispatch_action(binding)
        on_activate.assert_called_once_with(binding)
        on_deactivate.assert_not_called()

    def test_copy_to_clipboard_deactivate_on_release(self) -> None:
        listener = self._make_listener()
        on_activate = MagicMock()
        on_deactivate = MagicMock()
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        binding = self._binding("copy_to_clipboard")
        listener.dispatch_release(binding)
        on_deactivate.assert_called_once()
        on_activate.assert_not_called()


@pytest.mark.linux_only
class TestEvdevHotkeyListener:
    """Test EvdevHotkeyListener with mocked evdev."""

    def _default_bindings(self) -> list[HotkeyBinding]:
        return [
            HotkeyBinding(
                modifiers=["KEY_LEFTCTRL", "KEY_LEFTSHIFT"],
                trigger="KEY_SPACE",
                action="push_to_talk",
            ),
        ]

    def test_push_to_talk_activates_on_combo(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener

        on_activate = MagicMock()
        on_deactivate = MagicMock()

        listener = EvdevHotkeyListener(
            bindings=self._default_bindings(),
        )
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        # Pre-set modifiers as held
        ctrl_code: int = listener.ecodes_dict["KEY_LEFTCTRL"]
        shift_code: int = listener.ecodes_dict["KEY_LEFTSHIFT"]
        space_code: int = listener.ecodes_dict["KEY_SPACE"]

        listener.held_keys.add(ctrl_code)
        listener.held_keys.add(shift_code)

        # Simulate space down (keystate=1)
        event = MagicMock()
        event.code = space_code
        key_event = MagicMock()
        key_event.keystate = 1
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_event)

        listener.handle_key_event(event, None)
        # on_activate should be called with a HotkeyBinding whose action is push_to_talk
        on_activate.assert_called_once()
        called_binding = on_activate.call_args[0][0]
        assert isinstance(called_binding, HotkeyBinding)
        assert called_binding.action == "push_to_talk"

    def test_push_to_talk_deactivates_on_release(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener

        on_activate = MagicMock()
        on_deactivate = MagicMock()

        listener = EvdevHotkeyListener(
            bindings=self._default_bindings(),
        )
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        space_code: int = listener.ecodes_dict["KEY_SPACE"]

        # Mark the trigger as suppressed (as if hotkey was pressed)
        listener.suppressed_triggers.add(space_code)

        # Simulate space up (keystate=0)
        event = MagicMock()
        event.code = space_code
        key_event = MagicMock()
        key_event.keystate = 0
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_event)

        listener.handle_key_event(event, None)
        # Release is debounced -- not called immediately
        on_deactivate.assert_not_called()

        # Advance time past the debounce window to fire the pending release
        listener.check_pending_releases(now=time.monotonic() + 1.0)
        on_deactivate.assert_called_once()

    def test_push_to_talk_debounce_cancels_on_repress(self, mocker: Any) -> None:
        """Spurious key-up then key-down within debounce window cancels release."""
        from murmur.hotkey.evdev import EvdevHotkeyListener

        on_activate = MagicMock()
        on_deactivate = MagicMock()

        listener = EvdevHotkeyListener(
            bindings=self._default_bindings(),
        )
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        ctrl_code: int = listener.ecodes_dict["KEY_LEFTCTRL"]
        shift_code: int = listener.ecodes_dict["KEY_LEFTSHIFT"]
        space_code: int = listener.ecodes_dict["KEY_SPACE"]

        listener.held_keys.add(ctrl_code)
        listener.held_keys.add(shift_code)
        listener.suppressed_triggers.add(space_code)

        # Simulate spurious space up
        key_up_event = MagicMock()
        key_up_event.code = space_code
        key_up = MagicMock()
        key_up.keystate = 0
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_up)
        listener.handle_key_event(key_up_event, None)

        assert space_code in listener.pending_releases
        on_deactivate.assert_not_called()

        # Simulate key-down again (spurious bounce -- user still holding)
        listener.held_keys.add(space_code)
        key_down_event = MagicMock()
        key_down_event.code = space_code
        key_down = MagicMock()
        key_down.keystate = 1
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_down)
        listener.handle_key_event(key_down_event, None)

        # Pending release should be cancelled
        assert space_code not in listener.pending_releases
        # Trigger still suppressed (hotkey still active)
        assert space_code in listener.suppressed_triggers
        on_deactivate.assert_not_called()
        # on_activate should NOT re-fire (spurious cancel, not a new press)
        on_activate.assert_not_called()

    def test_trigger_without_modifiers_no_activate(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener

        on_activate = MagicMock()

        listener = EvdevHotkeyListener(
            bindings=self._default_bindings(),
        )
        listener.set_callbacks(on_activate=on_activate, on_deactivate=MagicMock())

        space_code: int = listener.ecodes_dict["KEY_SPACE"]

        # Simulate space down without modifiers
        event = MagicMock()
        event.code = space_code
        key_event = MagicMock()
        key_event.keystate = 1
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_event)

        listener.handle_key_event(event, None)
        on_activate.assert_not_called()

    def test_invalid_key_name_raises(self) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener

        with pytest.raises(ValueError, match="Unknown evdev key name"):
            EvdevHotkeyListener(
                bindings=[
                    HotkeyBinding(
                        modifiers=["KEY_NONEXISTENT"],
                        trigger="KEY_SPACE",
                        action="push_to_talk",
                    )
                ],
            )

    def test_invalid_trigger_name_raises(self) -> None:
        from murmur.hotkey.evdev import EvdevHotkeyListener

        with pytest.raises(ValueError, match="Unknown evdev key name"):
            EvdevHotkeyListener(
                bindings=[
                    HotkeyBinding(
                        modifiers=["KEY_LEFTCTRL"],
                        trigger="KEY_BOGUS",
                        action="push_to_talk",
                    )
                ],
            )

    def test_find_keyboard_devices(self, mocker: Any) -> None:
        from murmur.hotkey.evdev import EV_KEY, KEY_A, KEY_Z, find_keyboard_devices

        mock_dev = MagicMock()
        mock_dev.name = "Test Keyboard"
        mock_dev.capabilities.return_value = {
            EV_KEY: [KEY_A, KEY_Z, 1, 2, 3],
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

    def test_device_disconnect_calls_fatal(self, mocker: Any) -> None:
        from selectors import EVENT_READ

        from murmur.hotkey.evdev import EvdevHotkeyListener

        listener = EvdevHotkeyListener(
            bindings=self._default_bindings(),
        )

        # Make fatal_from_thread set the stop event so loop exits
        def mock_fatal_fn(msg: str) -> None:
            listener.stop_event.set()

        mock_fatal = mocker.patch(
            "murmur.hotkey.evdev.fatal_from_thread",
            side_effect=mock_fatal_fn,
        )

        # Create mock device and uinput pair
        mock_dev = MagicMock()
        mock_dev.path = "/dev/input/event0"
        mock_dev.read.side_effect = OSError("No such device")
        mock_uinput = MagicMock()

        # Patch selectors.DefaultSelector at its source
        mock_selector = MagicMock()
        mock_key = MagicMock()
        mock_key.fileobj = mock_dev
        mock_selector.select.return_value = [(mock_key, EVENT_READ)]
        mocker.patch("selectors.DefaultSelector", return_value=mock_selector)

        listener.devices = [{"device": mock_dev, "uinput": mock_uinput}]
        listener.stop_event.clear()

        listener.listen_loop()

        mock_fatal.assert_called_once()
        call_msg: str = mock_fatal.call_args[0][0]
        assert "Input device disconnected" in call_msg
        assert "/dev/input/event0" in call_msg

    def test_multiple_bindings_dispatch(self, mocker: Any) -> None:
        """Test that different bindings dispatch different actions."""
        from murmur.hotkey.evdev import EvdevHotkeyListener

        bindings = [
            HotkeyBinding(
                modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
                trigger="KEY_SPACE",
                action="push_to_talk",
            ),
            HotkeyBinding(
                modifiers=["KEY_LEFTCTRL", "KEY_LEFTALT"],
                trigger="KEY_K",
                action="toggle",
            ),
        ]

        on_activate = MagicMock()
        on_deactivate = MagicMock()

        listener = EvdevHotkeyListener(bindings=bindings)
        listener.set_callbacks(on_activate=on_activate, on_deactivate=on_deactivate)

        ctrl_code: int = listener.ecodes_dict["KEY_LEFTCTRL"]
        alt_code: int = listener.ecodes_dict["KEY_LEFTALT"]
        k_code: int = listener.ecodes_dict["KEY_K"]

        listener.held_keys.add(ctrl_code)
        listener.held_keys.add(alt_code)

        # Press K -> toggle -> activate
        event = MagicMock()
        event.code = k_code
        key_event = MagicMock()
        key_event.keystate = 1
        mocker.patch("murmur.hotkey.evdev.categorize", return_value=key_event)

        listener.handle_key_event(event, None)
        on_activate.assert_called_once()
        called_binding = on_activate.call_args[0][0]
        assert isinstance(called_binding, HotkeyBinding)
        assert called_binding.action == "toggle"

    @pytest.mark.hardware()
    def test_real_keyboard_detection(self) -> None:
        """Integration test: detect real keyboard (requires hardware)."""
        from murmur.hotkey.evdev import find_keyboard_devices

        devices = find_keyboard_devices()
        assert len(devices) > 0, "No keyboard devices detected"
