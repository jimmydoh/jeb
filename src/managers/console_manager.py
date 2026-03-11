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
            JEBLogger.info("CONS", f"Attaching to {app} hardware instances")

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
        print(prompt, end="")
        while True:
            if self.input_queue:
                line = self.input_queue.pop(0)
                # Echo the injected line so the output buffer looks like a terminal
                echoed_line = f"{prompt}{line}"
                self.output_buffer.append(echoed_line)
                if len(self.output_buffer) > self._output_buffer_max:
                    self.output_buffer = self.output_buffer[-self._output_buffer_max:]
                print(line)
                return line
            if supervisor.runtime.serial_bytes_available:
                return sys.stdin.readline().strip()
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
        print("\n--- BUZZER TEST ---")

        buzzer = self._get_manager('buzzer')
        if buzzer is None:
            try:
                from managers.buzzer_manager import BuzzerManager
                buzzer = BuzzerManager(Pins.BUZZER)
            except Exception as e:
                print(f"FAILED to init buzzer: {e}")
                return

        presets = self.get_tone_presets()

        while True:
            print("\n[Buzzer Menu]")
            print("1. Play Tone (440Hz)")
            print("2. Play Scale (C Major)")
            for i, (name, _) in enumerate(presets, 3):
                print(f"{i}. Preset: {name}")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                await buzzer.stop()
                break
            elif choice == "1":
                print("Playing 440Hz...")
                buzzer.play_note(440, 1.0)
            elif choice == "2":
                print("Playing Scale...")
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
                        print(f"Playing {name}...")
                        buzzer.play_sequence(data)
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")

        print("Buzzer Test Exit.")

    async def test_display(self):
        """Test the OLED display."""
        print("\n--- DISPLAY TEST ---")

        display = self._get_manager('display')
        if display is None:
            print("Initializing DisplayManager...")
            try:
                from managers.display_manager import DisplayManager
                i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)
                oled_addr = getattr(Pins, 'I2C_ADDRESSES', {}).get("OLED", 0x3C)
                display = DisplayManager(i2c, device_address=oled_addr)
            except Exception as e:
                print(f"FAILED to init display: {e}")
                return

        while True:
            print("\n[Display Menu]")
            print("1. Show Status Message")
            print("2. Show Header Text")
            print("3. Show Footer Text")
            print("4. Show Long Text (scrolling)")
            print("5. Clear Display")
            print("6. Test Slide In Animation")
            print("7. Test Typewriter Animation")
            print("8. Test Blink Animation")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                display.update_status("Console Test", "Testing display...")
                print("Status updated.")
            elif choice == "2":
                display.update_header("CONSOLE TEST")
                print("Header updated.")
            elif choice == "3":
                display.update_footer("Footer test")
                print("Footer updated.")
            elif choice == "4":
                long_text = "This is a long text test to demonstrate scrolling on the OLED display. "
                display.update_header(long_text)
                display.update_status(long_text, long_text)
                display.update_footer(long_text)
                print("Long text updated. It should scroll if it exceeds display width.")
            elif choice == "5":
                display.update_status("", "")
                display.update_header("")
                display.update_footer("")
                print("Display cleared.")
            elif choice == "6":
                display.update_status("", "")
                display.update(display.status, "Slide In Animation", anim="slide_in", direction="left")
                print("Slide in animation triggered.")
            elif choice == "7":
                display.update_status("", "")
                display.update(display.status, "Typewriter Animation", anim="typewriter")
                display.update(display.sub_status, "Typewriter Animation", anim="typewriter", direction="right")
                print("Typewriter animation triggered.")
            elif choice == "8":
                display.update_status("", "")
                display.update(display.status, "Blink Animation", anim="blink")
                print("Blink animation triggered.")
            else:
                print("Invalid selection.")

        print("Display Test Exit.")

    async def test_leds(self):
        """Test individual button LEDs."""
        print("\n--- LED TEST ---")

        leds = self._get_manager('leds')
        if leds is None:
            print("No LED manager available from app. LED test requires running app.")
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
            print("\n[LED Menu]")
            print("1. All LEDs - Solid Color")
            print("2. All LEDs - Flash (Cyan)")
            print("3. All LEDs - Breathe (Magenta)")
            print("4. Rainbow Animation (5s)")
            print("5. All LEDs Off")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                leds.off_led(-1)
                break
            elif choice == "1":
                print("Select color:")
                for i, (name, _) in enumerate(colors, 1):
                    print(f"{i}. {name}")
                c = await self.get_input(">> ")
                try:
                    ci = int(c) - 1
                    if 0 <= ci < len(colors):
                        leds.set_led(-1, colors[ci][1])
                        print(f"LEDs set to {colors[ci][0]}.")
                    else:
                        print("Invalid selection.")
                except ValueError:
                    print("Please enter a number.")
            elif choice == "2":
                leds.set_led(-1, Palette.CYAN, anim_mode="FLASH")
                print("LEDs flashing cyan.")
            elif choice == "3":
                leds.set_led(-1, Palette.MAGENTA, anim_mode="BREATH")
                print("LEDs breathing magenta.")
            elif choice == "4":
                leds.start_rainbow(duration=5.0)
                print("Rainbow animation started (5s).")
            elif choice == "5":
                leds.off_led(-1)
                print("LEDs off.")
            else:
                print("Invalid selection.")

        print("LED Test Exit.")

    async def test_matrix(self):
        """Test the LED matrix display."""
        print("\n--- MATRIX TEST ---")

        matrix = self._get_manager('matrix')
        if matrix is None:
            print("No Matrix manager available from app. Matrix test requires running app.")
            return

        fill_colors = [
            ("Red",   Palette.RED),
            ("Green", Palette.GREEN),
            ("Blue",  Palette.BLUE),
            ("White", Palette.WHITE),
        ]

        while True:
            print("\n[Matrix Menu]")
            for i, (name, _) in enumerate(fill_colors, 1):
                print(f"{i}. Fill {name}")
            print("5. Rainbow Animation (5s)")
            print("6. Clear Matrix")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice in ("1", "2", "3", "4"):
                color_name, color = fill_colors[int(choice) - 1]
                matrix.fill(color)
                print(f"Matrix filled {color_name}.")
            elif choice == "5":
                matrix.rainbow(duration=5.0)
                print("Rainbow animation started (5s).")
            elif choice == "6":
                matrix.fill(Palette.OFF)
                print("Matrix cleared.")
            else:
                print("Invalid selection.")

        print("Matrix Test Exit.")

    async def test_audio(self):
        """Test the I2S audio system."""
        print("\n--- AUDIO TEST ---")

        audio = self._get_manager('audio')
        if audio is None:
            print("No Audio manager available from app. Audio test requires running app.")
            return

        while True:
            print("\n[Audio Menu]")
            print("1. Play Menu Tick")
            print("2. Play Menu Select")
            print("3. Rapid Fire Tick (10x)")
            print("4. Stop All Audio")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                await audio.play("audio/menu/tick.wav", bus_id=audio.CH_SFX)
                print("Playing menu tick.")
            elif choice == "2":
                await audio.play("audio/menu/select.wav", bus_id=audio.CH_SFX)
                print("Playing menu select.")
            elif choice == "3":
                print("Playing rapid fire ticks...")
                for _ in range(10):
                    await audio.play("audio/menu/tick.wav", bus_id=audio.CH_SFX, interrupt=False)
                    await asyncio.sleep(0.1)
            elif choice == "4":
                audio.stop_all()
                print("Audio stopped.")
            else:
                print("Invalid selection.")

        print("Audio Test Exit.")

    async def test_synth(self):
        """Test the synthio synthesizer."""
        print("\n--- SYNTH TEST ---")

        synth = self._get_manager('synth')
        if synth is None:
            print("No Synth manager available from app. Synth test requires running app.")
            return

        notes = [
            ("C4", 261.63),
            ("A4", 440.00),
            ("C5", 523.25),
        ]

        while True:
            print("\n[Synth Menu]")
            for i, (note_name, freq) in enumerate(notes, 1):
                print(f"{i}. Play {note_name} ({freq:.0f}Hz) - 0.5s")
            print("4. Play C Major Arpeggio")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice in ("1", "2", "3"):
                note_name, freq = notes[int(choice) - 1]
                synth.play_note(freq, duration=0.5)
                print(f"Playing {note_name}...")
            elif choice == "4":
                print("Playing C Major arpeggio...")
                for freq in [261.63, 329.63, 392.00, 523.25]:
                    synth.play_note(freq, duration=0.3)
                    await asyncio.sleep(0.35)
            else:
                print("Invalid selection.")

        print("Synth Test Exit.")

    async def test_segment(self):
        """Test the 14-segment display."""
        print("\n--- SEGMENT DISPLAY TEST ---")

        segment = self._get_manager('segment')
        if segment is None:
            print("Initializing SegmentManager...")
            try:
                from managers.segment_manager import SegmentManager
                i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA)
                segment = SegmentManager(i2c)
            except Exception as e:
                print(f"FAILED to init segment display: {e}")
                return

        while True:
            print("\n[Segment Menu]")
            print("1. Show 'HELLO'")
            print("2. Show Custom Text")
            print("3. Matrix Animation (2s)")
            print("4. Corrupt Animation (2s)")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                await segment.start_message("HELLO", loop=False)
                print("Showing HELLO.")
            elif choice == "2":
                text = await self.get_input("Enter text: ")
                await segment.start_message(text, loop=False)
                print(f"Showing '{text}'.")
            elif choice == "3":
                await segment.apply_command("DSPMATRIX", "2.0")
                print("Matrix animation (2s).")
            elif choice == "4":
                await segment.apply_command("DSPCORRUPT", "2.0")
                print("Corrupt animation (2s).")
            else:
                print("Invalid selection.")

        print("Segment Test Exit.")

    async def test_power(self):
        """Read and display power rail voltages."""
        print("\n--- POWER MONITOR ---")

        power = self._get_manager('power')
        if power is None:
            print("No Power manager available from app. Power test requires running app.")
            return

        while True:
            print("\n[Power Menu]")
            print("1. Read All Voltage Rails")
            print("2. Check Satellite Bus State")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                print("\nPower Readings:")
                try:
                    for bus in power.buses.values():
                        message = f"{bus.name}: {bus.v_now:.2f} V"
                        if bus.has_current and bus.i_now is not None:
                            message += f", {bus.i_now:.2f} mA"
                        if bus.has_power and bus.p_now is not None:
                            message += f", {bus.p_now:.2f} mW"
                        message += f" [{bus.get_status_string()}]"
                        print(f"- {message}")
                except Exception as e:
                    print(f"  Error reading voltages: {e}")
            elif choice == "2":
                try:
                    connected = power.satbus_connected
                    powered = power.satbus_powered
                    print(f"Satellite bus connected: {connected}")
                    print(f"Satellite bus powered:   {powered}")
                except Exception as e:
                    print(f"Error reading bus state: {e}")
            else:
                print("Invalid selection.")

        print("Power Monitor Exit.")

    async def test_relay(self):
        """Test relay outputs."""
        print("\n--- RELAY TEST ---")

        relay = self._get_manager('relay')
        if relay is None:
            print("No Relay manager available from app. Relay test requires running app.")
            return

        while True:
            num = getattr(relay, 'num_relays', 0)
            print(f"\n[Relay Menu]  (available relays: {num})")
            print("1. Trigger All Relays (0.1s pulse)")
            print("2. Toggle Single Relay by Index")
            print("3. All Relays OFF")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                relay.set_relay(-1, False)
                break
            elif choice == "1":
                await relay.trigger_relay(-1, duration=0.1, cycles=1)
                print("All relays triggered.")
            elif choice == "2":
                idx_str = await self.get_input("Enter relay index: ")
                try:
                    i = int(idx_str)
                    new_state = not relay.get_state(i)
                    relay.set_relay(i, new_state)
                    print(f"Relay {i} {'ON' if new_state else 'OFF'}.")
                except Exception as e:
                    print(f"Error: {e}")
            elif choice == "3":
                relay.set_relay(-1, False)
                print("All relays off.")
            else:
                print("Invalid selection.")

        print("Relay Test Exit.")

    async def test_hid(self):
        """Monitor HID inputs (buttons, encoders, toggles) for 10 seconds."""
        print("\n--- HID INPUT MONITOR ---")

        hid = self._get_manager('hid')
        if hid is None:
            print("No HID manager available from app. HID test requires running app.")
            return

        print("Monitoring inputs for 10 seconds. Press any input...")
        for _ in range(200):  # 10 s at 0.05 s intervals
            microcontroller.watchdog.feed()
            try:
                status = hid.get_status_string()
                if status and not status.startswith("0000,,,,0,0,0"):
                    print(f"\rHID: {status}", end="")
            except Exception:
                pass
            await asyncio.sleep(0.05)
        print("\nHID Monitor Exit.")

    async def test_i2c_scan(self):
        """Scan the I2C bus and print discovered device addresses."""
        print("\n--- I2C SCAN ---")

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
                print(f"I2C Error: {e}")
                return

        try:
            while not i2c.try_lock():
                await asyncio.sleep(0.01)

            print("Scanning I2C bus...")
            devices = []
            try:
                devices = i2c.scan()
            except Exception as e:
                print(f"I2C Scan Error: {e}")
            finally:
                i2c.unlock()

            if devices:
                print("Devices found:", [hex(d) for d in devices])
                print("Common addresses:")
                print("- 0x20: MCP23017 (Expander)")
                print("- 0x3C: OLED Display")
            else:
                print("No I2C devices found.")
        except Exception as e:
            print(f"I2C Error: {e}")
        finally:
            if standalone_i2c is not None:
                standalone_i2c.deinit()

        await asyncio.sleep(1)

    async def test_mode_launcher(self):
        """Dynamically launch a game mode or its tutorial from the console."""
        print("\n--- MODE LAUNCHER ---")

        if self.app is None:
            print("No app instance available. Mode Launcher requires a running app.")
            return

        if not hasattr(self.app, 'mode_registry') or not self.app.mode_registry:
            print("App has no mode registry. Cannot list modes.")
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
            # Check old menu flag or new category flag
            if meta.get("menu") == "MAIN" or meta.get("category") in ["CORE", "EXP1", "ZERO"]:
                reqs = meta.get("requires", [])
                if "INDUSTRIAL" in reqs and not has_industrial:
                    continue  # Skip this mode, missing hardware
                game_modes.append(meta)

        if not game_modes:
            print("No launchable game modes found (or missing hardware).")
            return

        # Sort by order then name for a stable display
        game_modes.sort(key=lambda m: (m.get("order", 9999), m.get("name", "")))

        print("\nAvailable Game Modes:")
        for i, meta in enumerate(game_modes, 1):
            tutorial_tag = " [+T]" if meta.get("has_tutorial", False) else ""
            print(f"  {i}. {meta['name']}{tutorial_tag}")
        print("  0. Back to Main Menu")

        raw = await self.get_input("Select mode number >> ")

        if raw == "0":
            return

        try:
            idx = int(raw) - 1
        except ValueError:
            print("Invalid input. Please enter a number.")
            return

        if idx < 0 or idx >= len(game_modes):
            print("Selection out of range.")
            return

        selected_meta = game_modes[idx]
        mode_id = selected_meta["id"]
        has_tutorial = selected_meta.get("has_tutorial", False)

        if has_tutorial:
            print(f"\nLaunch '{selected_meta['name']}':")
            print("  1. Main Game")
            print("  2. Tutorial")
            variant_choice = await self.get_input(">> ")
        else:
            variant_choice = "1"

        if variant_choice in ("1", "2"):
            if variant_choice == "2":
                self.app._pending_mode_variant = "TUTORIAL"
                print(f"Mode switch requested: {selected_meta['name']} (tutorial)")
            else:
                self.app._pending_mode_variant = None
                print(f"Mode switch requested: {selected_meta['name']} (main game)")

            # 3. Set the HIGH PRIORITY OVERRIDE flag (NOT self.app.mode!)
            self.app.console_override_mode = mode_id

            # 4. Forcefully interrupt the CURRENT mode so the app loop can transition
            if hasattr(self.app, 'active_mode') and self.app.active_mode:
                # Trigger the graceful exit flag in BaseMode / UtilityMode
                self.app.active_mode._exit_requested = True

                # If the app runner stores the asyncio.Task, cancel it directly to be safe
                if hasattr(self.app, 'active_mode_task') and self.app.active_mode_task:
                    self.app.active_mode_task.cancel()

            print(">>> Injection sent. Waiting for active mode to yield...")
        else:
            print("Invalid selection. Returning to main menu.")

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
        print("\n--- LIVE DEBUG CONSOLE ---")
        print("Commands: enc/btn/tog/mom, sat enc/btn/tog/mom, <attr>=<value>, exit")
        print("Type 'help' for command reference.")

        if self.app is None:
            print("No app instance available. Live Debug Console requires a running app.")
            return

        while True:
            raw = await self.get_input("debug> ")
            cmd = raw.strip()

            if not cmd:
                continue

            if cmd.lower() == "exit":
                print("Exiting Live Debug Console.")
                break

            if cmd.lower() == "help":
                print("  enc <index> <delta>     - core encoder (relative ticks)")
                print("  btn <index>             - core button tap")
                print("  tog <index> <0|1>       - core latching toggle")
                print("  mom <index> <U|D|C>     - core momentary toggle")
                print("  sat enc <i> <delta>     - satellite encoder (relative ticks)")
                print("  sat btn <i>             - satellite button tap")
                print("  sat tog <i> <0|1>       - satellite latching toggle")
                print("  sat mom <i> <U|D|C>     - satellite momentary toggle")
                print("  <attr> = <value>        - set attribute on active mode")
                print("  exit                    - return to main menu")
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
                    print("No active game mode running. God Mode is unavailable.")
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
                    print(f"Set {attr} = {repr(value)}")
                except Exception as e:
                    print(f"Error setting attribute: {e}")
                continue

            # ------------------------------------------------------------------
            # HID spoofing
            # ------------------------------------------------------------------
            tokens = cmd.split()

            if tokens[0].lower() == "sat":
                # Satellite HID commands
                self._debug_cmd_sat(tokens[1:])
            else:
                # Core HID commands
                self._debug_cmd_core(tokens)

    def _debug_cmd_core(self, tokens):
        """Parse and apply a core HID debug command."""
        hid = getattr(self.app, 'hid', None)
        if hid is None:
            print("No core HID manager available.")
            return

        verb = tokens[0].lower() if tokens else ""

        if verb == "enc":
            if len(tokens) < 3:
                print("Usage: enc <index> <delta>")
                return
            try:
                idx = int(tokens[1])
                delta = int(tokens[2])
            except ValueError:
                print("enc: index and delta must be integers.")
                return
            if idx < 0 or idx >= len(hid.encoder_positions):
                print(f"enc: index {idx} out of range (0-{len(hid.encoder_positions)-1}).")
                return
            hid.encoder_positions[idx] += delta
            print(f"Core encoder[{idx}] adjusted by {delta:+d} -> {hid.encoder_positions[idx]}")

        elif verb == "btn":
            if len(tokens) < 2:
                print("Usage: btn <index>")
                return
            try:
                idx = int(tokens[1])
            except ValueError:
                print("btn: index must be an integer.")
                return
            if idx < 0 or idx >= len(hid.buttons_values):
                print(f"btn: index {idx} out of range (0-{len(hid.buttons_values)-1}).")
                return
            hid.buttons_tapped[idx] = True
            print(f"Core button[{idx}] tapped.")

        elif verb == "tog":
            if len(tokens) < 3:
                print("Usage: tog <index> <0|1>")
                return
            try:
                idx = int(tokens[1])
                val = int(tokens[2])
            except ValueError:
                print("tog: index and value must be integers.")
                return
            if idx < 0 or idx >= len(hid.latching_values):
                print(f"tog: index {idx} out of range (0-{len(hid.latching_values)-1}).")
                return
            hid.latching_values[idx] = bool(val)
            print(f"Core toggle[{idx}] set to {'ON' if val else 'OFF'}.")

        elif verb == "mom":
            if len(tokens) < 3:
                print("Usage: mom <index> <U|D|C>")
                return
            try:
                idx = int(tokens[1])
            except ValueError:
                print("mom: index must be an integer.")
                return
            direction = tokens[2].upper()
            if direction not in ("U", "D", "C"):
                print("mom: direction must be U, D, or C.")
                return
            if idx < 0 or idx >= len(hid.momentary_values):
                print(f"mom: index {idx} out of range (0-{len(hid.momentary_values)-1}).")
                return
            if direction == "U":
                hid.momentary_tapped[idx][0] = True
            elif direction == "D":
                hid.momentary_tapped[idx][1] = True
            # C (centre) - no tap, just ensure both directions are cleared
            else:
                hid.momentary_values[idx][0] = False
                hid.momentary_values[idx][1] = False
            label = {"U": "UP", "D": "DOWN", "C": "CENTRE"}[direction]
            print(f"Core momentary[{idx}] set to {label}.")

        else:
            print(f"Unknown HID command: '{verb}'. Type 'help' for usage.")

    def _debug_cmd_sat(self, tokens):
        """Parse and apply a satellite HID debug command."""
        satellites = getattr(self.app, 'satellites', None)
        if not satellites:
            print("No satellites connected.")
            return

        # Use the first active satellite
        sat = None
        for s in satellites.values():
            if getattr(s, 'is_active', False):
                sat = s
                break
        if sat is None:
            print("No active satellite found.")
            return

        hid = getattr(sat, 'hid', None)
        if hid is None:
            print("Satellite has no HID manager.")
            return

        verb = tokens[0].lower() if tokens else ""

        if verb == "enc":
            if len(tokens) < 3:
                print("Usage: sat enc <index> <delta>")
                return
            try:
                idx = int(tokens[1])
                delta = int(tokens[2])
            except ValueError:
                print("sat enc: index and delta must be integers.")
                return
            if idx < 0 or idx >= len(hid.encoder_positions):
                print(f"sat enc: index {idx} out of range (0-{len(hid.encoder_positions)-1}).")
                return
            hid.encoder_positions[idx] += delta
            print(f"Sat encoder[{idx}] adjusted by {delta:+d} -> {hid.encoder_positions[idx]}")

        elif verb == "btn":
            if len(tokens) < 2:
                print("Usage: sat btn <index>")
                return
            try:
                idx = int(tokens[1])
            except ValueError:
                print("sat btn: index must be an integer.")
                return
            if idx < 0 or idx >= len(hid.buttons_values):
                print(f"sat btn: index {idx} out of range (0-{len(hid.buttons_values)-1}).")
                return
            hid.buttons_tapped[idx] = True
            print(f"Sat button[{idx}] tapped.")

        elif verb == "tog":
            if len(tokens) < 3:
                print("Usage: sat tog <index> <0|1>")
                return
            try:
                idx = int(tokens[1])
                val = int(tokens[2])
            except ValueError:
                print("sat tog: index and value must be integers.")
                return
            if idx < 0 or idx >= len(hid.latching_values):
                print(f"sat tog: index {idx} out of range (0-{len(hid.latching_values)-1}).")
                return
            hid.latching_values[idx] = bool(val)
            print(f"Sat toggle[{idx}] set to {'ON' if val else 'OFF'}.")

        elif verb == "mom":
            if len(tokens) < 3:
                print("Usage: sat mom <index> <U|D|C>")
                return
            try:
                idx = int(tokens[1])
            except ValueError:
                print("sat mom: index must be an integer.")
                return
            direction = tokens[2].upper()
            if direction not in ("U", "D", "C"):
                print("sat mom: direction must be U, D, or C.")
                return
            if idx < 0 or idx >= len(hid.momentary_values):
                print(f"sat mom: index {idx} out of range (0-{len(hid.momentary_values)-1}).")
                return
            if direction == "U":
                hid.momentary_tapped[idx][0] = True
            elif direction == "D":
                hid.momentary_tapped[idx][1] = True
            else:
                hid.momentary_values[idx][0] = False
                hid.momentary_values[idx][1] = False
            label = {"U": "UP", "D": "DOWN", "C": "CENTRE"}[direction]
            print(f"Sat momentary[{idx}] set to {label}.")

        else:
            print(f"Unknown satellite HID command: '{verb}'. Type 'help' for usage.")

    async def start(self):
        """Main interactive loop for the Console Manager."""

        await asyncio.sleep(2)  # Short delay to allow main app to start up when running alongside

        print("\n" + "="*30)
        print(" JEB HARDWARE DIAGNOSTICS ")
        print("="*30)
        if self.app is not None:
            print("Running alongside main application.")

        while True:
            # Feed the hardware watchdog timer to prevent system reset
            microcontroller.watchdog.feed()

            print("\n[MAIN MENU]")
            print("1. Test Buzzer")
            print("2. Test Display")
            print("3. Test LEDs")
            print("4. Test Matrix")
            print("5. Test Audio")
            print("6. Test Synth")
            print("7. Test Segment Display")
            print("8. Monitor Power")
            print("9. Test Relays")
            print("H. Monitor HID Inputs")
            print("I. I2C Bus Scan")
            print("L. Live Debug Console")
            print("M. Launch Game Mode")
            print("R. Reboot")

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
                print("Invalid selection.")
