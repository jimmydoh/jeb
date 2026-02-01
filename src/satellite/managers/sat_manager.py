"""
Docstring for satellite.managers.sat_manager
"""

import asyncio
import time

import board
import busio

from .hid_manager import HIDManager
from .led_manager import LEDManager
from .power_manager import PowerManager
from .segment_manager import SegmentManager

class SatManager:
    """Satellite-side Manager to handle various subsystems."""
    def __init__(self, type):
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
        self.hid = HIDManager(button_pins, toggle_pins, momentary_toggle_pins, keypad_rows, keypad_cols, encoder_pins)
        self.segment = SegmentManager(self.i2c)

        # UART for satellite communication
        self.uart_up = busio.UART(uart_up_tx, uart_up_rx, baudrate=115200, receiver_buffer_size=512, timeout=0.01)
        self.uart_down = busio.UART(uart_down_tx, uart_down_rx, baudrate=115200, timeout=0.01)

        # State Variables
        self.type = type
        self.id = None
        self.last_tx = 0
        self.led_loops = [False] * 6
        self.led_tasks = [None] * 6
        self.global_led_task = None
        self.current_display_task = None

    def get_status_packet(self):
        """Read all inputs and format status packet."""
        # READ INPUTS
        # Expects Index 0 to be Buttons
        btn_val = "0" if not self.hid.enc_btn.value else "1"

        # Latching Toggles, 4-bit String
        toggle_bits = "".join(["1" if not t.value else "0" for t in self.hid.toggles])

        # Momentary Toggles "U", "D" or "C"
        momentary_1_val = "U" if not self.hid.momentary_1_up.value else ("D" if not self.hid.momentary_1_down.value else "C")
        momentary_vals = momentary_1_val + "C" # Placeholder for L2

        # Keypad
        k_event = self.hid.k_pad.events.get()
        k_val = str(k_event.key_number) if k_event and k_event.pressed else "N"

        # Raw Encoder Pins for Master-side Quadrature Logic
        enc_a_val = "1" if self.hid.enc_a.value else "0"
        enc_b_val = "1" if self.hid.enc_b.value else "0"

        # FORMAT: STATUS|Button,Toggles,Momentary,Key,EncA,EncB
        return f"STATUS|{btn_val},{toggle_bits},{momentary_vals},{k_val},{enc_a_val},{enc_b_val}\n"

    async def process_local_cmd(self, cmd, val):
        """Process commands addressed to this satellite.

        TODO Adjust async logic for LED and Segment tasks - will be handled by manager classes
        """
        if cmd == "ID_ASSIGN":
            type_prefix = val[:2]
            current_index = int(val[2:])
            if type_prefix == self.type:
                # We are the correct type, increment the index
                new_index = current_index + 1
                self.id = f"{type_prefix}{new_index:02d}" # e.g. "0101"

                # Visual confirmation on 14-segments
                asyncio.create_task(self.segment.segment_message(f"ID {self.id}", loop=False))

                # Pass the NEW index downstream for the next box
                self.uart_down.write(f"ALL|ID_ASSIGN|{self.id}\n".encode())
            else:
                # Not our type? Pass it along unchanged
                self.uart_down.write(f"ALL|ID_ASSIGN|{val}\n".encode())
        elif cmd == "LED" or cmd == "LEDBREATH":
            p = val.split(",")
            idx_raw = p[0]
            target_indices = range(6) if idx_raw == "ALL" else [int(idx_raw)]
            # Interrupt any global animation
            if self.global_led_task:
                    self.global_led_task.cancel()
            for i in target_indices:
                # Interrupt any existing animation for this specific LED
                self.led_loops[i] = False
                if self.led_tasks[i]:
                    self.led_tasks[i].cancel()

                # Apply New State
                if cmd == "LED":
                    # Static Color
                    r, g, b = [int(int(c) * 0.2) for c in p[1:4]]
                    self.led.pixels[i] = (r, g, b)

                elif cmd == "LEDBREATH":
                    # Start individual pulse task
                    r, g, b = int(p[1]), int(p[2]), int(p[3])
                    dur = float(p[4]) if len(p) > 4 else 2.0
                    self.led_tasks[i] = asyncio.create_task(self.led.breathe_led(i, (r, g, b), brightness=1.0, duration=dur))
        elif cmd == "LEDCYLON":
            # Split parameters: r, g, b, duration (optional)
            p = val.split(",")
            r, g, b = int(p[0]), int(p[1]), int(p[2])
            dur = float(p[3]) if len(p) > 3 else 2.0

            # Cancel any existing LED task and start new one
            for i in range(6):
                self.led_loops[i] = False
                if self.led_tasks[i]:
                    self.led_tasks[i].cancel()
                self.led_loops[i] = True
            self.global_led_task = asyncio.create_task(self.led.start_cylon((r, g, b), duration=dur))
        elif cmd == "LEDSTROBE":
            # Split parameters: r, g, b, duration (optional)
            p = val.split(",")
            r, g, b = int(p[0]), int(p[1]), int(p[2])
            dur = float(p[3]) if len(p) > 3 else 2.0

            # Cancel any existing LED task and start new one
            for i in range(6):
                self.led_loops[i] = False
                if self.led_tasks[i]:
                    self.led_tasks[i].cancel()
                self.led_loops[i] = True
            self.global_led_task = asyncio.create_task(self.led.start_strobe((r, g, b), duration=dur))
        elif cmd == "DSP":
            # Split parameters: message, loop (0/1), speed (float), direction (L/R)
            p = val.split(",")
            msg_text = p[0]
            do_loop = True if (len(p) > 1 and p[1] == "1") else False
            spd = float(p[2]) if len(p) > 2 else 0.3
            dir = p[3] if len(p) > 3 else "L"

            # Cancel any existing display task and start new one
            self.display_loop = False
            if self.current_display_task:
                self.current_display_task.cancel()
            await asyncio.sleep(0.01)
            asyncio.create_task(self.segment.segment_message(msg_text, do_loop, spd, dir))
        elif cmd == "DSPANIMCORRUPT":
            self.display_loop = False
            if self.current_display_task:
                self.current_display_task.cancel()
            # Duration can be passed in 'val' or defaulted
            dur = float(val) if val else 2.0
            self.current_display_task = asyncio.create_task(self.segment.display_corruption_anim(dur))
        elif cmd == "DSPANIMMATRIX":
            self.display_loop = False
            if self.current_display_task:
                self.current_display_task.cancel()
            # Duration can be passed in 'val' or defaulted
            dur = float(val) if val else 2.0
            self.current_display_task = asyncio.create_task(self.segment.display_matrix_rain(dur))


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
                    self.uart_up.write(f"NEW_SAT|{self.type}\n".encode())
                    self.last_tx = time.monotonic()
                    # TODO Better Amber LED Animation
                    self.led.pixels.fill((128, 64, 0))
            else: # Normal Operation
                if time.monotonic() - self.last_tx > 0.1:
                    self.uart_up.write(f"{self.id}|{self.get_status_packet()}\n".encode())
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
