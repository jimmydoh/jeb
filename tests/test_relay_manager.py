#!/usr/bin/env python3
"""Unit tests for RelayManager."""

import sys
import os
import asyncio
import pytest

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()
    
    def __call__(self, *args, **kwargs):
        return MockModule()

sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['ulab'] = MockModule()
sys.modules['neopixel'] = MockModule()

# Add src directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from managers.relay_manager import RelayManager


class MockDigitalPin:
    """Mock digitalio.DigitalInOut for testing."""
    def __init__(self):
        self.value = False


class MockLEDManager:
    """Mock LEDManager for testing LED slaving."""
    def __init__(self, num_leds):
        self.pixels = [(0, 0, 0)] * num_leds
        self.n = num_leds


def test_relay_manager_initialization():
    """Test that RelayManager initializes correctly."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    assert manager.num_relays == 4, "Should have 4 relays"
    assert len(manager.relay_states) == 4, "Should track 4 relay states"
    assert all(state is False for state in manager.relay_states), "All relays should start OFF"
    assert all(pin.value is False for pin in pins), "All pins should start LOW"


def test_set_relay_single():
    """Test setting a single relay on and off."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Turn on relay 1
    manager.set_relay(1, True)
    assert manager.get_state(1) is True, "Relay 1 should be ON"
    assert pins[1].value is True, "Pin 1 should be HIGH"
    assert manager.get_state(0) is False, "Relay 0 should still be OFF"
    
    # Turn off relay 1
    manager.set_relay(1, False)
    assert manager.get_state(1) is False, "Relay 1 should be OFF"
    assert pins[1].value is False, "Pin 1 should be LOW"


def test_set_relay_all():
    """Test setting all relays at once."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Turn all relays ON (using -1)
    manager.set_relay(-1, True)
    assert all(manager.get_state(i) for i in range(4)), "All relays should be ON"
    assert all(pin.value for pin in pins), "All pins should be HIGH"
    
    # Turn all relays OFF
    manager.set_relay(-1, False)
    assert all(not manager.get_state(i) for i in range(4)), "All relays should be OFF"
    assert all(not pin.value for pin in pins), "All pins should be LOW"


@pytest.mark.asyncio
async def test_trigger_relay_single_cycle():
    """Test triggering a relay with a single on/off cycle."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Trigger relay 2 with short duration
    await manager.trigger_relay(2, duration=0.01, cycles=1)
    
    # After completion, relay should be OFF
    assert manager.get_state(2) is False, "Relay should be OFF after trigger"
    assert pins[2].value is False, "Pin should be LOW after trigger"


@pytest.mark.asyncio
async def test_trigger_relay_multiple_cycles():
    """Test triggering a relay with multiple on/off cycles."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Trigger relay 1 with 3 cycles
    await manager.trigger_relay(1, duration=0.01, cycles=3)
    
    # After completion, relay should be OFF
    assert manager.get_state(1) is False, "Relay should be OFF after all cycles"


@pytest.mark.asyncio
async def test_trigger_simultaneous():
    """Test triggering multiple relays simultaneously."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Trigger relays 0 and 2 simultaneously
    await manager.trigger_simultaneous(indices=[0, 2], duration=0.01, cycles=1)
    
    # After completion, both should be OFF
    assert manager.get_state(0) is False, "Relay 0 should be OFF"
    assert manager.get_state(2) is False, "Relay 2 should be OFF"


@pytest.mark.asyncio
async def test_trigger_simultaneous_all():
    """Test triggering all relays simultaneously."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Trigger all relays (indices=None means all)
    await manager.trigger_simultaneous(indices=None, duration=0.01, cycles=1)
    
    # After completion, all should be OFF
    assert all(not manager.get_state(i) for i in range(4)), "All relays should be OFF"


@pytest.mark.asyncio
async def test_trigger_progressive():
    """Test triggering relays progressively (one after another)."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Trigger relays 0, 1, 2 progressively
    await manager.trigger_progressive(indices=[0, 1, 2], duration=0.02, delay=0.005, cycles=1)
    
    # After completion, all should be OFF
    assert all(not manager.get_state(i) for i in range(3)), "All triggered relays should be OFF"


@pytest.mark.asyncio
async def test_trigger_random():
    """Test triggering relays in random order."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Trigger relays randomly within timeframe
    await manager.trigger_random(indices=[0, 1, 2], duration=0.01, timeframe=0.05, cycles=1)
    
    # After completion, all should be OFF
    assert all(not manager.get_state(i) for i in range(3)), "All triggered relays should be OFF"


def test_led_slaving_setup():
    """Test setting up LED to relay slaving."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    led_manager = MockLEDManager(8)
    
    # Slave relay 2 to LED 5
    manager.slave_to_led(2, led_manager, 5)
    
    assert 2 in manager._led_slave_map, "Relay 2 should be in slave map"
    assert manager._led_slave_map[2] == (led_manager, 5), "Should map to correct LED"


