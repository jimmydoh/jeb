"""
Industrial Satellite Firmware (Satellite-side)

Handles hardware I/O and logic for the Industrial Satellite when running
on the actual satellite hardware. This class manages physical hardware
including neopixels, segment displays, encoders, and power management.

Hardware HID Layout:
    Latching Toggles  (12 total):
        [0-7]  — 8x Small latching toggles arranged in 2 rows of 4 (Expander 1, pins 0-7)
        [8]    — Guarded latching toggle / Master Arm (Expander 2, pin 2)
        [9]    — 2-Position key switch / Secure State (Expander 2, pin 3)
        [10]   — 3-Position rotary switch, Position A / Mode A (Expander 2, pin 4)
        [11]   — 3-Position rotary switch, Position B / Mode B (Expander 2, pin 5)
    Momentary Toggles (1 pair):
        [0]    — On-Off-On toggle, UP/DOWN directions (Expander 2, pins 0-1)
    Encoders          (1):
        [0]    — Rotary encoder with integrated push button (GP2/GP3/GP12)
    Buttons           (1):
        [0]    — Large momentary button / Panic or Execute (Expander 2, pin 6)
    Matrix Keypads    (1):
        [0]    — 9-digit 3x3 keypad (rows GP16-18, cols GP19-21)
"""

import asyncio
import time
import busio
import neopixel

from utilities.jeb_pixel import JEBPixel
from utilities.logger import JEBLogger
from utilities.pins import Pins
from utilities.palette import Palette
from utilities.payload_parser import parse_values, get_int

from transport.protocol import (
    CMD_MODE,
    CMD_SYNC_FRAME,
    CMD_SETENC,
    LED_COMMANDS,
    DSP_COMMANDS,
)
from transport import Message
from managers.hid_manager import HIDManager
from managers.led_manager import LEDManager
from managers.render_manager import RenderManager
from managers.segment_manager import SegmentManager

from .base_firmware import SatelliteFirmware

TYPE_ID = "01"
TYPE_NAME = "INDUSTRIAL"

# Dim blue used as low-power breathing colour during sleep
SLEEP_LED_COLOR = (0, 0, 32)

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
            expander_configs=Pins.EXPANDER_CONFIGS,
            monitor_only=False
        )

        # Init LED Hardware
        self.root_pixels = neopixel.NeoPixel(
            Pins.LED_CONTROL,
            8,
            brightness=0.3,
            auto_write=False
        )

        # Init LEDManager with JEBPixel wrapper for the 8 onboard LEDs
        self.led_jeb_pixel = JEBPixel(self.root_pixels, start_idx=0, num_pixels=8, pixel_order="RGB")
        self.leds = LEDManager(self.led_jeb_pixel)

        self.renderer = RenderManager(
            self.root_pixels,
            sync_role="SLAVE",
        )

        self.renderer.add_animator(self.leds)  # Register LEDManager for animation updates

        self.last_interaction_time = 0
        self.attract_running = False
        self._idle_display_buffer = ""
        self._sleeping = False

        self._system_handlers.update({
            CMD_SYNC_FRAME: self._handle_sync_frame,
            CMD_SETENC: self._handle_set_enc,
            CMD_MODE: self._handle_mode_command,
        })
        JEBLogger.info("FIRM", "Industrial Satellite Firmware initialized.", src=self.id)

    async def _handle_sync_frame(self, val):
        # val is tuple (frame, time) from binary payload
        self.renderer.apply_sync(int(val[0]))
        # Keep GlobalAnimationController in sync if one has been initialised
        if self._global_anim_ctrl is not None:
            self._global_anim_ctrl.sync_frame(int(val[0]))

    async def _handle_set_enc(self, val):
        # Handle both binary tuple and text formats
        if isinstance(val, (list, tuple)):
            self.hid.reset_encoder(int(val[0]))
        else:
            values = parse_values(val)
            self.hid.reset_encoder(get_int(values, 0))

    async def _handle_mode_command(self, val):
        """Handle CMD_MODE from the Core (SLEEP or ACTIVE)."""
        mode_str = val.strip() if isinstance(val, str) else str(val).strip()
        JEBLogger.info("FIRM", f"MODE command: {mode_str}", src=self.id)
        if mode_str == "SLEEP":
            await self._enter_sleep()
        elif mode_str == "ACTIVE":
            await self._wake_local()

    async def _enter_sleep(self):
        """Enter satellite sleep state: blank display, breath LEDs, throttle loops."""
        if self._sleeping:
            return
        self._sleeping = True
        await self.segment.clear()
        self.leds.set_led(-1, SLEEP_LED_COLOR, brightness=0.1, anim="BREATH", speed=0.5)
        self.renderer.target_frame_rate = 10

    async def _wake_local(self):
        """Exit satellite sleep state: restore display loops and LED rate."""
        if not self._sleeping:
            return
        self._sleeping = False
        self.renderer.target_frame_rate = self.renderer.DEFAULT_FRAME_RATE

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

    def _register_global_anim_leds(self, offset_x, offset_y):
        """Register onboard LEDs with the global animation controller at the given offset."""
        self._global_anim_ctrl.register_led_strip(
            self.leds,
            offset_x=offset_x,
            offset_y=offset_y,
            orientation='horizontal',
        )

    def _get_status_bytes(self):
        return self.hid.get_status_bytes()

    async def on_mode_change(self, new_mode):
        """React to mode changes by cleaning up local hardware state."""
        JEBLogger.info("FIRM", f"Mode changed to {new_mode}", src=self.id)
        self.attract_running = False
        self.last_interaction_time = time.monotonic()
        self._idle_display_buffer = ""

        # Clear LEDs (using priority 99 to override local animations)
        for i in range(5):
            self.leds.off_led(i, priority=99)

        # Clear Segment display
        await self.segment.clear()

        # Flush the HID queues so old button presses don't trigger game events
        self.hid.flush()

