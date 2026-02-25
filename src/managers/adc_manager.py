"""
ADC Manager - Generic Analog-to-Digital Converter interface.
Supports both I2C expansion ADCs (e.g., ADS1115) and native analogio pins.
Supports lazy-loading to prevent crashes if libraries/hardware are missing.
"""

from utilities.logger import JEBLogger

class ADCManager:
    def __init__(self, i2c_bus=None, chip_type="ADS1115", address=0x48):
        """
        Initializes the generic ADC Manager.

        :param i2c_bus: The initialized busio.I2C object (required for I2C ADCs, None for native).
        :param chip_type: String identifier for the hardware (e.g., "ADS1115", "NATIVE").
        :param address: I2C address of the chip (only used for I2C ADCs).

        Note: When using chip_type="ADS1115" or other I2C ADCs, i2c_bus must be provided.
              When using chip_type="NATIVE", i2c_bus should be None.
        """
        self.i2c_bus = i2c_bus
        self.chip_type = chip_type.upper()
        self.address = address

        JEBLogger.info("ADCM",f"[INIT] ADCManager - chip_type: {self.chip_type} address: {self.address}")

        # Validate that I2C bus is provided for I2C chip types
        if self.chip_type != "NATIVE" and i2c_bus is None:
            JEBLogger.warning("ADCM", f"⚠️ ADCManager: I2C bus required for chip type '{self.chip_type}'")
            # Set hardware to None and don't attempt initialization
            self.hardware = None
            self.channels = {}
            return

        self.hardware = None
        self.channels = {} # Stores mapped names to channel objects and multipliers

        self._lazy_init()

    def _lazy_init(self):
        """Attempts to load the specific hardware library based on chip_type."""
        if self.chip_type == "ADS1115":
            try:
                # Lazy load the Adafruit library only if this chip type is requested
                import adafruit_ads1x15.ads1115 as ADS
                self.ads_module = ADS # Keep a reference to the module for pin mapping

                self.hardware = ADS.ADS1115(self.i2c_bus, address=self.address)
                JEBLogger.info("ADCM", f"✅ ADCManager: {self.chip_type} initialized at {hex(self.address)}")
            except ImportError:
                JEBLogger.warning("ADCM", f"⚠️ ADCManager: Failed to import adafruit_ads1x15. ADC offline.")
            except Exception as e:
                JEBLogger.warning("ADCM", f"⚠️ ADCManager: Hardware not found on I2C bus. ({e})")
        elif self.chip_type == "NATIVE":
            try:
                # For native ADC pins, we don't need hardware initialization
                # The analogio.AnalogIn will be created per-channel in add_channel
                self.hardware = True  # Marker to indicate native ADC is available
                JEBLogger.info("ADCM", f"✅ ADCManager: {self.chip_type} ADC initialized (analogio)")
            except Exception as e:
                JEBLogger.warning("ADCM", f"⚠️ ADCManager: Failed to initialize native ADC. ({e})")
        else:
            JEBLogger.warning("ADCM", f"⚠️ ADCManager: Unsupported chip type '{self.chip_type}'")

    def add_channel(self, name, pin_or_index, divider_multiplier=1.0):
        """
        Maps a physical ADC pin to a logical name and applies voltage divider math.

        :param name: String name for the reading (e.g., "20V_MAIN").
        :param pin_or_index: For I2C ADCs (e.g., ADS1115): Integer pin index (0-3).
                             For NATIVE ADCs: board pin object (e.g., board.GP26).
        :param divider_multiplier: The inverse of the physical voltage divider (e.g., 11.0).
                                   This is the factor to multiply the ADC voltage by to get
                                   the actual voltage being measured.

        Examples:
            # I2C ADC (ADS1115)
            adc.add_channel("20V_BUS", pin_or_index=0, divider_multiplier=11.0)

            # Native ADC
            adc.add_channel("20V_BUS", pin_or_index=board.GP26, divider_multiplier=11.0)
        """
        if not self.hardware:
            return

        if self.chip_type == "ADS1115":
            try:
                from adafruit_ads1x15.analog_in import AnalogIn

                # Map standard integers to Adafruit's specific pin objects
                pin_map = {
                    0: self.ads_module.P0,
                    1: self.ads_module.P1,
                    2: self.ads_module.P2,
                    3: self.ads_module.P3
                }

                if pin_or_index not in pin_map:
                    raise ValueError(f"Invalid pin_index {pin_or_index} for {self.chip_type}")

                self.channels[name] = {
                    "analog_in": AnalogIn(self.hardware, pin_map[pin_or_index]),
                    "multiplier": float(divider_multiplier),
                    "type": "I2C"
                }
                JEBLogger.info("ADCM", f"   - Mapped '{name}' to Pin {pin_or_index} (x{divider_multiplier})")

            except Exception as e:
                JEBLogger.warning("ADCM", f"⚠️ ADCManager: Failed to configure channel '{name}' - {e}")

        elif self.chip_type == "NATIVE":
            try:
                import analogio

                # For native pins, pin_or_index should be a board pin object
                analog_in = analogio.AnalogIn(pin_or_index)

                self.channels[name] = {
                    "analog_in": analog_in,
                    "multiplier": float(divider_multiplier),
                    "type": "NATIVE"
                }
                JEBLogger.info("ADCM", f"   - Mapped '{name}' to native ADC pin (x{divider_multiplier})")

            except Exception as e:
                JEBLogger.warning("ADCM", f"⚠️ ADCManager: Failed to configure native channel '{name}' - {e}")

    def read(self, name):
        """
        Reads the specified channel and automatically applies the voltage divider math.
        Returns 0.0 if the hardware is offline or the channel isn't found.
        """
        if not self.hardware or name not in self.channels:
            return 0.0

        channel = self.channels[name]
        try:
            if channel.get("type") == "NATIVE":
                # For native ADC, calculate voltage from raw value
                # Native ADC reading: value is 0-65535, reference is 3.3V
                raw_voltage = (channel["analog_in"].value * 3.3) / 65535
            else:
                # For I2C ADC (ADS1115), use the .voltage property directly
                raw_voltage = channel["analog_in"].voltage

            # Apply voltage divider multiplication
            return raw_voltage * channel["multiplier"]
        except Exception:
            return 0.0

    def read_all(self):
        """Returns a dictionary of all configured channels and their current voltages."""
        return {name: self.read(name) for name in self.channels.keys()}
