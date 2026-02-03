#filepath: src/core/managers/jeb_manager.py
"""
Docstring for core.jeb_state
"""

import asyncio
import board
import busio
import neopixel
from adafruit_ticks import ticks_ms, ticks_diff

from modes import IndustrialStartup, MainMenu, SafeCracker, Simon
from satellites import IndustrialSatellite
from utilities import JEBPixel

from .audio_manager import AudioManager
from .display_manager import DisplayManager
from .hid_manager import HIDManager
from .led_manager import LEDManager
from .matrix_manager import MatrixManager
from .power_manager import PowerManager

class JEBManager:
    """Class to hold global state for the master controller."""
    def __init__(self):
        # Init Pins
        # UART Pins
        uart_tx = getattr(board, "GP0")
        uart_rx = getattr(board, "GP1")
        # GlowBit Matrix
        matrix_pin = getattr(board, "GP4")
        # E-Stop Pin
        estop_pin = getattr(board, "GP7")
        # I2C Pins
        scl = getattr(board, "GP9")
        sda = getattr(board, "GP8")
        # Mosfet Control Pin
        mosfet_pin = getattr(board, "GP14")
        # Connection Sense Pin
        detect_pin = getattr(board, "GP15")
        # I2S Audio Pins
        sck = getattr(board, "GP17")
        ws  = getattr(board, "GP16")
        sd  = getattr(board, "GP18")
        # Button Pins
        button_pins = [
            getattr(board, "GP19"), # Button A
            getattr(board, "GP20"), # Button B
            getattr(board, "GP21"), # Button C
            getattr(board, "GP22"), # Button D
            getattr(board, "GP25"), # Rotary Encoder Push
        ]
        # Rotary Encoder Pins
        encoder_pins = [
            getattr(board, "GP23"), # Encoder A
            getattr(board, "GP24"), # Encoder B
        ]
        # ADC Pins for Power Monitoring
        sense_pins = [
            getattr(board, "GP26"), # Pre-MOSFET 20V Input
            getattr(board, "GP27"), # Post-MOSFET 20V Bus
            getattr(board, "GP29"), # 5V LED Rail
            getattr(board, "GP28"), # 5V Logic Rail
        ]

        # Init power manager first for voltage readings
        self.power = PowerManager(sense_pins, mosfet_pin, detect_pin)

        # TODO Check power state

        # Init I2C bus
        self.i2c = busio.I2C(scl, sda)

        # Init other managers
        self.audio = AudioManager(sck,ws,sd)
        self.display = DisplayManager(self.i2c)
        self.hid = HIDManager(button_pins, estop_pin, encoder_pins)

        # Init LEDs
        self.root_pixels = neopixel.NeoPixel(matrix_pin, 68, brightness=0.2, auto_write=False)
        self.matrix_jeb_pixel = JEBPixel(self.root_pixels, start_idx=0, num_pixels=64)
        self.matrix = MatrixManager(self.matrix_jeb_pixel)
        self.led_jeb_pixel = JEBPixel(self.root_pixels, start_idx=64, num_pixels=4)
        self.leds = LEDManager(self.led_jeb_pixel)

        # Preload Common UI Sounds
        self.audio.preload([
            "audio/menu_tick.wav",
            "audio/menu_select.wav",
        ])

        # UART for satellite communication
        self.uart = busio.UART(uart_tx, uart_rx, baudrate=115200, receiver_buffer_size=512, timeout=0.01)

        # System State
        self.satellites = {}
        self.sat_telemetry = {}
        self.mode = "DASHBOARD"
        self.meltdown = False
        self.sat_active = False
        self.last_raw_uart = ""

    async def discover_satellites(self):
        """Triggers the ID assignment chain."""
        await self.display.update_status("SCANNING BUS...", "ASSIGNING IDs")
        # Reset local registry
        self.satellites = {}

        # Broadcast to Industrial type (01) starting at index 00
        self.uart.write("ALL|ID_ASSIGN|0100\n".encode())
        await asyncio.sleep(0.5)

    def get_sat(self, sid):
        """Retrieve a satellite by its ID."""
        return self.satellites.get(sid)

    def send_all(self, cmd, val):
        """Broadcast a command to all connected satellites."""
        for sid in self.satellites:
            self.get_sat(sid).send_cmd(cmd, val)

    async def cleanup_task(self, task):
        """Gracefully awaits the cancellation of a task."""
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def run_mode_with_safety(self, mode_instance, target_sat=None):
        """Execute a task while monitoring for interrupts.

        Parameters:
            mode_coroutine (coroutine): The main game or mode coroutine to run.
            target_sat (Satellite, optional): Specific satellite to monitor.
        """
        # Create the game as a background task
        sub_task = asyncio.create_task(mode_instance.execute())

        while not sub_task.done():
            # E-Stop engaged
            if self.meltdown:
                sub_task.cancel()
                await self.cleanup_task(sub_task)
                return "ESTOP_ABORT"

            # Long-press Button D to abort
            if self.hid.is_pressed(3, long=True, duration=5000):
                sub_task.cancel()
                await self.display.update_status("USER ABORT", "EXITING MODE...")
                await self.cleanup_task(sub_task)
                return "MANUAL_ABORT"

            # Target satellite unplugged
            # (if applicable)
            if target_sat and not target_sat.is_active:
                sub_task.cancel()
                await self.cleanup_task(sub_task)
                return "LINK_LOST"
            await asyncio.sleep(0.1)
        return "SUCCESS"

    def handle_packet(self, line):
        """Parses incoming UART packets and updates satellite states."""
        self.last_raw_uart = line
        try:
            parts = line.split("|")
            if len(parts) < 3:
                return  # Malformed packet

            sid, cmd, payload = parts[0], parts[1], parts[2]

            # Command Processing
            if cmd == "STATUS":
                if sid in self.satellites:
                    if not self.satellites[sid].is_active:
                        self.satellites[sid].is_active = True
                        asyncio.create_task(self.display.update_status("SAT RECONNECTED", f"ID: {sid}"))
                        if self.satellites[sid].sat_type == "INDUSTRIAL":
                            self.satellites[sid].send_cmd("DSPANIMCORRECT", "1.5")
                            asyncio.create_task(self.audio.play_sfx("link_restored.wav", voice=1))
                    self.satellites[sid].update_heartbeat()
                    self.satellites[sid].update_from_packet(payload)
                else:
                    asyncio.create_task(self.display.update_status("UNKNOWN SAT",f"{sid} sent STATUS."))
            elif cmd == "POWER":
                v_data = payload.split(",")
                self.sat_telemetry[sid] = {
                    "in": float(v_data[0]),
                    "bus": float(v_data[1]),
                    "log": float(v_data[2])
                }
            elif cmd == "ERROR":
                asyncio.create_task(self.display.update_status("REMOTE FAULT", f"SAT {sid}: {payload}"))
                asyncio.create_task(self.audio.play_sfx("alarm_klaxon.wav", voice=1))
            elif cmd == "HELLO":
                if sid in self.satellites:
                    self.satellites[sid].update_heartbeat()
                else:
                    if payload == "INDUSTRIAL":
                        self.satellites[sid] = IndustrialSatellite(sid, self.uart)
                    asyncio.create_task(self.display.update_status("NEW SAT",f"{sid} sent HELLO."))
            elif cmd == "NEW_SAT":
                asyncio.create_task(self.display.update_status("SAT CONNECTED", f"TYPE {payload} FOUND"))
                self.uart.write(f"ALL|ID_ASSIGN|{payload}00\n".encode())
            else:
                asyncio.create_task(self.display.update_status("UNKNOWN COMMAND", f"{sid} sent {cmd}"))
        except Exception as e:
            print(f"Error handling packet: {e}")

    async def monitor_sats(self):
        """Background task to monitor inbound messages from satellite boxes."""
        while True:
            # UART Packet Handling
            if self.power.satbus_powered and self.uart.in_waiting > 0:
                while self.uart.in_waiting > 0:
                    raw_line = self.uart.readline()
                    if raw_line is not None:
                        try:
                            line = raw_line.decode().strip()
                            if line:
                                self.handle_packet(line)
                        except UnicodeError:
                            print("UART Malformed Packet Received")

            # Link Watchdog
            now = ticks_ms()
            for sid, sat in self.satellites.items():
                if ticks_diff(now, sat.last_seen) > 5000:
                    if sat.is_active:
                        sat.is_active = False
                        asyncio.create_task(self.display.update_status("LINK LOST", f"ID: {sid}"))
                else:
                    if not sat.is_active:
                        sat.is_active = True
                        asyncio.create_task(self.display.update_status("LINK RESTORED", f"ID: {sid}"))

            await asyncio.sleep(0.01)

    async def monitor_estop(self):
        """Background task to monitor the Emergency Stop button.

        Engaging the E-Stop triggers meltdown mode with audio alarms.

        Releasing the E-Stop resets the system.
        """
        while True:
            if not self.hid.estop and not self.meltdown:
                self.meltdown = True
                self.send_all("LED", "ALL,0,0,0") # Kill all LEDs

                # Audio Alarms
                await self.audio.play_sfx("background_winddown.wav", voice=0, loop=False)
                await self.audio.set_volume(0, 0.2)
                await self.audio.play_sfx("alarm_klaxon.wav", voice=1, loop=True)
                await self.audio.play_sfx("voice_meltdown.wav", voice=2, loop=True)

                # High Contrast Warning on OLED
                self.display.update_status("!!! EMERGENCY STOP !!!", "PULL UP TO RESET")

                # Strobe the neobar and satellite LEDs
                while not self.hid.estop: # While button is still latched down
                    # TODO Implement alarm LED strobing
                    await asyncio.sleep(0.2)

                # Once button is twisted/reset
                self.meltdown = False
                await self.audio.play_sfx("system_reset.wav")
                await self.display.update_status("SAFETY RESET", "PLEASE STAND BY")
                await asyncio.sleep(2)
            await asyncio.sleep(0.01)

    async def monitor_power(self):
        """Background task to watch for brownouts or disconnects."""
        while True:
            v = self.power.status

            if self.mode == "DASHBOARD":
                #self.display.update_telemetry(v["bus"], v["log"])
                # TODO Implement telemetry display
                print(f"Power Rail - BUS: {v['bus']:.2f}V | LOGIC: {v['log']:.2f}V")

            # Scenario: LED buck converter is failing or overloaded
            if v["led"] < 4.5 and v["raw"] > 18.0:
                await self.display.update_status("LED PWR FAILURE", "CHECK 5A FUSE")
                # Potentially dim the GlowBit automatically to save power
                self.matrix.pixels.brightness = 0.02

            # Scenario: Logic rail is sagging (Audio Amp drawing too much?)
            if v["log"] < 4.7:
                await self.display.update_status("LOGIC BROWNOUT", "REDUCING VOLUME")
                await self.audio.set_volume(1, 0.5) # Lower SFX volume

            await asyncio.sleep(0.5)

    async def monitor_connection(self):
        """Background task to detect physical RJ45 connection and manage bus power."""
        while True:
            if self.power.satbus_connected and not self.power.satbus_powered:
                # PHYSICAL LINK DETECTED - Trigger Soft Start
                await self.display.update_status("LINK DETECTED", "POWERING BUS...")
                success, error = await self.power.soft_start_satellites()

                if success:
                    await self.audio.play_sfx("link_restored.wav", voice=1)
                    # Power is stable, trigger the ID assignment chain
                    await self.discover_satellites()
                else:
                    await self.display.update_status("PWR ERROR", error)
                    await self.audio.play_sfx("fail.wav", voice=1)

            elif not self.power.satbus_connected and self.power.satbus_powered:
                # PHYSICAL LINK LOST - Immediate Hardware Cut-off
                self.power.emergency_kill()
                await self.display.update_status("SAT LINK LOST", "BUS OFFLINE")
                await self.audio.play_sfx("link_lost.wav", voice=1)

            await asyncio.sleep(0.5) # Poll twice per second to save CPU

    async def start(self):
        """Main async loop for the Master Controller."""
        # Start background infrastructure tasks
        asyncio.create_task(self.monitor_sats()) # UART Comms
        asyncio.create_task(self.monitor_estop()) # Emergency Stop
        asyncio.create_task(self.monitor_power()) # Analog Power Monitoring
        asyncio.create_task(self.monitor_connection()) # RJ45 Link Detection
        asyncio.create_task(self.matrix.animate_loop()) # LED Matrix Animations

        # Fancy bootup sequence
        #TODO Add boot animation
        self.audio.play_sfx("voice/os_online.wav", voice=2)

        while True:
            # Meltdown state pauses the menu selection
            while self.meltdown:
                await asyncio.sleep(0.1)

            # MAIN MENU
            # Display the main menu and get selected mode
            self.mode = await self.run_mode_with_safety(MainMenu(self))

            # Handle e-stops first
            if self.mode == "ESTOP_ABORT":
                # System is in meltdown; loop back and wait for reset
                continue

            # Otherwise run the selected mode
            # Core Box Games
            elif self.mode == "SIMON":
                await self.run_mode_with_safety(Simon(self, 0.5, 3000))
            elif self.mode == "SAFE":
                await self.run_mode_with_safety(SafeCracker(self))

            # Industrial Satellite Games
            elif self.mode == "IND":
                sat = next((s for s in self.satellites.values() if s.sat_type == "INDUSTRIAL"), None)
                if sat:
                    mode_instance = IndustrialStartup(self, sat)
                    run_ind = True
                    while run_ind:
                        result = await self.run_mode_with_safety(mode_instance, target_sat=sat)
                        if result == "LINK_LOST":
                            await self.display.update_status("LINK LOST", "RECONNECT IN 60s")
                            asyncio.create_task(self.audio.play_sfx("link_lost.wav", voice=1))
                            await asyncio.sleep(1)
                            # 60 second countdown
                            disconnect_time = ticks_ms()
                            while not sat.is_active and run_ind:
                                elapsed = ticks_diff(ticks_ms(), disconnect_time)
                                if elapsed > 60000:
                                    run_ind = False
                                    continue
                                secs_left = 60 - (elapsed // 1000)
                                await self.display.update_status("LINK LOST", f"ABORT IN: {secs_left}s")
                                await asyncio.sleep(0.1)
                            if sat.is_active and run_ind:
                                await self.display.update_status("LINK RESTORED", "RESUMING...")
                                asyncio.create_task(self.audio.play_sfx("link_restored.wav", voice=1))
                                await asyncio.sleep(1)
                        else:
                            run_ind = False
            # Returns from sub-menus
            elif self.mode == "SETTINGS":
                continue
            elif self.mode == "DEBUG":
                continue
            elif self.mode == "CALIB":
                continue
            elif self.mode == "UARTLOG":
                continue
            elif self.mode == "FACTORY_RESET":
                await self.display.update_status("FACTORY RESET", "REBOOTING...")
                await asyncio.sleep(2)

            await asyncio.sleep(0.1)
