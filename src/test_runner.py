import asyncio

import board
import time
import sys
import supervisor
from utilities import tones

# Import Managers (Lazy import inside functions is also an option)
try:
    from managers.buzzer_manager import BuzzerManager
except ImportError:
    BuzzerManager = None

async def get_input(prompt):
    """Safe blocking input wrapper."""
    print(prompt, end="")
    while True:
        if supervisor.runtime.serial_bytes_available:
            return sys.stdin.readline().strip()
        await asyncio.sleep(0.05)

def get_tone_presets():
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

async def test_buzzer():
    print("\n--- BUZZER TEST ---")
    print("Initializing BuzzerManager on GP10...")
    
    try:
        buzzer = BuzzerManager(board.GP10, volume=0.5, testing=True)
    except Exception as e:
        print(f"FAILED to init buzzer: {e}")
        return

    # 1. Fetch the dynamic list once
    presets = get_tone_presets()

    while True:
        print("\n[Buzzer Menu]")
        print("1. Play Tone (440Hz)")
        print("2. Play Scale (C Major)")
        
        # 2. Dynamically print presets starting at index 3
        # enumerate(list, start_number) is perfect for this
        for i, (name, _) in enumerate(presets, 3):
            print(f"{i}. Preset: {name}")
            
        print("0. Back to Main Menu")
        
        choice = await get_input(">> ")
        
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

async def test_i2c_scan():
    print("\n--- I2C SCAN ---")
    import busio
    try:
        i2c = busio.I2C(board.GP5, board.GP4) # SCL, SDA
        while not i2c.try_lock():
            pass
        
        print("Scanning I2C bus...")
        devices = i2c.scan()
        i2c.unlock()
        
        if devices:
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

async def main_menu():
    print("\n" + "="*30)
    print(" JEB HARDWARE DIAGNOSTICS ")
    print("="*30)
    
    while True:
        print("\n[MAIN MENU]")
        print("1. Test Buzzer (GP10)")
        print("2. I2C Bus Scan (GP4/5)")
        print("3. Test Buttons (Coming Soon)")
        print("4. Test Screen (Coming Soon)")
        print("R. Reboot")
        
        choice = await get_input("Select Option >> ")
        
        if choice == "1":
            await test_buzzer()
        elif choice == "2":
            await test_i2c_scan()
        elif choice.upper() == "R":
            supervisor.reload()
        else:
            print("Invalid selection.")

async def run():
    asyncio.run(main_menu())