## Satellite Development Guide

### Creating New Satellites

All satellite firmware classes must inherit from `SatelliteFirmware` (defined in `src/satellites/base_firmware.py`). To ensure system stability, the following methods **must** be implemented by any subclass:

1.  **`custom_start(self)`**
    * **Purpose**: Handles satellite-specific hardware initialization (e.g., setting up I2C, specific GPIO, or initial state).
    * **Behavior**: Must be an `async` method.

2.  **`_get_status_bytes(self)`**
    * **Purpose**: Returns the binary status payload for telemetry.
    * **Behavior**: Must return a `bytes` object representing the current state (e.g., button states, sensor values).

**Example:**

```python
class MyNewSatellite(SatelliteFirmware):
    async def custom_start(self):
        # Initialize custom hardware
        self.sensor = MySensor()
        await self.sensor.start()

    def _get_status_bytes(self):
        # Return 1 byte of status
        return bytes([0x01 if self.sensor.active else 0x00])
```
Note: The system validates these requirements at import time. If a subclass fails to implement them, a `TypeError` will be raised immediately.
