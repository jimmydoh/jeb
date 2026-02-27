"""Manages power sensing and MOSFET control for satellite bus."""

import asyncio

import digitalio
from utilities.logger import JEBLogger
from utilities.power_bus import ADCSensorWrapper, INASensorWrapper, PowerBus, BusStatus

class PowerManager:
    """
    Class to manage power sensing and MOSFET control for satellite bus.

    Accepts a dictionary of :class:`~utilities.power_bus.PowerBus` objects so
    that ADC-backed and INA260-backed rails can be mixed without any
    hardware-specific logic inside this class.
    """
    def __init__(self, power_sensors, mosfet_pin, detect_pin, i2c_bus=None):
        """
        Initialize PowerManager with PowerBus dependencies.

        :param power_sensors: Dict mapping rail names to :class:`~utilities.power_bus.PowerBus`
                              instances (e.g. ``{"input_20v": PowerBus(...), ...}``).
        :param mosfet_pin: Pin for MOSFET control.
        :param detect_pin: Pin for satellite bus detection.
        :param i2c_bus: Optional I2C bus instance for INA260-backed rails.
        """

        JEBLogger.info("POWR", f"[INIT] PowerManager")

        self._adc_managers = []
        self.buses = {}

        # Init ADCManager channels, INA chips and PowerBus instances
        for power_sensor in power_sensors:
            chip_type = power_sensor.get("chip_type")
            channels = power_sensor.get("channels", [])

            if chip_type in ("NATIVE", "ADS1115"):
                from managers.adc_manager import ADCManager

                # Keep it as a local variable; the wrappers will maintain the reference
                hw_instance = ADCManager(
                    i2c_bus=i2c_bus if chip_type == "ADS1115" else None,
                    chip_type=chip_type,
                    address=power_sensor.get("address", 0x48 if chip_type == "ADS1115" else 0x00),
                    channels=channels
                )

                # Helper to generate the right wrapper for this hardware type
                def create_wrapper(channel_name):
                    return ADCSensorWrapper(hw_instance, channel_name)

            elif chip_type == "INA260":
                # INA chips don't use ADCManager, they talk straight to I2C
                address = power_sensor.get("address", 0x40)

                def create_wrapper(channel_name):
                    return INASensorWrapper(i2c_bus, address)

            else:
                JEBLogger.warning("POWR", f"⚠️ PowerManager: Unsupported chip type '{power_sensor['chip_type']}' for power sensor '{power_sensor['name']}'")
                continue

            # Init PowerBus instances for each channel defined under this sensor
            for channel in channels:
                name = channel.get("name", "unnamed_channel")

                # Instantiate the correct wrapper dynamically
                sensor = create_wrapper(name)

                min_threshold = channel.get("min", 1.0)
                max_threshold = channel.get("max", None)
                critical = channel.get("critical", False)

                power_bus = PowerBus(name, sensor, min_threshold, max_threshold, critical)
                self.buses[name] = power_bus

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
        """Update all buses and return current status as a dict."""
        return {name: bus.update() for name, bus in self.buses.items()}

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

        # Find the input bus to check for brownout during soft start
        input_bus = self.get_input_bus()
        if not input_bus:
            JEBLogger.warning("POWR", "⚠️ No input bus found for soft start checks")
            return False, "NO INPUT BUS"
        elif input_bus.is_healthy():
            JEBLogger.info("POWR", "Input bus healthy, proceeding with soft start")
        else:
            JEBLogger.warning("POWR", "⚠️ Input bus unhealthy, aborting soft start")
            JEBLogger.warning("POWR", f"  |> Input Voltage: {input_bus.v_now} V")
            return False, "INPUT BUS UNHEALTHY"

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
                satbus_bus = self.get_satbus_bus()
                if not satbus_bus:
                    JEBLogger.warning("POWR", "⚠️ No satbus bus found for soft start checks")
                    break
                elif not satbus_bus.is_healthy():
                    JEBLogger.warning("POWR", "⚠️ SatBus bus unhealthy during soft start, cutting power")
                    JEBLogger.warning("POWR", f"  |> SatBus Voltage: {satbus_bus.v_now} V")
                    self.emergency_kill()
                    return False, "SATBUS BUS UNHEALTHY"

            await asyncio.sleep(check_interval)

        JEBLogger.info("POWR", "Soft start complete, satellite bus stable")
        return True, "OK"

    def emergency_kill(self):
        """Instant hardware cut-off for the satellite bus."""
        self.sat_pwr.value = False
        JEBLogger.warning("POWR", "⚠️ EMERGENCY BUS SHUTDOWN: Downstream power cut off")

    def is_healthy(self):
        """Quick diagnostic check performed by background tasks"""
        warning = False
        for bus in self.buses.values():
            if bus.critical and not bus.is_healthy():
                JEBLogger.error("POWR", f"⚠️ Critical bus '{bus.name}' is unhealthy during integrity check")
                return False, f"Critical Bus {bus.name} {bus.get_status_string()}"
            elif not bus.is_healthy():
                JEBLogger.warning("POWR", f"⚠️ Non-critical bus '{bus.name}' is unhealthy during integrity check")
        if warning:
            return True, "Non-critical bus issues detected"
        else:
            return True, "All buses healthy"

    async def check_power_integrity(self):
        """Full diagnostic check performed at boot and during play."""
        JEBLogger.info("POWR", "Performing power integrity check")

        for bus in self.buses.values():
            JEBLogger.info("POWR", f"  |> {str(bus)}")
            if bus.critical and not bus.is_healthy():
                JEBLogger.error("POWR", f"⚠️ Critical bus '{bus.name}' is unhealthy during integrity check")
                return False
            elif not bus.is_healthy():
                JEBLogger.warning("POWR", f"⚠️ Non-critical bus '{bus.name}' is unhealthy during integrity check")
            else:
                JEBLogger.debug("POWR", f"Bus '{bus.name}' is healthy during integrity check")
        return True

    def get_telemetry_payload(self):
        """Return telemetry data for all buses, including current/power where available.

        Only keys supported by the underlying sensor are included, so the
        network parser can safely consume the payload without capability checks.
        """
        return {bus.name: bus.get_telemetry() for bus in self.buses.values()}

    def get_input_bus(self):
        """Convenience method to return the primary input bus for health checks."""
        # Get the first bus that has "input" in its name, or None if not found
        for name, bus in self.buses.items():
            if "input" in name.lower():
                return bus
        return None

    def get_satbus_bus(self):
        """Convenience method to return the downstream bus for health checks."""
        # Get the first bus that has "satbus" in its name, or None if not found
        for name, bus in self.buses.items():
            if "satbus" in name.lower():
                return bus
        return None

    def get_main_bus(self):
        """Convenience method to return the main logic bus for health checks."""
        # Get the first bus that has "main" in its name, or None if not found
        for name, bus in self.buses.items():
            if "main" in name.lower():
                return bus
        return None

    def get_other_buses(self):
        """Convenience method to return a dict of non-primary buses for telemetry."""
        # Return all buses that don't have "input", "satbus", or "main" in their name
        other_buses = {}
        for name, bus in self.buses.items():
            if not any(keyword in name.lower() for keyword in ("input", "satbus", "main")):
                other_buses[name] = bus
        return other_buses
