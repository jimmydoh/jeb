# File: src/core/core_manager.py
"""
Core Manager for JEB Master Controller.

TODO: Implement HardwareContext for modes to limit access
"""
import asyncio
import busio
import microcontroller
import neopixel
from adafruit_ticks import ticks_ms, ticks_diff

from managers import (
    AudioManager,
    BuzzerManager,
    DataManager,
    DisplayManager,
    HIDManager,
    LEDManager,
    MatrixManager,
    PowerManager,
    RenderManager,
    SatelliteNetworkManager,
    SynthManager,
)
from modes import AVAILABLE_MODES, BaseMode
from transport import (
    UARTTransport,
    COMMAND_MAP,
    DEST_MAP,
    MAX_INDEX_VALUE,
    PAYLOAD_SCHEMAS,
)
from utilities import (
    JEBPixel,
    Pins,
)

class CoreManager:
    """Class to hold global state for the master controller.

    This class manages the core system state including:
    - Hardware managers (display, audio, LED, etc.)
    - Mode registry and active mode state
    - Satellite network connections
    - Power management and safety monitoring

    Public Interface:
        modes: Dict[str, Type[BaseMode]] - Registry of available modes by mode ID
            Each mode class has a METADATA dict with the following structure:
            {
                "id": str,              # Unique mode identifier
                "name": str,            # Display name
                "icon": str,            # Icon key from icon library
                "requires": List[str],  # Required hardware ["CORE", "INDUSTRIAL", etc.]
                "settings": List[dict]  # Optional settings configuration
            }

        satellites: Dict[int, Satellite] - Registry of connected satellites by slot ID
            Each satellite has properties:
            - sat_type_name: str (e.g., "INDUSTRIAL", "AUDIO")
            - is_active: bool
            - slot_id: int
    """
    def __init__(self, config=None):
        # Load config or use defaults
        if config is None:
            config = {}

        self.debug_mode = config.get("debug_mode", False)
        self.root_data_dir = config.get("root_data_dir", "/")

        # Watchdog Flag Pattern - Prevents blind feeding if critical tasks crash
        # Each critical background task must set its flag to True each iteration
        # The watchdog is only fed if ALL flags are True, then flags are reset
        self.watchdog_flags = {
            "sat_network": False,
            "estop": False,
            "power": False,
            "connection": False,
            "hw_hid": False,
            "render": False,
        }

        # Init Data Manager for persistent storage of scores and settings
        self.data = DataManager(root_dir=self.root_data_dir)

        # Init Pins
        Pins.initialize(profile="CORE", type_id="00")

        # Init power manager first for voltage readings
        self.power = PowerManager(
            Pins.SENSE_PINS,
            ["input", "satbus", "main", "led"],
            Pins.MOSFET_CONTROL,
            Pins.SATBUS_DETECT,
        )

        # Init I2C bus
        self.i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)

        # UART for satellite communication
        uart_hw = busio.UART(
            Pins.UART_TX,
            Pins.UART_RX,
            baudrate=config.get("uart_baudrate", 115200),
            receiver_buffer_size=config.get("uart_buffer_size", 512),
            timeout=0.01,
        )

        # Wrap with transport layer for protocol handling
        self.transport = UARTTransport(
            uart_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS
        )

        # Init Basic Audio (Buzzer)
        self.buzzer = BuzzerManager(Pins.BUZZER, volume=0.5)

        # Init Primary Audio (I2S) and Synthesizer
        self.audio = AudioManager(
            Pins.I2S_SCK, Pins.I2S_WS, Pins.I2S_SD, root_data_dir=self.root_data_dir
        )
        self.audio.preload(
            [
                "audio/common/menu_tick.wav",
                "audio/common/menu_select.wav",
            ]
        )
        self.synth = SynthManager()
        self.audio.attach_synth(self.synth.source)  # Connect synth to audio mixer

        # Init Display (OLED)
        self.display = DisplayManager(self.i2c)
        self.hid = HIDManager(
            encoders=Pins.ENCODERS,
            mcp_i2c=self.i2c,
            mcp_int_pin=Pins.EXPANDER_INT,
            expanded_buttons=Pins.EXPANDER_BUTTONS,
        )

        # Initialize Satellite Network Manager
        self.sat_network = SatelliteNetworkManager(
            self.transport, self.display, self.audio, self.watchdog_flags
        )
        if self.debug_mode:
            self.sat_network.set_debug_mode(True)

        # Init LEDs
        self.root_pixels = neopixel.NeoPixel(
            Pins.LED_CONTROL, 68, brightness=0.3, auto_write=False
        )

        # LED Matrix Manager (first 64 pixels)
        self.matrix_jeb_pixel = JEBPixel(self.root_pixels, start_idx=0, num_pixels=64)
        self.matrix = MatrixManager(self.matrix_jeb_pixel)

        # Button LED Manager (last 4 pixels)
        self.led_jeb_pixel = JEBPixel(self.root_pixels, start_idx=64, num_pixels=4)
        self.leds = LEDManager(self.led_jeb_pixel)

        # Setup Render Manager to coordinate LED animations
        self.renderer = RenderManager(
            self.root_pixels,
            watchdog_flags=self.watchdog_flags,
            sync_role="MASTER",
            network_manager=self.sat_network
        )
        self.renderer.add_animator(self.leds)
        self.renderer.add_animator(self.matrix)

        # System State
        self._mode_registry = {}

        # modes: Public registry mapping mode IDs to mode classes
        # See class docstring for detailed structure documentation
        self.modes = {}
        for mode_class in AVAILABLE_MODES:
            # Store by class name for registry access
            self._mode_registry[mode_class.__name__] = mode_class
            # Store by mode ID for efficient lookup in main loop
            # Safely access METADATA, defaulting if missing
            meta = getattr(mode_class, "METADATA", BaseMode.METADATA)
            self.modes[meta["id"]] = mode_class
        self.mode = "DASHBOARD"

        # Track e-stop 'Meltdown'
        self.meltdown = False

    def _get_mode(self, mode_name):
        """Get a mode class from the registry with helpful error message.

        Args:
            mode_name: Name of the mode class to retrieve

        Returns:
            The mode class

        Raises:
            KeyError: If the mode is not found in the registry
        """
        if mode_name not in self._mode_registry:
            available = ", ".join(sorted(self._mode_registry.keys()))
            raise KeyError(
                f"Mode '{mode_name}' not found in registry. Available modes: {available}"
            )
        return self._mode_registry[mode_name]

    # Satellite Network Delegation Properties
    @property
    def satellites(self):
        """Access the satellite registry from SatelliteNetworkManager.

        Returns a dictionary mapping slot IDs to Satellite objects:
            Dict[int, Satellite]

        Each Satellite object provides:
            - sat_type_name (str): Type identifier (e.g., "INDUSTRIAL", "AUDIO")
            - is_active (bool): Whether the satellite is currently connected
            - slot_id (int): Physical slot position in the daisy chain

        Example usage:
            for sat_id, satellite in self.core.satellites.items():
                if satellite.sat_type_name == "INDUSTRIAL" and satellite.is_active:
                    # Use the satellite
                    pass
        """
        return self.sat_network.satellites

    @property
    def sat_telemetry(self):
        """Access satellite telemetry from SatelliteNetworkManager."""
        return self.sat_network.sat_telemetry

    @property
    def last_message_debug(self):
        """Access last debug message from SatelliteNetworkManager."""
        return self.sat_network.last_message_debug

    def safe_feed_watchdog(self):
        """Feed watchdog only if all critical tasks are alive.

        Uses the Watchdog Flag Pattern to prevent blind feeding.
        Only feeds if all critical background tasks have set their flags,
        indicating they are still running properly.
        """
        # Check if all critical tasks have reported in
        if all(self.watchdog_flags.values()):
            # All tasks are alive - safe to feed the watchdog
            microcontroller.watchdog.feed()
            # Reset all flags for the next iteration
            for key in self.watchdog_flags:
                self.watchdog_flags[key] = False
        # If any flag is False, we DON'T feed the watchdog
        # This will trigger a system reset, recovering from the zombie state

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
            # Feed the watchdog only if all critical tasks are alive
            self.safe_feed_watchdog()

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

    # --- Background Tasks ---
    async def monitor_estop(self):
        """Background task to monitor the E-Stop button (gameplay interaction).

        Engaging the E-Stop triggers meltdown mode with audio alarms.

        Releasing the E-Stop resets the system.
        """
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog_flags["estop"] = True

            if not self.hid.estop and not self.meltdown:
                self.meltdown = True
                self.sat_network.send_all("LED", "ALL,0,0,0")  # Kill all LEDs

                # Audio Alarms
                await self.audio.play(
                    "background_winddown.wav", channel=self.audio.CH_ATMO, loop=False
                )
                await self.audio.set_level(self.audio.CH_ATMO, 0.2)
                await self.audio.play(
                    "alarm_klaxon.wav", channel=self.audio.CH_SFX, loop=True
                )
                await self.audio.play(
                    "voice_meltdown.wav", channel=self.audio.CH_VOICE, loop=True
                )

                # High Contrast Warning on OLED
                self.display.update_status("!!! EMERGENCY STOP !!!", "PULL UP TO RESET")

                # Strobe the neobar and satellite LEDs
                while not self.hid.estop:  # While button is still latched down
                    self.watchdog_flags["estop"] = True  # Signal that we are alive and waiting
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
            # Set watchdog flag to indicate this task is alive
            self.watchdog_flags["power"] = True

            v = self.power.status

            if self.mode == "DASHBOARD":
                # self.display.update_telemetry(v["bus"], v["log"])
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
                await self.audio.set_level(self.audio.CH_SFX, 0.5)  # Lower SFX volume

            await asyncio.sleep(0.5)

    async def monitor_connection(self):
        """Background task to detect physical RJ45 connection and manage bus power."""
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog_flags["connection"] = True

            if self.power.satbus_connected and not self.power.satbus_powered:
                # PHYSICAL LINK DETECTED - Trigger Soft Start
                await self.display.update_status("LINK DETECTED", "POWERING BUS...")
                success, error = await self.power.soft_start_satellites()

                if success:
                    await self.audio.play(
                        "link_restored.wav", channel=self.audio.CH_SFX
                    )
                    # Power is stable, trigger the ID assignment chain
                    await self.sat_network.discover_satellites()
                else:
                    await self.display.update_status("PWR ERROR", error)
                    await self.audio.play("fail.wav", channel=self.audio.CH_SFX)

            elif not self.power.satbus_connected and self.power.satbus_powered:
                # PHYSICAL LINK LOST - Immediate Hardware Cut-off
                self.power.emergency_kill()
                await self.display.update_status("SAT LINK LOST", "BUS OFFLINE")
                await self.audio.play("link_lost.wav", channel=self.audio.CH_SFX)

            await asyncio.sleep(0.5)  # Poll twice per second to save CPU

    async def monitor_hw_hid(self):
        """Background task to poll hardware inputs."""
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog_flags["hw_hid"] = True

            self.hid.hw_update()
            await asyncio.sleep(0.01)

    async def start(self):
        """Main async loop for the Master Controller."""
        # --- POWER ON SELF TEST ---
        # Check power integrity before starting main application loop
        if self.power.check_power_integrity():
            self.buzzer.play_song("POWER_UP")
            print("Power integrity check passed. Starting system...")
            await self.display.update_status("POWER OK", "STARTING SYSTEM...")
            await asyncio.sleep(1)

            # Start transport monitoring to handle satellite activation
            # (currently does nothing, but add in case of future queue etc.)
            self.transport.start()
            # Start Satellite Bus connection monitor
            asyncio.create_task(self.monitor_connection())
            # Start expanded power monitoring
            asyncio.create_task(self.monitor_power())

        else:
            self.buzzer.play_song("POWER_FAIL")
            print("Power integrity check failed! Check power supply and connections.")
            await self.display.update_status("POWER ERROR", "CHECK CONNECTIONS")
            # Do not start main loop if power is not stable
            while True:
                await asyncio.sleep(1)

        # Continue with other background tasks after power integrity is confirmed
        asyncio.create_task(self.sat_network.monitor_satellites())  # Satellite Network Management
        asyncio.create_task(self.monitor_hw_hid())  # Local Hardware Input Polling
        asyncio.create_task(self.renderer.run())  # Centralized Render Loop

        # --- Experimental / Future Use ---
        #asyncio.create_task(self.monitor_estop())  # E-Stop Button (Gameplay)
        #asyncio.create_task(self.synth.start_generative_drone())  # Background Music Drone

        # Bootup has completed, play a fancy animation
        # TODO Add boot animation and audio

        while True:
            # Feed the watchdog only if all critical tasks are alive
            self.safe_feed_watchdog()

            # Meltdown state pauses the menu selection
            while self.meltdown:
                self.safe_feed_watchdog()
                await asyncio.sleep(0.1)

            # --- GENERIC MODE RUNNER ---
            # Check if the mode is in self.modes (Dict[mode_id: str, mode_class: Type[BaseMode]])
            if self.mode in self.modes:
                mode_class = self.modes[self.mode]
                # Access the mode's METADATA class attribute (documented in BaseMode)
                meta = mode_class.METADATA

                # Check Dependencies
                target_sat = None
                requirements_met = True

                for req in meta.get("requires", []):
                    if req == "CORE":
                        continue
                    found = False
                    # Check self.satellites: Dict[slot_id: int, Satellite]
                    for sat in self.satellites.values():
                        if sat.sat_type_name == req and sat.is_active:
                            found = True
                            target_sat = sat  # Set target satellite for monitoring
                            break
                    if not found:
                        requirements_met = False
                        break

                if requirements_met:
                    mode_instance = mode_class(self)

                    if target_sat:
                        run_robust = True
                        while run_robust:
                            result = await self.run_mode_with_safety(
                                mode_instance, target_sat=target_sat
                            )
                            if result == "LINK_LOST":
                                await self.display.update_status(
                                    "LINK LOST", "RECONNECT IN 60s"
                                )
                                asyncio.create_task(
                                    self.audio.play(
                                        "link_lost.wav", channel=self.audio.CH_SFX
                                    )
                                )
                                await asyncio.sleep(1)
                                # 60 second countdown
                                disconnect_time = ticks_ms()
                                while not target_sat.is_active and run_robust:
                                    elapsed = ticks_diff(ticks_ms(), disconnect_time)
                                    if elapsed > 60000:
                                        run_robust = False
                                        continue
                                    secs_left = 60 - (elapsed // 1000)
                                    await self.display.update_status(
                                        "LINK LOST", f"ABORT IN: {secs_left}s"
                                    )
                                    await asyncio.sleep(0.1)
                                if target_sat.is_active and run_robust:
                                    await self.display.update_status(
                                        "LINK RESTORED", "RESUMING..."
                                    )
                                    asyncio.create_task(
                                        self.audio.play(
                                            "link_restored.wav", channel=self.audio.CH_SFX
                                        )
                                    )
                                    await asyncio.sleep(1)
                            else:
                                run_robust = False
                    else:
                        await self.run_mode_with_safety(mode_instance)
                else:
                    print(f"Cannot start {self.mode}: Missing Dependency")
                    await self.display.update_status(
                        "REQUIREMENT NOT MET", f"NEED {', '.join(meta.get('requires', []))}"
                    )
                    await self.audio.play("fail.wav", channel=self.audio.CH_SFX)
                    await asyncio.sleep(2)
                    self.mode = "DASHBOARD"  # Return to dashboard if requirements not met

            else:
                print(f"Mode {self.mode} not found in registry.")
                await self.display.update_status("MODE NOT FOUND", self.mode)
                await self.audio.play("fail.wav", channel=self.audio.CH_SFX)
                await asyncio.sleep(2)
                self.mode = "DASHBOARD"  # Return to dashboard if mode not found

            await asyncio.sleep(0.1)
