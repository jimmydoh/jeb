# ADCManager Extension: Edge Cases and Extensibility Guide

## Overview

This document details edge cases, design considerations, and extensibility guidelines for the ADCManager extension that supports both I2C ADC expansion boards and native analogio pins.

## Architecture Overview

### Design Principles

1. **Uniform Interface**: All ADC access goes through ADCManager, regardless of source
2. **Centralized Configuration**: Pin assignments and voltage dividers defined in Pins.py
3. **Lazy Loading**: Graceful degradation when hardware is missing
4. **Type Safety**: Clear separation between I2C and native ADC handling

### Component Roles

- **ADCManager**: Generic ADC interface supporting both I2C and native pins
- **Pins.py**: Centralized pin mapping and ADC configuration per firmware type
- **PowerManager**: Consumer that uses ADCManager for voltage sensing
- **CoreManager/SatelliteFirmware**: Initialize and wire components together

## Edge Cases

### 1. Role Assignment Conflicts

**Issue**: What if multiple firmware types try to use the same physical pin for different roles?

**Solution**: 
- Each firmware type has its own profile in Pins.py (e.g., "CORE", "SAT")
- Pin assignments are profile-specific and never overlap
- ADC_CONFIG is defined per profile, ensuring proper role assignment

**Example**:
```python
# CORE profile uses GP26-GP29 for voltage sensing
if profile == "CORE":
    cls.ADC_SENSE_A = board.GP26  # Pre-MOSFET 20V
    cls.ADC_SENSE_B = board.GP27  # Post-MOSFET 20V
    cls.ADC_SENSE_C = board.GP28  # 5V Logic
    cls.ADC_SENSE_D = board.GP29  # 5V LED

# SAT profile uses same pins but may have different roles
elif profile == "SAT":
    cls.ADC_SENSE_A = board.GP26  # Pre-MOSFET 20V
    cls.ADC_SENSE_B = board.GP27  # Post-MOSFET 20V
    cls.ADC_SENSE_C = board.GP28  # 5V Main
    # GP29 spare - no LED rail in SAT
```

### 2. Mixed ADC Types on Same Board

**Issue**: What if a future board needs both I2C ADC and native ADC simultaneously?

**Solution**:
- Create multiple ADCManager instances (one per type)
- Pass appropriate instance to each consumer
- ADC_CONFIG can be extended to support multiple ADC types

**Example**:
```python
# Future board with both types
cls.ADC_CONFIG = {
    "primary": {
        "chip_type": "NATIVE",
        "channels": [...]
    },
    "expansion": {
        "chip_type": "ADS1115",
        "address": 0x48,
        "channels": [...]
    }
}

# In manager initialization
self.adc_native = ADCManager(None, chip_type="NATIVE")
self.adc_i2c = ADCManager(i2c_bus, chip_type="ADS1115")
```

### 3. Hardware Initialization Failure

**Issue**: What if ADC hardware fails to initialize?

**Solution**:
- ADCManager uses lazy loading with try/except
- `hardware` field set to None on failure
- `read()` returns 0.0 for missing hardware
- Warning messages printed but system continues

**Behavior**:
```python
# Hardware init fails
⚠️ ADCManager: Hardware not found on I2C bus. (error details)

# Reads return safe defaults
voltage = adc.read("channel_name")  # Returns 0.0
all_voltages = adc.read_all()      # Returns {}
```

### 4. Voltage Divider Calibration

**Issue**: How to handle boards with different voltage divider ratios?

**Solution**:
- Voltage divider multipliers defined as module-level constants in Pins.py
- Easy to adjust per firmware type or create calibration system
- Named constants (DIVIDER_MULTIPLIER_20V, DIVIDER_MULTIPLIER_5V) improve clarity

**Calibration Path**:
```python
# Current approach - compile-time constants
DIVIDER_MULTIPLIER_20V = 1 / 0.1263  # ≈7.919

# Future calibration extension
def load_calibration():
    """Load calibration from config file"""
    config = read_config()
    return {
        "20V": config.get("cal_20v", DIVIDER_MULTIPLIER_20V),
        "5V": config.get("cal_5v", DIVIDER_MULTIPLIER_5V)
    }
```

### 5. Channel Name Collisions

**Issue**: What if different ADC managers use the same channel name?

**Solution**:
- Channel names scoped to individual ADCManager instance
- PowerManager references channels by name within its ADC instance
- Use prefixes if multiple ADCManagers needed (e.g., "native_input_20v", "i2c_input_20v")

### 6. Dynamic Pin Assignment

**Issue**: Can pins be reassigned at runtime?

**Current**: 
- Pin assignments are static, set during Pins.initialize()
- ADCManager channels added during initialization

**Future Extension**:
```python
# Could add runtime channel management
def reconfigure_adc(adc_manager, new_config):
    """Dynamically reconfigure ADC channels"""
    # Clear existing channels
    adc_manager.channels.clear()
    
    # Add new channels
    for ch in new_config["channels"]:
        adc_manager.add_channel(ch["name"], ch["pin"], ch["multiplier"])
```

## Extensibility Guidelines

### Adding New Firmware Types

To add a new firmware type (e.g., "SAT" Type 02):

1. **Add profile to Pins.py**:
```python
elif profile == "SAT" and type_id == "02":
    # Define pin assignments
    cls.ADC_SENSE_A = board.GP26
    cls.ADC_SENSE_B = board.GP27
    # ... more pins
    
    # Define ADC configuration
    cls.ADC_CONFIG = {
        "chip_type": "NATIVE",  # or "ADS1115"
        "address": None,         # or 0x48 for I2C
        "channels": [
            {"name": "role_name", "pin": cls.PIN, "multiplier": DIVIDER},
            # ... more channels
        ]
    }
```

