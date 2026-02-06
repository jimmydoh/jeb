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

from utilities import JEBPixel, Palette, Pins, parse_values, get_int, get_float, get_str

from transport import Message, UARTTransport, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS

from managers import HIDManager, LEDManager, PowerManager, SegmentManager, UARTManager

from .base import Satellite

TYPE_ID = "01"
TYPE_NAME = "INDUSTRIAL"


class _QueuedUARTManager:
    """Wrapper for UARTManager that writes to a queue instead of hardware.
    
    This prevents race conditions by ensuring all upstream UART writes
    go through a single TX worker task that drains the queue.
    """
    
    def __init__(self, queue):
        """Initialize the queued UART manager.
        
        Parameters:
            queue (asyncio.Queue): Queue to push data to.
        """
        self.queue = queue
    
    def write(self, data):
        """Queue data for writing instead of writing directly.
        
        This is a synchronous wrapper around the async queue.put().
        In CircuitPython's asyncio, we can use put_nowait() since
        the queue is unbounded by default.
        
        Parameters:
            data (bytes): Data to queue for transmission.
            
        Raises:
            asyncio.QueueFull: If the queue is somehow bounded and full.
        """
        try:
            # Use put_nowait for synchronous context
            # This is safe because asyncio.Queue is unbounded by default
            self.queue.put_nowait(data)
        except Exception as e:
            # In case of unexpected queue behavior, raise with context
            raise RuntimeError(f"Failed to queue UART data: {e}") from e


