#!/usr/bin/env python3
"""Tests for HIDManager hardware-mode debouncing via MCP expander.

Specifically validates the 500 ms tap-window behaviour for:
  - Guarded Toggle  (Expander 2, latching toggle, expander index 0)
  - Key Switch      (Expander 2, latching toggle, expander index 1)
  - Big Red Button  (Expander 2, button, expander index 0)

These controls are wired through a MCP23008 I/O expander and their events
reach HIDManager via MCPKeys.  This test confirms that the existing
_hw_expander_latching_toggles() and _hw_expander_buttons() implementations
already perform correct debouncing – the issue raised is therefore resolved.
"""

import sys
import os
from unittest import mock

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# ---------------------------------------------------------------------------
# CircuitPython stubs
# ---------------------------------------------------------------------------
_cp_mocks = ['digitalio', 'board', 'busio', 'keypad', 'rotaryio', 'adafruit_ticks']
for _m in _cp_mocks:
    if _m not in sys.modules:
        sys.modules[_m] = mock.MagicMock()

# Controllable tick time
_tick_time = 0


def _ticks_ms():
    return _tick_time


def _ticks_diff(new, old):
    return new - old


sys.modules['adafruit_ticks'].ticks_ms = _ticks_ms
sys.modules['adafruit_ticks'].ticks_diff = _ticks_diff


# ---------------------------------------------------------------------------
# Minimal fakes
# ---------------------------------------------------------------------------

class _FakeEvent:
    """Minimal keypad.Event substitute."""
    def __init__(self, key_number, pressed):
        self.key_number = key_number
        self.pressed = pressed
        self.released = not pressed


class _FakeMCPKeys:
    """Replay a preset list of events; mimic MCPKeys.events.get() interface."""
    def __init__(self, events=None):
        self._queue = list(events or [])
        self.events = self  # MCPKeys sets self.events = self

    def get(self):
        return self._queue.pop(0) if self._queue else None


# ---------------------------------------------------------------------------
# Helper: build a minimal HIDManager with an injected fake expander
# ---------------------------------------------------------------------------

def _make_hid_with_expander(num_buttons=1, num_latching=2,
                             btn_events=None, latch_events=None):
    """
    Return a HIDManager (hw mode) whose state arrays are sized for the given
    counts and whose single fake expander is pre-loaded with the given events.
    """
    sys.modules['adafruit_ticks'].ticks_ms = _ticks_ms
    sys.modules['adafruit_ticks'].ticks_diff = _ticks_diff

    if 'managers.hid_manager' in sys.modules:
        del sys.modules['managers.hid_manager']
    from managers.hid_manager import HIDManager

    # Create in hw mode; no real hardware is needed because the expander is
    # injected directly after construction.
    hid = HIDManager(encoders=[])

    # Resize state arrays to match the number of expander-provided inputs.
    hid.buttons_values = [False] * num_buttons
    hid.buttons_timestamps = [0] * num_buttons
    hid.buttons_tapped = [False] * num_buttons
    hid._local_button_count = 0

    hid.latching_values = [False] * num_latching
    hid.latching_timestamps = [0] * num_latching
    hid.latching_tapped = [False] * num_latching
    hid._local_latching_count = 0

    # Inject a fake expander that replays the supplied events.
    hid.has_expander = True
    hid._active_expanders = [{
        "btn_keys":   _FakeMCPKeys(btn_events or []),
        "btn_offset": 0,
        "latch_keys": _FakeMCPKeys(latch_events or []),
        "latch_offset": 0,
        "mom_keys":   None,
        "mom_offset": 0,
        "abs_btn_base":   0,
        "abs_latch_base": 0,
        "abs_mom_base":   0,
    }]

    return hid


# ---------------------------------------------------------------------------
# Big Red Button (expander button) tap detection
# ---------------------------------------------------------------------------

def test_big_red_button_tap_not_set_on_press():
    """Pressing the Big Red Button must NOT immediately set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_buttons=1,
        btn_events=[_FakeEvent(0, pressed=True)],
    )

    hid._hw_expander_buttons()

    assert hid.buttons_tapped[0] is False, \
        "Tap flag must not fire on press"


def test_big_red_button_tap_set_on_quick_release():
    """Releasing the Big Red Button within 500 ms must set the tap flag."""
    global _tick_time
    _tick_time = 1000

    press_event   = _FakeEvent(0, pressed=True)
    release_event = _FakeEvent(0, pressed=False)

    hid = _make_hid_with_expander(
        num_buttons=1,
        btn_events=[press_event],
    )
    hid._hw_expander_buttons()          # press recorded at t=1000

    # Inject the release event and advance time by 200 ms (within window)
    _tick_time = 1200
    hid._active_expanders[0]["btn_keys"]._queue.append(release_event)
    hid._hw_expander_buttons()          # release processed at t=1200

    assert hid.buttons_tapped[0] is True, \
        "Tap flag must be set when Big Red Button is released within 500 ms"
    assert hid.buttons_values[0] is False, \
        "Button value must be cleared on release"


def test_big_red_button_tap_not_set_on_slow_release():
    """Releasing the Big Red Button after 500 ms must NOT set the tap flag."""
    global _tick_time
    _tick_time = 1000

    press_event   = _FakeEvent(0, pressed=True)
    release_event = _FakeEvent(0, pressed=False)

    hid = _make_hid_with_expander(
        num_buttons=1,
        btn_events=[press_event],
    )
    hid._hw_expander_buttons()          # press at t=1000

    _tick_time = 1600                   # 600 ms later – outside the window
    hid._active_expanders[0]["btn_keys"]._queue.append(release_event)
    hid._hw_expander_buttons()

    assert hid.buttons_tapped[0] is False, \
        "Tap flag must not be set when Big Red Button is released after 500 ms"


def test_big_red_button_tap_consumed_once():
    """is_button_pressed(action='tap') must return True once then clear the flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_buttons=1,
        btn_events=[
            _FakeEvent(0, pressed=True),
            _FakeEvent(0, pressed=False),
        ],
    )
    hid._hw_expander_buttons()          # press at t=1000
    _tick_time = 1100
    hid._hw_expander_buttons()          # release at t=1100

    assert hid.is_button_pressed(0, action="tap") is True
    assert hid.is_button_pressed(0, action="tap") is False, \
        "Tap flag must be consumed on first read"


