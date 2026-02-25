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

        JEBLogger.info("CONS",f"[INIT] ConsoleManager - role: {self.role} type_id: {self.type_id}")

        if app is None:
            Pins.initialize(profile=role, type_id=type_id)
        else:
            JEBLogger.info("CONS", f"Attaching to {app} hardware instances")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_manager(self, name):
        """Return a named manager from the running app, or ``None``."""
        if self.app is not None:
            return getattr(self.app, name, None)
        return None

    async def get_input(self, prompt):
        """Safe non-blocking serial input wrapper."""
        print(prompt, end="")
        while True:
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
            print("4. Clear Display")
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
                display.update_status("", "")
                display.update_header("")
                display.update_footer("")
                print("Display cleared.")
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
                leds.set_led(-1, Palette.CYAN, anim="FLASH")
                print("LEDs flashing cyan.")
            elif choice == "3":
                leds.set_led(-1, Palette.MAGENTA, anim="BREATH")
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
                matrix.start_rainbow(duration=5.0)
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
            print("3. Stop All Audio")
            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                break
            elif choice == "1":
                await audio.play("audio/menu/tick.wav", channel=audio.CH_SFX)
                print("Playing menu tick.")
            elif choice == "2":
                await audio.play("audio/menu/select.wav", channel=audio.CH_SFX)
                print("Playing menu select.")
            elif choice == "3":
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
            elif choice.upper() == "R":
                supervisor.reload()
            else:
                print("Invalid selection.")
