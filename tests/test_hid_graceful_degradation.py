#!/usr/bin/env python3
"""Tests for HIDManager graceful degradation when the I/O expander is absent."""

import sys
import os
from unittest import mock

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# CircuitPython module stubs required for import
_cp_mocks = [
    'digitalio', 'board', 'busio', 'keypad', 'rotaryio',
    'adafruit_ticks',
]
for _m in _cp_mocks:
    if _m not in sys.modules:
        sys.modules[_m] = mock.MagicMock()

# adafruit_ticks needs ticks_ms and ticks_diff to return predictable values
sys.modules['adafruit_ticks'].ticks_ms = mock.MagicMock(return_value=0)
sys.modules['adafruit_ticks'].ticks_diff = mock.MagicMock(return_value=0)


def _make_hid(**kwargs):
    """Import and instantiate a fresh HIDManager with mocked hardware."""
    # Force reimport to pick up the latest source
    if 'managers.hid_manager' in sys.modules:
        del sys.modules['managers.hid_manager']

    from managers.hid_manager import HIDManager
    # HIDManager requires encoders to be a list (len() is called on it); default to []
    kwargs.setdefault('encoders', [])
    return HIDManager(**kwargs)


def test_has_expander_false_with_no_mcp_params():
    """has_expander should be False when no MCP params are supplied."""
    hid = _make_hid()
    assert hid.has_expander is False


def test_has_expander_false_when_mcp_import_fails():
    """has_expander stays False when the adafruit_mcp230xx library is missing."""
    # Ensure the library import raises ImportError
    sys.modules.pop('adafruit_mcp230xx', None)
    sys.modules.pop('adafruit_mcp230xx.mcp23008', None)

    mock_i2c = mock.MagicMock()

    with mock.patch.dict(sys.modules, {
        'adafruit_mcp230xx': mock.MagicMock(),
        'adafruit_mcp230xx.mcp23008': mock.MagicMock(
            side_effect=ImportError("No module named adafruit_mcp230xx")
        ),
    }):
        # Patch the from...import to raise ImportError
        with mock.patch('builtins.__import__', side_effect=_import_raiser('adafruit_mcp230xx')):
            hid = _make_hid(
                expander_configs=[{"chip": "MCP23008", "address": 0x20, "i2c": mock_i2c}],
            )
    assert hid.has_expander is False


def _import_raiser(blocked_prefix):
    """Return an __import__ side-effect that raises ImportError for blocked modules."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def _inner(name, *args, **kwargs):
        if name.startswith(blocked_prefix):
            raise ImportError(f"Mocked ImportError for {name}")
        return real_import(name, *args, **kwargs)

    return _inner


def test_has_expander_false_when_oserror_raised():
    """has_expander stays False when the I2C device is absent (OSError)."""
    mock_i2c = mock.MagicMock()

    # Simulate the MCP23008 class raising OSError on construction (device not on bus)
    mock_mcp_class = mock.MagicMock(side_effect=OSError("I2C device not found"))
    mock_mcp_module = mock.MagicMock()
    mock_mcp_module.MCP23008 = mock_mcp_class

    with mock.patch.dict(sys.modules, {
        'adafruit_mcp230xx': mock.MagicMock(),
        'adafruit_mcp230xx.mcp23008': mock_mcp_module,
    }):
        hid = _make_hid(
            expander_configs=[{"chip": "MCP23008", "address": 0x20, "i2c": mock_i2c}],
        )

    assert hid.has_expander is False


def test_has_expander_false_when_valueerror_raised():
    """has_expander stays False when MCP23008() raises ValueError."""
    mock_i2c = mock.MagicMock()

    mock_mcp_class = mock.MagicMock(side_effect=ValueError("bad address"))
    mock_mcp_module = mock.MagicMock()
    mock_mcp_module.MCP23008 = mock_mcp_class

    with mock.patch.dict(sys.modules, {
        'adafruit_mcp230xx': mock.MagicMock(),
        'adafruit_mcp230xx.mcp23008': mock_mcp_module,
    }):
        hid = _make_hid(
            expander_configs=[{"chip": "MCP23008", "address": 0x20, "i2c": mock_i2c}],
        )

    assert hid.has_expander is False


def test_has_expander_true_when_mcp_initializes():
    """has_expander is True when the MCP chip initialises successfully."""
    mock_i2c = mock.MagicMock()

    mock_mcp_instance = mock.MagicMock()
    mock_mcp_class = mock.MagicMock(return_value=mock_mcp_instance)
    mock_mcp_module = mock.MagicMock()
    mock_mcp_module.MCP23008 = mock_mcp_class

    with mock.patch.dict(sys.modules, {
        'adafruit_mcp230xx': mock.MagicMock(),
        'adafruit_mcp230xx.mcp23008': mock_mcp_module,
        'utilities.mcp_keys': mock.MagicMock(),
    }):
        hid = _make_hid(
            expander_configs=[{"chip": "MCP23008", "address": 0x20, "i2c": mock_i2c}],
        )

    assert hid.has_expander is True


def test_hw_update_skips_expander_when_not_present():
    """hw_update() does not call expander poll methods when has_expander=False."""
    hid = _make_hid()
    assert hid.has_expander is False

    # Patch the expander polling methods and unrelated methods that have
    # pre-existing attribute dependencies outside the scope of this test
    with mock.patch.object(hid, '_hw_poll_buttons', return_value=False), \
         mock.patch.object(hid, '_hw_poll_latching_toggles', return_value=False), \
         mock.patch.object(hid, '_hw_poll_momentary_toggles', return_value=False), \
         mock.patch.object(hid, '_hw_poll_encoders', return_value=False), \
         mock.patch.object(hid, '_hw_poll_encoder_buttons', return_value=False), \
         mock.patch.object(hid, '_hw_poll_matrix_keypads', return_value=False), \
         mock.patch.object(hid, '_hw_poll_estop', return_value=False), \
         mock.patch.object(hid, '_hw_expander_buttons') as mock_exp_btn, \
         mock.patch.object(hid, '_hw_expander_latching_toggles') as mock_exp_latch, \
         mock.patch.object(hid, '_hw_expander_momentary_toggles') as mock_exp_mom:

        result = hid.hw_update()

    # Expander methods must NOT be called when has_expander is False
    mock_exp_btn.assert_not_called()
    mock_exp_latch.assert_not_called()
    mock_exp_mom.assert_not_called()
    assert result is False


def test_monitor_only_has_expander_false():
    """has_expander is always False in monitor_only mode."""
    hid = _make_hid(monitor_only=True)
    assert hid.has_expander is False
