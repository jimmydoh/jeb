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

async def run_hardware_spy_loop(core, screen):
    """
    This Pygame loop runs in the background. Instead of mocking the managers,
    it looks at the REAL CoreManager's state and draws it to the screen.
    """
    # Initialize Pygame fonts
    pygame.font.init()
    oled_font = pygame.font.SysFont("courier", 12, bold=True)

    # ==========================================
    # UI LAYOUT CONSTANTS (600x600 Square)
    # ==========================================
    WINDOW_SIZE = 600

    # OLED (Top Right)
    OLED_W, OLED_H = 256, 128
    OLED_X = WINDOW_SIZE - OLED_W - 20
    OLED_Y = 20

    # MATRIX (Centered vertically/horizontally)
    CELL_SIZE = 36
    MATRIX_SIZE = 8 * CELL_SIZE
    MATRIX_X = (WINDOW_SIZE - MATRIX_SIZE) // 2
    MATRIX_Y = 160

    # BUTTONS / LEDS (Bottom Center, under matrix)
    BTN_Y = 510
    BTN_RADIUS = 26
    BTN_SPACING = MATRIX_SIZE // 4
    # Calculate 4 centers evenly spaced under the matrix
    BTN_CENTERS = [(MATRIX_X + (BTN_SPACING // 2) + (i * BTN_SPACING), BTN_Y) for i in range(4)]

    # ENCODER (Bottom Right)
    ENC_X = WINDOW_SIZE - 70
    ENC_Y = 510
    ENC_RADIUS = 35

    while True:
        # ==========================================
        # 1. INPUT HANDLING (Keyboard & Mouse)
        # ==========================================
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # --- MOUSE CLICKS (Interactive UI) ---
            if event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.MOUSEBUTTONUP:
                is_pressed = (event.type == pygame.MOUSEBUTTONDOWN)
                mx, my = event.pos

                # Check Arcade Buttons (0-3)
                for i, (bx, by) in enumerate(BTN_CENTERS):
                    if (mx - bx)**2 + (my - by)**2 <= BTN_RADIUS**2:
                        if HardwareMocks.mcp:
                            # Set hardware pin logic
                            HardwareMocks.mcp.get_pin(i).value = not is_pressed
                            # Trigger MCP interrupt
                            if HardwareMocks.mcp_int:
                                HardwareMocks.mcp_int.value = False

                # Check Encoder Push
                if (mx - ENC_X)**2 + (my - ENC_Y)**2 <= ENC_RADIUS**2:
                    if HardwareMocks.encoder_btn:
                        HardwareMocks.encoder_btn.events.queue.append(
                            MockKeypadEvent(key_number=0, pressed=is_pressed, released=not is_pressed)
                        )

            # --- MOUSE WHEEL (Interactive Encoder) ---
            elif event.type == pygame.MOUSEWHEEL:
                if HardwareMocks.encoder:
                    # Scroll Up = Right Turn, Scroll Down = Left Turn
                    HardwareMocks.encoder.position += event.y

            # --- KEYBOARD FALLBACK ---
            elif event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                is_pressed = (event.type == pygame.KEYDOWN)

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFT and HardwareMocks.encoder:
                        HardwareMocks.encoder.position -= 1
                    elif event.key == pygame.K_RIGHT and HardwareMocks.encoder:
                        HardwareMocks.encoder.position += 1

                # Encoder Push
                if event.key == pygame.K_RETURN and HardwareMocks.encoder_btn:
                    HardwareMocks.encoder_btn.events.queue.append(
                        MockKeypadEvent(key_number=0, pressed=is_pressed, released=not is_pressed)
                    )
                # Main Buttons
                key_map = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3}
                if event.key in key_map and HardwareMocks.mcp:
                    idx = key_map[event.key]
                    HardwareMocks.mcp.get_pin(idx).value = not is_pressed
                    if HardwareMocks.mcp_int:
                        HardwareMocks.mcp_int.value = False

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
        if HardwareMocks.encoder:
            # Map position to a 360 degree angle
            angle = (HardwareMocks.encoder.position * 18) % 360
            rad = math.radians(angle - 90) # -90 puts 0 at the top
            ix = ENC_X + math.cos(rad) * (ENC_RADIUS - 10)
            iy = ENC_Y + math.sin(rad) * (ENC_RADIUS - 10)
            pygame.draw.line(screen, (255, 100, 100), (ENC_X, ENC_Y), (ix, iy), 4)

        pygame.display.flip()
        await asyncio.sleep(0.016) # ~60 FPS


async def main():
    pygame.init()
    # Update to the new square window size
    screen = pygame.display.set_mode((600, 600))
    pygame.display.set_caption("JEB Embedded Hardware Emulator")

    print("========================================")
    print("      BOOTING CORE MANAGER...      ")
    print("========================================")

    core = CoreManager()
    print("========================================")
    print("      STARTING HARDWARE EMULATOR...      ")
    print("========================================")
    render_task = asyncio.create_task(run_hardware_spy_loop(core, screen))

    try:
        await core.start()
    except Exception as e:
        print(f"System crashed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        render_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