class IndustrialSatelliteFirmware(Satellite):
    """Satellite-side firmware for Industrial Satellite.

    Handles hardware I/O, power management, and local command processing.
    Runs on the physical satellite hardware and manages all peripherals.
    """
    
    def __init__(self):
        """Initialize the Industrial Satellite Firmware."""
        # State Variables
        self.last_tx = 0

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

        # Wrap UARTs with buffering managers
        uart_up_mgr = UARTManager(uart_up_hw)
        uart_down_mgr = UARTManager(uart_down_hw)
        
        # Create upstream TX queue to prevent race conditions
        # All upstream writes must go through this queue
        self.upstream_queue = asyncio.Queue()
        
        # Create a wrapper UART manager that writes to the queue
        self.uart_up_mgr_queued = _QueuedUARTManager(self.upstream_queue)
        
        # Wrap with transport layer using the queued manager
        self.transport_up = UARTTransport(self.uart_up_mgr_queued, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
        self.transport_down = UARTTransport(uart_down_mgr, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
        
        # Store the raw UART managers
        self.uart_up_mgr = uart_up_mgr  # Hardware UART (only used by TX worker)
        self.uart_down_mgr = uart_down_mgr
        
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

    async def process_local_cmd(self, cmd, val):
        """Process commands addressed to this satellite.
        
        Handles both text and binary payloads efficiently.
        Binary payloads are processed using parse_values() which now
        avoids the "String Boomerang" issue.

        TODO Adjust async logic for LED and Segment tasks - will be handled by manager classes
        """
        if cmd == "ID_ASSIGN":
            # ID_ASSIGN uses text format, ensure val is string
            if isinstance(val, bytes):
                val = val.decode('utf-8')
            type_prefix = val[:2]
            current_index = int(val[2:])
            if type_prefix == self.sat_type_id:
                # We are the correct type, increment the index
                new_index = current_index + 1
                self.id = f"{type_prefix}{new_index:02d}" # e.g. "0101"

                # Visual confirmation on 14-segments
                self.segment.start_message(f"ID {self.id}", loop=False)

                # Pass the NEW index downstream for the next box
                msg_out = Message("ALL", "ID_ASSIGN", self.id)
                self.transport_down.send(msg_out)
            else:
                # Not our type? Pass it along unchanged
                msg_out = Message("ALL", "ID_ASSIGN", val)
                self.transport_down.send(msg_out)

        elif cmd == "SETENC":
            # Set the encoder position to a specific value
            # parse_values now handles both bytes and strings efficiently!
            if len(val) > 0:
                values = parse_values(val)
                self.hid.reset_encoder(get_int(values, 0))

        elif cmd == "LED" or cmd == "LEDFLASH" or cmd == "LEDBREATH":
            # Parse payload once for all LED types
            # parse_values now handles bytes without String Boomerang!
            values = parse_values(val)
            idx_raw = get_str(values, 0)
            target_indices = range(6) if idx_raw == "ALL" else [get_int(values, 0)]

            for i in target_indices:

                # E.g. LED|r,g,b,duration,brightness,priority
                # LED|0,100,100,100,2.0,0.2,2
                # Set LED 0 to RGB(100,100,100) for 2.0 seconds at 20% brightness, priority 2
                if cmd == "LED":
                    # Static Color
                    r = get_int(values, 1)
                    g = get_int(values, 2)
                    b = get_int(values, 3)
                    duration_val = get_float(values, 4)
                    duration = duration_val if duration_val > 0 else None
                    brightness = get_float(values, 5, 1.0)
                    priority = get_int(values, 6, 2)
                    self.leds.solid_led(i,
                                       (r, g, b),
                                       brightness=brightness,
                                       duration=duration,
                                       priority=priority)

                # E.g. LEDFLASH|r,g,b,duration,brightness,priority,speed,off_speed
                # LEDFLASH|0,255,0,2.0,0.5,2,0.5,0.1
                # LED 0 flashes green for 2s at 50% brightness, speed 0.5s on, 0.1s off, priority 2
                elif cmd == "LEDFLASH":
                    # Flashing Animation
                    r = get_int(values, 1)
                    g = get_int(values, 2)
                    b = get_int(values, 3)
                    duration_val = get_float(values, 4)
                    duration = duration_val if duration_val > 0 else None
                    brightness = get_float(values, 5, 1.0)
                    priority = get_int(values, 6, 2)
                    speed = get_float(values, 7, 0.1)
                    off_speed_val = get_float(values, 8)
                    off_speed = off_speed_val if off_speed_val > 0 else None
                    self.leds.flash_led(i,
                                       (r, g, b),
                                       brightness=brightness,
                                       duration=duration,
                                       priority=priority,
                                       speed=speed,
                                       off_speed=off_speed)

                # E.g. LEDBREATH|r,g,b,duration,brightness,priority,speed
                # LEDBREATH|0,0,0,255,2.0,0.2,3,2.0
                # LED 0 breathes blue over 2s at 20% brightness, speed 2.0, priority 3
                elif cmd == "LEDBREATH":
                    # Breathing Animation
                    r = get_int(values, 1)
                    g = get_int(values, 2)
                    b = get_int(values, 3)
                    duration_val = get_float(values, 4)
                    duration = duration_val if duration_val > 0 else None
                    brightness = get_float(values, 5, 1.0)
                    priority = get_int(values, 6, 2)
                    speed = get_float(values, 7, 2.0)
                    self.leds.breathe_led(i,
                                         (r, g, b),
                                         brightness=brightness,
                                         duration=duration,
                                         priority=priority,
                                         speed=speed)

        elif cmd == "LEDCYLON":
            # E.g. LEDCYLON|r,g,b,duration,speed
            # LEDCYLON|255,0,0,2.0,0.08
            # Red Cylon for 2 seconds at 0.08 speed
            values = parse_values(val)
            r = get_int(values, 0)
            g = get_int(values, 1)
            b = get_int(values, 2)
            duration_val = get_float(values, 3, 2.0)
            duration = duration_val if duration_val > 0 else 2.0
            speed = get_float(values, 4, 0.08)
            self.leds.start_cylon((r, g, b),
                                 duration=duration,
                                 speed=speed)

        elif cmd == "LEDCENTRI":
            # E.g. LEDCENTRI|r,g,b,duration,speed
            # LEDCENTRI|255,0,0,2.0,0.08
            # Red Centrifuge for 2 seconds at 0.08 speed
            values = parse_values(val)
            r = get_int(values, 0)
            g = get_int(values, 1)
            b = get_int(values, 2)
            duration_val = get_float(values, 3, 2.0)
            duration = duration_val if duration_val > 0 else 2.0
            speed = get_float(values, 4, 0.08)
            self.leds.start_centrifuge((r, g, b),
                                      duration=duration,
                                      speed=speed)

        elif cmd == "LEDRAINBOW":
            # E.g. LEDRAINBOW|duration,speed
            # LEDRAINBOW|2.0,0.08
            # Rainbow for 2 seconds at 0.08 speed
            values = parse_values(val)
            duration_val = get_float(values, 0, 2.0)
            duration = duration_val if duration_val > 0 else 2.0
            speed = get_float(values, 1, 0.08)
            self.leds.start_rainbow(duration=duration,
                                   speed=speed)

        elif cmd == "LEDGLITCH":
            # E.g. LEDGLITCH|duration,speed
            # LEDGLITCH|2.0,0.08
            # Glitch for 2 seconds at 0.08 speed
            values = parse_values(val)
            duration_val = get_float(values, 0, 2.0)
            duration = duration_val if duration_val > 0 else 2.0
            speed = get_float(values, 1, 0.08)
            # TODO Find a way to pass multiple colors
            colors = [
                Palette.YELLOW,
                Palette.CYAN,
                Palette.WHITE,
                Palette.MAGENTA,
            ]
            self.leds.start_glitch(colors,
                                   duration=duration,
                                   speed=speed)

        elif cmd == "DSP":
            # E.g. DSP|message,loop,speed,direction
            # DSP|HELLO,1,0.2,L
            # Display "HELLO" looping at 0.2s speed, left direction
            values = parse_values(val)
            message = get_str(values, 0)
            loop = True if get_str(values, 1) == "1" else False
            speed = get_float(values, 2, 0.3)
            direction = get_str(values, 3, "L")

            # Cancel any existing display task and start new one
            self.segment.start_message(message, loop, speed, direction)

        elif cmd == "DSPCORRUPT":
            # E.g. DSPCORRUPT|duration
            # DSPCORRUPT|2.0
            # Start corruption animation for 2 seconds
            values = parse_values(val)
            duration_val = get_float(values, 0, 2.0)
            duration = duration_val if duration_val > 0 else 2.0
            self.segment.start_corruption(duration)

        elif cmd == "DSPMATRIX":
            # E.g. DSPMATRIX|duration
            # DSPMATRIX|2.0
            # Start matrix rain animation for 2 seconds
            values = parse_values(val)
            duration_val = get_float(values, 0, 2.0)
            duration = duration_val if duration_val > 0 else 2.0
            self.segment.start_matrix(duration)

    async def _upstream_tx_worker(self):
        """Dedicated task to drain the upstream TX queue to hardware.
        
        This is the ONLY task that should write directly to uart_up_mgr.
        All other code must push data to upstream_queue.
        
        This prevents race conditions where multiple tasks interleave
        partial packets, causing CRC failures and data corruption.
        """
        while True:
            # Wait for data to be available in the queue
            data = await self.upstream_queue.get()
            # Write to hardware UART
            self.uart_up_mgr.write(data)
            # Mark task as done
            self.upstream_queue.task_done()

    async def relay_downstream_to_upstream(self):
        """Ultra-fast, non-blocking relay of downstream data to the Master.
        
        Pushes data to the upstream TX queue instead of direct hardware write
        to prevent race conditions with transport_up messages.
        """
        # Pre-allocate a buffer to avoid memory fragmentation
        buf = bytearray(64)
        while True:
            if self.uart_down_mgr.in_waiting > 0:
                # Read whatever is available and queue it for upstream transmission
                num_read = self.uart_down_mgr.readinto(buf)
                # Copy to bytes() is necessary since buf is reused in the loop
                # and the queued data must remain valid until the TX worker processes it
                await self.upstream_queue.put(bytes(buf[:num_read]))
            await asyncio.sleep(0) # Yield control immediately to other tasks

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
        # Start the dedicated upstream TX worker (prevents race conditions)
        asyncio.create_task(self._upstream_tx_worker())
        # Start monitoring tasks
        asyncio.create_task(self.monitor_power())
        asyncio.create_task(self.monitor_connection())
        asyncio.create_task(self.relay_downstream_to_upstream())

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
