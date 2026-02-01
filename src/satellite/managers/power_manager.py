"""
Docstring for satellite.managers.power_manager
"""

import asyncio
import analogio
import digitalio
import board

class PowerManager:
    """Satellite-side Power Management to mirror Master safety logic."""
    def __init__(self, sense_pins, mosfet_pin, detect_pin):
        # ADC Assignments per Satellite Header
        self.sense_input = analogio.AnalogIn(sense_pins[0])   # 20V Input from Upstream
        self.sense_satbus = analogio.AnalogIn(sense_pins[1])  # 20V Output to Downstream
        self.sense_logbus = analogio.AnalogIn(sense_pins[2])  # 5V Logic Rail (Post-Buck)

        # MOSFET Control (GP14 -> 2N3904 -> IRF5305)
        self.sat_pwr = digitalio.DigitalInOut(mosfet_pin)
        self.sat_pwr.direction = digitalio.Direction.OUTPUT
        self.sat_pwr.value = False

        # Connection Sense Pin (GP15)
        # In JADNET STD, Pins 7&8 bridge to GND on the Downstream Sat-Side
        self.sat_detect = digitalio.DigitalInOut(detect_pin)
        self.sat_detect.pull = digitalio.Pull.UP

        # Scaling Factors (Matching Master Ratios)
        self.RATIO_20V = 0.1263  # 47k / 6.8k divider
        self.RATIO_5V = 0.5      # 10k / 10k divider

        # Voltage Tracking: [Last, Max, Min]
        self.v_input = [0.0, 0.0, 99.0]
        self.v_satbus = [0.0, 0.0, 99.0]
        self.v_logicbus = [0.0, 0.0, 99.0]

    def get_v(self, sensor, ratio):
        """Standardized voltage calculation for RP2350 ADC."""
        return round(((sensor.value * 3.3) / 65535) / ratio, 2)

    @property
    def status(self):
        """Updates and returns current rail voltages."""
        self.v_input[0] = self.get_v(self.sense_input, self.RATIO_20V)
        self.v_satbus[0] = self.get_v(self.sense_satbus, self.RATIO_20V)
        self.v_logicbus[0] = self.get_v(self.sense_logbus, self.RATIO_5V)

        # Update max/min records for diagnostics
        for rail in [self.v_input, self.v_satbus, self.v_logicbus]:
            if rail[0] > rail[1]: rail[1] = rail[0]
            if rail[0] < rail[2] or rail[2] == 0.0: rail[2] = rail[0]

        return {
            "in": self.v_input[0],
            "bus": self.v_satbus[0],
            "log": self.v_logicbus[0]
        }

    @property
    def satbus_connected(self):
        """Detects if a downstream RJ45 is physically plugged in."""
        return not self.sat_detect.value

    async def soft_start_downstream(self):
        """Enables 20V pass-through to the next Satellite in the chain."""
        v = self.status
        if v["in"] < 18.0:
            return False, "LOW UPSTREAM VOLTAGE"

        self.sat_pwr.value = True
        await asyncio.sleep(0.5) # Wait for downstream inrush/stabilization

        if self.status["bus"] < 17.0:
            self.sat_pwr.value = False
            return False, "DOWNSTREAM BUS BROWNOUT"
        return True, "OK"

    def emergency_kill(self):
        """Instant hardware cut-off of the downstream power rail."""
        self.sat_pwr.value = False
