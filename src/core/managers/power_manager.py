"""Manages power sensing and MOSFET control for satellite bus."""

import asyncio

import board
import analogio
import digitalio

class PowerManager:
    """Class to manage power sensing and MOSFET control for satellite bus."""
    def __init__(self, sense_pins, mosfet_pin, detect_pin):
        # ADC Assignments (ADC0-ADC3)
        self.sense_input = analogio.AnalogIn(sense_pins[0])  # Pre-MOSFET 20V Input
        self.sense_satbus = analogio.AnalogIn(sense_pins[1]) # Post-MOSFET 20V Bus
        self.sense_ledbus = analogio.AnalogIn(sense_pins[2]) # 5V LED Rail
        self.sense_logbus = analogio.AnalogIn(sense_pins[3]) # 5V Logic Rail

        # MOSFET Control
        self.sat_pwr = digitalio.DigitalInOut(mosfet_pin)
        self.sat_pwr.direction = digitalio.Direction.OUTPUT
        self.sat_pwr.value = False

        # Connection Sense Pin
        self.sat_detect = digitalio.DigitalInOut(detect_pin)
        self.sat_detect.pull = digitalio.Pull.UP # RJ45 Pins 7&8 bridge to GND

        # Scaling Factors
        self.RATIO_20V = 0.1263  # 47k / 6.8k
        self.RATIO_5V = 0.5      # 10k / 10k

        # Voltage Values
        self.v_input = [0.0, 0.0, 99.0] # Last, Max, Min
        self.v_satbus = [0.0, 0.0, 99.0] # Last, Max, Min
        self.v_ledbus = [0.0, 0.0, 99.0] # Last, Max, Min
        self.v_logicbus = [0.0, 0.0, 99.0] # Last, Max, Min

    def get_v(self, sensor, ratio):
        """Converts ADC reading to actual voltage based on divider ratio."""
        return round(((sensor.value * 3.3) / 65535) / ratio, 2)

    @property
    def status(self):
        """Primary touch point - updates voltage readings and returns as Dict."""
        self.v_input[0] = self.get_v(self.sense_input, self.RATIO_20V)
        self.v_satbus[0] = self.get_v(self.sense_satbus, self.RATIO_20V)
        self.v_ledbus[0] = self.get_v(self.sense_ledbus, self.RATIO_5V)
        self.v_logicbus[0] = self.get_v(self.sense_logbus, self.RATIO_5V)

        # Update max/min records
        for rail in [self.v_input, self.v_satbus, self.v_ledbus, self.v_logicbus]:
            if rail[0] > rail[1]: rail[1] = rail[0]
            if rail[0] < rail[2] or rail[2] == 0.0: rail[2] = rail[0]

        return {
            "raw": self.v_input[0],
            "bus": self.v_satbus[0],
            "led": self.v_ledbus[0],
            "log": self.v_logicbus[0]
        }

    @property
    def max(self):
        """Return maximum recorded voltages as Dict."""
        return {
            "raw": self.v_input[1],
            "bus": self.v_satbus[1],
            "led": self.v_ledbus[1],
            "log": self.v_logicbus[1]
        }

    @property
    def min(self):
        """Return minimum recorded voltages as Dict."""
        return {
            "raw": self.v_input[2],
            "bus": self.v_satbus[2],
            "led": self.v_ledbus[2],
            "log": self.v_logicbus[2]
        }

    @property
    def satbus_connected(self):
        """Returns True if satellite chain is physically connected."""
        return not self.sat_detect.value

    @property
    def satbus_powered(self):
        """Returns True if satellite bus power is enabled."""
        return self.sat_pwr.value

    async def soft_start_satellites(self):
        """Powers up the expansion chain with a safety check."""
        v = self.status
        if v["raw"] < 18.0:
            return False, "LOW INPUT VOLTAGE"

        self.sat_pwr.value = True
        await asyncio.sleep(0.5) # Wait for satellite buck converters

        if self.status["bus"] < 17.0:
            self.sat_pwr.value = False
            return False, "BUS BROWNOUT"
        return True, "OK"

    def emergency_kill(self):
        """Instant hardware cut-off for the satellite bus."""
        self.sat_pwr.value = False

    async def check_power_integrity(self):
        """Diagnostic check performed at boot and during play."""
        if self.v_input < 15.0:
            return False
        if self.v_input > 18.0 and self.v_satbus < 1.0:
            return False
        return True


    async def power_on_satellites(self):
        """Sequentially enables power and verifies link health."""
        # 1. Enable the 20V MOSFET
        self.sat_pwr.value = True
        await asyncio.sleep(0.5) # Wait for buck converters to stabilize

        # 2. Check Voltage
        if self.status["bus"] < 18.0:
            self.sat_pwr.value = False # Emergency Shutdown
            return False

        # 3. Begin Handshake
        #uart.write(f"ALL|ID_ASSIGN|0100\n".encode())
        return True
