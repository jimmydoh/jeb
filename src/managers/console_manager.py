import sys

import asyncio
import busio
import microcontroller
import supervisor

from managers.buzzer_manager import BuzzerManager

from utilities import Pins,tones


class ConsoleManager():
    """A simple console manager for hardware diagnostics and development testing."""

    def __init__(self, role, type_id):
        self.role = role
        self.type_id = type_id
        Pins.initialize(profile=role, type_id=type_id)
        print(f"ConsoleManager for role {self.role} and type_id {self.type_id} initialized.")

    async def get_input(self, prompt):
        """Safe blocking input wrapper."""
        print(prompt, end="")
        while True:
            if supervisor.runtime.serial_bytes_available:
                return sys.stdin.readline().strip()
            await asyncio.sleep(0.05)

    def get_tone_presets(self):
        """
        Introspects utilities.tones to find all valid song dictionaries.
        Returns a list of tuples: [('COIN', dict), ('MARIO_THEME', dict), ...]
        """
        presets = []
        # Get all attributes of the module
        for name in dir(tones):
            # Skip private/internal attributes
            if name.startswith("_"):
                continue

            val = getattr(tones, name)

            # Filter: Must be a Dictionary and have a 'sequence' key
            if isinstance(val, dict) and "sequence" in val:
                presets.append((name, val))

        # Sort alphabetically for a tidy menu
        return sorted(presets, key=lambda x: x[0])

    async def test_buzzer(self):
        """Test the buzzer by allowing the user to play tones, scales, and presets."""
        print("\n--- BUZZER TEST ---")
        print("Initializing BuzzerManager on GP10...")

        try:
            buzzer = BuzzerManager(Pins.BUZZER, volume=0.5, testing=True)
        except Exception as e:
            print(f"FAILED to init buzzer: {e}")
            return

        # 1. Fetch the dynamic list once
        presets = self.get_tone_presets()

        while True:
            print("\n[Buzzer Menu]")
            print("1. Play Tone (440Hz)")
            print("2. Play Scale (C Major)")

            # 2. Dynamically print presets starting at index 3
            # enumerate(list, start_number) is perfect for this
            for i, (name, _) in enumerate(presets, 3):
                print(f"{i}. Preset: {name}")

            print("0. Back to Main Menu")

            choice = await self.get_input(">> ")

            if choice == "0":
                buzzer.stop()
                buzzer.buzzer.deinit()
                break

            elif choice == "1":
                print("Playing 440Hz...")
                buzzer.tone(440, 1.0)

            elif choice == "2":
                print("Playing Scale...")
                scale = [
                    ('C4', 0.2), ('D4', 0.2), ('E4', 0.2), ('F4', 0.2),
                    ('G4', 0.2), ('A4', 0.2), ('B4', 0.2), ('C5', 0.4)
                ]
                buzzer.play_song({'sequence': scale, 'bpm': 120})

            else:
                # 3. Handle Dynamic Selection
                try:
                    # Convert input to integer
                    idx = int(choice)

                    # Check if it matches a preset (offset by 3)
                    preset_index = idx - 3

                    if 0 <= preset_index < len(presets):
                        name, data = presets[preset_index]
                        print(f"Playing {name}...")
                        buzzer.play_song(data)
                    else:
                        print("Invalid selection.")

                except ValueError:
                    print("Please enter a number.")

        print("Buzzer Test Exit.")

    async def test_i2c_scan(self):
        """Test the I2C bus by scanning for devices and printing their addresses."""
        print("\n--- I2C SCAN ---")
        try:
            i2c = busio.I2C(Pins.I2C_SCL, Pins.I2C_SDA) # SCL, SDA
            while not i2c.try_lock():
                pass

            print("Scanning I2C bus...")
            devices = []
            try:
                devices = i2c.scan()
            except Exception as e:
                print(f"I2C Scan Error: {e}")
            finally:
                i2c.unlock()

            if len(devices) > 0:
                print("Devices found:", [hex(d) for d in devices])
                print("Common addresses:")
                print("- 0x20: MCP23017 (Expander)")
                print("- 0x3C: OLED Display")
            else:
                print("No I2C devices found.")

            i2c.deinit()
        except Exception as e:
            print(f"I2C Error: {e}")

        await asyncio.sleep(1)

    async def start(self):
        """Main loop for the Test Manager."""
        print("\n" + "="*30)
        print(" JEB HARDWARE DIAGNOSTICS ")
        print("="*30)

        while True:
            # Feed the hardware watchdog timer to prevent system reset
            microcontroller.watchdog.feed()

            print("\n[MAIN MENU]")
            print("1. Test Buzzer (GP10)")
            print("2. I2C Bus Scan (GP4/5)")
            print("R. Reboot")

            choice = await self.get_input("Select Option >> ")

            if choice == "1":
                await self.test_buzzer()
            elif choice == "2":
                await self.test_i2c_scan()
            elif choice.upper() == "R":
                supervisor.reload()
            else:
                print("Invalid selection.")
