"""Manages power sensing and MOSFET control for satellite bus."""

import asyncio

import digitalio
from utilities.logger import JEBLogger

class PowerManager:
    """
    Class to manage power sensing and MOSFET control for satellite bus.

    Accepts a dictionary of :class:`~utilities.power_bus.PowerBus` objects so
    that ADC-backed and INA260-backed rails can be mixed without any
    hardware-specific logic inside this class.
    """
    def __init__(self, buses, mosfet_pin, detect_pin):
        """
        Initialize PowerManager with PowerBus dependencies.

        :param buses: Dict mapping rail names to :class:`~utilities.power_bus.PowerBus`
                      instances (e.g. ``{"input_20v": PowerBus(...), ...}``).
        :param mosfet_pin: Pin for MOSFET control.
        :param detect_pin: Pin for satellite bus detection.
        """
        self.buses = buses if buses is not None else {}

        JEBLogger.info("POWR", f"[INIT] PowerManager - buses: {list(self.buses.keys())}")

        # MOSFET Control
        self.sat_pwr = digitalio.DigitalInOut(mosfet_pin)
        self.sat_pwr.direction = digitalio.Direction.OUTPUT
        self.sat_pwr.value = False

        # Connection Sense Pin
        self.sat_detect = digitalio.DigitalInOut(detect_pin)
        self.sat_detect.pull = digitalio.Pull.UP  # RJ45 Pins 7&8 bridge to GND

        # Soft Start Configuration
        # Blanking time allows satellite input capacitors to charge before
        # voltage checks begin, preventing false brownout detection
        self.SOFT_START_BLANKING_TIME = 0.015  # 15ms blanking period

    @property
    def status(self):
        """Update all buses and return current voltages as a dict."""
        for bus in self.buses.values():
            bus.update()
        return {name: bus.v_now for name, bus in self.buses.items()}

    @property
    def max(self):
        """Return maximum recorded voltages as a dict."""
        return {name: bus.v_max for name, bus in self.buses.items()}

    @property
    def min(self):
        """Return minimum recorded voltages as a dict."""
        return {name: bus.v_min for name, bus in self.buses.items()}

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

        for bus in self.buses.values():
            bus.update()

        if "input_20v" not in self.buses or self.buses["input_20v"].v_now < 18.0:
            return False, "LOW INPUT VOLTAGE"

        self.sat_pwr.value = True
        start_time = time.monotonic()

        # Fast-check loop: monitor voltage every 15ms during 500ms ramp-up
        # to detect short circuits immediately instead of waiting full delay
        total_delay = 0.5   # 500ms total ramp-up time
        check_interval = 0.015  # 15ms check interval

        while time.monotonic() - start_time < total_delay:
            elapsed = time.monotonic() - start_time

            # Only check for short circuit after blanking time has elapsed
            if elapsed >= self.SOFT_START_BLANKING_TIME:
                for bus in self.buses.values():
                    bus.update()
                if "satbus_20v" in self.buses and self.buses["satbus_20v"].v_now < 17.0:
                    self.sat_pwr.value = False
                    return False, "BUS BROWNOUT"

            await asyncio.sleep(check_interval)

        return True, "OK"

    def emergency_kill(self):
        """Instant hardware cut-off for the satellite bus."""
        self.sat_pwr.value = False

    async def check_power_integrity(self):
        """Diagnostic check performed at boot and during play."""
        JEBLogger.info("POWR", "Performing power integrity check")
        for bus in self.buses.values():
            bus.update()

        input_v = self.buses["input_20v"].v_now if "input_20v" in self.buses else 0.0
        satbus_v = self.buses["satbus_20v"].v_now if "satbus_20v" in self.buses else 0.0
        main_v = self.buses["main_5v"].v_now if "main_5v" in self.buses else 0.0
        led_v = self.buses["led_5v"].v_now if "led_5v" in self.buses else 0.0

        JEBLogger.debug("POWR", f"  |> Input Voltage: {input_v} V")
        JEBLogger.debug("POWR", f"  |> SatBus Voltage: {satbus_v} V")
        JEBLogger.debug("POWR", f"  |> Logic Rail: {main_v} V")
        JEBLogger.debug("POWR", f"  |> LED Rail: {led_v} V")

        if input_v < 15.0:
            return False
        if input_v > 18.0 and satbus_v < 1.0:
            return False
        return True

    def get_telemetry_payload(self):
        """Return telemetry data for all buses, including current/power where available.

        Only keys supported by the underlying sensor are included, so the
        network parser can safely consume the payload without capability checks.
        """
        payload = {}
        for name, bus in self.buses.items():
            entry = {"v": bus.v_now}
            if bus.has_current:
                entry["i"] = bus.i_now
            if bus.has_power:
                entry["p"] = bus.p_now
            payload[name] = entry
        return payload