2. **Initialize managers in firmware**:
```python
# In satellite firmware __init__
Pins.initialize(profile="SAT", type_id="02")
adc_config = Pins.ADC_CONFIG
self.adc = ADCManager(
    i2c_bus=self.i2c if adc_config["chip_type"] != "NATIVE" else None,
    chip_type=adc_config["chip_type"],
    address=adc_config.get("address", 0x48)
)
for ch in adc_config["channels"]:
    self.adc.add_channel(ch["name"], ch["pin"], ch["multiplier"])
```

### Adding New ADC Chip Types

To support a new I2C ADC chip (e.g., ADS1015):

1. **Extend ADCManager._lazy_init()**:
```python
elif self.chip_type == "ADS1015":
    try:
        import adafruit_ads1x15.ads1015 as ADS
        self.ads_module = ADS
        self.hardware = ADS.ADS1015(self.i2c_bus, address=self.address)
        print(f"✅ ADCManager: {self.chip_type} initialized at {hex(self.address)}")
    except Exception as e:
        print(f"⚠️ ADCManager: Hardware init failed. ({e})")
```

2. **Extend add_channel() if needed**:
```python
elif self.chip_type == "ADS1015":
    # Similar to ADS1115, may have different pin mapping
    pin_map = {0: self.ads_module.P0, ...}
    # ... rest of implementation
```

### Adding New Consumer Types

To create a new ADC consumer (beyond PowerManager):

1. **Accept ADCManager in constructor**:
```python
class SensorManager:
    def __init__(self, adc_manager, sensor_channels):
        self.adc = adc_manager
        self.channels = sensor_channels
```

2. **Read through ADCManager**:
```python
def read_sensor(self, sensor_name):
    return self.adc.read(sensor_name)
```

3. **Initialize with appropriate ADC instance**:
```python
# In CoreManager or firmware
self.sensors = SensorManager(self.adc, ["temp", "humidity"])
```

## Best Practices

### 1. Configuration Over Code

**DO**: Define hardware specifics in Pins.py
```python
cls.ADC_CONFIG = {
    "chip_type": "NATIVE",
    "channels": [{"name": "input_20v", ...}]
}
```

**DON'T**: Hardcode in manager
```python
self.adc = ADCManager(None, "NATIVE")
self.adc.add_channel("input_20v", board.GP26, 7.919)
```

### 2. Use Named Constants

**DO**: Module-level constants for voltage dividers
```python
DIVIDER_MULTIPLIER_20V = 1 / 0.1263
cls.ADC_CONFIG["channels"][0]["multiplier"] = DIVIDER_MULTIPLIER_20V
```

**DON'T**: Inline calculations
```python
{"multiplier": 1/0.1263}
```

### 3. Graceful Degradation

**DO**: Check for hardware availability
```python
if self.adc.hardware:
    voltage = self.adc.read("input_20v")
else:
    voltage = 0.0  # Safe default
```

**DON'T**: Assume hardware is always present
```python
voltage = self.adc.read("input_20v")  # May fail silently
```

### 4. Clear Naming

**DO**: Descriptive channel names
```python
{"name": "input_20v", ...}  # Clear purpose
{"name": "satbus_20v", ...}  # Clear purpose
```

**DON'T**: Generic names
```python
{"name": "ch0", ...}  # What does it measure?
{"name": "adc1", ...}  # Not descriptive
```

## Testing Considerations

### Unit Tests

- Mock both I2C and native ADC hardware
- Test lazy loading and error conditions
- Verify voltage divider math
- Test graceful degradation

### Integration Tests

- Test PowerManager with ADCManager
- Verify all profiles (CORE, SAT)
- Test with missing hardware
- Validate backward compatibility

### Hardware Tests

When testing on actual hardware:
1. Verify voltage readings with multimeter
2. Test under load conditions
3. Validate max/min tracking
4. Test MOSFET control timing

## Migration Guide

For existing code using direct analogio:

**Before**:
```python
import analogio
self.adc_pin = analogio.AnalogIn(board.GP26)
voltage = (self.adc_pin.value * 3.3 / 65535) / 0.1263
```

**After**:
```python
from managers.adc_manager import ADCManager
self.adc = ADCManager(None, chip_type="NATIVE")
self.adc.add_channel("voltage", board.GP26, 1/0.1263)
voltage = self.adc.read("voltage")
```

## Future Enhancements

Potential future improvements:

1. **Runtime Calibration**: Load voltage divider multipliers from config
2. **Multi-ADC Support**: Single manager handling multiple ADC chips
3. **Averaging**: Built-in averaging for noise reduction
4. **Alerts**: Voltage threshold monitoring with callbacks
5. **Logging**: Historical voltage data with timestamps
6. **Auto-ranging**: Automatic gain adjustment for I2C ADCs

## Summary

The ADCManager extension provides a robust, extensible foundation for ADC management in the JEB system. By centralizing configuration in Pins.py and using a uniform interface, the system can easily support:

- Multiple firmware types with different pin assignments
- Mixed I2C and native ADC configurations
- Future board configurations and ADC chip types
- Graceful degradation when hardware fails
- Easy calibration and adjustment

The design prioritizes safety, clarity, and maintainability while preserving backward compatibility with existing code.
