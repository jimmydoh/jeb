#!/usr/bin/env python3
"""Tests for HIDManager software-mode tap detection.

Verifies that _sw_set_buttons (and related SW setters) fire the tap flag on
RELEASE (matching hardware behaviour), not on PRESS.  Also verifies that
flush() clears pending tap flags to prevent ghost inputs.
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

# ticks_ms / ticks_diff need to be controllable per-test
_tick_time = 0


def _ticks_ms():
    return _tick_time


def _ticks_diff(new, old):
    return new - old


sys.modules['adafruit_ticks'].ticks_ms = _ticks_ms
sys.modules['adafruit_ticks'].ticks_diff = _ticks_diff


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_hid(**kwargs):
    """Fresh HIDManager in monitor_only mode with 4 buttons."""
    # Ensure timing functions are set correctly before (re-)importing the module
    sys.modules['adafruit_ticks'].ticks_ms = _ticks_ms
    sys.modules['adafruit_ticks'].ticks_diff = _ticks_diff

    if 'managers.hid_manager' in sys.modules:
        del sys.modules['managers.hid_manager']
    from managers.hid_manager import HIDManager
    kwargs.setdefault('encoders', [])
    kwargs.setdefault('monitor_only', True)
    kwargs.setdefault('buttons', ['dummy'] * 4)  # 4 buttons (A, B, C, D)
    return HIDManager(**kwargs)


# ---------------------------------------------------------------------------
# Button tap tests
# ---------------------------------------------------------------------------

def test_sw_button_tap_not_set_on_press():
    """Pressing a button must NOT immediately set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid()

    # Simulate D button (index 3) pressed
    hid._sw_set_buttons("0001")

    assert hid.buttons_tapped[3] is False, \
        "Tap flag must not fire on PRESS; it should fire on RELEASE"


def test_sw_button_tap_set_on_quick_release():
    """Releasing a button within 500 ms of pressing it must set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid()

    # Press D button
    hid._sw_set_buttons("0001")
    assert hid.buttons_tapped[3] is False

    # Release D button 200 ms later (within the 500 ms window)
    _tick_time = 1200
    hid._sw_set_buttons("0000")

    assert hid.buttons_tapped[3] is True, \
        "Tap flag must be set when button is released within 500 ms"


def test_sw_button_tap_not_set_on_slow_release():
    """Releasing a button after 500 ms must NOT set the tap flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid()

    # Press D button
    hid._sw_set_buttons("0001")

    # Release D button 600 ms later (outside the 500 ms window)
    _tick_time = 1600
    hid._sw_set_buttons("0000")

    assert hid.buttons_tapped[3] is False, \
        "Tap flag must not be set when button is released after 500 ms"


def test_sw_button_tap_consumed_by_is_button_pressed():
    """is_button_pressed(action='tap') must return True once then clear the flag."""
    global _tick_time
    _tick_time = 1000

    hid = _make_hid()

    hid._sw_set_buttons("0001")   # press
    _tick_time = 1100
    hid._sw_set_buttons("0000")   # release -> tap flag set

    # First read: True, flag cleared
    assert hid.is_button_pressed(3, action="tap") is True
    # Second read: False (already consumed)
    assert hid.is_button_pressed(3, action="tap") is False


def test_sw_button_d_tap_sequence_for_settings():
    """Full D-button tap cycle matches what main_menu expects to enter settings."""
    global _tick_time
    _tick_time = 1000  # Start at non-zero time so press timestamp > 0

    hid = _make_hid()

    # 1. D pressed - tap should NOT fire yet (button still held)
    hid._sw_set_buttons("0001")
    btn_d_during_press = hid.is_button_pressed(3, action="tap")
    assert btn_d_during_press is False, \
        "Tap must not be readable while button is still held"

    # 2. D released within 500 ms
    _tick_time = 1200
    hid._sw_set_buttons("0000")

    # 3. Now the tap is readable
    btn_d_after_release = hid.is_button_pressed(3, action="tap")
    assert btn_d_after_release is True, \
        "Tap must be readable after button is released"

    # 4. Button is no longer held (values cleared)
    assert hid.buttons_values[3] is False


# ---------------------------------------------------------------------------
# Encoder-button tap tests
# ---------------------------------------------------------------------------

def test_sw_encoder_button_tap_on_release():
    """Encoder button tap must fire on release, not press."""
    global _tick_time
    _tick_time = 500

    hid = _make_hid(encoders=[['dummy_a', 'dummy_b', 'dummy_btn']])

    # Press encoder button (True)
    hid._sw_set_encoder_buttons([True])
    assert hid.encoder_buttons_tapped[0] is False

    # Release within 500 ms
    _tick_time = 700
    hid._sw_set_encoder_buttons([False])
    assert hid.encoder_buttons_tapped[0] is True


# ---------------------------------------------------------------------------
# flush() clears tapped flags
# ---------------------------------------------------------------------------

def test_flush_clears_buttons_tapped():
    """flush() must clear all buttons_tapped flags to prevent ghost inputs."""
    global _tick_time
    _tick_time = 0

    hid = _make_hid()

    # Manually set a tap flag (simulating residue from a previous mode)
    hid.buttons_tapped[3] = True

    hid.flush()

    assert hid.buttons_tapped[3] is False, \
        "flush() must clear buttons_tapped to prevent ghost D-button press"


def test_flush_clears_all_tap_flags():
    """flush() must clear tap flags for buttons, latching toggles, and encoder buttons."""
    global _tick_time
    _tick_time = 0

    hid = _make_hid(
        latching_toggles=['dummy'] * 2,
        encoders=[['a', 'b', 'btn']],
    )

    hid.buttons_tapped[0] = True
    hid.latching_tapped[1] = True
    hid.encoder_buttons_tapped[0] = True

    hid.flush()

    assert hid.buttons_tapped[0] is False
    assert hid.latching_tapped[1] is False
    assert hid.encoder_buttons_tapped[0] is False


# ---------------------------------------------------------------------------
# Regression: old code set tap on press (this validates the old bug is gone)
# ---------------------------------------------------------------------------

def test_old_bug_tap_on_press_is_fixed():
    """Regression: tap must NOT be set during the same call that sets the button high."""
    global _tick_time
    _tick_time = 0

    hid = _make_hid()

    # Old buggy code would have set buttons_tapped[3] = True here
    hid._sw_set_buttons("0001")

    assert hid.buttons_tapped[3] is False, \
        "Regression: tap must not be set on press (old bug: ticks_diff(now, now) < 500)"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [
        test_sw_button_tap_not_set_on_press,
        test_sw_button_tap_set_on_quick_release,
        test_sw_button_tap_not_set_on_slow_release,
        test_sw_button_tap_consumed_by_is_button_pressed,
        test_sw_button_d_tap_sequence_for_settings,
        test_sw_encoder_button_tap_on_release,
        test_flush_clears_buttons_tapped,
        test_flush_clears_all_tap_flags,
        test_old_bug_tap_on_press_is_fixed,
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
