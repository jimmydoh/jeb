"""
Industrial Satellite Firmware (Satellite-side)

Handles hardware I/O and logic for the Industrial Satellite when running
on the actual satellite hardware. This class manages physical hardware
including neopixels, segment displays, encoders, and power management.
"""

import asyncio
import busio
import neopixel

from utilities.jeb_pixel import JEBPixel
from utilities.pins import Pins
from utilities.payload_parser import parse_values, get_int

from transport.protocol import (
    CMD_SYNC_FRAME,
    CMD_SETENC,
    LED_COMMANDS,
    DSP_COMMANDS,
)
from managers.hid_manager import HIDManager
from managers.led_manager import LEDManager
from managers.render_manager import RenderManager
from managers.segment_manager import SegmentManager

from .base_firmware import SatelliteFirmware

TYPE_ID = "01"
TYPE_NAME = "INDUSTRIAL"

class IndustrialSatelliteFirmware(SatelliteFirmware):
    """Satellite-side firmware for Industrial Satellite.

    Handles hardware I/O, power management, and local command processing.
    Runs on the physical satellite hardware and manages all peripherals.
    """
    def __init__(self):
        """Initialize the Industrial Satellite Firmware."""
        # --- ACTIVE MODE (Running on Satellite Hardware) ---
        # Initialize base class with upstream transport
        super().__init__(
            sid=None,
            sat_type_id=TYPE_ID,
            sat_type_name=TYPE_NAME,
        )

        # Satellite specific hardware initialization
        # Init I2C bus
        self.i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)

        # Init Segment Display
        self.segment = SegmentManager(
            self.i2c,
            device_addresses=[
                Pins.I2C_ADDRESSES.get("SEGMENT_LEFT", 0x70),
                Pins.I2C_ADDRESSES.get("SEGMENT_RIGHT", 0x71)
            ]
        )

        # Init HID
        self.hid = HIDManager(
            encoders=Pins.ENCODERS,
            matrix_keypads=Pins.MATRIX_KEYPADS,
            mcp_chip="MCP23008",
            mcp_i2c=self.i2c,
            mcp_i2c_address=Pins.I2C_ADDRESSES.get("EXPANDER"),
            mcp_int_pin=Pins.EXPANDER_INT,
            expanded_latching_toggles=Pins.EXPANDER_LATCHING,
            expanded_momentary_toggles=Pins.EXPANDER_MOMENTARY,
            monitor_only=False
        )

        # Init LED Hardware
        self.root_pixels = neopixel.NeoPixel(
            Pins.LED_CONTROL,
            5,
            brightness=0.3,
            auto_write=False
        )

        # Init LEDManager with JEBPixel wrapper for the 5 onboard LEDs
        self.led_jeb_pixel = JEBPixel(self.root_pixels, start_idx=0, num_pixels=5)
        self.leds = LEDManager(self.led_jeb_pixel)

        self.renderer = RenderManager(
            self.root_pixels,
            sync_role="SLAVE",
        )

        self.renderer.add_animator(self.leds)  # Register LEDManager for animation updates

        self._system_handlers.update({
            CMD_SYNC_FRAME: self._handle_sync_frame,
            CMD_SETENC: self._handle_set_enc,
        })

    async def _handle_sync_frame(self, val):
        # val is tuple (frame, time) from binary payload
        self.renderer.apply_sync(int(val[0]))

    async def _handle_set_enc(self, val):
        # Handle both binary tuple and text formats
        if isinstance(val, (list, tuple)):
            self.hid.reset_encoder(int(val[0]))
        else:
            values = parse_values(val)
            self.hid.reset_encoder(get_int(values, 0))

    async def _process_local_cmd(self, cmd, val):
        """Process a command received from upstream that is addressed to this satellite.

        Parameters:
            cmd (str): Command type.
            val (str or bytes): Command value.
        """
        if await super()._process_local_cmd(cmd, val):
            return True # Command was handled!

        # 2. Subsystem Delegation (Prefix Routing)
        if cmd in LED_COMMANDS:
            self.leds.apply_command(cmd, val)
            return True
        elif cmd in DSP_COMMANDS:
            await self.segment.apply_command(cmd, val)
            return True
        return False

    def _get_status_bytes(self):
        return self.hid.get_status_bytes()

#region --- Async Background Tasks ---
    async def monitor_hw_hid(self):
        """Background task to poll hardware inputs."""
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog.check_in("hw_hid")
            if self.hid.hw_update(self.id):
                self.trigger_status_update()  # Trigger status update on state change
            await asyncio.sleep(0.01) # Poll at 100Hz
#endregion

    async def custom_start(self):
        """Custom startup sequence for the Industrial Satellite."""

        # Register additional watchdog flags
        self.watchdog.register_flags(["hw_hid"])
        self.watchdog.register_flags(["render"])

        # Return list of background tasks to run concurrently with the main loop
        return [
            self.monitor_hw_hid(),
            self.renderer.run(
                heartbeat_callback=lambda: self.watchdog.check_in("render")
            )
        ]
