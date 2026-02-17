# File: src/core/core_manager.py
"""
Core Manager for JEB Master Controller.

TODO: Implement HardwareContext for modes to limit access
"""
import asyncio
import busio
import neopixel
from adafruit_ticks import ticks_ms, ticks_diff

from managers import PowerManager, WatchdogManager

from managers.audio_manager import AudioManager
from managers.buzzer_manager import BuzzerManager
from managers.data_manager import DataManager
from managers.display_manager import DisplayManager
from managers.hid_manager import HIDManager
from managers.led_manager import LEDManager
from managers.matrix_manager import MatrixManager
from managers.render_manager import RenderManager
from managers.satellite_network_manager import SatelliteNetworkManager
from managers.synth_manager import SynthManager

from modes.manifest import MODE_REGISTRY

from transport import UARTTransport
from transport.protocol import (
    COMMAND_MAP,
    DEST_MAP,
    MAX_INDEX_VALUE,
    PAYLOAD_SCHEMAS,
)

from utilities.jeb_pixel import JEBPixel
from utilities.pins import Pins
from utilities import tones

POW_INPUT = "input_20v"
POW_BUS = "satbus_20v"
POW_MAIN = "main_5v"
POW_LED = "led_5v"

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

        # --- SAFETY EVENTS ---
        self.estop_event = asyncio.Event()
        self.abort_event = asyncio.Event()
        self.target_sat_event = asyncio.Event()
        self.meltdown = False

        # Init Watchdog Manager
        self.watchdog = None

        # Init Data Manager for persistent storage of scores and settings
        self.data = DataManager(root_dir=self.root_data_dir)

        # Init Pins
        Pins.initialize(profile="CORE", type_id="00")

        # Init power manager first for voltage readings
        self.power = PowerManager(
            Pins.SENSE_PINS,
            [POW_INPUT, POW_BUS, POW_MAIN, POW_LED],
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
            receiver_buffer_size=config.get("uart_buffer_size", 1024),
            timeout=0.01,
        )

        # Wrap with transport layer for protocol handling
        self.transport = UARTTransport(
            uart_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS
        )

        # Init Basic Audio (Buzzer)
        self.buzzer = BuzzerManager(Pins.BUZZER)

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
        self.display = DisplayManager(self.i2c, device_address=Pins.I2C_ADDRESSES["OLED"])
        self.hid = HIDManager(
            encoders=Pins.ENCODERS,
            mcp_chip="MCP23008",
            mcp_i2c=self.i2c,
            mcp_i2c_address=Pins.I2C_ADDRESSES.get("EXPANDER"),
            mcp_int_pin=Pins.EXPANDER_INT,
            expanded_buttons=Pins.EXPANDER_BUTTONS,
        )

        # Initialize Satellite Network Manager
        self.sat_network = SatelliteNetworkManager(
            self.transport,
            self.display,
            self.audio,
            self.abort_event,
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
            sync_role="MASTER",
            network_manager=self.sat_network
        )
        self.renderer.add_animator(self.leds)
        self.renderer.add_animator(self.matrix)

        # System Modes
        self.mode_registry = MODE_REGISTRY
        self.loaded_modes = {} # Cache for instantiated mode classes
        self.mode = "DASHBOARD" # Start in main menu mode

    def _get_mode(self, mode_name):
        """Get a mode class from the registry with helpful error message.

        Args:
            mode_name: Name of the mode class to retrieve

        Returns:
            The mode class

        Raises:
            KeyError: If the mode is not found in the registry
        """
        if mode_name not in [mode["id"] for mode in self.mode_registry]:
            available = ", ".join(sorted([mode["id"] for mode in self.mode_registry]))
            raise KeyError(
                f"Mode '{mode_name}' not found in registry. Available modes: {available}"
            )
        return next(mode for mode in self.mode_registry if mode["id"] == mode_name)

    def _get_mode_metadata(self, mode_id):
        """Get mode metadata from the registry.

        Args:
            mode_id: The unique identifier of the mode
        Returns:
            A dictionary containing the mode's metadata
        Raises:
            KeyError: If the mode_id is not found in the registry
        """
        if mode_id not in self.mode_registry:
            raise KeyError(f"Mode ID '{mode_id}' not found in registry.")
        return self.mode_registry[mode_id]

    def _load_mode_class(self, mode_id):
        """Dynamically load a mode class from the registry.

        Args:
            mode_id: The unique identifier of the mode to load

        Returns:
            The mode class

        Raises:
            ImportError: If the module or class cannot be imported
            KeyError: If the mode_id is not in the registry
        """
        if mode_id in self.loaded_modes:
            return self.loaded_modes[mode_id]

        if mode_id not in self.mode_registry:
            available = ", ".join(sorted(self.mode_registry.keys()))
            raise KeyError(
                f"Mode ID '{mode_id}' not found in registry. Available modes: {available}"
            )

        meta = self.mode_registry[mode_id]
        module_path = meta["module_path"]
        class_name = meta["class_name"]

        try:
            # Dynamic Import
            module = __import__(module_path, None, None, [class_name])
            mode_class = getattr(module, class_name)
            self.loaded_modes[mode_id] = mode_class
            return mode_class
        except ImportError as e:
            raise ImportError(f"Failed to import module '{module_path}' for mode '{mode_id}': {e}") from e
        except AttributeError as e:
            raise ImportError(f"Module '{module_path}' does not have class '{class_name}' for mode '{mode_id}': {e}") from e

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
        # Create the mode and monitor event tasks
        sub_task = asyncio.create_task(mode_instance.execute())
        estop_task = asyncio.create_task(self.estop_event.wait())
        abort_task = asyncio.create_task(self.abort_event.wait())

        if target_sat:
            target_sat_monitor_task = asyncio.create_task(self.monitor_satellite(target_sat))
            target_sat_task = asyncio.create_task(self.target_sat_event.wait())

        # Clear events before starting
        self.abort_event.clear()
        self.target_sat_event.clear()

        # Wait for the first of the mode completion or any safety event
        tasks_to_wait = [sub_task, estop_task, abort_task]
        if target_sat:
            tasks_to_wait.extend([target_sat_monitor_task, target_sat_task])
        try:
            done, pending = await asyncio.wait(
                tasks_to_wait,
                return_when=asyncio.FIRST_COMPLETED,
            )
        except Exception as e:
            print(f"Error while running mode with safety monitoring: {e}")
            import traceback
            traceback.print_exc()
            self.display.update_status("MODE ERROR", "CHECK LOGS")
            return "MODE_ERROR"

        # Cleanup: Cancel any pending tasks
        for task in pending:
            task.cancel()

        if target_sat:
            # Ensure the satellite monitor task is also cancelled
            target_sat_monitor_task.cancel()

        # Determine the result based on which task completed
        if estop_task in done:
            self.display.update_status("ESTOP ENGAGED", "EXITING MODE...")
            return "ESTOP_ABORT"
        elif abort_task in done:
            self.display.update_status("SYSTEM ABORT", "RESETTING CORE...")
            self.abort_event.clear()  # Reset the event for future use
            return "SYSTEM_ABORT"
        elif target_sat:
            if target_sat_task in done:
                self.display.update_status("LINK LOST", "EXITING MODE...")
                return "LINK_LOST"

        if sub_task in done:
            # Propagate any exceptions from the mode task
            try:
                result = sub_task.result()  # Get the result or exception
                return result if result else "SUCCESS"
            except Exception as e:
                print(f"Error in mode execution: {e}")
                import traceback
                traceback.print_exc()
                self.display.update_status("MODE ERROR", "CHECK LOGS")
                return "MODE_ERROR"

        return "UNKNOWN_EXIT"

    # --- Background Tasks ---
    async def monitor_estop(self):
        """
        Background task to monitor the E-Stop button.
        Used for Gameplay elements only - NOT A SAFETY FEATURE.

        Engaging the E-Stop triggers meltdown mode with audio alarms.

        Releasing the E-Stop returns to the normal state.

        TODO: Decision - get rid of this altogether and just use the button
        for manual aborts in modes? The meltdown state is fun but may not be
        worth the complexity. Also prevents the button from being used as
        an actual gameplay element if it's tied to a global meltdown state.
        """
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog.check_in("estop")

            if self.meltdown:
                if not self.hid.estop: # User reset the button
                    self.meltdown = False
                    self.estop_event.clear()  # Reset the event for future use
                    await self.audio.play("system_reset.wav")
                    self.display.update_status("SAFETY RESET", "PLEASE STAND BY")
                    await asyncio.sleep(2)
                else:
                    # Still in meltdown, continue strobing and waiting for reset
                    await asyncio.sleep(0.05)
                    continue
            elif self.hid.estop:
                # E-Stop has been engaged, trigger meltdown
                self.meltdown = True
                self.estop_event.set()  # Signal to any listening tasks that E-Stop is engaged
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
                self.display.update_status("!!! EMERGENCY STOP !!!", "PULL UP TO RESET")

            await asyncio.sleep(0.05)

    async def monitor_power(self):
        """Background task to watch for brownouts or disconnects."""
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog.check_in("power")

            v = self.power.status

            if self.mode == "DASHBOARD":
                # self.display.update_telemetry(v["bus"], v["log"])
                # TODO Implement telemetry display
                #print(f"Power Rail - BUS: {v[POW_BUS]:.2f}V | LOGIC: {v[POW_MAIN]:.2f}V")
                pass

            # Scenario: LED buck converter is failing or overloaded
            if v[POW_LED] < 4.5 and v[POW_INPUT] > 18.0:
                self.display.update_status("LED PWR FAILURE", "CHECK 5A FUSE")

            # Scenario: Logic rail is sagging (Audio Amp drawing too much?)
            if v[POW_MAIN] < 4.7:
                self.display.update_status("LOGIC BROWNOUT", "REDUCING VOLUME")
                await self.audio.set_level(self.audio.CH_SFX, 0.5)  # Lower SFX volume

            await asyncio.sleep(0.5)

    async def monitor_connection(self):
        """Background task to detect physical RJ45 connection and manage bus power."""
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog.check_in("connection")

            if self.power.satbus_connected and not self.power.satbus_powered:
                # PHYSICAL LINK DETECTED - Trigger Soft Start
                self.display.update_status("LINK DETECTED", "POWERING BUS...")
                success, error = await self.power.soft_start_satellites()

                if success:
                    await self.audio.play(
                        "link_restored.wav", channel=self.audio.CH_SFX
                    )
                    # Power is stable, trigger the ID assignment chain
                    await self.sat_network.discover_satellites()
                else:
                    self.display.update_status("PWR ERROR", error)
                    await self.audio.play("fail.wav", channel=self.audio.CH_SFX)

            elif not self.power.satbus_connected and self.power.satbus_powered:
                # PHYSICAL LINK LOST - Immediate Hardware Cut-off
                self.power.emergency_kill()
                self.display.update_status("SAT LINK LOST", "BUS OFFLINE")
                await self.audio.play("link_lost.wav", channel=self.audio.CH_SFX)

            await asyncio.sleep(0.5)  # Poll twice per second to save CPU

    async def monitor_hw_hid(self):
        """Background task to poll hardware inputs."""
        while True:
            # Set watchdog flag to indicate this task is alive
            self.watchdog.check_in("hw_hid")
            self.hid.hw_update()

            if self.hid.is_button_pressed(3, long=True, duration=5000):
                # Long-press Button D to trigger manual abort
                self.abort_event.set()

            await asyncio.sleep(0.02) # Poll at 50Hz

    async def monitor_satellite(self, sat):
        """
        Background task to monitor a specific satellite.
        """
        if not sat:
            await asyncio.Event().wait()  # Wait indefinitely if no satellite provided
            return

        while sat.is_active:
            await asyncio.sleep(0.5)  # Poll at 2Hz to save CPU

        self.target_sat_event.set()  # Signal that the target satellite has been disconnected

    async def monitor_watchdog_feed(self):
        """Background task to feed the watchdog if all systems are healthy."""
        while True:
            self.watchdog.safe_feed()
            await asyncio.sleep(1)  # Feed the watchdog every second

    async def start(self):
        """Main async loop for the Master Controller."""
        # --- POWER ON SELF TEST ---
        # Check power integrity before starting main application loop
        if await self.power.check_power_integrity():
            self.buzzer.play_sequence(tones.POWER_UP)
            print("Power integrity check passed. Starting system...")
            self.display.update_status("POWER OK", "STARTING SYSTEM...")
            await asyncio.sleep(1)

            print("Initializing Watchdog Manager...")
            self.watchdog = WatchdogManager(
                task_names=[
                    "power",
                    "connection",
                    "hw_hid"
                ],
                timeout=5.0
            )

            # Start transport monitoring to handle satellite activation
            self.transport.start()
            # Start Satellite Bus connection monitor
            asyncio.create_task(self.monitor_connection())
            # Start expanded power monitoring
            asyncio.create_task(self.monitor_power())
            # Start hardware input monitoring
            asyncio.create_task(self.monitor_hw_hid())

        else:
            self.buzzer.play_sequence(tones.POWER_FAIL)
            print("Power integrity check failed! Check power supply and connections.")
            self.display.update_status("POWER ERROR", "CHECK CONNECTIONS")
            # Do not start main loop if power is not stable
            while True:
                await asyncio.sleep(1)

        # Continue with other background tasks after power integrity is confirmed
        self.watchdog.register_flags(["sat_network"])
        asyncio.create_task( # Satellite Network Management
            self.sat_network.monitor_satellites(
                heartbeat_callback=lambda: self.watchdog.check_in("sat_network")
            )
        )

        self.watchdog.register_flags(["sat_messages"])
        asyncio.create_task(
            self.sat_network.monitor_messages(
                heartbeat_callback=lambda: self.watchdog.check_in("sat_messages")
            )
        )

        self.watchdog.register_flags(["render"])
        asyncio.create_task( # Centralized Render Loop
            self.renderer.run(
                heartbeat_callback=lambda: self.watchdog.check_in("render")
            )
        )

        if self.display:
            asyncio.create_task(self.display.scroll_loop())

        asyncio.create_task(self.monitor_watchdog_feed())  # Start watchdog feed loop

        # --- Experimental / Future Use ---
        #self.watchdog.register_flags(["estop"])
        #asyncio.create_task(self.monitor_estop())  # E-Stop Button (Gameplay)
        #asyncio.create_task(self.synth.start_generative_drone())  # Background Music Drone

        # Bootup has completed, play a fancy animation
        # TODO Add boot animation and audio

        while True:
            # Meltdown state pauses the menu selection
            while self.meltdown:
                await asyncio.sleep(0.1)

            # --- GENERIC MODE RUNNER ---
            # Check if the mode is in self.mode_registry
            if self.mode in self.mode_registry:
                # Retrieve mode requirements
                meta = self.mode_registry[self.mode]
                requirements = meta.get("requires", [])

                # Check Dependencies
                target_sat = None
                requirements_met = True

                for req in requirements:
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

                    # LAZY LOAD THE MODE CLASS
                    try:
                        mode_class = self._load_mode_class(self.mode)
                    except (ImportError, KeyError) as e:
                        print(f"Error loading mode '{self.mode}': {e}")
                        self.display.update_status("MODE LOAD ERROR", self.mode)
                        await self.audio.play("fail.wav", channel=self.audio.CH_SFX)
                        await asyncio.sleep(2)
                        self.mode = "DASHBOARD"  # Return to dashboard if mode fails to load
                        continue

                    mode_instance = mode_class(self)

                    if target_sat:
                        run_robust = True
                        while run_robust:
                            result = await self.run_mode_with_safety(
                                mode_instance, target_sat=target_sat
                            )
                            if result == "LINK_LOST":
                                self.display.update_status(
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
                                    self.display.update_status(
                                        "LINK LOST", f"ABORT IN: {secs_left}s"
                                    )
                                    await asyncio.sleep(0.1)
                                if target_sat.is_active and run_robust:
                                    self.display.update_status(
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
                    self.display.update_status(
                        "REQUIREMENT MISSING", f"NEED: {', '.join(requirements)}"
                    )
                    await self.audio.play("fail.wav", channel=self.audio.CH_SFX)
                    await asyncio.sleep(2)
                    self.mode = "DASHBOARD"  # Return to dashboard if requirements not met

            else:
                print(f"Mode {self.mode} not found in registry.")
                self.display.update_status("MODE NOT FOUND", self.mode)
                await self.audio.play("fail.wav", channel=self.audio.CH_SFX)
                await asyncio.sleep(2)
                self.mode = "DASHBOARD"  # Return to dashboard if mode not found

            await asyncio.sleep(0.1)
