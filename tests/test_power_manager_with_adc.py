#!/usr/bin/env python3
"""Unit tests for PowerManager using ADCManager for voltage sensing."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()
    
    def __call__(self, *args, **kwargs):
        return MockModule()


# Mock digitalio module
class MockDigitalInOut:
    """Mock DigitalInOut class."""
    def __init__(self, pin):
        self.pin = pin
        self.direction = None
        self.pull = None
        self.value = False


class MockDigitalioModule:
    """Mock digitalio module."""
    Direction = type('Direction', (), {'OUTPUT': 'OUTPUT', 'INPUT': 'INPUT'})()
    Pull = type('Pull', (), {'UP': 'UP', 'DOWN': 'DOWN'})()
    
    @staticmethod
    def DigitalInOut(pin):
        return MockDigitalInOut(pin)


sys.modules['digitalio'] = MockDigitalioModule()
sys.modules['asyncio'] = __import__('asyncio')
sys.modules['board'] = MockModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()


# Mock ADCManager for testing
class MockADCManager:
    """Mock ADCManager for testing PowerManager."""
    def __init__(self):
        self.channels = {}
        self.readings = {
            "input_20v": 19.5,
            "satbus_20v": 18.8,
            "main_5v": 5.0,
            "led_5v": 4.9,
        }
    
    def read(self, name):
        """Return mock voltage reading."""
        return self.readings.get(name, 0.0)
    
    def set_reading(self, name, value):
        """Set a mock voltage reading for testing."""
        self.readings[name] = value


from managers.power_manager import PowerManager


def test_power_manager_initialization():
    """Test PowerManager initializes with ADCManager."""
    print("Testing PowerManager initialization with ADCManager...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v", "satbus_20v", "main_5v", "led_5v"]
    
    # Mock pins
    class MockPin:
        pass
    
    mosfet_pin = MockPin()
    detect_pin = MockPin()
    
    power = PowerManager(mock_adc, sense_names, mosfet_pin, detect_pin)
    
    assert power.adc == mock_adc
    assert power.sense_names == sense_names
    assert hasattr(power, "v_input_20v")
    assert hasattr(power, "v_satbus_20v")
    assert hasattr(power, "v_main_5v")
    assert hasattr(power, "v_led_5v")
    
    print("✓ PowerManager initialization test passed")


def test_power_manager_status():
    """Test PowerManager reads voltages from ADCManager."""
    print("\nTesting PowerManager voltage status reading...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v", "satbus_20v", "main_5v", "led_5v"]
    
    class MockPin:
        pass
    
    power = PowerManager(mock_adc, sense_names, MockPin(), MockPin())
    
    # Get status
    status = power.status
    
    # Verify readings match ADCManager mock values
    assert abs(status["input_20v"] - 19.5) < 0.01
    assert abs(status["satbus_20v"] - 18.8) < 0.01
    assert abs(status["main_5v"] - 5.0) < 0.01
    assert abs(status["led_5v"] - 4.9) < 0.01
    
    print(f"  ✓ Status: {status}")
    print("✓ PowerManager status test passed")


def test_power_manager_max_min_tracking():
    """Test PowerManager tracks max and min voltages."""
    print("\nTesting PowerManager max/min voltage tracking...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v", "satbus_20v"]
    
    class MockPin:
        pass
    
    power = PowerManager(mock_adc, sense_names, MockPin(), MockPin())
    
    # Read initial values
    _ = power.status
    
    # Change values and read again
    mock_adc.set_reading("input_20v", 20.5)
    mock_adc.set_reading("satbus_20v", 17.0)
    _ = power.status
    
    # Change to lower values
    mock_adc.set_reading("input_20v", 18.0)
    mock_adc.set_reading("satbus_20v", 19.5)
    _ = power.status
    
    # Check max values
    max_vals = power.max
    assert max_vals["input_20v"] == 20.5
    assert max_vals["satbus_20v"] == 19.5
    
    # Check min values
    min_vals = power.min
    assert min_vals["input_20v"] == 18.0
    assert min_vals["satbus_20v"] == 17.0
    
    print(f"  ✓ Max: {max_vals}")
    print(f"  ✓ Min: {min_vals}")
    print("✓ PowerManager max/min tracking test passed")


def test_power_manager_mosfet_control():
    """Test PowerManager MOSFET control."""
    print("\nTesting PowerManager MOSFET control...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v"]
    
    class MockPin:
        pass
    
    power = PowerManager(mock_adc, sense_names, MockPin(), MockPin())
    
    # MOSFET should be off initially
    assert power.sat_pwr.value == False
    assert power.satbus_powered == False
    
    # Turn on
    power.sat_pwr.value = True
    assert power.satbus_powered == True
    
    # Emergency kill
    power.emergency_kill()
    assert power.sat_pwr.value == False
    assert power.satbus_powered == False
    
    print("  ✓ MOSFET control working correctly")
    print("✓ PowerManager MOSFET control test passed")


def test_power_manager_backward_compatibility():
    """Test that PowerManager maintains backward compatibility."""
    print("\nTesting PowerManager backward compatibility...")
    
    mock_adc = MockADCManager()
    
    # Test with standard sense names
    sense_names = ["input_20v", "satbus_20v", "main_5v", "led_5v"]
    
    class MockPin:
        pass
    
    power = PowerManager(mock_adc, sense_names, MockPin(), MockPin())
    
    # All original properties should work
    status = power.status
    max_vals = power.max
    min_vals = power.min
    
    assert isinstance(status, dict)
    assert isinstance(max_vals, dict)
    assert isinstance(min_vals, dict)
    assert len(status) == 4
    
    # Check satbus detection
    assert hasattr(power, "satbus_connected")
    assert hasattr(power, "satbus_powered")
    
    # Check MOSFET control
    assert hasattr(power, "sat_pwr")
    assert hasattr(power, "emergency_kill")
    
    print("  ✓ All original PowerManager APIs preserved")
    print("✓ PowerManager backward compatibility test passed")


def test_power_manager_sat_profile():
    """Test PowerManager with Satellite profile (3 channels instead of 4)."""
    print("\nTesting PowerManager with Satellite profile...")
    
    mock_adc = MockADCManager()
    
    # Satellite has only 3 channels
    sense_names = ["input_20v", "satbus_20v", "main_5v"]
    
    class MockPin:
        pass
    
    power = PowerManager(mock_adc, sense_names, MockPin(), MockPin())
    
    status = power.status
    
    # Should only have 3 channels
    assert len(status) == 3
    assert "input_20v" in status
    assert "satbus_20v" in status
    assert "main_5v" in status
    assert "led_5v" not in status
    
    print(f"  ✓ Satellite profile status: {status}")
    print("✓ PowerManager satellite profile test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("PowerManager with ADCManager Test Suite")
    print("=" * 60)
    
    test_power_manager_initialization()
    test_power_manager_status()
    test_power_manager_max_min_tracking()
    test_power_manager_mosfet_control()
    test_power_manager_backward_compatibility()
    test_power_manager_sat_profile()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print()
    print("PowerManager successfully integrates with ADCManager:")
    print("  • Reads voltages through ADCManager instead of direct analogio")
    print("  • Maintains all original APIs for backward compatibility")
    print("  • Tracks max/min voltages correctly")
    print("  • MOSFET control works as expected")
    print("  • Supports both Core and Satellite profiles")
