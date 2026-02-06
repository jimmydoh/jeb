# File: src/core/core_manager.py
"""Core Manager for JEB Master Controller."""

import asyncio
import busio
import microcontroller
import neopixel
from adafruit_ticks import ticks_ms, ticks_diff

from modes import IndustrialStartup, JEBris, MainMenu, SafeCracker, Simon

from satellites import IndustrialSatelliteDriver

from utilities import JEBPixel, Pins, parse_values, get_float

from transport import Message, UARTTransport, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS

from managers import AudioManager
from managers import BuzzerManager
from managers import DataManager
from managers import DisplayManager
from managers import HIDManager
from managers import LEDManager
from managers import MatrixManager
from managers import PowerManager
from managers import SynthManager
from managers import UARTManager

class CoreManager:
    """Class to hold global state for the master controller."""

    def __init__(self, root_data_dir="/"):

        self.root_data_dir = root_data_dir

        # Init Data Manager for persistent storage of scores and settings
        self.data = DataManager(root_dir=root_data_dir)

        # Init Pins
        Pins.initialize(profile="CORE", type_id="00")

        # Init power manager first for voltage readings
        self.power = PowerManager(
            Pins.SENSE_PINS,
            ["input", "satbus", "main", "led"],
            Pins.MOSFET_CONTROL,
            Pins.SATBUS_DETECT
        )

        # TODO Check power state

        # Init Buzzer for early audio feedback
        self.buzzer = BuzzerManager(Pins.BUZZER, volume=0.5)
        self.buzzer.play_song("POWER_UP")

        # Init I2C bus
        self.i2c = busio.I2C(
            Pins.I2C_SCL,
            Pins.I2C_SDA
        )

        # Init other managers
        self.audio = AudioManager(
            Pins.I2S_SCK,
            Pins.I2S_WS,
            Pins.I2S_SD,
            root_data_dir=self.root_data_dir
        )

        self.synth = SynthManager()
        self.audio.attach_synth(self.synth.source) # Connect synth to audio mixer
        
        self.display = DisplayManager(self.i2c)
        self.hid = HIDManager(
            encoders=Pins.ENCODERS,
            mcp_i2c=self.i2c,
            mcp_int_pin=Pins.EXPANDER_INT,
            expanded_buttons=Pins.EXPANDER_BUTTONS
        )

        # Init LEDs
        self.root_pixels = neopixel.NeoPixel(
            Pins.LED_CONTROL,
            68,
            brightness=0.3,
            auto_write=False
        )

        # LED Matrix Manager (first 64 pixels)
        self.matrix_jeb_pixel = JEBPixel(
            self.root_pixels,
            start_idx=0,
            num_pixels=64
        )
        self.matrix = MatrixManager(self.matrix_jeb_pixel)

        # Button LED Manager (last 4 pixels)
        self.led_jeb_pixel = JEBPixel(
            self.root_pixels,
            start_idx=64,
            num_pixels=4
        )
        self.leds = LEDManager(self.led_jeb_pixel)

        # Preload Common UI Sounds
        self.audio.preload([
            "audio/menu_tick.wav",
            "audio/menu_select.wav",
        ])

        # UART for satellite communication
        uart_hw = busio.UART(
            Pins.UART_TX,
            Pins.UART_RX,
            baudrate=115200,
            receiver_buffer_size=512,
            timeout=0.01
            )

        # Wrap UART with buffering manager
        uart_manager = UARTManager(uart_hw)

        # Wrap with transport layer for protocol handling
        self.transport = UARTTransport(uart_manager, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

        # System State
        self.satellites = {}
        self.sat_telemetry = {}
        self.mode = "DASHBOARD"
        self.meltdown = False
        self.sat_active = False
        self.last_message_debug = ""

    async def discover_satellites(self):
        """Triggers the ID assignment chain."""
        await self.display.update_status("SCANNING BUS...", "ASSIGNING IDs")
        # Reset local registry
        self.satellites = {}

        # Broadcast to Industrial type (01) starting at index 00
        message = Message("ALL", "ID_ASSIGN", "0100")
        self.transport.send(message)
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
            if self.hid.is_button_pressed(3, long=True, duration=5000):
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

    def handle_message(self, message):
        """Processes incoming messages and updates satellite states."""
        # Store message representation for debugging
        self.last_message_debug = str(message)
        try:
            sid = message.destination
            cmd = message.command
            payload = message.payload

            # Command Processing
            if cmd == "STATUS":
                if sid in self.satellites:
                    if not self.satellites[sid].is_active:
                        self.satellites[sid].is_active = True
                        asyncio.create_task(
                            self.display.update_status(
                                "SAT RECONNECTED",
                                f"ID: {sid}"
                            )
                        )
                        if self.satellites[sid].sat_type == "INDUSTRIAL":
                            self.satellites[sid].send_cmd("DSPANIMCORRECT", "1.5")
                            asyncio.create_task(
                                self.audio.play(
                                    "link_restored.wav",
                                    channel=self.audio.CH_SFX
                                )
                            )
                    self.satellites[sid].update_from_packet(payload)
                else:
                    asyncio.create_task(
                        self.display.update_status(
                            "UNKNOWN SAT",
                            f"{sid} sent STATUS."
                        )
                    )
            elif cmd == "POWER":
                v_data = parse_values(payload)
                self.sat_telemetry[sid] = {
                    "in": get_float(v_data, 0),
                    "bus": get_float(v_data, 1),
                    "log": get_float(v_data, 2)
                }
            elif cmd == "ERROR":
                asyncio.create_task(
                    self.display.update_status(
                        "SAT ERROR",
                        f"ID: {sid} ERR: {payload}"
                    )
                )
                asyncio.create_task(self.audio.play("alarm_klaxon.wav", channel=self.audio.CH_SFX))
            elif cmd == "HELLO":
                if sid in self.satellites:
                    self.satellites[sid].update_heartbeat()
                else:
                    if payload == "INDUSTRIAL":
                        self.satellites[sid] = IndustrialSatelliteDriver(sid, self.transport)
                    asyncio.create_task(
                        self.display.update_status(
                            "NEW SAT",
                            f"{sid} sent HELLO."
                        )
                    )
            elif cmd == "NEW_SAT":
                asyncio.create_task(
                    self.display.update_status(
                        "SAT CONNECTED",
                        f"TYPE {payload} FOUND"
                    )
                )
                msg_out = Message("ALL", "ID_ASSIGN", f"{payload}00")
                self.transport.send(msg_out)
            else:
                asyncio.create_task(
                    self.display.update_status(
                        "UNKNOWN COMMAND",
                        f"{sid} sent {cmd}"
                    )
                )
        except Exception as e:
            print(f"Error handling message: {e}")

    async def monitor_sats(self):
        """Background task to monitor inbound messages from satellite boxes."""
        while True:
            # Message Handling via transport layer
            if self.power.satbus_powered:
                try:
                    # Receive message via transport (non-blocking)
                    message = self.transport.receive()
                    if message:
                        self.handle_message(message)
                except ValueError as e:
                    # Buffer overflow or other error
                    print(f"Transport Error: {e}")
                except Exception as e:
                    print(f"Transport Unexpected Error: {e}")

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
                        asyncio.create_task(
                            self.display.update_status(
                                "LINK RESTORED",
                                f"ID: {sid}"
                            )
                        )

            await asyncio.sleep(0.01)

    async def monitor_estop(self):
        """Background task to monitor the E-Stop button (gameplay interaction).

        Engaging the E-Stop triggers meltdown mode with audio alarms.

        Releasing the E-Stop resets the system.
        """
        while True:
            if not self.hid.estop and not self.meltdown:
                self.meltdown = True
                self.send_all("LED", "ALL,0,0,0") # Kill all LEDs

                # Audio Alarms
                await self.audio.play(
                    "background_winddown.wav",
                    channel=self.audio.CH_ATMO,
                    loop=False
                )
                await self.audio.set_level(self.audio.CH_ATMO, 0.2)
                await self.audio.play(
                    "alarm_klaxon.wav",
                    channel=self.audio.CH_SFX,
                    loop=True
                )
                await self.audio.play(
                    "voice_meltdown.wav",
                    channel=self.audio.CH_VOICE,
                    loop=True
                )

                # High Contrast Warning on OLED
                self.display.update_status("!!! EMERGENCY STOP !!!", "PULL UP TO RESET")

                # Strobe the neobar and satellite LEDs
                while not self.hid.estop: # While button is still latched down
                    # TODO Implement alarm LED strobing
                    await asyncio.sleep(0.2)

                # Once button is twisted/reset
                self.meltdown = False
                await self.audio.play("system_reset.wav")
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
                await self.audio.set_level(self.audio.CH_SFX, 0.5) # Lower SFX volume

            await asyncio.sleep(0.5)

    async def monitor_connection(self):
        """Background task to detect physical RJ45 connection and manage bus power."""
        while True:
            if self.power.satbus_connected and not self.power.satbus_powered:
                # PHYSICAL LINK DETECTED - Trigger Soft Start
                await self.display.update_status("LINK DETECTED", "POWERING BUS...")
                success, error = await self.power.soft_start_satellites()

                if success:
                    await self.audio.play("link_restored.wav", channel=self.audio.CH_SFX)
                    # Power is stable, trigger the ID assignment chain
                    await self.discover_satellites()
                else:
                    await self.display.update_status("PWR ERROR", error)
                    await self.audio.play("fail.wav", channel=self.audio.CH_SFX)

            elif not self.power.satbus_connected and self.power.satbus_powered:
                # PHYSICAL LINK LOST - Immediate Hardware Cut-off
                self.power.emergency_kill()
                await self.display.update_status("SAT LINK LOST", "BUS OFFLINE")
                await self.audio.play("link_lost.wav", channel=self.audio.CH_SFX)

            await asyncio.sleep(0.5) # Poll twice per second to save CPU

    async def monitor_hw_hid(self):
        """Background task to poll hardware inputs."""
        while True:
            self.hid.hw_update()
            await asyncio.sleep(0.01)

    async def start(self):
        """Main async loop for the Master Controller."""
        # Start background infrastructure tasks
        asyncio.create_task(self.monitor_sats())        # UART Comms
        asyncio.create_task(self.monitor_estop())       # E-Stop Button (Gameplay)
        asyncio.create_task(self.monitor_power())       # Analog Power Monitoring
        asyncio.create_task(self.monitor_connection())  # RJ45 Link Detection
        asyncio.create_task(self.monitor_hw_hid())      # Local Hardware Input Polling
        asyncio.create_task(self.leds.animate_loop())   # Button LED Animations
        asyncio.create_task(self.matrix.animate_loop()) # Matrix LED Animations
        asyncio.create_task(self.synth.start_generative_drone()) # Background Music Drone

        # Fancy bootup sequence
        #TODO Add boot animation
        self.audio.play("voice/os_online.wav", channel=self.audio.CH_VOICE)

        while True:
            # Feed the hardware watchdog timer to prevent system reset
            microcontroller.watchdog.feed()

            # Meltdown state pauses the menu selection
            while self.meltdown:
                microcontroller.watchdog.feed()
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
            elif self.mode == "JEBRIS":
                await self.run_mode_with_safety(JEBris(self))
            elif self.mode == "SIMON":
                await self.run_mode_with_safety(Simon(self, 0.5, 3000))
            elif self.mode == "SAFE":
                await self.run_mode_with_safety(SafeCracker(self))

            # Industrial Satellite Games
            elif self.mode == "IND":
                sat = next(
                    (s for s in self.satellites.values() if s.sat_type == "INDUSTRIAL"),
                    None,
                )
                if sat:
                    mode_instance = IndustrialStartup(self, sat)
                    run_ind = True
                    while run_ind:
                        result = await self.run_mode_with_safety(mode_instance, target_sat=sat)
                        if result == "LINK_LOST":
                            await self.display.update_status("LINK LOST", "RECONNECT IN 60s")
                            asyncio.create_task(
                                self.audio.play(
                                    "link_lost.wav",
                                    channel=self.audio.CH_SFX
                                )
                            )
                            await asyncio.sleep(1)
                            # 60 second countdown
                            disconnect_time = ticks_ms()
                            while not sat.is_active and run_ind:
                                elapsed = ticks_diff(ticks_ms(), disconnect_time)
                                if elapsed > 60000:
                                    run_ind = False
                                    continue
                                secs_left = 60 - (elapsed // 1000)
                                await self.display.update_status(
                                    "LINK LOST",
                                    f"ABORT IN: {secs_left}s"
                                )
                                await asyncio.sleep(0.1)
                            if sat.is_active and run_ind:
                                await self.display.update_status("LINK RESTORED", "RESUMING...")
                                asyncio.create_task(
                                    self.audio.play(
                                        "link_restored.wav",
                                        channel=self.audio.CH_SFX
                                    )
                                )
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
