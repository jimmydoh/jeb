"""Manages power sensing and MOSFET control for satellite bus."""

import asyncio

import digitalio

class PowerManager:
    """
    Class to manage power sensing and MOSFET control for satellite bus.

    Now uses ADCManager for all voltage readings instead of direct analogio access.
    """
    def __init__(self, adc_manager, sense_names, mosfet_pin, detect_pin):
        """
        Initialize PowerManager with ADCManager for voltage sensing.
        
        :param adc_manager: ADCManager instance configured with voltage sensing channels
        :param sense_names: List of channel names to monitor (e.g., ["input_20v", "satbus_20v", ...])
        :param mosfet_pin: Pin for MOSFET control
        :param detect_pin: Pin for satellite bus detection
        """
        # Store ADCManager reference
        self.adc = adc_manager
        
        # Store sense names and initialize voltage tracking
        self.sense_names = sense_names if sense_names is not None else []
        
        # Initialize voltage tracking for each channel: [Last, Max, Min]
        for name in self.sense_names:
            setattr(self, f"v_{name}", [0.0, 0.0, 99.0])

        # MOSFET Control
        self.sat_pwr = digitalio.DigitalInOut(mosfet_pin)
        self.sat_pwr.direction = digitalio.Direction.OUTPUT
        self.sat_pwr.value = False

        # Connection Sense Pin
        self.sat_detect = digitalio.DigitalInOut(detect_pin)
        self.sat_detect.pull = digitalio.Pull.UP # RJ45 Pins 7&8 bridge to GND

        # Soft Start Configuration
        # Blanking time allows satellite input capacitors to charge before
        # voltage checks begin, preventing false brownout detection
        self.SOFT_START_BLANKING_TIME = 0.015  # 15ms blanking period

    @property
    def status(self):
        """Primary touch point - updates voltage readings and returns as Dict."""
        for name in self.sense_names:
            # Read voltage from ADCManager (already has divider math applied)
            voltage = self.adc.read(name)
            v_list = getattr(self, f"v_{name}")

            # Round to 2 decimal places for consistency
            v_list[0] = round(voltage, 2)

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
        if v["input_20v" if "input_20v" in self.sense_names else "0"] < 18.0:
            return False, "LOW INPUT VOLTAGE"

        self.sat_pwr.value = True
        start_time = time.monotonic()

        # Fast-check loop: monitor voltage every 15ms during 500ms ramp-up
        # to detect short circuits immediately instead of waiting full delay
        total_delay = 0.5  # 500ms total ramp-up time
        check_interval = 0.015  # 15ms check interval

        while time.monotonic() - start_time < total_delay:
            elapsed = time.monotonic() - start_time

            # Only check for short circuit after blanking time has elapsed
            if elapsed >= self.SOFT_START_BLANKING_TIME:
                v = self.status
                if v["satbus_20v" if "satbus_20v" in self.sense_names else "1"] < 17.0:
                    self.sat_pwr.value = False
                    return False, "BUS BROWNOUT"

            await asyncio.sleep(check_interval)

        return True, "OK"

    def emergency_kill(self):
        """Instant hardware cut-off for the satellite bus."""
        self.sat_pwr.value = False

    async def check_power_integrity(self):
        """Diagnostic check performed at boot and during play."""
        print("Performing power integrity check...")
        v = self.status
        print(f" | Input Voltage: {v['input_20v' if 'input_20v' in self.sense_names else '0']} V"
              f" | SatBus Voltage: {v['satbus_20v' if 'satbus_20v' in self.sense_names else '1']} V"
              f" | Logic Rail: {v['main_5v' if 'main_5v' in self.sense_names else '2']} V"
              f" | LED Rail: {v['led_5v' if 'led_5v' in self.sense_names else '3']} V")
        if v["input_20v" if "input_20v" in self.sense_names else "0"] < 15.0:
            return False
        if v["input_20v" if "input_20v" in self.sense_names else "0"] > 18.0 \
            and v["satbus_20v" if "satbus_20v" in self.sense_names else "1"] < 1.0:
            return False
        return True
