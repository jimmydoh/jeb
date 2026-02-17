import sys
import os

# 1. PATH INJECTION: Force Python to treat the 'src' folder as the root directory
# This allows all absolute imports inside the JEB codebase (e.g., 'from managers.matrix_manager')
# to resolve perfectly on the PC.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR) # insert(0) ensures 'src' takes priority over system packages

# 1. IMPORT YOUR MOCKS FIRST!
# This MUST happen before importing any real JEB code so sys.modules is patched
import jeb_emulator
from jeb_emulator import HardwareMocks, MockKeypadEvent

# 2. IMPORT THE REAL CODE
import asyncio
import math
import pygame
from core.core_manager import CoreManager
from satellites.sat_01_firmware import IndustrialSatelliteFirmware
from utilities.logger import JEBLogger, LogLevel

JEBLogger.set_level(LogLevel.DEBUG)
JEBLogger.enable_file_logging(False)

# ==========================================
# UART WIRETAP (Monkey Patching)
# ==========================================
from transport.uart_transport import UARTTransport

# 1. Save the original, un-modified transmit method
# (If your method is called 'send', 'transmit', or 'send_message', update this!)
original_transmit = UARTTransport.send

# 2. Create our Wiretap function
# NOTE: If your real send method uses 'async def', make this 'async def' and 'await' the original call!
def spy_transmit(self, message):
    # Adjust these attribute names to match your actual transport/message.py class properties
    src = getattr(message, 'source', 'Unknown')
    dest = getattr(message, 'destination', 'Unknown')
    cmd = getattr(message, 'command', 'Unknown')
    payload = getattr(message, 'payload', '')

    suppressed_commands = [
        "SYNC_FRAME",
        "STATUS",
        "POWER"
    ]

    if cmd not in suppressed_commands:
        # Format a beautiful console log
        JEBLogger.info("UART", f"{src:<4}➔ {dest:<4} | CMD:{cmd:<10} | DATA:{payload}", src="EMUL")

    # 3. Pass it along to the real transport layer so it still gets sent!
    return original_transmit(self, message)

# 4. Hijack the class! Every time ANY transport tries to send, it hits our spy first.
UARTTransport.send = spy_transmit

