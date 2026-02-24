import sys
import os

# 1. PATH INJECTION: Force Python to treat the 'src' folder as the root directory
# This allows all absolute imports inside the JEB codebase (e.g., 'from managers.matrix_manager')
# to resolve perfectly on the PC.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
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
        "POWER",
        "PING"
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
    # UI LAYOUT CONSTANTS (1600x800 Widescreen)
    # ==========================================
    WINDOW_SIZE_W = 1600
    WINDOW_SIZE_H = 800

    # SATELLITE (Type 01 - Right Side)
    SAT_W = 760
    SAT_H = 680
    SAT_X = WINDOW_SIZE_W - SAT_W - 20
    SAT_Y = 20

    # OLED (Top Left)
    OLED_W, OLED_H = 256, 128
    OLED_X = 20
    OLED_Y = 20

    # MATRIX (Centered vertically/horizontally)
    CELL_SIZE = 24
    MATRIX_DIM_X = 16
    MATRIX_DIM_Y = 16
    TILE_GAP = 3

    # Calculate visual size including the center gap
    MATRIX_VISUAL_W = (16 * CELL_SIZE) + TILE_GAP
    MATRIX_X = (WINDOW_SIZE_W - SAT_W - MATRIX_VISUAL_W) // 2
    MATRIX_Y = 180

    # BUTTONS / LEDS (Bottom Center, under matrix)
    BTN_Y = MATRIX_Y + (16 * CELL_SIZE) + TILE_GAP + 60
    BTN_RADIUS = 26
    BTN_SPACING = MATRIX_VISUAL_W // 4
    BTN_CENTERS = [(MATRIX_X + (BTN_SPACING // 2) + (i * BTN_SPACING), BTN_Y) for i in range(4)]

    # ENCODER (To the right of buttons)
    ENC_X = MATRIX_X + MATRIX_VISUAL_W + 60
    ENC_Y = BTN_Y
    ENC_RADIUS = 35

    while True:
        try:
            # ==========================================
            # 1. INPUT HANDLING (Keyboard & Mouse)
            # ==========================================
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    for task in asyncio.all_tasks():
                        task.cancel()
                    return

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
                                    core_mcp.peek_pin(i).value = not is_pressed
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
                        # SATELLITE TYPE 01 INPUTS (QUADRANT LAYOUT)
                        # ==================================================
                        # Fetch the mocks from the SAT_01 context sandbox
                        sat_mcp = HardwareMocks.get("SAT_01", "mcp")
                        sat_mcp_int = HardwareMocks.get("SAT_01", "mcp_int")
                        sat_mcp2 = HardwareMocks.get("SAT_01", "mcp2")
                        sat_mcp2_int = HardwareMocks.get("SAT_01", "mcp2_int")
                        sat_keypad = HardwareMocks.get("SAT_01", "matrix_keypad")
                        sat_encoder_btn = HardwareMocks.get("SAT_01", "encoder_btn")

                        # --- QUADRANT 1 (Top Left): Latching Toggles ---
                        if event.type == pygame.MOUSEBUTTONDOWN and sat_mcp:
                            for i in range(8):
                                tx, ty = SAT_X + 60 + (i % 4)*80, SAT_Y + 110 + (i // 4)*120
                                if (mx - tx)**2 + (my - ty)**2 <= 25**2:
                                    pin = sat_mcp.peek_pin(i)
                                    pin.value = not pin.value
                                    JEBLogger.note("INPT", f"Toggle Pin {i} {'UP' if pin.value else 'DOWN'}", src="EMUL")
                                    if sat_mcp_int: sat_mcp_int.value = False # FIRE INTERRUPT!

                        # --- QUADRANT 2 (Top Right): Keypad ---
                        if sat_keypad:
                            for r in range(4):
                                for c in range(3):
                                    kx, ky = SAT_X + 460 + c*70, SAT_Y + 160 + r*60
                                    if (mx - kx)**2 + (my - ky)**2 <= 22**2:
                                        key_idx = r * 3 + c
                                        JEBLogger.note("INPT", f"Keypad Button {key_idx} {'Pressed' if is_pressed else 'Released'}", src="EMUL")
                                        sat_keypad.events.queue.append(
                                            MockKeypadEvent(key_number=key_idx, pressed=is_pressed, released=not is_pressed)
                                        )

                        # --- QUADRANT 3 (Bottom Left): Specials, Momentary, Big Button ---
                        if event.type == pygame.MOUSEBUTTONDOWN and sat_mcp2:
                            for j, pin_num in enumerate([2, 3, 4, 5]):
                                tx, ty = SAT_X + 60 + j*80, SAT_Y + 400
                                if (mx - tx)**2 + (my - ty)**2 <= 25**2:
                                    pin = sat_mcp2.peek_pin(pin_num)
                                    pin.value = not pin.value
                                    JEBLogger.note("INPT", f"Special Pin {pin_num} {'UP' if pin.value else 'DOWN'}", src="EMUL")
                                    if sat_mcp2_int: sat_mcp2_int.value = False

                        MOM_X, MOM_Y = SAT_X + 100, SAT_Y + 540
                        if sat_mcp2:
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                if (mx - MOM_X)**2 + (my - (MOM_Y - 20))**2 <= 20**2:
                                    sat_mcp2.peek_pin(0).value = False # Pushed UP
                                    JEBLogger.note("INPT", f"Momentary UP", src="EMUL")
                                    if sat_mcp2_int: sat_mcp2_int.value = False
                                elif (mx - MOM_X)**2 + (my - (MOM_Y + 20))**2 <= 20**2:
                                    sat_mcp2.peek_pin(1).value = False # Pushed DOWN
                                    JEBLogger.note("INPT", f"Momentary DOWN", src="EMUL")
                                    if sat_mcp2_int: sat_mcp2_int.value = False
                            elif event.type == pygame.MOUSEBUTTONUP:
                                if not sat_mcp2.peek_pin(0).value or not sat_mcp2.peek_pin(1).value:
                                    sat_mcp2.peek_pin(0).value = True
                                    sat_mcp2.peek_pin(1).value = True
                                    JEBLogger.note("INPT", f"Momentary CENTER", src="EMUL")
                                    if sat_mcp2_int: sat_mcp2_int.value = False

                        BIG_BTN_X, BIG_BTN_Y = SAT_X + 260, SAT_Y + 540
                        if sat_mcp2:
                            if event.type == pygame.MOUSEBUTTONDOWN:
                                if (mx - BIG_BTN_X)**2 + (my - BIG_BTN_Y)**2 <= 34**2:
                                    sat_mcp2.peek_pin(6).value = False
                                    JEBLogger.note("INPT", f"Big Button Pressed", src="EMUL")
                                    if sat_mcp2_int: sat_mcp2_int.value = False
                            elif event.type == pygame.MOUSEBUTTONUP:
                                if not sat_mcp2.peek_pin(6).value:
                                    sat_mcp2.peek_pin(6).value = True
                                    JEBLogger.note("INPT", f"Big Button Released", src="EMUL")
                                    if sat_mcp2_int: sat_mcp2_int.value = False

                        # --- QUADRANT 4 (Bottom Right): Rotary Encoder ---
                        SAT_ENC_X, SAT_ENC_Y = SAT_X + 560, SAT_Y + 500
                        if (mx - SAT_ENC_X)**2 + (my - SAT_ENC_Y)**2 <= 35**2:
                            if sat_encoder_btn:
                                JEBLogger.note("INPT", f"Rotary Encoder Button {'Pressed' if is_pressed else 'Released'}", src="EMUL")
                                sat_encoder_btn.events.queue.append(
                                    MockKeypadEvent(key_number=0, pressed=is_pressed, released=not is_pressed)
                                )

                # --- MOUSE WHEEL (Interactive Encoder) ---
                elif event.type == pygame.MOUSEWHEEL:
                    mx, my = pygame.mouse.get_pos()
                    if mx < (WINDOW_SIZE_W - SAT_W): # Left side (Core Encoder)
                        if HardwareMocks.get("CORE", "encoder"):
                            HardwareMocks.get("CORE", "encoder").position += 1 if event.y > 0 else -1
                    else: # Right side (Satellite Encoder)
                        if HardwareMocks.get("SAT_01", "encoder") and HardwareMocks.get("SAT_01", "encoder"):
                            HardwareMocks.get("SAT_01", "encoder").position += 1 if event.y > 0 else -1

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
                        HardwareMocks.get("CORE", "mcp").peek_pin(idx).value = not is_pressed
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

                    # [NEW] ADC Voltage Manipulation for Testing
                    # Simulate Native ADC voltage drop (for native analogio-based power monitoring)
                    if event.key == pygame.K_v and is_pressed:
                        # Try to simulate a brownout on native ADC pin (typically board.GP26)
                        native_pin = HardwareMocks.get("CORE", "analog_pin", "board.GP26")
                        if native_pin:
                            native_pin.value = 10000  # Drop voltage significantly (~0.5V)
                            JEBLogger.warning("EMUL", "⚡ SIMULATED VOLTAGE DROP (Native ADC GP26) -> 10000 (~0.5V)", src="EMUL")
                        else:
                            JEBLogger.note("EMUL", "No native analog pin found at GP26", src="EMUL")

                    # Restore Native ADC voltage
                    if event.key == pygame.K_b and is_pressed:
                        native_pin = HardwareMocks.get("CORE", "analog_pin", "board.GP26")
                        if native_pin:
                            native_pin.value = 49650  # Restore to healthy ~2.5V
                            JEBLogger.note("EMUL", "✅ RESTORED VOLTAGE (Native ADC GP26) -> 49650 (~2.5V)", src="EMUL")

                    # Simulate I2C ADC voltage drop (for ADS1115-based power monitoring)
                    if event.key == pygame.K_n and is_pressed:
                        # Try to drop voltage on I2C ADC channel P0
                        i2c_pin = HardwareMocks.get("CORE", "ads_channel", 0)  # 0 is P0
                        if i2c_pin:
                            i2c_pin.voltage = 0.5  # Drop directly to 0.5V
                            JEBLogger.warning("EMUL", "⚡ SIMULATED VOLTAGE DROP (I2C ADC P0) -> 0.5V", src="EMUL")
                        else:
                            JEBLogger.note("EMUL", "No I2C ADC channel found at P0", src="EMUL")

                    # Restore I2C ADC voltage
                    if event.key == pygame.K_m and is_pressed:
                        i2c_pin = HardwareMocks.get("CORE", "ads_channel", 0)
                        if i2c_pin:
                            i2c_pin.voltage = 2.5  # Restore to healthy 2.5V
                            JEBLogger.note("EMUL", "✅ RESTORED VOLTAGE (I2C ADC P0) -> 2.5V", src="EMUL")


            # ==========================================
            # 2. RENDERING
            # ==========================================
            screen.fill((30, 32, 40)) # Dark sleek enclosure background

            # --- HELP TEXT (Top Left) ---
            help_lines = [
                "Keyboard Controls:",
                "V/B - Native ADC: Drop/Restore voltage",
                "N/M - I2C ADC: Drop/Restore voltage",
                "P - Toggle satellite connection"
            ]
            help_font = pygame.font.SysFont("Courier", 12)
            for i, line in enumerate(help_lines):
                help_surf = help_font.render(line, True, (80, 80, 80))
                screen.blit(help_surf, (10, WINDOW_SIZE_H - 30 - i*15))

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

                    elif hasattr(element, 'text') and element.text != "":
                        screen_x = OLED_X + (base_x + ex) * 2
                        screen_y = OLED_Y + (base_y + ey - 4) * 2

                        # Handle Custom Colors and Backgrounds (for Settings Menu)
                        t_color = getattr(element, 'color', 0xFFFFFF)
                        bg_color = getattr(element, 'background_color', None)

                        # Translate to emulator OLED colors
                        def hex_to_rgb(hex_val, is_bg=False):
                            if hex_val == 0xFFFFFF:
                                return (150, 220, 255) # Classic JEB Emulator blue
                            elif hex_val == 0x000000:
                                return (10, 10, 12)    # OLED background color
                            return ((hex_val >> 16) & 0xFF, (hex_val >> 8) & 0xFF, hex_val & 0xFF)

                        text_rgb = hex_to_rgb(t_color)

                        text_surface = oled_font.render(str(element.text), True, text_rgb)

                        if bg_color is not None:
                            bg_rgb = hex_to_rgb(bg_color, is_bg=True)
                            text_w, text_h = text_surface.get_size()
                            # Draw a background rectangle slightly padded
                            pygame.draw.rect(screen, bg_rgb, (screen_x - 2, screen_y, text_w + 4, text_h))

                        screen.blit(text_surface, (screen_x, screen_y))

                    elif hasattr(element, 'bitmap'):
                        # Render TileGrid Bitmaps (for Audio Visualizer)
                        bmp = element.bitmap
                        palette = getattr(element, 'pixel_shader', None)

                        # Optimization: Only draw pixels that are active (val > 0)
                        for y in range(bmp.height):
                            for x in range(bmp.width):
                                val = bmp[x, y]
                                if val > 0:
                                    # Default to emulator blue if palette mapping fails
                                    color_rgb = (150, 220, 255)
                                    if palette:
                                        raw_hex = palette[val]
                                        if raw_hex == 0xFFFFFF:
                                            color_rgb = (150, 220, 255)
                                        else:
                                            color_rgb = ((raw_hex >> 16) & 0xFF, (raw_hex >> 8) & 0xFF, raw_hex & 0xFF)

                                    # Scale 1x1 pixels to 2x2 blocks for the emulator OLED view
                                    rect_x = OLED_X + (base_x + ex + x) * 2
                                    rect_y = OLED_Y + (base_y + ey + y) * 2
                                    pygame.draw.rect(screen, color_rgb, (rect_x, rect_y, 2, 2))

                render_display_tree(core.display.root, 0, 0)

                # 2. REMOVE CLIPPING MASK (So the matrix/buttons can draw normally)
                screen.set_clip(None)

            # --- SPY: 16x16 MATRIX RENDERER ---
            # Draws four 8x8 quadrants with a gap
            if hasattr(core, 'matrix') and core.matrix:
                # Background container
                bg_rect = (MATRIX_X - 10, MATRIX_Y - 10, MATRIX_VISUAL_W + 20, MATRIX_VISUAL_W + 20)
                pygame.draw.rect(screen, (10, 10, 15), bg_rect, border_radius=5)

                # [CHANGE] Iterate 0-15 for both axes
                for y in range(16):
                    for x in range(16):
                        # Get Color from firmware
                        # We use the public _get_idx logic to fetch the specific pixel index
                        # corresponding to this logical X/Y
                        idx = core.matrix._get_idx(x, y)

                        try:
                            # Safely handle list length in case resize hasn't propagated
                            if idx < len(core.matrix.pixels):
                                color = core.matrix.pixels[idx]
                            else:
                                color = (0,0,0) # Out of bounds
                        except:
                            color = (0,0,0)

                        # [CHANGE] Calculate Visual Position (With Tiled Gaps)
                        x_offset = 0 if x < 8 else TILE_GAP
                        y_offset = 0 if y < 8 else TILE_GAP

                        rect_x = MATRIX_X + (x * CELL_SIZE) + x_offset
                        rect_y = MATRIX_Y + (y * CELL_SIZE) + y_offset

                        rect = (rect_x, rect_y, CELL_SIZE - 2, CELL_SIZE - 2)

                        safe_color = tuple(max(0, min(255, int(c))) for c in color)

                        # Draw faint outline for unlit pixels
                        if safe_color == (0,0,0):
                            pygame.draw.rect(screen, (25, 25, 30), rect, 1)
                        else:
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

            if HardwareMocks.satellite_plugged_in:
                # Simulate Power Loss (Overrides graphics if MOSFET is off)
                is_powered = HardwareMocks.get("CORE", "satbus_mosfet_pin", None) and HardwareMocks.get("CORE", "satbus_mosfet_pin").value
                if not is_powered:
                    JEBLogger.warning("EMUL", "⚡ SAT_01 POWER LOST ⚡ - MOSFET is OFF, simulating blackout!", src="EMUL")
                    if HardwareMocks.get("SAT_01", "pixels"):
                        HardwareMocks.get("SAT_01", "pixels").fill((0,0,0))

                # ==========================================
                # INDUSTRIAL YELLOW CHASSIS BOX
                # ==========================================
                # This draws the background box to separate the Sat from the Core
                pygame.draw.rect(screen, (220, 180, 40), (SAT_X, SAT_Y, SAT_W, SAT_H), border_radius=10)
                pygame.draw.rect(screen, (100, 80, 20), (SAT_X, SAT_Y, SAT_W, SAT_H), 4, border_radius=10)

                # ==========================================
                # --- QUADRANT 1 (Top Left): LEDs & Toggles
                # ==========================================
                sat_pixels = HardwareMocks.get("SAT_01", "pixels")
                sat_mcp = HardwareMocks.get("SAT_01", "mcp")
                for i in range(8):
                    # 1. NeoPixels
                    led_tx = SAT_X + 60 + (i % 4) * 80
                    led_ty = SAT_Y + 60 + (i // 4) * 120
                    pygame.draw.circle(screen, (30, 30, 30), (led_tx, led_ty), 12)
                    try:
                        if sat_pixels:
                            color = sat_pixels[i]
                            if isinstance(color, int):
                                color = ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)
                            safe_color = tuple(max(0, min(255, int(c))) for c in color[:3])
                            if any(c > 0 for c in safe_color):
                                pygame.draw.circle(screen, safe_color, (led_tx, led_ty), 9)
                            else:
                                pygame.draw.circle(screen, (10, 10, 10), (led_tx, led_ty), 9)
                    except: pass

                    # 2. Latching Toggles
                    tx = SAT_X + 60 + (i % 4)*80
                    ty = SAT_Y + 110 + (i // 4)*120
                    state = True if not sat_mcp else sat_mcp.peek_pin(i).value
                    pygame.draw.rect(screen, (80, 80, 80), (tx-15, ty-25, 30, 50), border_radius=4)
                    pygame.draw.rect(screen, (40, 40, 40), (tx-15, ty-25, 30, 50), 2, border_radius=4)
                    if state: # UP
                        pygame.draw.rect(screen, (180, 180, 180), (tx-6, ty-25, 12, 28), border_radius=3)
                        pygame.draw.circle(screen, (150, 150, 150), (tx, ty-25), 6)
                    else:     # DOWN
                        pygame.draw.rect(screen, (120, 120, 120), (tx-6, ty, 12, 28), border_radius=3)
                        pygame.draw.circle(screen, (90, 90, 90), (tx, ty+28), 6)

                # ==========================================
                # --- QUADRANT 2 (Top Right): Segment & Keypad
                # ==========================================
                # 1. 14-Segment Display
                if HardwareMocks.get("SAT_01", "segments", key=0x70) and HardwareMocks.get("SAT_01", "segments", key=0x71):
                    seg_font = pygame.font.SysFont("courier", 32, bold=True)
                    left_display = HardwareMocks.get("SAT_01", "segments", key=0x71)
                    right_display = HardwareMocks.get("SAT_01", "segments", key=0x70)

                    full_text = "".join(left_display.chars) if left_display else "    "
                    full_text += "".join(right_display.chars) if right_display else "    "

                    SEG_X, SEG_Y = SAT_X + 430, SAT_Y + 60
                    SEG_W, SEG_H = 240, 60
                    pygame.draw.rect(screen, (15, 5, 5), (SEG_X, SEG_Y, SEG_W, SEG_H))
                    pygame.draw.rect(screen, (40, 10, 10), (SEG_X, SEG_Y, SEG_W, SEG_H), 2)

                    text_surface = seg_font.render(full_text, True, (255, 40, 40))
                    text_rect = text_surface.get_rect(center=(SEG_X + SEG_W//2, SEG_Y + SEG_H//2))
                    screen.blit(text_surface, text_rect)

                # 2. Keypad (3x4)
                KEYPAD_LABELS = ['1','2','3','4','5','6','7','8','9','*','0','#']
                for r in range(4):
                    for c in range(3):
                        kx, ky = SAT_X + 460 + c*70, SAT_Y + 160 + r*60
                        pygame.draw.circle(screen, (30, 30, 30), (kx, ky), 22)
                        pygame.draw.circle(screen, (180, 180, 180), (kx, ky), 20)
                        idx = r * 3 + c
                        lbl = oled_font.render(KEYPAD_LABELS[idx], True, (0, 0, 0))
                        lbl_rect = lbl.get_rect(center=(kx, ky))
                        screen.blit(lbl, lbl_rect)

                # ==========================================
                # --- QUADRANT 3 (Bottom Left): Specials, Mom, Big Btn
                # ==========================================
                sat_mcp2 = HardwareMocks.get("SAT_01", "mcp2")
                # 1. Specials
                spec_labels = ["ARM", "KEY", "ROT-A", "ROT-B"]
                spec_pins2  = [2, 3, 4, 5]
                spec_colors = [(200, 60, 60), (60, 120, 200), (100, 200, 100), (100, 200, 100)]
                for j, (pin_num, label, act_color) in enumerate(zip(spec_pins2, spec_labels, spec_colors)):
                    tx, ty = SAT_X + 60 + j*80, SAT_Y + 400
                    state = True if not sat_mcp2 else sat_mcp2.peek_pin(pin_num).value
                    pygame.draw.rect(screen, (80, 80, 80), (tx-15, ty-25, 30, 50), border_radius=4)
                    pygame.draw.rect(screen, (40, 40, 40), (tx-15, ty-25, 30, 50), 2, border_radius=4)
                    ind_color = act_color if not state else (60, 60, 60)
                    pygame.draw.circle(screen, ind_color, (tx, ty+30), 5)
                    if state: # UP
                        pygame.draw.rect(screen, (180, 180, 180), (tx-6, ty-25, 12, 28), border_radius=3)
                        pygame.draw.circle(screen, (150, 150, 150), (tx, ty-25), 6)
                    else:     # DOWN
                        pygame.draw.rect(screen, (120, 120, 120), (tx-6, ty, 12, 28), border_radius=3)
                        pygame.draw.circle(screen, (90, 90, 90), (tx, ty+28), 6)
                    lbl_surf = oled_font.render(label, True, (50, 30, 10))
                    screen.blit(lbl_surf, (tx - 18, ty + 37))

                # 2. Momentary
                MOM_X, MOM_Y = SAT_X + 100, SAT_Y + 540
                pygame.draw.rect(screen, (80, 80, 80), (MOM_X-15, MOM_Y-25, 30, 50), border_radius=4)
                pygame.draw.rect(screen, (40, 40, 40), (MOM_X-15, MOM_Y-25, 30, 50), 2, border_radius=4)
                state_up = True if not sat_mcp2 else sat_mcp2.peek_pin(0).value
                state_down = True if not sat_mcp2 else sat_mcp2.peek_pin(1).value
                if not state_up:
                    pygame.draw.rect(screen, (180, 180, 180), (MOM_X-6, MOM_Y-25, 12, 28), border_radius=3)
                    pygame.draw.circle(screen, (150, 150, 150), (MOM_X, MOM_Y-25), 6)
                elif not state_down:
                    pygame.draw.rect(screen, (120, 120, 120), (MOM_X-6, MOM_Y, 12, 28), border_radius=3)
                    pygame.draw.circle(screen, (90, 90, 90), (MOM_X, MOM_Y+28), 6)
                else:
                    pygame.draw.rect(screen, (150, 150, 150), (MOM_X-6, MOM_Y-12, 12, 24), border_radius=3)
                    pygame.draw.circle(screen, (130, 130, 130), (MOM_X, MOM_Y), 6)

                # 3. Big Red Button
                BIG_BTN_X, BIG_BTN_Y = SAT_X + 260, SAT_Y + 540
                btn_pressed = sat_mcp2 and not sat_mcp2.peek_pin(6).value
                big_btn_color = (150, 10, 10) if btn_pressed else (220, 30, 30)
                pygame.draw.circle(screen, (20, 20, 20), (BIG_BTN_X, BIG_BTN_Y), 34)
                pygame.draw.circle(screen, big_btn_color, (BIG_BTN_X, BIG_BTN_Y), 30)
                lbl_surf = oled_font.render("!", True, (255, 200, 200))
                lbl_rect = lbl_surf.get_rect(center=(BIG_BTN_X, BIG_BTN_Y))
                screen.blit(lbl_surf, lbl_rect)

                # ==========================================
                # --- QUADRANT 4 (Bottom Right): Encoder
                # ==========================================
                SAT_ENC_X, SAT_ENC_Y = SAT_X + 560, SAT_Y + 500
                pygame.draw.circle(screen, (20, 20, 20), (SAT_ENC_X, SAT_ENC_Y), 35)
                pygame.draw.circle(screen, (70, 70, 75), (SAT_ENC_X, SAT_ENC_Y), 30)
                if HardwareMocks.get("SAT_01", "encoder"):
                    angle = (HardwareMocks.get("SAT_01", "encoder").position * 18) % 360
                    rad = math.radians(angle - 90)
                    ix = SAT_ENC_X + math.cos(rad) * 25
                    iy = SAT_ENC_Y + math.sin(rad) * 25
                    pygame.draw.line(screen, (255, 100, 100), (SAT_ENC_X, SAT_ENC_Y), (ix, iy), 4)

            pygame.display.flip()
            await asyncio.sleep(0.016) # ~60 FPS
        except Exception as e:
            JEBLogger.error("EMUL", f"Error in render loop: {e}", src="EMUL")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(1) # Pause to prevent spamming errors

async def main():
    pygame.init()
    screen = pygame.display.set_mode((1600, 800))
    pygame.display.set_caption("JEB Embedded Hardware Emulator")

    JEBLogger.note("CORE", " --- BOOTING CORE MANAGER --- ", src="EMUL")
    HardwareMocks.set_context("CORE")
    core = CoreManager()
    core.matrix.fill((0,255,0))

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
    except asyncio.CancelledError:
        JEBLogger.note("EMUL", "🛑 Emulator closed cleanly.", src="EMUL")
    except Exception as e:
        JEBLogger.error("EMUL", f"System crashed: {e}", src="EMUL")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 [EMULATOR] Shutting down from console (Ctrl+C)...")
    finally:
        pygame.quit()
