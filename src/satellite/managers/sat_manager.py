"""
Docstring for satellite.managers.sat_manager
"""

import asyncio
import time

import board
import busio

from utilities import Palette

from .hid_manager import HIDManager
from .led_manager import LEDManager
from .power_manager import PowerManager
from .segment_manager import SegmentManager

class SatManager:
    """Satellite-side Manager to handle various subsystems."""
    def __init__(self, sat_type):
        # Init Pins
        # UART Pins
        uart_up_tx = getattr(board, "GP1")
        uart_up_rx = getattr(board, "GP0")
        uart_down_tx = getattr(board, "GP4")
        uart_down_rx = getattr(board, "GP5")
        # LEDs
        led_pin = getattr(board, "GP6")
        # I2C Pins
        scl = getattr(board, "GP2")
        sda = getattr(board, "GP3")
        # Keypad Pins
        keypad_rows = [getattr(board, f"GP{n}") for n in (7,8,9,10)]
        keypad_cols = [getattr(board, f"GP{n}") for n in (11,12,13)]
        # Mosfet Control Pin
        mosfet_pin = getattr(board, "GP14")
        # Connection Sense Pin
        detect_pin = getattr(board, "GP15")
        # Encoder Pins
        encoder_pins = [
            getattr(board, "GP17"), # Encoder A
            getattr(board, "GP18"), # Encoder B
        ]
        button_pins = [
            getattr(board, "GP19"), # Encoder Button
        ]
        # Toggle Pins
        toggle_pins = [
            getattr(board, "GP20"), # Toggle 1
            getattr(board, "GP21"), # Toggle 2
            getattr(board, "GP22"), # Toggle 3
            getattr(board, "GP23"), # Toggle 4
        ]
        # Momentary Toggle Pins
        momentary_toggle_pins = [
            getattr(board, "GP24"), # Momentary Toggle 1 Up
            getattr(board, "GP25"), # Momentary Toggle 1 Down
        ]
        # ADC Pins for Power Monitoring
        sense_pins = [
            getattr(board, "GP26"), # Pre-MOSFET 20V Input
            getattr(board, "GP27"), # Post-MOSFET 20V Bus
            getattr(board, "GP28"), # 5V Logic Rail
        ]

        # Init power manager first for voltage readings
        self.power = PowerManager(sense_pins, mosfet_pin, detect_pin)

        # TODO Check power state

        # Init I2C bus
        self.i2c = busio.I2C(scl, sda)

        # Init other managers
        self.led = LEDManager(led_pin, num_pixels=6)
        self.hid = HIDManager(button_pins,
                              toggle_pins,
                              momentary_toggle_pins,
                              keypad_rows,
                              keypad_cols,
                              encoder_pins)
        self.segment = SegmentManager(self.i2c)

        # UART for satellite communication
        self.uart_up = busio.UART(uart_up_tx,
                                  uart_up_rx,
                                  baudrate=115200,
                                  receiver_buffer_size=512,
                                  timeout=0.01)
        self.uart_down = busio.UART(uart_down_tx,
                                   uart_down_rx,
                                   baudrate=115200,
                                   timeout=0.01)

        # State Variables
        self.sat_type = sat_type
        self.id = None
        self.last_tx = 0

    async def process_local_cmd(self, cmd, val):
        """Process commands addressed to this satellite.

        TODO Adjust async logic for LED and Segment tasks - will be handled by manager classes
        """
        if cmd == "ID_ASSIGN":
            type_prefix = val[:2]
            current_index = int(val[2:])
            if type_prefix == self.sat_type:
                # We are the correct type, increment the index
                new_index = current_index + 1
                self.id = f"{type_prefix}{new_index:02d}" # e.g. "0101"

                # Visual confirmation on 14-segments
                self.segment.start_message(f"ID {self.id}", loop=False)

                # Pass the NEW index downstream for the next box
                self.uart_down.write(f"ALL|ID_ASSIGN|{self.id}\n".encode())
            else:
                # Not our type? Pass it along unchanged
                self.uart_down.write(f"ALL|ID_ASSIGN|{val}\n".encode())

        elif cmd == "SETENC":
            # Set the encoder position to a specific value
            if len(val) > 0:
                self.hid.set_encoder_position(int(val))

        elif cmd == "LED" or cmd == "LEDFLASH" or cmd == "LEDBREATH":
            p = val.split(",")
            idx_raw = p[0]
            target_indices = range(6) if idx_raw == "ALL" else [int(idx_raw)]

            for i in target_indices:

                # E.g. LED|r,g,b,duration,brightness,priority
                # LED|0,100,100,100,2.0,0.2,2
                # Set LED 0 to RGB(100,100,100) for 2.0 seconds at 20% brightness, priority 2
                if cmd == "LED":
                    # Static Color
                    r, g, b = int(p[1]), int(p[2]), int(p[3])
                    duration = float(p[4]) if len(p) > 4 and float(p[4]) > 0 else None
                    brightness = float(p[5]) if len(p) > 5 else 1.0
                    priority = int(p[6]) if len(p) > 6 else 2
                    self.led.solid_led(i,
                                       (r, g, b),
                                       brightness=brightness,
                                       duration=duration,
                                       priority=priority)

                # E.g. LEDFLASH|r,g,b,duration,brightness,priority,speed,off_speed
                # LEDFLASH|0,255,0,2.0,0.5,2,0.5,0.1
                # LED 0 flashes green for 2s at 50% brightness, speed 0.5s on, 0.1s off, priority 2
                elif cmd == "LEDFLASH":
                    # Flashing Animation
                    r, g, b = int(p[1]), int(p[2]), int(p[3])
                    duration = float(p[4]) if len(p) > 4 and float(p[4]) > 0 else None
                    brightness = float(p[5]) if len(p) > 5 else 1.0
                    priority = int(p[6]) if len(p) > 6 else 2
                    speed = float(p[7]) if len(p) > 7 else 0.1
                    off_speed = float(p[8]) if len(p) > 8 else None
                    self.led.flash_led(i,
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
                    r, g, b = int(p[1]), int(p[2]), int(p[3])
                    duration = float(p[4]) if len(p) > 4 and float(p[4]) > 0 else None
                    brightness = float(p[5]) if len(p) > 5 else 1.0
                    priority = int(p[6]) if len(p) > 6 else 2
                    speed = float(p[7]) if len(p) > 7 else 2.0
                    self.led.breathe_led(i,
                                         (r, g, b),
                                         brightness=brightness,
                                         duration=duration,
                                         priority=priority,
                                         speed=speed)

        elif cmd == "LEDCYLON":
            # E.g. LEDCYLON|r,g,b,duration,speed
            # LEDCYLON|255,0,0,2.0,0.08
            # Red Cylon for 2 seconds at 0.08 speed
            p = val.split(",")
            r, g, b = int(p[0]), int(p[1]), int(p[2])
            duration = float(p[3]) if len(p) > 3 and float(p[3]) > 0 else 2.0
            speed = float(p[4]) if len(p) > 4 else 0.08
            self.led.start_cylon((r, g, b),
                                 duration=duration,
                                 speed=speed)

        elif cmd == "LEDCENTRI":
            # E.g. LEDCENTRI|r,g,b,duration,speed
            # LEDCENTRI|255,0,0,2.0,0.08
            # Red Centrifuge for 2 seconds at 0.08 speed
            p = val.split(",")
            r, g, b = int(p[0]), int(p[1]), int(p[2])
            duration = float(p[3]) if len(p) > 3 and float(p[3]) > 0 else 2.0
            speed = float(p[4]) if len(p) > 4 else 0.08
            self.led.start_centrifuge((r, g, b),
                                      duration=duration,
                                      speed=speed)

        elif cmd == "LEDRAINBOW":
            # E.g. LEDRAINBOW|duration,speed
            # LEDRAINBOW|2.0,0.08
            # Rainbow for 2 seconds at 0.08 speed
            p = val.split(",")
            duration = float(p[0]) if len(p) > 0 and float(p[0]) > 0 else 2.0
            speed = float(p[1]) if len(p) > 1 else 0.08
            self.led.start_rainbow(duration=duration,
                                   speed=speed)

        elif cmd == "LEDGLITCH":
            # E.g. LEDGLITCH|duration,speed
            # LEDGLITCH|2.0,0.08
            # Glitch for 2 seconds at 0.08 speed
            p = val.split(",")
            duration = float(p[0]) if len(p) > 0 and float(p[0]) > 0 else 2.0
            speed = float(p[1]) if len(p) > 1 else 0.08
            # TODO Find a way to pass multiple colors
            colors = [
                Palette.YELLOW,
                Palette.CYAN,
                Palette.WHITE,
                Palette.MAGENTA,
            ]
            self.led.start_glitch(colors,
                                   duration=duration,
                                   speed=speed)

        elif cmd == "DSP":
            # E.g. DSP|message,loop,speed,direction
            # DSP|HELLO,1,0.2,L
            # Display "HELLO" looping at 0.2s speed, left direction
            p = val.split(",")
            message = p[0]
            loop = True if (len(p) > 1 and p[1] == "1") else False
            speed = float(p[2]) if len(p) > 2 else 0.3
            direction = p[3] if len(p) > 3 else "L"

            # Cancel any existing display task and start new one
            self.segment.start_message(message, loop, speed, direction)

        elif cmd == "DSPCORRUPT":
            # E.g. DSPCORRUPT|duration
            # DSPCORRUPT|2.0
            # Start corruption animation for 2 seconds
            duration = float(val) if val and float(val) > 0 else 2.0
            self.segment.start_corruption(duration)

        elif cmd == "DSPMATRIX":
            # E.g. DSPMATRIX|duration
            # DSPMATRIX|2.0
            # Start matrix rain animation for 2 seconds
            duration = float(val) if val and float(val) > 0 else 2.0
            self.segment.start_matrix(duration)

    async def relay_downstream_to_upstream(self):
        """Ultra-fast, non-blocking relay of downstream data to the Master."""
        # Pre-allocate a buffer to avoid memory fragmentation
        buf = bytearray(64)
        while True:
            if self.uart_down.in_waiting > 0:
                # Read whatever is available and immediately fire it upstream
                num_read = self.uart_down.readinto(buf)
                self.uart_up.write(buf[:num_read])
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
                self.uart_up.write(f"{self.id}|POWER|{v['in']},{v['bus']},{v['log']}\n".encode())
                last_broadcast = now

            # Safety Check: Logic rail sagging (Potential Buck Converter or Audio overload)
            if v["log"] < 4.7:
                # Local warning: Dim LEDs to reduce current draw
                self.led.pixels.brightness = 0.05
                self.uart_up.write(f"{self.id}|ERROR|LOGIC_BROWNOUT:{v['log']}V\n".encode())

            # Safety Check: Downstream Bus Failure
            if self.power.sat_pwr.value and v["bus"] < 17.0:
                self.power.emergency_kill() # Instant cut-off
                self.uart_up.write(f"{self.id}|ERROR|BUS_SHUTDOWN:LOW_V\n".encode())

            await asyncio.sleep(0.5)

    async def monitor_connection(self):
        """Background task to manage the downstream RJ45 power pass-through."""
        while True:
            # Scenario: Physical link detected but power is currently OFF
            if self.power.satbus_connected and not self.power.sat_pwr.value:
                self.uart_up.write(f"{self.id}|LOG|LINK_DETECTED:INIT_PWR\n".encode())
                # Perform soft-start to protect the bus
                success, error = await self.power.soft_start_downstream()
                if success:
                    self.uart_up.write(f"{self.id}|LOG|LINK_ACTIVE\n".encode())
                else:
                    self.uart_up.write(f"{self.id}|ERROR|PWR_FAILED:{error}\n".encode())
                    self.led.pixels.fill((255, 0, 0))

            # Scenario: Physical link lost while power is ON
            elif not self.power.satbus_connected and self.power.sat_pwr.value:
                self.power.emergency_kill() # Immediate hardware cut-off
                self.uart_up.write(f"{self.id}|ERROR|LINK_LOST\n".encode())
                self.led.pixels.fill((0, 0, 0))

            await asyncio.sleep(0.5)

    async def start(self):
        """Main async loop for handling communication and tasks.

            TODO:
                Move the TX/RX handling into separate async tasks for better responsiveness.
        """
        asyncio.create_task(self.monitor_power())
        asyncio.create_task(self.monitor_connection())
        asyncio.create_task(self.relay_downstream_to_upstream())

        while True:

            # TX TO UPSTREAM
            if not self.id: # Initial Discovery Phase
                if time.monotonic() - self.last_tx > 3.0:
                    self.uart_up.write(f"NEW_SAT|{self.sat_type}\n".encode())
                    self.last_tx = time.monotonic()
                    self.led.flash_led(-1,
                                       Palette.AMBER,
                                       brightness=0.5,
                                       duration=1.0,
                                       priority=1)
            else: # Normal Operation
                if time.monotonic() - self.last_tx > 0.1:
                    self.uart_up.write(
                        f"{self.id}|STATUS|{self.hid.get_status_string()}\n".encode())
                    self.last_tx = time.monotonic()

            # RX FROM UPSTREAM -> CMD PROCESSING & TX TO DOWNSTREAM
            if self.uart_up.in_waiting:
                line = self.uart_up.readline().decode().strip()
                if "|" in line:
                    parts = line.split("|")
                    if parts[0] == self.id or parts[0] == "ALL":
                        self.process_local_cmd(parts[1], parts[2])
                    self.uart_down.write((line + "\n").encode())

            await asyncio.sleep(0.01)
