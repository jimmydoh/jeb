import sys

import asyncio
import busio
import microcontroller
import supervisor

from utilities.pins import Pins
from utilities import tones
from utilities.palette import Palette
from utilities.logger import JEBLogger


class ConsoleManager():
    """Interactive console manager for hardware diagnostics and development testing.

    Runs as a parallel async task alongside the main application when test_mode
    is enabled in config.json. Provides an interactive text menu for testing all
    major hardware components without needing to find in-game triggers.

    When an ``app`` reference is provided the manager will reuse the hardware
    instances that were already initialised by the application, avoiding bus
    conflicts and ensuring tests exercise the live hardware state.  When ``app``
    is ``None`` the manager falls back to creating its own lightweight instances
    (or relies on injected dummy classes when hardware is disabled).
    """

    def __init__(self, role, type_id, app=None):
        self.role = role
        self.type_id = type_id
        self.app = app

        # Ring buffer for web console output
        self.output_buffer = []
        self._output_buffer_max = 500
        # Queue for commands injected from the web interface
        self.input_queue = []

        JEBLogger.info("CONS",f"[INIT] ConsoleManager - role: {self.role} type_id: {self.type_id}")

        if app is None:
            Pins.initialize(profile=role, type_id=type_id)
        else:
            JEBLogger.debug("CONS", f"Attaching to {app}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _print(self, msg=""):
        """Print a line to the serial console and append it to the output buffer."""
        print(msg)
        self.output_buffer.append(str(msg))
        if len(self.output_buffer) > self._output_buffer_max:
            self.output_buffer = self.output_buffer[-self._output_buffer_max:]

    def get_output(self):
        """Return the buffered console output as a newline-joined string."""
        return "\n".join(self.output_buffer)

    def _get_manager(self, name):
        """Return a named manager from the running app, or ``None``."""
        if self.app is not None:
            return getattr(self.app, name, None)
        return None

    async def get_input(self, prompt):
        """Safe non-blocking serial input wrapper.

        Checks the web-injected ``input_queue`` before blocking on the real
        serial port so that the web console can send commands even when no
        physical terminal is connected.
        """
        self._print(prompt)

        serial_line = ""

        while True:
            # 1. Check for injected commands from WebServerManager
            JEBLogger.debug("CONS", f"Checking input queue: {self.input_queue}")
            if self.input_queue:
                line = self.input_queue.pop(0)
                self._print(f"WEB>> {line}") # Echo it so the web user sees what they typed
                return line

            # 2. Check for physical serial input (Strictly non-blocking)
            while supervisor.runtime.serial_bytes_available:
                JEBLogger.debug("CONS", f"Reading from serial: {supervisor.runtime.serial_bytes_available} bytes available")
                char = sys.stdin.read(1)
                if char in ('\n', '\r'):
                    if serial_line: # Ignore empty carriage returns
                        self._print(f"SYS>> {serial_line}") # Echo physical input to the web buffer
                        line = serial_line
                        serial_line = ""
                        return line
                else:
                    serial_line += char

            await asyncio.sleep(0.05)

    def get_tone_presets(self):
        """Introspect utilities.tones and return all valid song dictionaries.

        Returns a list of tuples: [('COIN', dict), ('MARIO_THEME', dict), ...]
        """
        presets = []
        for name in dir(tones):
            if name.startswith("_"):
                continue
            val = getattr(tones, name)
            if isinstance(val, dict) and "sequence" in val:
                presets.append((name, val))
        return sorted(presets, key=lambda x: x[0])

    # ------------------------------------------------------------------
    # Hardware test routines
    # ------------------------------------------------------------------

    async def test_buzzer(self):
        """Test the buzzer by playing tones, scales, and preset songs."""
        self._print("\n--- BUZZER TEST ---")

        buzzer = self._get_manager('buzzer')
        if buzzer is None:
            try:
                from managers.buzzer_manager import BuzzerManager
                buzzer = BuzzerManager(Pins.BUZZER)
            except Exception as e:
                self._print(f"FAILED to init buzzer: {e}")
                return

        presets = self.get_tone_presets()

        while True:
            self._print("\n[Buzzer Menu]")
            self._print("1. Play Tone (440Hz)")
            self._print("2. Play Scale (C Major)")
            for i, (name, _) in enumerate(presets, 3):
                self._print(f"{i}. Preset: {name}")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                buzzer.stop()
                break
            elif choice == "1":
                self._print("Playing 440Hz...")
                buzzer.play_note(440, 1.0)
            elif choice == "2":
                self._print("Playing Scale...")
                sequence_data = {
                    'bpm': 120,
                    'sequence': [
                        ('C4', 0.2), ('D4', 0.2), ('E4', 0.2), ('F4', 0.2),
                        ('G4', 0.2), ('A4', 0.2), ('B4', 0.2), ('C5', 0.4)
                    ]
                }
                buzzer.play_sequence(sequence_data)
            else:
                try:
                    idx = int(choice)
                    preset_index = idx - 3
                    if 0 <= preset_index < len(presets):
                        name, data = presets[preset_index]
                        self._print(f"Playing {name}...")
                        buzzer.play_sequence(data)
                    else:
                        self._print("Invalid selection.")
                except ValueError:
                    self._print("Please enter a number.")

        self._print("Buzzer Test Exit.")

    async def test_display(self):
        """Test the OLED display."""
        self._print("\n--- DISPLAY TEST ---")

        display = self._get_manager('display')
        if display is None:
            self._print("Initializing DisplayManager...")
            try:
                from managers.display_manager import DisplayManager
                i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)
                oled_addr = getattr(Pins, 'I2C_ADDRESSES', {}).get("OLED", 0x3C)
                display = DisplayManager(i2c, device_address=oled_addr)
            except Exception as e:
                self._print(f"FAILED to init display: {e}")
                return

        while True:
            self._print("\n[Display Menu]")
            self._print("1. Show Status Message")
            self._print("2. Show Header Text")
            self._print("3. Show Footer Text")
            self._print("4. Show Long Text (scrolling)")
            self._print("5. Clear Display")
            self._print("6. Test Slide In Animation")
            self._print("7. Test Typewriter Animation")
            self._print("8. Test Blink Animation")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                display.update_status("Console Test", "Testing display...")
                self._print("Status updated.")
            elif choice == "2":
                display.update_header("CONSOLE TEST")
                self._print("Header updated.")
            elif choice == "3":
                display.update_footer("Footer test")
                self._print("Footer updated.")
            elif choice == "4":
                long_text = "This is a long text test to demonstrate scrolling on the OLED display. "
                display.update_header(long_text)
                display.update_status(long_text, long_text)
                display.update_footer(long_text)
                self._print("Long text updated. It should scroll if it exceeds display width.")
            elif choice == "5":
                display.update_status("", "")
                display.update_header("")
                display.update_footer("")
                self._print("Display cleared.")
            elif choice == "6":
                display.update_status("", "")
                display.update(display.status, "Slide In Animation", anim="slide_in", direction="left")
                self._print("Slide in animation triggered.")
            elif choice == "7":
                display.update_status("", "")
                display.update(display.status, "Typewriter Animation", anim="typewriter")
                display.update(display.sub_status, "Typewriter Animation", anim="typewriter", direction="right")
                self._print("Typewriter animation triggered.")
            elif choice == "8":
                display.update_status("", "")
                display.update(display.status, "Blink Animation", anim="blink")
                self._print("Blink animation triggered.")
            else:
                self._print("Invalid selection.")

        self._print("Display Test Exit.")

    async def test_leds(self):
        """Test individual button LEDs."""
        self._print("\n--- LED TEST ---")

        leds = self._get_manager('leds')
        if leds is None:
            self._print("No LED manager available from app. LED test requires running app.")
            return

        colors = [
            ("Red",     Palette.RED),
            ("Green",   Palette.GREEN),
            ("Blue",    Palette.BLUE),
            ("White",   Palette.WHITE),
            ("Cyan",    Palette.CYAN),
            ("Magenta", Palette.MAGENTA),
        ]

        while True:
            self._print("\n[LED Menu]")
            self._print("1. All LEDs - Solid Color")
            self._print("2. All LEDs - Flash (Cyan)")
            self._print("3. All LEDs - Breathe (Magenta)")
            self._print("4. Rainbow Animation (5s)")
            self._print("5. All LEDs Off")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                leds.off_led(-1)
                break
            elif choice == "1":
                self._print("Select color:")
                for i, (name, _) in enumerate(colors, 1):
                    self._print(f"{i}. {name}")
                c = await self.get_input(">> ")
                try:
                    ci = int(c) - 1
                    if 0 <= ci < len(colors):
                        leds.set_led(-1, colors[ci][1])
                        self._print(f"LEDs set to {colors[ci][0]}.")
                    else:
                        self._print("Invalid selection.")
                except ValueError:
                    self._print("Please enter a number.")
            elif choice == "2":
                leds.set_led(-1, Palette.CYAN, anim_mode="FLASH")
                self._print("LEDs flashing cyan.")
            elif choice == "3":
                leds.set_led(-1, Palette.MAGENTA, anim_mode="BREATH")
                self._print("LEDs breathing magenta.")
            elif choice == "4":
                leds.start_rainbow(duration=5.0)
                self._print("Rainbow animation started (5s).")
            elif choice == "5":
                leds.off_led(-1)
                self._print("LEDs off.")
            else:
                self._print("Invalid selection.")

        self._print("LED Test Exit.")

    async def test_matrix(self):
        """Test the LED matrix display."""
        self._print("\n--- MATRIX TEST ---")

        matrix = self._get_manager('matrix')
        if matrix is None:
            self._print("No Matrix manager available from app. Matrix test requires running app.")
            return

        fill_colors = [
            ("Red",   Palette.RED),
            ("Green", Palette.GREEN),
            ("Blue",  Palette.BLUE),
            ("White", Palette.WHITE),
        ]

        while True:
            self._print("\n[Matrix Menu]")
            for i, (name, _) in enumerate(fill_colors, 1):
                self._print(f"{i}. Fill {name}")
            self._print("5. Rainbow Animation (5s)")
            self._print("6. Clear Matrix")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice in ("1", "2", "3", "4"):
                color_name, color = fill_colors[int(choice) - 1]
                matrix.fill(color)
                self._print(f"Matrix filled {color_name}.")
            elif choice == "5":
                matrix.rainbow(duration=5.0)
                self._print("Rainbow animation started (5s).")
            elif choice == "6":
                matrix.fill(Palette.OFF)
                self._print("Matrix cleared.")
            else:
                self._print("Invalid selection.")

        self._print("Matrix Test Exit.")

    async def test_audio(self):
        """Test the I2S audio system."""
        self._print("\n--- AUDIO TEST ---")

        audio = self._get_manager('audio')
        if audio is None:
            self._print("No Audio manager available from app. Audio test requires running app.")
            return

        while True:
            self._print("\n[Audio Menu]")
            self._print("1. Play Menu Tick")
            self._print("2. Play Menu Select")
            self._print("3. Rapid Fire Tick (10x)")
            self._print("4. Stop All Audio")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                await audio.play("audio/menu/tick.wav", bus_id=audio.CH_SFX)
                self._print("Playing menu tick.")
            elif choice == "2":
                await audio.play("audio/menu/select.wav", bus_id=audio.CH_SFX)
                self._print("Playing menu select.")
            elif choice == "3":
                self._print("Playing rapid fire ticks...")
                for _ in range(10):
                    await audio.play("audio/menu/tick.wav", bus_id=audio.CH_SFX, interrupt=False)
                    await asyncio.sleep(0.1)
            elif choice == "4":
                audio.stop_all()
                self._print("Audio stopped.")
            else:
                self._print("Invalid selection.")

        self._print("Audio Test Exit.")

    async def test_synth(self):
        """Test the synthio synthesizer."""
        self._print("\n--- SYNTH TEST ---")

        synth = self._get_manager('synth')
        if synth is None:
            self._print("No Synth manager available from app. Synth test requires running app.")
            return

        notes = [
            ("C4", 261.63),
            ("A4", 440.00),
            ("C5", 523.25),
        ]

        while True:
            self._print("\n[Synth Menu]")
            for i, (note_name, freq) in enumerate(notes, 1):
                self._print(f"{i}. Play {note_name} ({freq:.0f}Hz) - 0.5s")
            self._print("4. Play C Major Arpeggio")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice in ("1", "2", "3"):
                note_name, freq = notes[int(choice) - 1]
                synth.play_note(freq, duration=0.5)
                self._print(f"Playing {note_name}...")
            elif choice == "4":
                self._print("Playing C Major arpeggio...")
                for freq in [261.63, 329.63, 392.00, 523.25]:
                    synth.play_note(freq, duration=0.3)
                    await asyncio.sleep(0.35)
            else:
                self._print("Invalid selection.")

        self._print("Synth Test Exit.")

    async def test_segment(self):
        """Test the 14-segment display."""
        self._print("\n--- SEGMENT DISPLAY TEST ---")

        segment = self._get_manager('segment')
        if segment is None:
            self._print("Initializing SegmentManager...")
            try:
                from managers.segment_manager import SegmentManager
                i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)
                segment = SegmentManager(i2c)
            except Exception as e:
                self._print(f"FAILED to init segment display: {e}")
                return

        while True:
            self._print("\n[Segment Menu]")
            self._print("1. Show 'HELLO'")
            self._print("2. Show Custom Text")
            self._print("3. Matrix Animation (2s)")
            self._print("4. Corrupt Animation (2s)")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                await segment.start_message("HELLO", loop=False)
                self._print("Showing HELLO.")
            elif choice == "2":
                text = await self.get_input("Enter text: ")
                await segment.start_message(text, loop=False)
                self._print(f"Showing '{text}'.")
            elif choice == "3":
                await segment.apply_command("DSPMATRIX", "2.0")
                self._print("Matrix animation (2s).")
            elif choice == "4":
                await segment.apply_command("DSPCORRUPT", "2.0")
                self._print("Corrupt animation (2s).")
            else:
                self._print("Invalid selection.")

        self._print("Segment Test Exit.")

    async def test_power(self):
        """Read and display power rail voltages."""
        self._print("\n--- POWER MONITOR ---")

        power = self._get_manager('power')
        if power is None:
            self._print("No Power manager available from app. Power test requires running app.")
            return

        while True:
            self._print("\n[Power Menu]")
            self._print("1. Read All Voltage Rails")
            self._print("2. Check Satellite Bus State")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                self._print("\nPower Readings:")
                try:
                    for bus in power.buses.values():
                        message = f"{bus.name}: {bus.v_now:.2f} V"
                        if bus.has_current and bus.i_now is not None:
                            message += f", {bus.i_now:.2f} mA"
                        if bus.has_power and bus.p_now is not None:
                            message += f", {bus.p_now:.2f} mW"
                        message += f" [{bus.get_status_string()}]"
                        self._print(f"- {message}")
                except Exception as e:
                    self._print(f"  Error reading voltages: {e}")
            elif choice == "2":
                try:
                    connected = power.satbus_connected
                    powered = power.satbus_powered
                    self._print(f"Satellite bus connected: {connected}")
                    self._print(f"Satellite bus powered:   {powered}")
                except Exception as e:
                    self._print(f"Error reading bus state: {e}")
            else:
                self._print("Invalid selection.")

        self._print("Power Monitor Exit.")

    async def test_relay(self):
        """Test relay outputs."""
        self._print("\n--- RELAY TEST ---")

        relay = self._get_manager('relay')
        if relay is None:
            self._print("No Relay manager available from app. Relay test requires running app.")
            return

        while True:
            num = getattr(relay, 'num_relays', 0)
            self._print(f"\n[Relay Menu]  (available relays: {num})")
            self._print("1. Trigger All Relays (0.1s pulse)")
            self._print("2. Toggle Single Relay by Index")
            self._print("3. All Relays OFF")
            self._print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                relay.set_relay(-1, False)
                break
            elif choice == "1":
                await relay.trigger_relay(-1, duration=0.1, cycles=1)
                self._print("All relays triggered.")
            elif choice == "2":
                idx_str = await self.get_input("Enter relay index: ")
                try:
                    i = int(idx_str)
                    new_state = not relay.get_state(i)
                    relay.set_relay(i, new_state)
                    self._print(f"Relay {i} {'ON' if new_state else 'OFF'}.")
                except Exception as e:
                    self._print(f"Error: {e}")
            elif choice == "3":
                relay.set_relay(-1, False)
                self._print("All relays off.")
            else:
                self._print("Invalid selection.")

        self._print("Relay Test Exit.")

    async def test_hid(self):
        """Monitor HID inputs (buttons, encoders, toggles) for 10 seconds."""
        self._print("\n--- HID INPUT MONITOR ---")

        hid = self._get_manager('hid')
        if hid is None:
            self._print("No HID manager available from app. HID test requires running app.")
            return

        self._print("Monitoring inputs for 10 seconds. Press any input...")
        for _ in range(200):  # 10 s at 0.05 s intervals
            microcontroller.watchdog.feed()
            try:
                status = hid.get_status_string()
                if status and not status.startswith("0000,,,,0,0,0"):
                    self._print(f"\rHID: {status}")
            except Exception:
                pass
            await asyncio.sleep(0.05)
        self._print("\nHID Monitor Exit.")

    async def test_i2c_scan(self):
        """Scan the I2C bus and print discovered device addresses."""
        self._print("\n--- I2C SCAN ---")

        # Reuse the app's I2C bus when available to avoid hardware conflicts
        app_i2c = self._get_manager('i2c')
        standalone_i2c = None

        if app_i2c is not None:
            i2c = app_i2c
        else:
            try:
                standalone_i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)
                i2c = standalone_i2c
            except Exception as e:
                self._print(f"I2C Error: {e}")
                return

        try:
            while not i2c.try_lock():
                await asyncio.sleep(0.01)

            self._print("Scanning I2C bus...")
            devices = []
            try:
                devices = i2c.scan()
            except Exception as e:
                self._print(f"I2C Scan Error: {e}")
            finally:
                i2c.unlock()

            if devices:
                self._print("Devices found:", [hex(d) for d in devices])
                self._print("Common addresses:")
                self._print("- 0x20: MCP23017 (Expander)")
                self._print("- 0x3C: OLED Display")
            else:
                self._print("No I2C devices found.")
        except Exception as e:
            self._print(f"I2C Error: {e}")
        finally:
            if standalone_i2c is not None:
                standalone_i2c.deinit()

        await asyncio.sleep(1)

    async def test_mode_launcher(self):
        """Dynamically launch a game mode or its tutorial from the console."""
        self._print("\n--- MODE LAUNCHER ---")

        if self.app is None:
            self._print("No app instance available. Mode Launcher requires a running app.")
            return

        if not hasattr(self.app, 'mode_registry') or not self.app.mode_registry:
            self._print("App has no mode registry. Cannot list modes.")
            return

        # 1. Determine if the Industrial Satellite is physically connected
        has_industrial = False
        if hasattr(self.app, 'satellites'):
            for sat in self.app.satellites.values():
                if getattr(sat, 'sat_type_name', '') == "INDUSTRIAL" and getattr(sat, 'is_active', False):
                    has_industrial = True
                    break

        # 2. Collect modes, filtering out those missing hardware requirements
        game_modes = []
        for meta in self.app.mode_registry.values():
            if meta.get("menu") in ["MAIN", "CORE", "EXP1", "ZERO_PLAYER"]:
                reqs = meta.get("requires", [])
                if "INDUSTRIAL" in reqs and not has_industrial:
                    continue  # Skip this mode, missing hardware
                game_modes.append(meta)

        if not game_modes:
            self._print("No launchable game modes found (or missing hardware).")
            return

        # Sort by order then name for a stable display
        game_modes.sort(key=lambda m: (m.get("order", 9999), m.get("name", "")))

        self._print("\nAvailable Game Modes:")
        for i, meta in enumerate(game_modes, 1):
            tutorial_tag = " [+T]" if meta.get("has_tutorial", False) else ""
            self._print(f"  {i}. {meta['name']}{tutorial_tag}")
        self._print("  0. Back to Main Menu")

        raw = await self.get_input("Select mode number >> ")

        if raw == "0":
            return

        try:
            idx = int(raw) - 1
        except ValueError:
            self._print("Invalid input. Please enter a number.")
            return

        if idx < 0 or idx >= len(game_modes):
            self._print("Selection out of range.")
            return

        selected_meta = game_modes[idx]
        mode_id = selected_meta["id"]
        has_tutorial = selected_meta.get("has_tutorial", False)

        if has_tutorial:
            self._print(f"\nLaunch '{selected_meta['name']}':")
            self._print("  1. Main Game")
            self._print("  2. Tutorial")
            variant_choice = await self.get_input(">> ")
        else:
            variant_choice = "1"

        if variant_choice in ("1", "2"):
            if variant_choice == "2":
                self.app._pending_mode_variant = "TUTORIAL"
                self._print(f"Mode switch requested: {selected_meta['name']} (tutorial)")
            else:
                self.app._pending_mode_variant = None
                self._print(f"Mode switch requested: {selected_meta['name']} (main game)")

            # 3. Set the HIGH PRIORITY OVERRIDE flag (NOT self.app.mode!)
            self.app.console_override_mode = mode_id

            # 4. Forcefully interrupt the CURRENT mode so the app loop can transition
            if hasattr(self.app, 'active_mode') and self.app.active_mode:
                # Trigger the graceful exit flag in BaseMode / UtilityMode
                self.app.active_mode._exit_requested = True

                # If the app runner stores the asyncio.Task, cancel it directly to be safe
                if hasattr(self.app, 'active_mode_task') and self.app.active_mode_task:
                    self.app.active_mode_task.cancel()

            self._print(">>> Injection sent. Waiting for active mode to yield...")
        else:
            self._print("Invalid selection. Returning to main menu.")

    async def live_debug_console(self):
        """Live Debug Console for injecting virtual HID inputs and manipulating game state.

        Runs an interactive command loop alongside the active game mode.  Two
        categories of command are supported:

        **HID Spoofing** – inject virtual inputs into the core or satellite HID
        arrays so that the running mode sees them on its next poll cycle:

            enc <index> <delta>          – adjust core encoder *index* by *delta* ticks
            btn <index>                  – simulate a tap on core button *index*
            tog <index> <0|1>            – set core latching toggle *index* ON/OFF
            mom <index> <U|D|C>          – set core momentary toggle *index* (Up/Down/Centre)
            sat enc <index> <delta>      – adjust first satellite encoder *index* by *delta*
            sat btn <index>              – simulate a tap on first satellite button *index*
            sat tog <index> <0|1>        – set first satellite latching toggle *index*
            sat mom <index> <U|D|C>      – set first satellite momentary toggle *index*

        **God Mode** – directly modify attributes on the active mode instance:

            <attr> = <value>             – set *attr* on the active mode; value is
                                           auto-cast to int, then float, then kept as str

        Type ``exit`` to return to the main diagnostic menu.
        """
        self._print("\n--- LIVE DEBUG CONSOLE ---")
        self._print("Commands: enc/btn/tog/mom, sat enc/btn/tog/mom, <attr>=<value>, exit")
        self._print("Type 'help' for command reference.")

        if self.app is None:
            self._print("No app instance available. Live Debug Console requires a running app.")
            return

        while True:
            raw = await self.get_input("debug> ")
            cmd = raw.strip()

            if not cmd:
                continue

            if cmd.lower() == "exit":
                self._print("Exiting Live Debug Console.")
                break

            if cmd.lower() == "help":
                self._print("  enc <index> <delta>     - core encoder (relative ticks)")
                self._print("  btn <index>             - core button tap")
                self._print("  tog <index> <0|1>       - core latching toggle")
                self._print("  mom <index> <U|D|C>     - core momentary toggle")
                self._print("  sat enc <i> <delta>     - satellite encoder (relative ticks)")
                self._print("  sat btn <i>             - satellite button tap")
                self._print("  sat tog <i> <0|1>       - satellite latching toggle")
                self._print("  sat mom <i> <U|D|C>     - satellite momentary toggle")
                self._print("  <attr> = <value>        - set attribute on active mode")
                self._print("  exit                    - return to main menu")
                continue

            # ------------------------------------------------------------------
            # God Mode: assignment parser  (e.g. "score = 5000")
            # ------------------------------------------------------------------
            if "=" in cmd:
                parts = cmd.split("=", 1)
                attr = parts[0].strip()
                val_str = parts[1].strip()

                active = getattr(self.app, 'active_mode', None)
                if active is None:
                    self._print("No active game mode running. God Mode is unavailable.")
                    continue

                # Auto-cast: try int, then float, then keep as string
                try:
                    value = int(val_str)
                except ValueError:
                    try:
                        value = float(val_str)
                    except ValueError:
                        value = val_str

                try:
                    setattr(active, attr, value)
                    self._print(f"Set {attr} = {repr(value)}")
                except Exception as e:
                    self._print(f"Error setting attribute: {e}")
                continue

            # ------------------------------------------------------------------
            # HID spoofing
            # ------------------------------------------------------------------
            tokens = cmd.split()

            if tokens[0].lower() == "sat":
                # Satellite HID commands
                await self._debug_cmd_sat(tokens[1:])
            else:
                # Core HID commands
                await self._debug_cmd_core(tokens)

    async def _debug_cmd_core(self, tokens):
        """Parse and apply a core HID debug command."""
        hid = getattr(self.app, 'hid', None)
        await self._process_hid_cmd(hid, tokens, "Core")

    async def _debug_cmd_sat(self, tokens):
        """Parse and apply a satellite HID debug command."""
        satellites = getattr(self.app, 'satellites', None)
        if not satellites:
            self._print("No satellites connected.")
            return

        # Use the first active satellite
        sat = None
        for s in satellites.values():
            if getattr(s, 'is_active', False):
                sat = s
                break
        if sat is None:
            self._print("No active satellite found.")
            return

        hid = getattr(sat, 'hid', None)
        await self._process_hid_cmd(hid, tokens, "Sat")

    async def _process_hid_cmd(self, hid, tokens, prefix):
        """Unified HID command processor for both Core and Satellite."""
        if hid is None:
            self._print(f"No {prefix.lower()} HID manager available.")
            return

        verb = tokens[0].lower() if tokens else ""

        if verb == "enc":
            if len(tokens) < 3:
                self._print(f"Usage: {prefix.lower()} enc <index> <delta>")
                return
            try:
                idx = int(tokens[1])
                delta = int(tokens[2])
            except ValueError:
                self._print(f"{prefix.lower()} enc: index and delta must be integers.")
                return
            if idx < 0 or idx >= len(hid.encoder_positions):
                self._print(f"{prefix.lower()} enc: index {idx} out of range (0-{len(hid.encoder_positions)-1}).")
                return

            # Safely build the colon-separated string
            encoder_strs = []
            for i, val in enumerate(hid.encoder_positions):
                if i == idx:
                    encoder_strs.append(str(val + delta))
                    JEBLogger.debug("CONS", f"{prefix} encoder[{idx}] adjusted by {delta:+d} -> {val + delta}")
                else:
                    encoder_strs.append(str(val))

            encoder_str = ":".join(encoder_strs)
            hid._sw_set_encoders(encoder_str, override=True)
            JEBLogger.debug("CONS", f"{prefix} encoders set to: {encoder_str}")

        elif verb == "btn":
            if len(tokens) < 2:
                self._print(f"Usage: {prefix.lower()} btn <index> [0|1]")
                return
            try:
                idx = int(tokens[1])
            except ValueError:
                self._print("btn: index must be an integer.")
                return
            if idx < 0 or idx >= len(hid.buttons_values):
                self._print(f"btn: index {idx} out of range.")
                return

            buttons = hid.buttons_values.copy()  # Copy to avoid mutating original

            # If a 3rd argument is provided, HOLD the button in that state
            if len(tokens) >= 3:
                state = bool(int(tokens[2]))
                buttons[idx] = state
                buttons_str = "".join(['1' if b else '0' for b in buttons])
                hid._sw_set_buttons(buttons_str, override=True)
                self._print(f"{prefix} button[{idx}] held {'DOWN' if state else 'UP'}.")
            else:
                # Otherwise, simulate a quick physical tap
                buttons[idx] = True
                buttons_str = "".join(['1' if b else '0' for b in buttons])
                hid._sw_set_buttons(buttons_str, override=True)
                await asyncio.sleep(0.1)
                buttons[idx] = False
                buttons_str = "".join(['1' if b else '0' for b in buttons])
                hid._sw_set_buttons(buttons_str, override=True)
                self._print(f"{prefix} button[{idx}] tapped.")

        elif verb == "tog":
            if len(tokens) < 3:
                self._print(f"Usage: {prefix.lower()} tog <index> <0|1>")
                return
            try:
                idx = int(tokens[1])
                val = int(tokens[2])
            except ValueError:
                self._print(f"{prefix.lower()} tog: index and value must be integers.")
                return
            if idx < 0 or idx >= len(hid.latching_values):
                self._print(f"{prefix.lower()} tog: index {idx} out of range (0-{len(hid.latching_values)-1}).")
                return

            # Reconstruct the latching string
            toggles = list(hid.latching_values)
            toggles[idx] = bool(val)
            tog_str = "".join(['1' if t else '0' for t in toggles])

            hid._sw_set_latching_toggles(tog_str, override=True)
            self._print(f"{prefix} toggle[{idx}] set to {'ON' if val else 'OFF'}.")

        elif verb == "mom":
            if len(tokens) < 3:
                self._print(f"Usage: {prefix.lower()} mom <index> <U|D|C>")
                return
            try:
                idx = int(tokens[1])
            except ValueError:
                self._print("mom: index must be an integer.")
                return
            direction = tokens[2].upper()
            if direction not in ("U", "D", "C"):
                self._print("mom: direction must be U, D, or C.")
                return
            if idx < 0 or idx >= len(hid.momentary_values):
                self._print(f"mom: index {idx} out of range.")
                return

            # Reconstruct the momentary string ('U', 'D', or 'C')
            mom_states = []
            for i, (up, down) in enumerate(hid.momentary_values):
                if i == idx:
                    mom_states.append(direction)
                else:
                    if up:
                        mom_states.append("U")
                    elif down:
                        mom_states.append("D")
                    else:
                        mom_states.append("C")

            mom_str = "".join(mom_states)
            hid._sw_set_momentary_toggles(mom_str, override=True)

            label = {"U": "UP", "D": "DOWN", "C": "CENTRE"}[direction]
            self._print(f"{prefix} momentary[{idx}] held at {label}.")

        else:
            self._print(f"Unknown {prefix.lower()} HID command: '{verb}'. Type 'help' for usage.")

    async def start(self):
        """Main interactive loop for the Console Manager."""

        await asyncio.sleep(2)  # Short delay to allow main app to start up when running alongside

        self._print("\n" + "="*30)
        self._print(" JEB HARDWARE DIAGNOSTICS ")
        self._print("="*30)
        if self.app is not None:
            self._print("Running alongside main application.")

        while True:
            # Feed the hardware watchdog timer to prevent system reset
            microcontroller.watchdog.feed()

            self._print("\n[MAIN MENU]")
            self._print("1. Test Buzzer")
            self._print("2. Test Display")
            self._print("3. Test LEDs")
            self._print("4. Test Matrix")
            self._print("5. Test Audio")
            self._print("6. Test Synth")
            self._print("7. Test Segment Display")
            self._print("8. Monitor Power")
            self._print("9. Test Relays")
            self._print("H. Monitor HID Inputs")
            self._print("I. I2C Bus Scan")
            self._print("L. Live Debug Console")
            self._print("M. Launch Game Mode")
            self._print("R. Reboot")

            choice = await self.get_input("Select Option >> ")

            if choice == "1":
                await self.test_buzzer()
            elif choice == "2":
                await self.test_display()
            elif choice == "3":
                await self.test_leds()
            elif choice == "4":
                await self.test_matrix()
            elif choice == "5":
                await self.test_audio()
            elif choice == "6":
                await self.test_synth()
            elif choice == "7":
                await self.test_segment()
            elif choice == "8":
                await self.test_power()
            elif choice == "9":
                await self.test_relay()
            elif choice.upper() == "H":
                await self.test_hid()
            elif choice.upper() == "I":
                await self.test_i2c_scan()
            elif choice.upper() == "L":
                await self.live_debug_console()
            elif choice.upper() == "M":
                await self.test_mode_launcher()
            elif choice.upper() == "R":
                supervisor.reload()
            else:
                self._print("Invalid selection.")
