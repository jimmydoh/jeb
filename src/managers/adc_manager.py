"""
ADC Manager - Generic Analog-to-Digital Converter interface.
Supports lazy-loading to prevent crashes if libraries/hardware are missing.
"""

class ADCManager:
    def __init__(self, i2c_bus, chip_type="ADS1115", address=0x48):
        """
        Initializes the generic ADC Manager.
        
        :param i2c_bus: The initialized busio.I2C object.
        :param chip_type: String identifier for the hardware (e.g., "ADS1115").
        :param address: I2C address of the chip.
        """
        self.i2c_bus = i2c_bus
        self.chip_type = chip_type.upper()
        self.address = address
        
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
                print(f"✅ ADCManager: {self.chip_type} initialized at {hex(self.address)}")
            except ImportError:
                print(f"⚠️ ADCManager: Failed to import adafruit_ads1x15. ADC offline.")
            except Exception as e:
                print(f"⚠️ ADCManager: Hardware not found on I2C bus. ({e})")
        else:
            print(f"⚠️ ADCManager: Unsupported chip type '{self.chip_type}'")

    def add_channel(self, name, pin_index, divider_multiplier=1.0):
        """
        Maps a physical ADC pin to a logical name and applies voltage divider math.
        
        :param name: String name for the reading (e.g., "20V_MAIN").
        :param pin_index: Integer representing the pin (0, 1, 2, 3).
        :param divider_multiplier: The inverse of the physical voltage divider (e.g., 11.0).
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
                
                if pin_index not in pin_map:
                    raise ValueError(f"Invalid pin_index {pin_index} for {self.chip_type}")
                    
                self.channels[name] = {
                    "analog_in": AnalogIn(self.hardware, pin_map[pin_index]),
                    "multiplier": float(divider_multiplier)
                }
                print(f"   - Mapped '{name}' to Pin {pin_index} (x{divider_multiplier})")
                
            except Exception as e:
                print(f"⚠️ ADCManager: Failed to configure channel '{name}' - {e}")

    def read(self, name):
        """
        Reads the specified channel and automatically applies the voltage divider math.
        Returns 0.0 if the hardware is offline or the channel isn't found.
        """
        if not self.hardware or name not in self.channels:
            return 0.0
            
        channel = self.channels[name]
        try:
            # .voltage returns the actual voltage hitting the pin (e.g., 1.81V)
            raw_voltage = channel["analog_in"].voltage
            # Multiply it back to real-world bus voltage (e.g., 1.81V * 11.0 = 19.91V)
            return raw_voltage * channel["multiplier"]
        except Exception:
            return 0.0

    def read_all(self):
        """Returns a dictionary of all configured channels and their current voltages."""
        return {name: self.read(name) for name in self.channels.keys()}
