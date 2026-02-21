#!/usr/bin/env python3
"""Unit tests for PowerManager using PowerBus/ADCSensorWrapper for voltage sensing."""

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
    """Mock ADCManager for testing PowerBus via ADCSensorWrapper."""
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
from utilities.power_bus import ADCSensorWrapper, INASensorWrapper, PowerBus


class MockPin:
    """Minimal mock for a hardware pin."""
    pass


def _make_buses(mock_adc, names):
    """Helper: build a buses dict from an ADCManager and a list of rail names."""
    return {
        name: PowerBus(name, ADCSensorWrapper(mock_adc, name))
        for name in names
    }


def test_power_manager_initialization():
    """Test PowerManager initializes with PowerBus dependencies."""
    print("Testing PowerManager initialization with PowerBus...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v", "satbus_20v", "main_5v", "led_5v"]
    buses = _make_buses(mock_adc, sense_names)
    
    power = PowerManager(buses, MockPin(), MockPin())
    
    assert power.buses is buses
    assert set(power.buses.keys()) == set(sense_names)
    for name in sense_names:
        assert isinstance(power.buses[name], PowerBus)
    
    print("✓ PowerManager initialization test passed")


def test_power_manager_status():
    """Test PowerManager reads voltages from PowerBus/ADCSensorWrapper."""
    print("\nTesting PowerManager voltage status reading...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v", "satbus_20v", "main_5v", "led_5v"]
    buses = _make_buses(mock_adc, sense_names)
    
    power = PowerManager(buses, MockPin(), MockPin())
    
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
    """Test PowerManager tracks max and min voltages via PowerBus."""
    print("\nTesting PowerManager max/min voltage tracking...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v", "satbus_20v"]
    buses = _make_buses(mock_adc, sense_names)
    
    power = PowerManager(buses, MockPin(), MockPin())
    
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
    buses = _make_buses(mock_adc, ["input_20v"])
    
    power = PowerManager(buses, MockPin(), MockPin())
    
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
    """Test that PowerManager exposes the same public APIs as before."""
    print("\nTesting PowerManager backward compatibility...")
    
    mock_adc = MockADCManager()
    sense_names = ["input_20v", "satbus_20v", "main_5v", "led_5v"]
    buses = _make_buses(mock_adc, sense_names)
    
    power = PowerManager(buses, MockPin(), MockPin())
    
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
    buses = _make_buses(mock_adc, sense_names)
    
    power = PowerManager(buses, MockPin(), MockPin())
    
    status = power.status
    
    # Should only have 3 channels
    assert len(status) == 3
    assert "input_20v" in status
    assert "satbus_20v" in status
    assert "main_5v" in status
    assert "led_5v" not in status
    
    print(f"  ✓ Satellite profile status: {status}")
    print("✓ PowerManager satellite profile test passed")


def test_power_bus_adc_sensor_wrapper():
    """Test ADCSensorWrapper capability flags and reads."""
    print("\nTesting ADCSensorWrapper...")
    
    mock_adc = MockADCManager()
    wrapper = ADCSensorWrapper(mock_adc, "input_20v")
    
    assert wrapper.HAS_CURRENT == False
    assert wrapper.HAS_POWER == False
    assert abs(wrapper.read_voltage() - 19.5) < 0.01
    assert wrapper.read_current() is None
    assert wrapper.read_power() is None
    
    print("✓ ADCSensorWrapper test passed")


def test_power_bus_ina_sensor_wrapper():
    """Test INASensorWrapper capability flags and reads."""
    print("\nTesting INASensorWrapper...")
    
    class MockINA:
        voltage = 19.8
        current = 1250.0
        power = 24750.0
    
    wrapper = INASensorWrapper(MockINA())
    
    assert wrapper.HAS_CURRENT == True
    assert wrapper.HAS_POWER == True
    assert abs(wrapper.read_voltage() - 19.8) < 0.01
    assert abs(wrapper.read_current() - 1250.0) < 0.01
    assert abs(wrapper.read_power() - 24750.0) < 0.01
    
    print("✓ INASensorWrapper test passed")