def test_led_unslaving():
    """Test removing LED slaving from a relay."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    led_manager = MockLEDManager(8)
    
    # Slave and then unslave
    manager.slave_to_led(2, led_manager, 5)
    assert 2 in manager._led_slave_map, "Relay 2 should be slaved"
    
    manager.unslave_relay(2)
    assert 2 not in manager._led_slave_map, "Relay 2 should be unslaved"


@pytest.mark.asyncio
async def test_update_slaved_relays_led_on():
    """Test that slaved relays follow LED state when LED is on."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    led_manager = MockLEDManager(8)
    
    # Slave relay 1 to LED 3
    manager.slave_to_led(1, led_manager, 3)
    
    # Turn LED 3 on (any non-zero color)
    led_manager.pixels[3] = (255, 0, 0)
    
    # Update slaved relays
    await manager.update_slaved_relays()
    
    # Relay 1 should now be ON
    assert manager.get_state(1) is True, "Relay should be ON when LED is on"
    assert pins[1].value is True, "Pin should be HIGH when LED is on"


@pytest.mark.asyncio
async def test_update_slaved_relays_led_off():
    """Test that slaved relays follow LED state when LED is off."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    led_manager = MockLEDManager(8)
    
    # Slave relay 1 to LED 3
    manager.slave_to_led(1, led_manager, 3)
    
    # LED 3 is off (0, 0, 0)
    led_manager.pixels[3] = (0, 0, 0)
    
    # Update slaved relays
    await manager.update_slaved_relays()
    
    # Relay 1 should be OFF
    assert manager.get_state(1) is False, "Relay should be OFF when LED is off"
    assert pins[1].value is False, "Pin should be LOW when LED is off"


def test_clear():
    """Test clearing all relays and slaved mappings."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    led_manager = MockLEDManager(8)
    
    # Set some relays on and slave one
    manager.set_relay(0, True)
    manager.set_relay(2, True)
    manager.slave_to_led(1, led_manager, 3)
    
    # Clear everything
    manager.clear()
    
    # All relays should be off
    assert all(not manager.get_state(i) for i in range(4)), "All relays should be OFF"
    assert all(not pin.value for pin in pins), "All pins should be LOW"
    
    # Slave map should be empty
    assert len(manager._led_slave_map) == 0, "Slave map should be empty"


def test_bounds_checking():
    """Test that invalid indices are handled gracefully."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Out of bounds index should return False for get_state
    assert manager.get_state(-5) is False, "Invalid index should return False"
    assert manager.get_state(10) is False, "Invalid index should return False"
    
    # Out of bounds slave setup should be ignored
    led_manager = MockLEDManager(8)
    manager.slave_to_led(-1, led_manager, 0)  # Invalid relay index
    assert -1 not in manager._led_slave_map, "Invalid index should not be slaved"


@pytest.mark.asyncio
async def test_apply_command_relay():
    """Test RELAY command parsing."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Test turning on relay 2
    await manager.apply_command("RELAY", "2,1")
    assert manager.get_state(2) is True, "Relay 2 should be ON"
    
    # Test turning off relay 2
    await manager.apply_command("RELAY", "2,0")
    assert manager.get_state(2) is False, "Relay 2 should be OFF"
    
    # Test turning on all relays
    await manager.apply_command("RELAY", "ALL,1")
    assert all(manager.get_state(i) for i in range(4)), "All relays should be ON"


@pytest.mark.asyncio
async def test_apply_command_relaytrig():
    """Test RELAYTRIG command parsing."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Trigger relay 1 with duration and cycles
    await manager.apply_command("RELAYTRIG", "1,0.01,2")
    
    # After completion, relay should be OFF
    assert manager.get_state(1) is False, "Relay should be OFF after trigger"


@pytest.mark.asyncio
async def test_apply_command_with_tuple():
    """Test command parsing with tuple input."""
    pins = [MockDigitalPin() for _ in range(4)]
    manager = RelayManager(pins)
    
    # Test with tuple input (as from binary protocol)
    await manager.apply_command("RELAY", (2, 1))
    assert manager.get_state(2) is True, "Relay 2 should be ON with tuple input"
    
    await manager.apply_command("RELAY", (2, 0))
    assert manager.get_state(2) is False, "Relay 2 should be OFF with tuple input"


if __name__ == "__main__":
    print("=" * 60)
    print("RelayManager Test Suite")
    print("=" * 60)
    
    # Run tests
    pytest.main([__file__, "-v"])
