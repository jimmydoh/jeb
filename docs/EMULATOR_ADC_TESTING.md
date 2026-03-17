# Emulator ADC Testing Guide

> **Note:** The interactive emulator described in this guide (`tests/emulator/run_emulator.py`)
> has not yet been implemented. This document captures the intended design and is retained
> for reference when development begins. For current ADC testing, use the existing unit
> tests in `tests/test_adc_manager.py`.

This guide describes the planned JEB emulator design for testing ADCManager and voltage monitoring functionality interactively.

## Overview

The planned emulator will support both native ADC (analogio) and I2C ADC (ADS1115) mocking, allowing you to:
- Test brownout detection logic
- Simulate power failures
- Test soft_start_satellites() functionality
- Verify voltage monitoring without physical hardware

## Planned Keyboard Controls

The emulator will provide the following keyboard shortcuts for voltage manipulation:

### Native ADC (analogio) Controls
- **V** - Drop voltage on native ADC pin (GP26) to ~0.5V (simulates brownout)
- **B** - Restore voltage on native ADC pin to healthy ~2.5V

### I2C ADC (ADS1115) Controls
- **N** - Drop voltage on I2C ADC channel P0 to 0.5V (simulates brownout)
- **M** - Restore voltage on I2C ADC channel P0 to healthy 2.5V

### Other Controls
- **P** - Toggle satellite cable connection (hot-plug simulation)

## Planned Testing Scenarios

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

## Technical Design

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

Both mocks will register themselves with the HardwareMocks system:
- Native pins: `HardwareMocks.get("CORE", "analog_pin", "board.GP26")`
- I2C channels: `HardwareMocks.get("CORE", "ads_channel", 0)` for P0

The Pygame UI will use this registry to manipulate voltage values in real-time.

## Default Voltage Values

### Native ADC
- Healthy: 49650 raw (about 2.5V at 3.3V reference)
- With PowerManager RATIO_20V (0.1263): represents ~19.8V on the 20V rail (2.5V / 0.1263)
- With PowerManager RATIO_5V (0.5): represents ~5.0V on the 5V rail (2.5V / 0.5)

### I2C ADC (ADS1115)
- Healthy: 2.5V direct reading
- Through 11:1 divider: represents ~27.5V on the rail (2.5V × 11.0)
- Through 2:1 divider: represents ~5V on the rail (2.5V × 2.0)

## Current Testing (Unit Tests)

Until the interactive emulator is available, use the existing unit tests:

```bash
# Run ADC Manager tests
python tests/test_adc_manager.py

# Run power manager tests
python tests/test_power_manager_with_adc.py

# All tests should pass with the mocks
```

## See Also

- [ADC Manager Integration Guide](ADC_MANAGER_INTEGRATION.md) - How to use ADCManager in your code
- [ADC Manager Extension Guide](ADC_MANAGER_EXTENSION.md) - Edge cases and extensibility