async def run_hardware_spy_loop(core, satellite, screen):
    """
    This Pygame loop runs in the background. Instead of mocking the managers,
    it looks at the REAL CoreManager's state and draws it to the screen.
    """
    # Initialize Pygame fonts
    pygame.font.init()
    oled_font = pygame.font.SysFont("courier", 12, bold=True)

    # ==========================================
    # UI LAYOUT CONSTANTS (900x600 Widescreen)
    # ==========================================
    WINDOW_SIZE_W = 900
    WINDOW_SIZE_H = 600

    # SATELLITE (Type 01 - Right Side)
    SAT_X = 620
    SAT_Y = 20
    SAT_W = 260
    SAT_H = 560

    # OLED (Top Right)
    OLED_W, OLED_H = 256, 128
    OLED_X = WINDOW_SIZE_W - SAT_W - OLED_W - 20
    OLED_Y = 20

    # MATRIX (Centered vertically/horizontally)
    CELL_SIZE = 36
    MATRIX_SIZE = 8 * CELL_SIZE
    MATRIX_X = (WINDOW_SIZE_W - SAT_W - MATRIX_SIZE) // 2
    MATRIX_Y = 160

    # BUTTONS / LEDS (Bottom Center, under matrix)
    BTN_Y = 510
    BTN_RADIUS = 26
    BTN_SPACING = MATRIX_SIZE // 4
    # Calculate 4 centers evenly spaced under the matrix
    BTN_CENTERS = [(MATRIX_X + (BTN_SPACING // 2) + (i * BTN_SPACING), BTN_Y) for i in range(4)]

    # ENCODER (Bottom Right)
    ENC_X = WINDOW_SIZE_W - SAT_W - 70
    ENC_Y = 510
    ENC_RADIUS = 35

    # 4 Toggle Switches at the bottom of the satellite
    SAT_TOGGLE_CENTERS = [(SAT_X + 40 + i*60, SAT_Y + 450) for i in range(4)]

    while True:
        try:
            # ==========================================
            # 1. INPUT HANDLING (Keyboard & Mouse)
            # ==========================================
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                # --- MOUSE CLICKS (Interactive UI) ---
                if (event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.MOUSEBUTTONUP):
                    if event.button == 4 or event.button == 5:
                        # Let the MOUSEWHEEL event handle encoder rotation
                        continue
                    # Only listen for left click
                    elif event.button == 1:
                        is_pressed = (event.type == pygame.MOUSEBUTTONDOWN)
                        mx, my = event.pos

                        # Check Arcade Buttons (0-3)
                        for i, (bx, by) in enumerate(BTN_CENTERS):
                            if (mx - bx)**2 + (my - by)**2 <= BTN_RADIUS**2:
                                core_mcp = HardwareMocks.get("CORE", "mcp")
                                core_mcp_int = HardwareMocks.get("CORE", "mcp_int")

                                if core_mcp:
                                    core_mcp.get_pin(i).value = not is_pressed
                                    if core_mcp_int:
                                        core_mcp_int.value = False # Trigger Interrupt!

                        # Check Encoder Push
                        if (mx - ENC_X)**2 + (my - ENC_Y)**2 <= ENC_RADIUS**2:
                            if HardwareMocks.get("CORE", "encoder_btn"):
                                JEBLogger.note("CORE", f"Encoder Button {'Pressed' if is_pressed else 'Released'}", src="EMUL")
                                HardwareMocks.get("CORE", "encoder_btn").events.queue.append(
                                    MockKeypadEvent(key_number=0, pressed=is_pressed, released=not is_pressed)
                                )
                                JEBLogger.note("CORE", f"Encoder Button Queue: {HardwareMocks.get('CORE', 'encoder_btn').events.queue}", src="EMUL")

                        # ==================================================
                        # SATELLITE TYPE 01 INPUTS
                        # ==================================================
                        # Fetch the mocks from the SAT_01 context sandbox
                        sat_mcp = HardwareMocks.get("SAT_01", "mcp")
                        sat_mcp_int = HardwareMocks.get("SAT_01", "mcp_int")
                        sat_keypad = HardwareMocks.get("SAT_01", "matrix_keypad")
                        sat_encoder_btn = HardwareMocks.get("SAT_01", "encoder_btn")

                        # 1. Satellite Keypad (3x4)
                        if sat_keypad:
                            for r in range(4):
                                for c in range(3):
                                    kx, ky = SAT_X + 55 + c*75, SAT_Y + 140 + r*45
                                    if (mx - kx)**2 + (my - ky)**2 <= 20**2:
                                        key_idx = r * 3 + c
                                        sat_keypad.events.queue.append(
                                            MockKeypadEvent(key_number=key_idx, pressed=is_pressed, released=not is_pressed)
                                        )
                                        # [NEW] Diagnostic Prints!
                                        #JEBLogger.warning("KEYP", f"🖱️ Pygame queued Key {key_idx} (Pressed: {is_pressed})", src="EMUL")
                                        #JEBLogger.warning("KEYP", f"📦 Keypad Queue Size: {len(sat_keypad.events.queue)}", src="EMUL")

                        # 2. Satellite Encoder Push
                        SAT_ENC_X, SAT_ENC_Y = SAT_X + 110, SAT_Y + 480
                        if (mx - SAT_ENC_X)**2 + (my - SAT_ENC_Y)**2 <= 30**2:
                            if sat_encoder_btn:
                                sat_encoder_btn.events.queue.append(
                                    MockKeypadEvent(key_number=0, pressed=is_pressed, released=not is_pressed)
                                )

                        # 3. Satellite Latching Toggles (Click to flip)
                        if event.type == pygame.MOUSEBUTTONDOWN and sat_mcp:
                            for i in range(4):
                                tx, ty = SAT_X + 40 + i*60, SAT_Y + 70
                                if (mx - tx)**2 + (my - ty)**2 <= 25**2:
                                    pin = sat_mcp.get_pin(i) # Assuming pins 0-3 are latching
                                    pin.value = not pin.value
                                    if sat_mcp_int:
                                        sat_mcp_int.value = False # FIRE INTERRUPT!

                        # 4. Satellite Momentary Toggle (ON-OFF-ON)
                        MOM_X, MOM_Y = SAT_X + 210, SAT_Y + 480
                        if sat_mcp:
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                if (mx - MOM_X)**2 + (my - (MOM_Y - 20))**2 <= 20**2:
                                    sat_mcp.get_pin(4).value = False # Pushed UP (Active Low)
                                    if sat_mcp_int: sat_mcp_int.value = False
                                elif (mx - MOM_X)**2 + (my - (MOM_Y + 20))**2 <= 20**2:
                                    sat_mcp.get_pin(5).value = False # Pushed DOWN (Active Low)
                                    if sat_mcp_int: sat_mcp_int.value = False
                            elif event.type == pygame.MOUSEBUTTONUP:
                                # SPRING RETURN: If either pin is currently held down, snap them back to True!
                                if not sat_mcp.get_pin(4).value or not sat_mcp.get_pin(5).value:
                                    sat_mcp.get_pin(4).value = True
                                    sat_mcp.get_pin(5).value = True
                                    if sat_mcp_int:
                                        sat_mcp_int.value = False # FIRE INTERRUPT ON RELEASE!

                # --- MOUSE WHEEL (Interactive Encoder) ---
                elif event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    step_multiplier = 1
                    if mx < 600: # Left side (Core Encoder)
                        if HardwareMocks.get("CORE", "encoder"):
                            HardwareMocks.get("CORE", "encoder").position += (event.y * step_multiplier)
                    else: # Right side (Satellite Encoder)
                        if HardwareMocks.get("SAT_01", "encoder") and HardwareMocks.get("SAT_01", "encoder"):
                            HardwareMocks.get("SAT_01", "encoder").position += (event.y * step_multiplier)

                # --- KEYBOARD FALLBACK ---
                elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                    is_pressed = (event.type == pygame.KEYDOWN)

                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_LEFT and HardwareMocks.get("CORE", "encoder"):
                            HardwareMocks.get("CORE", "encoder").position -= 1
                        elif event.key == pygame.K_RIGHT and HardwareMocks.get("CORE", "encoder"):
                            HardwareMocks.get("CORE", "encoder").position += 1

                    # Encoder Push
                    if event.key == pygame.K_RETURN and HardwareMocks.get("CORE", "encoder_btn"):
                        HardwareMocks.get("CORE", "encoder_btn").events.queue.append(
                            MockKeypadEvent(key_number=0, pressed=is_pressed, released=not is_pressed)
                        )
                    # Main Buttons
                    key_map = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3}
                    if event.key in key_map and HardwareMocks.get("CORE", "mcp"):
                        idx = key_map[event.key]
                        HardwareMocks.get("CORE", "mcp").get_pin(idx).value = not is_pressed
                        if HardwareMocks.get("CORE", "mcp_int"):
                            HardwareMocks.get("CORE", "mcp_int").value = False

                    # [NEW] Hot-Plug Toggle
                    if event.key == pygame.K_p and is_pressed:
                        HardwareMocks.satellite_plugged_in = not HardwareMocks.satellite_plugged_in

                        satbus_detect = HardwareMocks.get("CORE", "satbus_detect_pin")
                        if satbus_detect:
                            # Pull the pin to Ground to simulate the physical connection
                            satbus_detect.value = not HardwareMocks.satellite_plugged_in

                            if HardwareMocks.satellite_plugged_in:
                                JEBLogger.note("EMUL", ">>> PHYSICAL ACTION: SATELLITE CABLE PLUGGED IN >>>", src="EMUL")
                            else:
                                JEBLogger.note("EMUL", "<<< PHYSICAL ACTION: SATELLITE CABLE UNPLUGGED <<<", src="EMUL")

            # ==========================================
            # 2. RENDERING
            # ==========================================
            screen.fill((30, 32, 40)) # Dark sleek enclosure background

            # --- SPY: OLED DISPLAY ---
            oled_rect = pygame.Rect(OLED_X, OLED_Y, OLED_W, OLED_H)
            pygame.draw.rect(screen, (10, 10, 12), oled_rect)
            pygame.draw.rect(screen, (80, 80, 90), oled_rect, 2) # Bezel

            if hasattr(core, 'display') and core.display and hasattr(core.display, 'root'):
                # 1. APPLY CLIPPING MASK (Nothing draws outside the OLED box)
                screen.set_clip(oled_rect)

                def render_display_tree(element, base_x, base_y):
                    if hasattr(element, 'hidden') and element.hidden: return
                    ex = getattr(element, 'x', 0)
                    ey = getattr(element, 'y', 0)

                    if hasattr(element, '_items'):
                        for child in element._items:
                            render_display_tree(child, base_x + ex, base_y + ey)
                    elif hasattr(element, 'text') and element.text:
                        screen_x = OLED_X + (base_x + ex) * 2
                        screen_y = OLED_Y + (base_y + ey - 4) * 2

                        # REMOVED the [:21] truncation so the full text can slide!
                        text_surface = oled_font.render(str(element.text), True, (150, 220, 255))
                        screen.blit(text_surface, (screen_x, screen_y))

                render_display_tree(core.display.root, 0, 0)

                # 2. REMOVE CLIPPING MASK (So the matrix/buttons can draw normally)
                screen.set_clip(None)

            # --- SPY: MATRIX MANAGER ---
            if hasattr(core, 'matrix') and core.matrix:
                for y in range(8):
                    for x in range(8):
                        idx = core.matrix._get_idx(x, y)
                        color = core.matrix.pixels[idx]
                        rect = (MATRIX_X + (x * CELL_SIZE), MATRIX_Y + (y * CELL_SIZE), CELL_SIZE - 2, CELL_SIZE - 2)

                        try:
                            safe_color = tuple(max(0, min(255, int(c))) for c in color)
                        except TypeError:
                            safe_color = (0, 0, 0)

                        pygame.draw.rect(screen, safe_color, rect)

            # --- SPY: LED MANAGER (Illuminated Buttons) ---
            # Handle either 'leds' or 'led' depending on your core attribute
            led_manager = getattr(core, 'leds', getattr(core, 'led', None))

            for i, (bx, by) in enumerate(BTN_CENTERS):
                btn_color = (50, 50, 50) # Unlit base color

                # Read real hardware LED state
                if led_manager and i < len(led_manager.pixels):
                    try:
                        r, g, b = [max(0, min(255, int(c))) for c in led_manager.pixels[i]]
                        if r > 0 or g > 0 or b > 0:
                            btn_color = (r, g, b)
                    except TypeError:
                        pass

                # Draw physical button
                pygame.draw.circle(screen, (20, 20, 20), (bx, by), BTN_RADIUS + 4) # Outer bezel
                pygame.draw.circle(screen, btn_color, (bx, by), BTN_RADIUS)        # Lit dome

                # Draw label Q, W, E, R
                txt_color = (255, 255, 255) if btn_color == (50, 50, 50) else (0, 0, 0)
                lbl = oled_font.render(["Q", "W", "E", "R"][i], True, txt_color)
                screen.blit(lbl, (bx - 5, by - 8))

            # --- SPY: ROTARY ENCODER ---
            pygame.draw.circle(screen, (20, 20, 20), (ENC_X, ENC_Y), ENC_RADIUS + 6) # Base Bezel
            pygame.draw.circle(screen, (70, 70, 75), (ENC_X, ENC_Y), ENC_RADIUS)     # Aluminum Knob

            # Visual rotation indicator
            if HardwareMocks.get("CORE", "encoder"):
                # Map position to a 360 degree angle
                angle = (HardwareMocks.get("CORE", "encoder").position * 18) % 360
                rad = math.radians(angle - 90) # -90 puts 0 at the top
                ix = ENC_X + math.cos(rad) * (ENC_RADIUS - 10)
                iy = ENC_Y + math.sin(rad) * (ENC_RADIUS - 10)
                pygame.draw.line(screen, (255, 100, 100), (ENC_X, ENC_Y), (ix, iy), 4)

            # ==========================================
            # --- SPY: TYPE 01 INDUSTRIAL SATELLITE ---
            # ==========================================
            # Add a helpful prompt on screen
            plug_text = "Press 'P' to Unplug Satellite" if HardwareMocks.satellite_plugged_in else "Press 'P' to Plug In Satellite"
            prompt_surf = oled_font.render(plug_text, True, (100, 100, 100))
            screen.blit(prompt_surf, (SAT_X, 10))

            if HardwareMocks.satellite_plugged_in:
                # Simulate Power Loss (Overrides graphics if MOSFET is off)
                is_powered = HardwareMocks.get("CORE", "satbus_mosfet_pin", None) and HardwareMocks.get("CORE", "satbus_mosfet_pin").value
                if not is_powered:
                    JEBLogger.warning("EMUL", "⚡ SAT_01 POWER LOST ⚡ - MOSFET is OFF, simulating blackout!", src="EMUL")
                    # Force hardware buffers to empty so they render dark
                    if HardwareMocks.get("SAT_01", "pixels"):
                        HardwareMocks.get("SAT_01", "pixels").fill((0,0,0))

                # Industrial Yellow Chassis
                pygame.draw.rect(screen, (220, 180, 40), (SAT_X, SAT_Y, SAT_W, SAT_H), border_radius=10)
                pygame.draw.rect(screen, (100, 80, 20), (SAT_X, SAT_Y, SAT_W, SAT_H), 4, border_radius=10)

                # 1. TOP: LATCHING TOGGLES
                for i in range(4):
                    tx, ty = SAT_X + 40 + i*60, SAT_Y + 70

                    # Read simulated electrical state
                    state = True
                    if HardwareMocks.get("SAT_01", "mcp"):
                        state = HardwareMocks.get("SAT_01", "mcp").peek_pin(i).value

                    # Switch Base
                    pygame.draw.rect(screen, (80, 80, 80), (tx-15, ty-25, 30, 50), border_radius=4)
                    pygame.draw.rect(screen, (40, 40, 40), (tx-15, ty-25, 30, 50), 2, border_radius=4)

                    # Switch Bat Angle
                    if state: # UP
                        pygame.draw.rect(screen, (180, 180, 180), (tx-6, ty-25, 12, 28), border_radius=3)
                        pygame.draw.circle(screen, (150, 150, 150), (tx, ty-25), 6)
                    else:     # DOWN
                        pygame.draw.rect(screen, (120, 120, 120), (tx-6, ty, 12, 28), border_radius=3)
                        pygame.draw.circle(screen, (90, 90, 90), (tx, ty+28), 6)

                # ==========================================
                # RENDER SAT 01 LEDs
                # ==========================================
                sat_pixels = HardwareMocks.get("SAT_01", "pixels")
                
                if sat_pixels:
                    led_y = SAT_Y + 25
                    for i in range(4):
                        tx = SAT_X + 40 + i * 60 
                        
                        # Draw outer Bezel
                        pygame.draw.circle(screen, (30, 30, 30), (tx, led_y), 12) 
                        
                        try:
                            color = sat_pixels[i] 
                            
                            # Handle hex integers just in case
                            if isinstance(color, int):
                                r = (color >> 16) & 0xFF
                                g = (color >> 8) & 0xFF
                                b = color & 0xFF
                                color = (r, g, b)
                                
                            safe_color = tuple(max(0, min(255, int(c))) for c in color[:3])
                            
                            # If the color is lit (>0), draw the glowing dome
                            if any(c > 0 for c in safe_color):
                                pygame.draw.circle(screen, safe_color, (tx, led_y), 9)
                            else:
                                pygame.draw.circle(screen, (10, 10, 10), (tx, led_y), 9)
                                
                        except Exception as e:
                            print(f"⚠️ [EMULATOR] LED Render Error on SAT_01 LED {i}: {e}")

                # 2. MIDDLE: KEYPAD (3x4)
                KEYPAD_LABELS = ['1','2','3','4','5','6','7','8','9','*','0','#']
                for r in range(4):
                    for c in range(3):
                        kx, ky = SAT_X + 55 + c*75, SAT_Y + 140 + r*45
                        # Button Bezel and Dome
                        pygame.draw.circle(screen, (30, 30, 30), (kx, ky), 22)
                        pygame.draw.circle(screen, (180, 180, 180), (kx, ky), 20)

                        # Key Text
                        idx = r * 3 + c
                        lbl = oled_font.render(KEYPAD_LABELS[idx], True, (0, 0, 0))
                        lbl_rect = lbl.get_rect(center=(kx, ky))
                        screen.blit(lbl, lbl_rect)

                # 3. LOWER-MIDDLE: SEGMENT DISPLAYS
                if HardwareMocks.get("SAT_01", "segments", key=0x70) and HardwareMocks.get("SAT_01", "segments", key=0x71):
                    seg_font = pygame.font.SysFont("courier", 32, bold=True)
                    left_display = HardwareMocks.get("SAT_01", "segments", key=0x71)
                    right_display = HardwareMocks.get("SAT_01", "segments", key=0x70)

                    full_text = "".join(left_display.chars) if left_display else "    "
                    full_text += "".join(right_display.chars) if right_display else "    "

                    SEG_X, SEG_Y = SAT_X + 20, SAT_Y + 340
                    SEG_W, SEG_H = 220, 60
                    pygame.draw.rect(screen, (15, 5, 5), (SEG_X, SEG_Y, SEG_W, SEG_H))
                    pygame.draw.rect(screen, (40, 10, 10), (SEG_X, SEG_Y, SEG_W, SEG_H), 2)

                    text_surface = seg_font.render(full_text, True, (255, 40, 40))
                    text_rect = text_surface.get_rect(center=(SEG_X + SEG_W//2, SEG_Y + SEG_H//2))
                    screen.blit(text_surface, text_rect)

                # 4. BOTTOM LEFT: ROTARY ENCODER
                SAT_ENC_X, SAT_ENC_Y = SAT_X + 110, SAT_Y + 480
                pygame.draw.circle(screen, (20, 20, 20), (SAT_ENC_X, SAT_ENC_Y), 35) # Base Bezel
                pygame.draw.circle(screen, (70, 70, 75), (SAT_ENC_X, SAT_ENC_Y), 30) # Knob

                # Dial Position indicator
                if HardwareMocks.get("SAT_01", "encoder"):
                    angle = (HardwareMocks.get("SAT_01", "encoder").position * 18) % 360
                    rad = math.radians(angle - 90)
                    ix = SAT_ENC_X + math.cos(rad) * 25
                    iy = SAT_ENC_Y + math.sin(rad) * 25
                    pygame.draw.line(screen, (255, 100, 100), (SAT_ENC_X, SAT_ENC_Y), (ix, iy), 4)

                # 5. BOTTOM RIGHT: MOMENTARY TOGGLE (ON-OFF-ON)
                MOM_X, MOM_Y = SAT_X + 210, SAT_Y + 480
                pygame.draw.rect(screen, (80, 80, 80), (MOM_X-15, MOM_Y-25, 30, 50), border_radius=4)
                pygame.draw.rect(screen, (40, 40, 40), (MOM_X-15, MOM_Y-25, 30, 50), 2, border_radius=4)

                state_up = True
                state_down = True
                if HardwareMocks.get("SAT_01", "mcp"):
                    # Assumes Pins 4 and 5 are the momentary inputs
                    state_up = HardwareMocks.get("SAT_01", "mcp").peek_pin(4).value
                    state_down = HardwareMocks.get("SAT_01", "mcp").peek_pin(5).value

                if not state_up: # Pushed UP
                    pygame.draw.rect(screen, (180, 180, 180), (MOM_X-6, MOM_Y-25, 12, 28), border_radius=3)
                    pygame.draw.circle(screen, (150, 150, 150), (MOM_X, MOM_Y-25), 6)
                elif not state_down: # Pushed DOWN
                    pygame.draw.rect(screen, (120, 120, 120), (MOM_X-6, MOM_Y, 12, 28), border_radius=3)
                    pygame.draw.circle(screen, (90, 90, 90), (MOM_X, MOM_Y+28), 6)
                else: # Centered (Spring returned)
                    pygame.draw.rect(screen, (150, 150, 150), (MOM_X-6, MOM_Y-12, 12, 24), border_radius=3)
                    pygame.draw.circle(screen, (130, 130, 130), (MOM_X, MOM_Y), 6)

            pygame.display.flip()
            await asyncio.sleep(0.016) # ~60 FPS
        except Exception as e:
            JEBLogger.error("EMUL", f"Error in render loop: {e}", src="EMUL")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(1) # Pause to prevent spamming errors

async def main():
    pygame.init()
    # Update to the new square window size
    screen = pygame.display.set_mode((900, 600))
    pygame.display.set_caption("JEB Embedded Hardware Emulator")

    JEBLogger.note("CORE", " --- BOOTING CORE MANAGER --- ", src="EMUL")
    HardwareMocks.set_context("CORE")
    core = CoreManager()

    JEBLogger.note("SAT1", " --- BOOTING SAT TYPE 01 FIRMWARE --- ", src="EMUL")
    HardwareMocks.set_context("SAT_01")
    satellite = IndustrialSatelliteFirmware()

    JEBLogger.note("EMUL", " --- STARTING HARDWARE EMULATOR --- ", src="EMUL")
    try:
        await asyncio.gather(
            core.start(),
            satellite.start(),
            run_hardware_spy_loop(core, satellite, screen)
        )
    except Exception as e:
        JEBLogger.error("EMUL", f"System crashed: {e}", src="EMUL")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