def test_power_bus_update_and_tracking():
    """Test PowerBus.update() tracks v_now, v_min, v_max correctly."""
    print("\nTesting PowerBus state tracking...")
    
    mock_adc = MockADCManager()
    mock_adc.set_reading("input_20v", 19.5)
    bus = PowerBus("input_20v", ADCSensorWrapper(mock_adc, "input_20v"))
    
    bus.update()
    assert bus.v_now == 19.5
    
    mock_adc.set_reading("input_20v", 20.5)
    bus.update()
    assert bus.v_max == 20.5
    
    mock_adc.set_reading("input_20v", 18.0)
    bus.update()
    assert bus.v_min == 18.0
    
    # ADC bus has no current capability
    assert bus.has_current == False
    assert bus.i_now is None
    
    print("✓ PowerBus state tracking test passed")


def test_power_bus_ina_current_tracking():
    """Test PowerBus tracks i_now / i_max for INA-backed buses."""
    print("\nTesting PowerBus INA current tracking...")
    
    class MockINA:
        def __init__(self):
            self.bus_voltage = 19.8
            self.current = 500.0
            self.power = 9900.0
    
    ina = MockINA()
    bus = PowerBus("input_20v", INASensorWrapper(ina))
    
    assert bus.has_current == True
    assert bus.has_power == True
    
    bus.update()
    assert bus.i_now == 500.0
    assert bus.i_max == 500.0
    
    ina.current = 800.0
    bus.update()
    assert bus.i_now == 800.0
    assert bus.i_max == 800.0
    
    ina.current = 300.0
    bus.update()
    assert bus.i_now == 300.0
    assert bus.i_max == 800.0  # i_max unchanged
    
    print("✓ PowerBus INA current tracking test passed")


def test_get_telemetry_payload():
    """Test PowerManager.get_telemetry_payload() respects capability flags."""
    print("\nTesting get_telemetry_payload()...")
    
    mock_adc = MockADCManager()
    
    # ADC-only bus
    adc_bus = PowerBus("input_20v", ADCSensorWrapper(mock_adc, "input_20v"))
    adc_bus.update()
    
    # INA-backed bus
    class MockINA:
        bus_voltage = 4.95
        current = 200.0
        power = 990.0
    ina_bus = PowerBus("main_5v", INASensorWrapper(MockINA()))
    ina_bus.update()
    
    power = PowerManager(
        {"input_20v": adc_bus, "main_5v": ina_bus},
        MockPin(), MockPin()
    )
    
    payload = power.get_telemetry_payload()
    
    # ADC rail: only voltage
    assert "v" in payload["input_20v"]
    assert "i" not in payload["input_20v"]
    assert "p" not in payload["input_20v"]
    
    # INA rail: voltage + current + power
    assert "v" in payload["main_5v"]
    assert "i" in payload["main_5v"]
    assert "p" in payload["main_5v"]
    assert abs(payload["main_5v"]["i"] - 200.0) < 0.01
    assert abs(payload["main_5v"]["p"] - 990.0) < 0.01
    
    print(f"  ✓ Payload: {payload}")
    print("✓ get_telemetry_payload() test passed")


if __name__ == "__main__":
    print("=" * 60)
    print("PowerManager with PowerBus/ADCSensorWrapper Test Suite")
    print("=" * 60)
    
    test_power_manager_initialization()
    test_power_manager_status()
    test_power_manager_max_min_tracking()
    test_power_manager_mosfet_control()
    test_power_manager_backward_compatibility()
    test_power_manager_sat_profile()
    test_power_bus_adc_sensor_wrapper()
    test_power_bus_ina_sensor_wrapper()
    test_power_bus_update_and_tracking()
    test_power_bus_ina_current_tracking()
    test_get_telemetry_payload()
    
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print()
    print("PowerManager successfully uses the PowerBus abstraction:")
    print("  • Reads voltages through ADCSensorWrapper/INASensorWrapper")
    print("  • Maintains all original APIs for backward compatibility")
    print("  • Tracks max/min voltages correctly")
    print("  • MOSFET control works as expected")
    print("  • Supports both Core and Satellite profiles")
    print("  • Telemetry payload respects sensor capabilities")

