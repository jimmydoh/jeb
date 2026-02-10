"""
Industrial Satellite Firmware (Satellite-side)

Handles hardware I/O and logic for the Industrial Satellite when running
on the actual satellite hardware. This class manages physical hardware
including neopixels, segment displays, encoders, and power management.
"""

import time

import asyncio
import microcontroller
import busio
import neopixel

from utilities import (
    JEBPixel,
    Palette,
    Pins,
    parse_values,
    get_int,
)
from transport import (
    Message,
    UARTTransport,
    CMD_ID_ASSIGN,
    CMD_SYNC_FRAME,
    CMD_SETENC,
    LED_COMMANDS,
    DSP_COMMANDS,
    COMMAND_MAP,
    DEST_MAP,
    MAX_INDEX_VALUE,
    PAYLOAD_SCHEMAS
)
from managers import (
    HIDManager,
    LEDManager,
    PowerManager,
    RenderManager,
    SegmentManager
)
from .base import Satellite

TYPE_ID = "01"
TYPE_NAME = "INDUSTRIAL"

class IndustrialSatelliteFirmware(Satellite):
    """Satellite-side firmware for Industrial Satellite.

    Handles hardware I/O, power management, and local command processing.
    Runs on the physical satellite hardware and manages all peripherals.
    """
    def __init__(self):
        """Initialize the Industrial Satellite Firmware."""
        # State Variables
        self.last_tx = 0

        # TODO: Implement satellite watchdog
        self.watchdog_flags = {
            "power": False,
            "connection": False,
            "hw_hid": False,
            "render": False,
        }

        # --- ACTIVE MODE (Running on Satellite Hardware) ---
        # Define REAL Pins for the Industrial Satellite
        Pins.initialize(profile="SAT", type_id=TYPE_ID)

        # Init power manager first for voltage readings
        self.power = PowerManager(
            Pins.SENSE_PINS,
            ["input", "satbus", "main"],
            Pins.MOSFET_CONTROL,
            Pins.SATBUS_DETECT
        )

        # TODO Check power state

        # UART for satellite communication
        uart_up_hw = busio.UART(
            Pins.UART_TX,
            Pins.UART_RX,
            baudrate=115200,
            receiver_buffer_size=512,
            timeout=0.01
        )
        uart_down_hw = busio.UART(
            Pins.UART_DOWN_TX,
            Pins.UART_DOWN_RX,
            baudrate=115200,
            timeout=0.01
        )

        # Wrap with transport layer using the queued manager
        self.transport_up = UARTTransport(uart_up_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS, queued=True)
        self.transport_down = UARTTransport(uart_down_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

        # Initialize base class with upstream transport
        super().__init__(sid=None, sat_type_id=TYPE_ID, sat_type_name=TYPE_NAME, transport=self.transport_up)

        # Init I2C bus
        self.i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)

        # Init HID
        self.hid = HIDManager(
            latching_toggles=Pins.EXPANDER_LATCHING,
            momentary_toggles=Pins.EXPANDER_MOMENTARY,
            encoders=Pins.ENCODERS,
            matrix_keypads=Pins.MATRIX_KEYPADS,
            monitor_only=False
        )

        # Init Segment Display
        self.segment = SegmentManager(self.i2c)

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
            watchdog_flags=self.watchdog_flags,
            sync_role="SLAVE",
        )

        self.renderer.add_animator(self.leds)  # Register LEDManager for animation updates

        # Frame sync state for coordinated animations with Core
        self.frame_counter = 0
        self.last_sync_frame = 0
        self.time_offset = 0.0  # Estimated time difference from Core (in seconds)

        self._system_handlers = {
            CMD_ID_ASSIGN: self._handle_id_assign,
            CMD_SYNC_FRAME: self._handle_sync_frame,
            CMD_SETENC: self._handle_set_enc,
        }

    async def process_local_cmd(self, cmd, val):
        """Optimized command processor using dispatch and delegation."""
        handler = self._system_handlers.get(cmd)
        if handler:
            await handler(val)
            return

        # 2. Subsystem Delegation (Prefix Routing)
        if cmd in LED_COMMANDS:
            await self.leds.apply_command(cmd, val)
        elif cmd in DSP_COMMANDS:
            await self.segment.apply_command(cmd, val)

    # --- Private Handlers for System Logic ---

    async def _handle_id_assign(self, val):
        if isinstance(val, bytes):
            val = val.decode('utf-8')
        type_prefix = val[:2]
        current_index = int(val[2:])

        if type_prefix == self.sat_type_id:
            new_index = current_index + 1
            self.id = f"{type_prefix}{new_index:02d}"
            await self.segment.start_message(f"ID {self.id}", loop=False)

            # Forward new index downstream
            msg_out = Message("ALL", CMD_ID_ASSIGN, self.id)
            self.transport_down.send(msg_out)
        else:
            # Pass original downstream
            msg_out = Message("ALL", CMD_ID_ASSIGN, val)
            self.transport_down.send(msg_out)

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

    async def monitor_power(self):
        """Background task to watch for local brownouts or downstream faults."""
        last_broadcast = 0
        while True:
            # Update voltages and get current readings
            v = self.power.status
            now = time.monotonic()

            # Send periodic voltage reports upstream every 5 seconds
            if now - last_broadcast > 5.0:
                msg_out = Message(self.id, "POWER", [v['in'], v['bus'], v['log']])
                self.transport_up.send(msg_out)
                last_broadcast = now

            # Safety Check: Logic rail sagging (Potential Buck Converter or Audio overload)
            if v["log"] < 4.7:
                # Local warning: Dim LEDs to reduce current draw
                self.leds.pixels.brightness = 0.05
                msg_out = Message(self.id, "ERROR", f"LOGIC_BROWNOUT:{v['log']}V")
                self.transport_up.send(msg_out)

            # Safety Check: Downstream Bus Failure
            if self.power.sat_pwr.value and v["bus"] < 17.0:
                self.power.emergency_kill() # Instant cut-off
                msg_out = Message(self.id, "ERROR", "BUS_SHUTDOWN:LOW_V")
                self.transport_up.send(msg_out)

            await asyncio.sleep(0.5)

    async def monitor_connection(self):
        """Background task to manage the downstream RJ45 power pass-through."""
        while True:
            # Scenario: Physical link detected but power is currently OFF
            if self.power.satbus_connected and not self.power.sat_pwr.value:
                msg_out = Message(self.id, "LOG", "LINK_DETECTED:INIT_PWR")
                self.transport_up.send(msg_out)
                # Perform soft-start to protect the bus
                success, error = await self.power.soft_start_satellites()
                if success:
                    msg_out = Message(self.id, "LOG", "LINK_ACTIVE")
                    self.transport_up.send(msg_out)
                else:
                    msg_out = Message(self.id, "ERROR", f"PWR_FAILED:{error}")
                    self.transport_up.send(msg_out)
                    self.leds.pixels.fill((255, 0, 0))

            # Scenario: Physical link lost while power is ON
            elif not self.power.satbus_connected and self.power.sat_pwr.value:
                self.power.emergency_kill() # Immediate hardware cut-off
                msg_out = Message(self.id, "ERROR", "LINK_LOST")
                self.transport_up.send(msg_out)
                self.leds.pixels.fill((0, 0, 0))

            await asyncio.sleep(0.5)

    async def start(self):
        """Main async loop for handling communication and tasks.

            TODO:
                Move the TX/RX handling into separate async tasks for better responsiveness.
        """
        # Start the trasnport tasks
        self.transport_up.start()
        self.transport_down.start()
        self.transport_up.enable_relay_from(self.transport_down)

        # Start monitoring tasks
        asyncio.create_task(self.monitor_power())
        asyncio.create_task(self.monitor_connection())
        asyncio.create_task(self.renderer.run())  # Start the RenderManager loop

        while True:
            # Feed the hardware watchdog timer to prevent system reset
            microcontroller.watchdog.feed()

            # TX TO UPSTREAM
            if not self.id: # Initial Discovery Phase
                if time.monotonic() - self.last_tx > 3.0:
                    msg_out = Message("SAT", "NEW_SAT", self.sat_type_id)
                    self.transport_up.send(msg_out)
                    self.last_tx = time.monotonic()
                    self.leds.flash_led(-1,
                                       Palette.AMBER,
                                       brightness=0.5,
                                       duration=1.0,
                                       priority=1)
            else: # Normal Operation
                if time.monotonic() - self.last_tx > 0.1:
                    # Use get_status_bytes() to avoid string allocation overhead
                    # Message class supports both str and bytes payloads
                    msg_out = Message(self.id, "STATUS", self.hid.get_status_bytes())
                    self.transport_up.send(msg_out)
                    self.last_tx = time.monotonic()

            # RX FROM UPSTREAM -> CMD PROCESSING & TX TO DOWNSTREAM
            try:
                # Receive message via transport (non-blocking)
                message = self.transport_up.receive()
                if message:
                    # Process if addressed to us or broadcast
                    if message.destination == self.id or message.destination == "ALL":
                        await self.process_local_cmd(message.command, message.payload)
                    # Forward message downstream
                    self.transport_down.send(message)
            except ValueError as e:
                # Buffer overflow or other error
                print(f"Transport Error: {e}")
            except Exception as e:
                print(f"Transport Unexpected Error: {e}")

            await asyncio.sleep(0.01)