# ---------------------------------------------------------------------------
# Guarded Toggle (expander latching toggle, index 0) tap detection
# ---------------------------------------------------------------------------

def test_guarded_toggle_tap_not_set_on_activation():
    """Activating the Guarded Toggle must NOT immediately set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_latching=2,
        latch_events=[_FakeEvent(0, pressed=True)],
    )
    hid._hw_expander_latching_toggles()

    assert hid.latching_tapped[0] is False, \
        "Tap flag must not fire when Guarded Toggle is turned on"


def test_guarded_toggle_tap_set_on_quick_deactivation():
    """Deactivating the Guarded Toggle within 500 ms must set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_latching=2,
        latch_events=[_FakeEvent(0, pressed=True)],
    )
    hid._hw_expander_latching_toggles()   # turned on at t=1000

    _tick_time = 1300
    hid._active_expanders[0]["latch_keys"]._queue.append(
        _FakeEvent(0, pressed=False)
    )
    hid._hw_expander_latching_toggles()   # turned off at t=1300

    assert hid.latching_tapped[0] is True, \
        "Tap flag must be set when Guarded Toggle is deactivated within 500 ms"
    assert hid.latching_values[0] is False


def test_guarded_toggle_tap_not_set_on_slow_deactivation():
    """Deactivating the Guarded Toggle after 500 ms must NOT set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_latching=2,
        latch_events=[_FakeEvent(0, pressed=True)],
    )
    hid._hw_expander_latching_toggles()

    _tick_time = 1600
    hid._active_expanders[0]["latch_keys"]._queue.append(
        _FakeEvent(0, pressed=False)
    )
    hid._hw_expander_latching_toggles()

    assert hid.latching_tapped[0] is False, \
        "Tap flag must not be set when Guarded Toggle is deactivated after 500 ms"


# ---------------------------------------------------------------------------
# Key Switch (expander latching toggle, index 1) tap detection
# ---------------------------------------------------------------------------

def test_key_switch_tap_set_on_quick_release():
    """Returning the Key Switch to OFF within 500 ms must set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_latching=2,
        latch_events=[_FakeEvent(1, pressed=True)],
    )
    hid._hw_expander_latching_toggles()   # key turned on at t=1000

    _tick_time = 1250
    hid._active_expanders[0]["latch_keys"]._queue.append(
        _FakeEvent(1, pressed=False)
    )
    hid._hw_expander_latching_toggles()

    assert hid.latching_tapped[1] is True, \
        "Tap flag must be set when Key Switch is released within 500 ms"
    assert hid.latching_values[1] is False


def test_key_switch_tap_not_set_on_slow_release():
    """Returning the Key Switch to OFF after 500 ms must NOT set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_latching=2,
        latch_events=[_FakeEvent(1, pressed=True)],
    )
    hid._hw_expander_latching_toggles()

    _tick_time = 2000
    hid._active_expanders[0]["latch_keys"]._queue.append(
        _FakeEvent(1, pressed=False)
    )
    hid._hw_expander_latching_toggles()

    assert hid.latching_tapped[1] is False, \
        "Tap flag must not be set when Key Switch is released after 500 ms"


def test_key_switch_hold_detection():
    """is_latching_toggled(action='hold') must be True when Key Switch held >= duration."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid_with_expander(
        num_latching=2,
        latch_events=[_FakeEvent(1, pressed=True)],
    )
    hid._hw_expander_latching_toggles()   # key on at t=1000

    _tick_time = 3500                     # 2500 ms later → exceeds default 2000 ms hold
    assert hid.is_latching_toggled(1, action="hold") is True, \
        "Key Switch must be reported as held after >= 2000 ms"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [
        test_big_red_button_tap_not_set_on_press,
        test_big_red_button_tap_set_on_quick_release,
        test_big_red_button_tap_not_set_on_slow_release,
        test_big_red_button_tap_consumed_once,
        test_guarded_toggle_tap_not_set_on_activation,
        test_guarded_toggle_tap_set_on_quick_deactivation,
        test_guarded_toggle_tap_not_set_on_slow_deactivation,
        test_key_switch_tap_set_on_quick_release,
        test_key_switch_tap_not_set_on_slow_release,
        test_key_switch_hold_detection,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} (error): {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
