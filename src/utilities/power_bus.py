# File: src/utilities/power_bus.py
"""PowerBus abstraction for mixed INA260/ADC power telemetry."""

try:
    from adafruit_ticks import ticks_ms as _hw_ticks_ms
    from adafruit_ticks import ticks_diff as _hw_ticks_diff
    # Guard against mock objects injected during test runs: verify that the
    # imported functions return integers before committing to them.
    if not isinstance(_hw_ticks_ms(), int):
        raise TypeError("adafruit_ticks.ticks_ms() returned a non-integer value")
    ticks_ms = _hw_ticks_ms
    ticks_diff = _hw_ticks_diff
except (ImportError, TypeError, AttributeError):
    import time as _time
    def ticks_ms(): return int(_time.monotonic() * 1000)  # noqa: E704
    def ticks_diff(new, old): return new - old  # noqa: E704


class ADCSensorWrapper:
    """Wraps an ADCManager channel to expose the standard sensor interface.

    Only voltage is available; current and power return None.
    """
    HAS_CURRENT = False
    HAS_POWER = False

    def __init__(self, adc_manager, channel_name):
        """
        :param adc_manager: ADCManager instance with the channel already added.
        :param channel_name: Name of the channel to read from the ADCManager.
        """
        self._adc = adc_manager
        self._channel = channel_name

    def read_voltage(self):
        """Return the channel voltage in volts."""
        return self._adc.read(self._channel)

    def read_current(self):
        """Not supported by ADC — returns None."""
        return None

    def read_power(self):
        """Not supported by ADC — returns None."""
        return None


class INASensorWrapper:
    """Wraps an INA260/INA228 device to expose the standard sensor interface.

    Voltage, current, and power are all available.
    """
    HAS_CURRENT = True
    HAS_POWER = True

    def __init__(self, ina_device):
        """
        :param ina_device: Adafruit INA260/INA228 driver instance.
        """
        self._ina = ina_device

    def read_voltage(self):
        """Return bus voltage in volts."""
        return self._ina.voltage

    def read_current(self):
        """Return current in milliamps."""
        return self._ina.current

    def read_power(self):
        """Return power in milliwatts."""
        return self._ina.power


class BusStatus:
    HEALTHY = 0
    UNDERVOLTAGE = 1
    OVERVOLTAGE = 2
    OFFLINE = 3


class PowerBus:
    """Represents a single power rail with state tracking and capability flags.

    Each bus holds a sensor wrapper and maintains running voltage/current
    stats.  Call :meth:`update` to refresh the readings from hardware.

    Convenience methods :meth:`is_healthy`, :meth:`get_telemetry`, and
    :meth:`__str__` use :meth:`_update_if_stale` internally to avoid
    redundant hardware reads when multiple callers invoke them within the
    same event-loop tick.  :meth:`update` always performs a hardware read
    and is used by explicit callers that need fresh data.
    """

    #: Minimum milliseconds between hardware sensor reads when using
    #: :meth:`_update_if_stale` (100 reads/s max).
    POLL_INTERVAL_MS = 10

    def __init__(self, name, sensor, min_threshold, max_threshold=None, critical=False):
        """
        :param name: Human-readable rail name (e.g. ``"input_20v"``).
        :param sensor: A duck-typed sensor wrapper
                       (:class:`ADCSensorWrapper` or :class:`INASensorWrapper`).
        :param min_threshold: Optional minimum voltage threshold for alerts.
        :param max_threshold: Optional maximum voltage threshold for alerts.
        :param critical: Boolean indicating if this bus is critical.
        """
        self.name = name
        self._sensor = sensor
        self._min_threshold = min_threshold
        self._max_threshold = max_threshold
        self._critical = critical

        # Capability flags derived from the sensor type
        self.has_current = getattr(sensor, 'HAS_CURRENT', False)
        self.has_power = getattr(sensor, 'HAS_POWER', False)

        # Live readings
        self.v_now = 0.0
        self.v_min = float('inf')
        self.v_max = 0.0
        self.i_now = None
        self.i_max = None
        self.p_now = None

        self.status = BusStatus.OFFLINE
        self._last_read_time = 0

    @property
    def critical(self):
        """Indicates if this bus is critical for system operation."""
        return self._critical

    def __str__(self):
        self._update_if_stale()  # Share a single read if called within the same tick
        result = f"{self.name}: {self.v_now:.2f} V"
        if self.has_current and self.i_now is not None:
            result += f", {self.i_now:.2f} mA"
        if self.has_power and self.p_now is not None:
            result += f", {self.p_now:.2f} mW"
        return result

    def get_telemetry(self):
        """Return a dict of current telemetry values for this bus."""
        self._update_if_stale()  # Share a single read if called within the same tick
        telemetry = {
            "name": self.name,
            "v": self.v_now,
            "status": self.status
        }
        if self.has_current and self.i_now is not None:
            telemetry["i"] = self.i_now
        if self.has_power and self.p_now is not None:
            telemetry["p"] = self.p_now
        return telemetry

    def get_status_string(self):
        return {
            BusStatus.HEALTHY: "HEALTHY",
            BusStatus.UNDERVOLTAGE: "UNDERVOLTAGE",
            BusStatus.OVERVOLTAGE: "OVERVOLTAGE",
            BusStatus.OFFLINE: "OFFLINE"
        }.get(self.status, "UNKNOWN")

    def is_healthy(self):
        """
        Returns True if the current voltage is within
        thresholds (if set), False otherwise.
        """
        status = self._update_if_stale()  # Share a single read if called within the same tick
        if status != BusStatus.HEALTHY:
            return False
        return True

    def _update_if_stale(self):
        """Read hardware only when the cached reading is older than :attr:`POLL_INTERVAL_MS`.

        Called by :meth:`is_healthy`, :meth:`get_telemetry`, and :meth:`__str__`
        to avoid redundant I2C/ADC transactions when multiple callers invoke these
        methods within the same event-loop tick (e.g. when both ``monitor_power``
        and ``PowerTelemetryMode`` run in the same asyncio iteration).

        Returns the current :attr:`status` value so callers can act on it without
        an extra attribute access.
        """
        now = ticks_ms()
        if ticks_diff(now, self._last_read_time) < self.POLL_INTERVAL_MS:
            return self.status  # Return cached status; hardware read not due yet
        return self.update()

    def update(self):
        """Poll the sensor and update all tracked state.

        Always performs a hardware read and records the timestamp so subsequent
        calls to :meth:`_update_if_stale` within the same tick are skipped.
        Use this when fresh data is required (e.g. direct callers, periodic
        sampling loops).  Prefer :meth:`is_healthy` and :meth:`get_telemetry`
        for read paths that can tolerate the :attr:`POLL_INTERVAL_MS` cache.
        """
        self._last_read_time = ticks_ms()

        v = self._sensor.read_voltage()

        if v is None:
            self.status = BusStatus.OFFLINE
            return self.status

        if v is not None:
            self.v_now = round(v, 2)
            if self.v_now > self.v_max:
                self.v_max = self.v_now
            if self.v_now < self.v_min:
                self.v_min = self.v_now

            if v <= self._min_threshold:
                self.status = BusStatus.UNDERVOLTAGE
            elif self._max_threshold is not None and v >= self._max_threshold:
                self.status = BusStatus.OVERVOLTAGE
            else:
                self.status = BusStatus.HEALTHY

        if self.has_current:
            i = self._sensor.read_current()
            if i is not None:
                self.i_now = i
                if self.i_max is None or i > self.i_max:
                    self.i_max = i

        if self.has_power:
            self.p_now = self._sensor.read_power()

        return self.status
