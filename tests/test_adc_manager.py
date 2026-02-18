#!/usr/bin/env python3
"""Unit tests for ADCManager (I2C ADC interface with lazy loading)."""

import sys
import os

# Mock CircuitPython modules BEFORE any imports
class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()
    
    def __call__(self, *args, **kwargs):
        return MockModule()


# Mock native AnalogIn for analogio
class MockNativeAnalogIn:
    """Mock AnalogIn for native analogio."""
    def __init__(self, pin):
        self.pin = pin
        # Default: simulates 1.81V ((1.81/3.3) * 65535 ≈ 35931 in 0-65535 range for 0-3.3V)
        self.value = 35931
        

class MockAnalogioModule:
    """Mock analogio module with AnalogIn."""
    @staticmethod
    def AnalogIn(pin):
        return MockNativeAnalogIn(pin)


sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['analogio'] = MockAnalogioModule()
sys.modules['microcontroller'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['storage'] = MockModule()
sys.modules['synthio'] = MockModule()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# Mock ADS1x15 module and classes
class MockAnalogIn:
    """Mock AnalogIn class for ADS1x15."""
    def __init__(self, ads, pin):
        self.ads = ads
        self.pin = pin
        self._voltage = 1.81  # Default mock voltage (e.g., 20V through 11:1 divider)
    
    @property
    def voltage(self):
        """Return mock voltage reading."""
        return self._voltage
    
    @voltage.setter
    def voltage(self, value):
        """Set mock voltage for testing."""
        self._voltage = value


class MockADS1115:
    """Mock ADS1115 class."""
    P0 = 0
    P1 = 1
    P2 = 2
    P3 = 3
    
    def __init__(self, i2c_bus, address=0x48):
        self.i2c_bus = i2c_bus
        self.address = address


class MockADS1115Module:
    """Mock ADS1115 module."""
    P0 = MockADS1115.P0
    P1 = MockADS1115.P1
    P2 = MockADS1115.P2
    P3 = MockADS1115.P3
    
    @staticmethod
    def ADS1115(i2c_bus, address=0x48):
        return MockADS1115(i2c_bus, address)


# Mock the adafruit_ads1x15 modules
sys.modules['adafruit_ads1x15'] = MockModule()
sys.modules['adafruit_ads1x15.ads1115'] = MockADS1115Module()
sys.modules['adafruit_ads1x15.analog_in'] = type('module', (), {'AnalogIn': MockAnalogIn})()


from managers.adc_manager import ADCManager


def test_adc_manager_initialization():
    """Test ADCManager initializes with correct parameters."""
    print("Testing ADCManager initialization...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c, chip_type="ADS1115", address=0x48)
    
    assert adc.i2c_bus == mock_i2c
    assert adc.chip_type == "ADS1115"
    assert adc.address == 0x48
    assert adc.hardware is not None
    assert isinstance(adc.channels, dict)
    assert len(adc.channels) == 0
    
    print("✓ ADCManager initialization test passed")


def test_adc_manager_add_channel():
    """Test adding channels to ADCManager."""
    print("\nTesting ADCManager channel addition...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c)
    
    # Add a 20V channel with 11:1 voltage divider
    adc.add_channel("20V_MAIN", pin_or_index=0, divider_multiplier=11.0)
    
    assert "20V_MAIN" in adc.channels
    assert adc.channels["20V_MAIN"]["multiplier"] == 11.0
    assert adc.channels["20V_MAIN"]["analog_in"] is not None
    
    # Add a 5V channel with 2:1 voltage divider
    adc.add_channel("5V_LED", pin_or_index=2, divider_multiplier=2.0)
    
    assert "5V_LED" in adc.channels
    assert adc.channels["5V_LED"]["multiplier"] == 2.0
    
    print("✓ ADCManager channel addition test passed")


def test_adc_manager_read_channel():
    """Test reading voltage from a channel."""
    print("\nTesting ADCManager voltage reading...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c)
    
    # Add channel and configure it
    adc.add_channel("20V_MAIN", pin_or_index=0, divider_multiplier=11.0)
    
    # Mock voltage is 1.81V by default, which should be 19.91V with 11x multiplier
    voltage = adc.read("20V_MAIN")
    expected = 1.81 * 11.0
    
    assert abs(voltage - expected) < 0.01, f"Expected {expected}V, got {voltage}V"
    
    print(f"  ✓ Read voltage: {voltage}V (expected ~{expected}V)")
    print("✓ ADCManager voltage reading test passed")


def test_adc_manager_read_nonexistent_channel():
    """Test reading from a channel that doesn't exist returns 0.0."""
    print("\nTesting ADCManager read from non-existent channel...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c)
    
    # Try to read from a channel that was never added
    voltage = adc.read("NONEXISTENT")
    
    assert voltage == 0.0, f"Expected 0.0V for non-existent channel, got {voltage}V"
    
    print("  ✓ Non-existent channel returns 0.0V")
    print("✓ ADCManager non-existent channel test passed")


def test_adc_manager_read_all():
    """Test reading all channels at once."""
    print("\nTesting ADCManager read_all functionality...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c)
    
    # Add multiple channels
    adc.add_channel("20V_MAIN", pin_or_index=0, divider_multiplier=11.0)
    adc.add_channel("20V_SAT", pin_or_index=1, divider_multiplier=11.0)
    adc.add_channel("5V_LED", pin_or_index=2, divider_multiplier=2.0)
    adc.add_channel("5V_LOGIC", pin_or_index=3, divider_multiplier=2.0)
    
    # Read all channels
    all_voltages = adc.read_all()
    
    assert isinstance(all_voltages, dict)
    assert "20V_MAIN" in all_voltages
    assert "20V_SAT" in all_voltages
    assert "5V_LED" in all_voltages
    assert "5V_LOGIC" in all_voltages
    assert len(all_voltages) == 4
    
    # Check that all values are reasonable
    for name, voltage in all_voltages.items():
        assert voltage > 0.0, f"Channel {name} has invalid voltage {voltage}V"
    
    print(f"  ✓ Read all voltages: {all_voltages}")
    print("✓ ADCManager read_all test passed")


def test_adc_manager_voltage_divider_math():
    """Test that voltage divider multiplication is correct."""
    print("\nTesting ADCManager voltage divider math...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c)
    
    # Test different divider ratios
    test_cases = [
        ("20V_INPUT", 0, 11.0, 1.81, 19.91),  # 20V with 11:1 divider
        ("5V_RAIL", 1, 2.0, 2.5, 5.0),        # 5V with 2:1 divider
        ("3V3_RAIL", 2, 1.0, 3.3, 3.3),       # 3.3V with no divider
    ]
    
    for name, pin, multiplier, raw_v, expected_v in test_cases:
        adc.add_channel(name, pin_or_index=pin, divider_multiplier=multiplier)
        
        # Set the mock voltage
        adc.channels[name]["analog_in"]._voltage = raw_v
        
        # Read the channel
        voltage = adc.read(name)
        
        assert abs(voltage - expected_v) < 0.01, \
            f"{name}: Expected {expected_v}V, got {voltage}V"
        
        print(f"  ✓ {name}: {raw_v}V × {multiplier} = {voltage}V")
    
    print("✓ ADCManager voltage divider math test passed")


def test_adc_manager_unsupported_chip():
    """Test that unsupported chip types are handled gracefully."""
    print("\nTesting ADCManager with unsupported chip type...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c, chip_type="UNSUPPORTED_CHIP")
    
    # Hardware should be None for unsupported chips
    assert adc.hardware is None
    assert adc.chip_type == "UNSUPPORTED_CHIP"
    
    # Adding channels should do nothing
    adc.add_channel("TEST", pin_or_index=0, divider_multiplier=1.0)
    assert len(adc.channels) == 0
    
    # Reading should return 0.0
    voltage = adc.read("TEST")
    assert voltage == 0.0
    
    print("✓ ADCManager unsupported chip test passed")


def test_adc_manager_invalid_pin_index():
    """Test that invalid pin indices are handled gracefully."""
    print("\nTesting ADCManager with invalid pin index...")
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c)
    
    # Try to add a channel with invalid pin index
    adc.add_channel("INVALID", pin_or_index=999, divider_multiplier=1.0)
    
    # Channel should not be added
    assert "INVALID" not in adc.channels
    
    print("✓ ADCManager invalid pin index test passed")


def test_adc_manager_lazy_loading():
    """Test that ADCManager handles missing libraries gracefully."""
    print("\nTesting ADCManager lazy loading behavior...")
    
    # This test verifies that the manager is designed to handle import failures
    # The actual import failure is hard to test in this environment, but we can
    # verify that the structure supports it.
    
    mock_i2c = MockModule()
    adc = ADCManager(mock_i2c)
    
    # If hardware failed to initialize, hardware would be None
    # In this mock environment, it should succeed
    assert adc.hardware is not None
    
    # But if we simulate a failed init:
    adc_failed = ADCManager(mock_i2c, chip_type="UNKNOWN")
    assert adc_failed.hardware is None
    
    # And reads should return 0.0 safely
    assert adc_failed.read("ANYTHING") == 0.0
    assert adc_failed.read_all() == {}
    
    print("✓ ADCManager lazy loading test passed")


def test_adc_manager_native_initialization():
    """Test ADCManager initializes with NATIVE chip type."""
    print("\nTesting ADCManager native ADC initialization...")
    
    # For native ADC, i2c_bus should be None
    adc = ADCManager(i2c_bus=None, chip_type="NATIVE")
    
    assert adc.i2c_bus is None
    assert adc.chip_type == "NATIVE"
    assert adc.hardware is not None  # Should be True for native
    assert isinstance(adc.channels, dict)
    assert len(adc.channels) == 0
    
    print("✓ ADCManager native initialization test passed")


def test_adc_manager_native_add_channel():
    """Test adding native ADC channels."""
    print("\nTesting ADCManager native channel addition...")
    
    # Mock board pin
    class MockPin:
        pass
    
    mock_pin = MockPin()
    
    adc = ADCManager(i2c_bus=None, chip_type="NATIVE")
    
    # Add a native 20V channel with voltage divider
    adc.add_channel("20V_INPUT", mock_pin, divider_multiplier=11.0)
    
    assert "20V_INPUT" in adc.channels
    assert adc.channels["20V_INPUT"]["multiplier"] == 11.0
    assert adc.channels["20V_INPUT"]["type"] == "NATIVE"
    assert adc.channels["20V_INPUT"]["analog_in"] is not None
    
    print("✓ ADCManager native channel addition test passed")


def test_adc_manager_native_read_channel():
    """Test reading voltage from a native ADC channel."""
    print("\nTesting ADCManager native voltage reading...")
    
    class MockPin:
        pass
    
    mock_pin = MockPin()
    
    adc = ADCManager(i2c_bus=None, chip_type="NATIVE")
    adc.add_channel("20V_INPUT", mock_pin, divider_multiplier=11.0)
    
    # Mock the analog_in value (simulating 1.81V at the pin = 19.91V with 11x multiplier)
    # Native ADC value is 0-65535 for 0-3.3V
    # 1.81V = (1.81/3.3) * 65535 = 35931
    adc.channels["20V_INPUT"]["analog_in"].value = 35931
    
    voltage = adc.read("20V_INPUT")
    expected = 1.81 * 11.0  # Should be ~19.91V
    
    assert abs(voltage - expected) < 0.1, f"Expected ~{expected}V, got {voltage}V"
    
    print(f"  ✓ Read voltage: {voltage}V (expected ~{expected}V)")
    print("✓ ADCManager native voltage reading test passed")


def test_adc_manager_mixed_channels():
    """Test ADCManager with both I2C and native channels would work independently."""
    print("\nTesting ADCManager design supports mixed usage...")
    
    # Create I2C ADC manager
    mock_i2c = MockModule()
    adc_i2c = ADCManager(mock_i2c, chip_type="ADS1115")
    adc_i2c.add_channel("I2C_CHANNEL", 0, divider_multiplier=2.0)
    
    # Create native ADC manager
    class MockPin:
        pass
    
    mock_pin = MockPin()
    adc_native = ADCManager(i2c_bus=None, chip_type="NATIVE")
    adc_native.add_channel("NATIVE_CHANNEL", mock_pin, divider_multiplier=11.0)
    
    # Both should work independently
    assert "I2C_CHANNEL" in adc_i2c.channels
    assert "NATIVE_CHANNEL" in adc_native.channels
    
    # Verify types are correct
    assert adc_i2c.channels["I2C_CHANNEL"]["type"] == "I2C"
    assert adc_native.channels["NATIVE_CHANNEL"]["type"] == "NATIVE"
    
    print("  ✓ I2C and native ADC managers work independently")
    print("✓ ADCManager mixed channels test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("ADCManager Test Suite")
    print("=" * 60)
    
    test_adc_manager_initialization()
    test_adc_manager_add_channel()
    test_adc_manager_read_channel()
    test_adc_manager_read_nonexistent_channel()
    test_adc_manager_read_all()
    test_adc_manager_voltage_divider_math()
    test_adc_manager_unsupported_chip()
    test_adc_manager_invalid_pin_index()
    test_adc_manager_lazy_loading()
    test_adc_manager_native_initialization()
    test_adc_manager_native_add_channel()
    test_adc_manager_native_read_channel()
    test_adc_manager_mixed_channels()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print()
    print("ADCManager successfully implements:")
    print("  • Lazy-loading hardware libraries")
    print("  • Generic ADC channel mapping")
    print("  • Automatic voltage divider math")
    print("  • Graceful degradation when hardware is offline")
    print("  • Support for ADS1115 I2C ADC chips")
    print("  • Support for native analogio ADC pins")
    print("  • Uniform interface for both I2C and native ADCs")
