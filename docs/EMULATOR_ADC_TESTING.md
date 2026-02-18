# Emulator ADC Testing Guide

This guide explains how to use the JEB emulator to test ADCManager and voltage monitoring functionality.

## Overview

The emulator now supports both native ADC (analogio) and I2C ADC (ADS1115) mocking, allowing you to:
- Test brownout detection logic
- Simulate power failures
- Test soft_start_satellites() functionality
- Verify voltage monitoring without physical hardware

## Keyboard Controls

The emulator provides the following keyboard shortcuts for voltage manipulation:

### Native ADC (analogio) Controls
- **V** - Drop voltage on native ADC pin (GP26) to ~0.5V (simulates brownout)
- **B** - Restore voltage on native ADC pin to healthy ~2.5V

### I2C ADC (ADS1115) Controls
- **N** - Drop voltage on I2C ADC channel P0 to 0.5V (simulates brownout)
- **M** - Restore voltage on I2C ADC channel P0 to healthy 2.5V

### Other Controls
- **P** - Toggle satellite cable connection (hot-plug simulation)

## Testing Scenarios

### Scenario 1: Test Brownout Detection (Native ADC)

If your code uses PowerManager with native analog pins:

1. Start the emulator: `python tests/emulator/run_emulator.py`
2. Wait for the system to boot normally
3. Press **V** to simulate a voltage drop
4. Observe console logs for brownout detection
5. Press **B** to restore voltage
6. System should recover

### Scenario 2: Test Brownout Detection (I2C ADC)

If your code uses ADCManager with ADS1115:

1. Start the emulator: `python tests/emulator/run_emulator.py`
2. Wait for the system to boot normally
3. Press **N** to simulate a voltage drop on I2C ADC
4. Observe console logs for brownout detection
5. Press **M** to restore voltage
6. System should recover

### Scenario 3: Test Soft Start with Brownout

1. Press **P** to unplug the satellite
2. Wait for the system to detect disconnection
3. Press **N** to pre-drop the voltage
4. Press **P** to plug in the satellite
5. The soft_start_satellites() should detect the brownout and kill power
6. Press **M** to restore voltage
7. Try plugging in again - should succeed

## Technical Details

### Native ADC Mock (analogio)

The native ADC mock returns 16-bit integer values (0-65535):
- Default: 49650 (~2.5V with 3.3V reference)
- Brownout: 10000 (~0.5V)
- Values are clamped to 16-bit range

### I2C ADC Mock (ADS1115)

The I2C ADC mock returns float voltage values:
- Default: 2.5V
- Brownout: 0.5V
- Voltage divider math is applied by ADCManager

### HardwareMocks Registry

Both mocks register themselves with the HardwareMocks system:
- Native pins: `HardwareMocks.get("CORE", "analog_pin", "board.GP26")`
- I2C channels: `HardwareMocks.get("CORE", "ads_channel", 0)` for P0

The Pygame UI uses this registry to manipulate voltage values in real-time.

## Default Voltage Values

### Native ADC
- Healthy: 49650 raw (about 2.5V at 3.3V reference)
- Through 11:1 divider: represents ~20V on the rail
- Through 2:1 divider: represents ~5V on the rail

### I2C ADC (ADS1115)
- Healthy: 2.5V direct reading
- Through 11:1 divider: represents ~27.5V on the rail
- Through 2:1 divider: represents ~5V on the rail

## Example Code Usage

### Programmatically Manipulating Voltage

```python
from jeb_emulator import HardwareMocks

# Simulate brownout on native ADC
native_pin = HardwareMocks.get("CORE", "analog_pin", "board.GP26")
if native_pin:
    native_pin.value = 10000  # Drops the voltage significantly

# Simulate brownout on I2C ADC
i2c_pin = HardwareMocks.get("CORE", "ads_channel", 0)  # 0 is P0
if i2c_pin:
    i2c_pin.voltage = 0.5  # Drop directly to 0.5V
```

## Troubleshooting

### "No native analog pin found at GP26"
This message appears if PowerManager isn't using GP26 for voltage sensing. Check your pin configuration in the Pins class.

### "No I2C ADC channel found at P0"
This message appears if ADCManager hasn't been initialized or channel 0 wasn't configured. Verify ADCManager is set up in CoreManager.

### Emulator crashes on startup
Ensure you're importing jeb_emulator.py before any JEB firmware code. The mocks must be set up first.

## Running Tests

The emulator mocks are tested in the test suite:

```bash
# Run ADC Manager tests
python tests/test_adc_manager.py

# All tests should pass with the mocks
```

## See Also

- [ADC Manager Integration Guide](ADC_MANAGER_INTEGRATION.md) - How to use ADCManager in your code
- [Emulator README](../tests/emulator/README.md) - General emulator usage
