"""Manages power sensing and MOSFET control for satellite bus."""

import asyncio

import analogio
import digitalio

class PowerManager:
    """Class to manage power sensing and MOSFET control for satellite bus."""
    def __init__(self, sense_pins, sense_names, mosfet_pin, detect_pin):

        # Dynamic ADC Assignments
        # Standard Order: [Input, SatBus, LogicRail, LEDRail]

        # Check that sense_pins and sense_names lengths match
        if sense_names is not None and len(sense_pins) != len(sense_names):
            raise ValueError("Length of sense_pins and sense_names must match.")

        if sense_names is not None:
            self.sense_names = sense_names
            for i, p in enumerate(sense_pins):
                setattr(self, f"sense_{sense_names[i]}", analogio.AnalogIn(p))
                setattr(self, f"v_{sense_names[i]}", [0.0, 0.0, 99.0]) # Last, Max, Min
        else:
            self.sense_names = []
            for i, p in enumerate(sense_pins):
                setattr(self, f"sense_{i}", analogio.AnalogIn(p))
                setattr(self, f"v_{i}", [0.0, 0.0, 99.0]) # Last, Max, Min
                self.sense_names.append(i)

        # Ideal ADC Sensors:
        # self.sense_input      - Pre-MOSFET 20V Input
        # self.sense_satbus     - Post-MOSFET 20V Bus
        # self.sense_logicbus   - 5V Logic Rail
        # self.sense_ledbus     - 5V LED Rail
        # self.v_input = [0.0, 0.0, 99.0] # Last, Max, Min
        # self.v_satbus = [0.0, 0.0, 99.0] # Last, Max, Min
        # self.v_ledbus = [0.0, 0.0, 99.0] # Last, Max, Min
        # self.v_logicbus = [0.0, 0.0, 99.0] # Last, Max, Min

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

    def get_v(self, sensor, ratio):
        """Converts ADC reading to actual voltage based on divider ratio."""
        return round(((sensor.value * 3.3) / 65535) / ratio, 2)

    @property
    def status(self):
        """Primary touch point - updates voltage readings and returns as Dict."""
        for name in self.sense_names:
            sensor = getattr(self, f"sense_{name}")
            ratio = self.RATIO_20V if "20V" in name else self.RATIO_5V
            v_attr = f"v_{name}"
            v_list = getattr(self, v_attr)

            v_list[0] = self.get_v(sensor, ratio)

            # Update max/min records
            if v_list[0] > v_list[1]:
                v_list[1] = v_list[0]
            if v_list[0] < v_list[2] or v_list[2] == 0.0:
                v_list[2] = v_list[0]
        return {name: getattr(self, f"v_{name}")[0] for name in self.sense_names}

    @property
    def max(self):
        """Return maximum recorded voltages as Dict."""
        return {name: getattr(self, f"v_{name}")[1] for name in self.sense_names}

    @property
    def min(self):
        """Return minimum recorded voltages as Dict."""
        return {name: getattr(self, f"v_{name}")[2] for name in self.sense_names}

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
        import time
        
        v = self.status
        if v["input" if "input" in self.sense_names else "0"] < 18.0:
            return False, "LOW INPUT VOLTAGE"

        self.sat_pwr.value = True
        start_time = time.monotonic()

        # Blanking time: Ignore voltage readings for the first 15ms
        # This allows satellite input capacitors to charge before 
        # enforcing the 17.0V limit, preventing false brownout detection
        blanking_time = 0.015  # 15ms blanking period
        
        # Fast-check loop: monitor voltage every 15ms during 500ms ramp-up
        # to detect short circuits immediately instead of waiting full delay
        total_delay = 0.5  # 500ms total ramp-up time
        check_interval = 0.015  # 15ms check interval
        
        while time.monotonic() - start_time < total_delay:
            elapsed = time.monotonic() - start_time
            
            # Only check for short circuit after blanking time has elapsed
            if elapsed >= blanking_time:
                v = self.status
                if v["satbus" if "satbus" in self.sense_names else "1"] < 17.0:
                    self.sat_pwr.value = False
                    return False, "BUS BROWNOUT"
            
            await asyncio.sleep(check_interval)

        return True, "OK"

    def emergency_kill(self):
        """Instant hardware cut-off for the satellite bus."""
        self.sat_pwr.value = False

    async def check_power_integrity(self):
        """Diagnostic check performed at boot and during play."""
        v = self.status
        if v["input" if "input" in self.sense_names else "0"] < 15.0:
            return False
        if v["input" if "input" in self.sense_names else "0"] > 18.0 \
            and v["satbus" if "satbus" in self.sense_names else "1"] < 1.0:
            return False
        return True
