# ADC Manager Integration Example

This document provides examples of how to integrate the ADCManager into the JEB CoreManager for voltage monitoring using an I2C ADC chip (ADS1115).

## Overview

The ADCManager provides a generic interface for I2C-based ADC chips, allowing you to offload voltage monitoring from the Raspberry Pi Pico's native ADC pins. This frees up the native ADC pins for time-critical tasks like audio loopback for spectrum analysis.

## Basic Integration

### Step 1: Import ADCManager

```python
from managers import ADCManager
```

### Step 2: Initialize ADCManager in CoreManager.__init__()

Add this after the I2C bus initialization (around line 156 in core_manager.py):

```python
# Init I2C bus
self.i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)

# Init ADC Manager for voltage monitoring (optional hardware)
# This uses lazy loading - if the ADS1115 isn't connected, it gracefully disables
self.adc = ADCManager(self.i2c, chip_type="ADS1115", address=0x48)

# Configure voltage monitoring channels
# R1=100kΩ, R2=10kΩ -> 1/11 divider -> Multiplier is 11.0
self.adc.add_channel("20V_MAIN", pin_index=0, divider_multiplier=11.0)
self.adc.add_channel("20V_SAT", pin_index=1, divider_multiplier=11.0)

# R1=10kΩ, R2=10kΩ -> 1/2 divider -> Multiplier is 2.0
self.adc.add_channel("5V_LED", pin_index=2, divider_multiplier=2.0)
self.adc.add_channel("5V_LOGIC", pin_index=3, divider_multiplier=2.0)
```

### Step 3: Reading Voltages

#### Read a Single Channel

```python
# In your game mode or monitoring code
voltage_20v = self.core.adc.read("20V_MAIN")
print(f"Main 20V Bus: {voltage_20v}V")
```

#### Read All Channels

```python
# Get all voltage readings at once
voltages = self.core.adc.read_all()
# Returns: {"20V_MAIN": 19.91, "20V_SAT": 19.85, "5V_LED": 5.02, "5V_LOGIC": 5.01}

for name, voltage in voltages.items():
    print(f"{name}: {voltage}V")
```

## Hardware Configuration

### ADS1115 Wiring

- **VDD** -> 3.3V (Pico pin 36)
- **GND** -> GND
- **SCL** -> GP5 (I2C_SCL)
- **SDA** -> GP4 (I2C_SDA)
- **ADDR** -> GND (for address 0x48)

### Voltage Dividers

For each voltage rail you want to monitor, connect a voltage divider:

#### 20V Rails (Main Input and Satellite Bus)
```
20V ----[ 100kΩ ]---- ADC Pin ----[ 10kΩ ]---- GND
                      (A0 or A1)
```
This creates an 11:1 divider (100k + 10k = 110k total, 10k to ground)
- 20V → 1.82V at ADC pin
- Use `divider_multiplier=11.0`

#### 5V Rails (LED and Logic)
```
5V ----[ 10kΩ ]---- ADC Pin ----[ 10kΩ ]---- GND
                     (A2 or A3)
```
This creates a 2:1 divider
- 5V → 2.5V at ADC pin
- Use `divider_multiplier=2.0`

## Crash-Proof Design

The ADCManager is designed to fail gracefully:

1. **Missing Library**: If `adafruit_ads1x15` isn't installed, it prints a warning and disables itself
2. **Missing Hardware**: If the ADS1115 isn't connected to I2C, it catches the error and disables itself
3. **Safe Reads**: When disabled, `read()` and `read_all()` return 0.0 safely

This ensures your JADNET core won't crash just because the ADC module isn't plugged in.

## Example: Replacing PowerManager with ADCManager

If you want to completely migrate from native ADC to I2C ADC:

### Before (using native ADC via PowerManager)
```python
self.power = PowerManager(
    Pins.SENSE_PINS,  # GP26-GP29
    [POW_INPUT, POW_BUS, POW_MAIN, POW_LED],
    Pins.MOSFET_CONTROL,
    Pins.SATBUS_DETECT,
)

# Later in code:
voltages = self.power.status
```

### After (using I2C ADC via ADCManager)
```python
# Keep PowerManager for MOSFET control, but without ADC pins
# (You'll need to modify PowerManager to make ADC optional)

# Add ADCManager for voltage monitoring
self.adc = ADCManager(self.i2c)
self.adc.add_channel("20V_MAIN", 0, 11.0)
self.adc.add_channel("20V_SAT", 1, 11.0)
self.adc.add_channel("5V_LED", 2, 2.0)
self.adc.add_channel("5V_LOGIC", 3, 2.0)

# Later in code:
voltages = self.adc.read_all()
```

## I2C Address Configuration

The ADS1115 supports four I2C addresses (selectable via ADDR pin):
- **0x48** (ADDR to GND) - Default
- **0x49** (ADDR to VDD)
- **0x4A** (ADDR to SDA)
- **0x4B** (ADDR to SCL)

If you need multiple ADS1115 chips, you can initialize multiple managers:

```python
self.adc_primary = ADCManager(self.i2c, address=0x48)
self.adc_secondary = ADCManager(self.i2c, address=0x49)
```

## Audio Loopback Circuit

Once you've freed up GP26-GP29, you can use one for audio loopback:

```python
# In Pins.initialize() for CORE profile:
cls.ADC_AUDIO_IN = getattr(board, "GP26")  # Now free for audio!
```

The audio loopback requires a DC bias circuit to center the AC audio signal:
- 10kΩ from 3.3V to GP26
- 10kΩ from GND to GP26
- 1µF capacitor from I2S DAC output to GP26

This creates a 1.65V bias point, allowing the full audio waveform to be captured.

## Testing

Run the ADCManager test suite to verify your installation:

```bash
python tests/test_adc_manager.py
```

All tests should pass, demonstrating:
- Lazy loading
- Channel configuration
- Voltage divider math
- Error handling