#region --- Async Background Tasks ---
    async def monitor_hw_hid(self):
        """Background task to poll hardware inputs."""
        while True:
            self.watchdog.check_in("hw_hid")
            changed = self.hid.hw_update(self.id)

            if self._sleeping:
                if changed:
                    # Local interaction while sleeping: wake locally and notify Core
                    await self._wake_local()
                    self.transport_up.send(Message(self.id, "CORE", CMD_MODE, "ACTIVE"))
                await asyncio.sleep(0.1)  # Throttled polling while sleeping
                continue

            if changed:
                # Any hardware interaction resets the attract mode timer
                self.last_interaction_time = time.monotonic()
                if self.attract_running:
                    self.attract_running = False
                    for i in range(5):
                        self.leds.off_led(i, priority=5)
                    await self.segment.clear()

            if self.operating_mode == "IDLE":
                if changed:
                    # 1. Hardware Toggles directly drive Local LEDs (Assuming 5 toggles, 5 LEDs)
                    for i in range(4):
                        if self.hid.is_latching_toggled(i):
                            JEBLogger.info("FIRM", f"Local Idle Toggle {i} ON", src=self.id)
                            self.leds.set_led(i, Palette.GREEN, priority=5)
                        else:
                            JEBLogger.info("FIRM", f"Local Idle Toggle {i} OFF", src=self.id)
                            self.leds.set_led(i, Palette.AMBER, priority=5)

                    # 2. Keypad typing directly to 14-Segment Displays
                    key = self.hid.get_keypad_next_key(0) # Assuming index 0 is your matrix keypad
                    while key:
                        JEBLogger.info("FIRM", f"Keypad Idle input received: {key}", src=self.id)
                        # Keep a running 4-character buffer
                        if len(self._idle_display_buffer) >= 8: # 4 chars * 2 displays = 8 total
                            self._idle_display_buffer = self._idle_display_buffer[1:]
                        self._idle_display_buffer += key
                        await self.segment.apply_command("DSP", self._idle_display_buffer)
                        key = self.hid.get_keypad_next_key(0)

                    # 3. Momentary Switch triggers an animation
                    # Direction "U" or "D" depends on your switch wiring
                    if self.hid.is_momentary_toggled(0, direction="U", action="tap"):
                        JEBLogger.info("FIRM", "Momentary Idle UP Triggered", src=self.id)
                        self._idle_display_buffer = "UP"
                        await self.segment.apply_command("DSP", self._idle_display_buffer)
                    if self.hid.is_momentary_toggled(0, direction="D", action="tap"):
                        JEBLogger.info("FIRM", "Momentary Idle DOWN Triggered", src=self.id)
                        self._idle_display_buffer = "DOWN"
                        await self.segment.apply_command("DSP", self._idle_display_buffer)

            else:
                # ACTIVE MODE: Only trigger upstream updates
                if changed:
                    self.trigger_status_update()

            await asyncio.sleep(0.01)

    async def attract_loop(self):
        """Passive background animation when nobody touches the satellite in IDLE mode."""
        # 30 seconds of inactivity triggers attract
        ATTRACT_TIMEOUT = 30.0

        while True:
            self.watchdog.check_in("attract")

            if self.operating_mode == "IDLE" and not self.attract_running:
                if time.monotonic() - self.last_interaction_time > ATTRACT_TIMEOUT:
                    JEBLogger.info("FIRM", "Entering Idle Attract Mode", src=self.id)
                    self.attract_running = True

                    # Fire off a passive sweeping LED animation
                    self.leds.start_cylon(Palette.CYAN, speed=0.08)

                    # Put a fun message on the segment displays
                    await self.segment.apply_command("DSP", "** JEB ROCKS **")

            await asyncio.sleep(0.5)
#endregion

    async def custom_start(self):
        """Custom startup sequence for the Industrial Satellite."""
        # Register additional watchdog flags
        self.watchdog.register_flags(["hw_hid", "render", "attract"])

        self.last_interaction_time = time.monotonic()

        return [
            self.monitor_hw_hid(),
            self.attract_loop(),
            self.renderer.run(
                heartbeat_callback=lambda: self.watchdog.check_in("render")
            )
        ]
