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

# 2. IMPORT THE REAL CODE
import asyncio
import pygame
from core.core_manager import CoreManager

async def run_hardware_spy_loop(core, screen):
    """
    This Pygame loop runs in the background. Instead of mocking the managers,
    it looks at the REAL CoreManager's state and draws it to the screen.
    """
    clock = pygame.time.Clock()

    # Initialize Pygame fonts
    pygame.font.init()
    oled_font = pygame.font.SysFont("monospace", 16, bold=True)

    # UI Layout constants
    cell_size = 30
    margin_x, margin_y = 80, 120

    # OLED layout constants
    oled_bg_rect = (10, 10, 380, 110)
    oled_margin_x, oled_margin_y = 20, 20

    while True:
        # 1. Handle OS Events (Quit window)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            # --- HARDWARE SIGNAL INJECTION ---
            if event.type == pygame.KEYDOWN:
                # Encoder Turn (Updates integer position)
                if event.key == pygame.K_LEFT and jeb_emulator.HardwareMocks.encoder:
                    jeb_emulator.HardwareMocks.encoder.position -= 1
                elif event.key == pygame.K_RIGHT and jeb_emulator.HardwareMocks.encoder:
                    jeb_emulator.HardwareMocks.encoder.position += 1

                # Encoder Push (Pushes event to hardware queue)
                elif event.key == pygame.K_RETURN and jeb_emulator.HardwareMock.encoder_btn:
                    jeb_emulator.HardwareMocks.encoder_btn.events.queue.append(jeb_emulator.MockKeypadEvent(key_number=0, pressed=True, released=False))

                # E-Stop Toggle (Flips digital logic level)
                elif event.key == pygame.K_ESCAPE and jeb_emulator.HardwareMocks.estop:
                    jeb_emulator.HardwareMocks.estop.value = not jeb_emulator.HardwareMocks.estop.value

            elif event.type == pygame.KEYUP:
                # Encoder Push Release
                if event.key == pygame.K_RETURN and jeb_emulator.HardwareMocks.encoder_btn:
                    jeb_emulator.HardwareMocks.encoder_btn.events.queue.append(jeb_emulator.MockKeypadEvent(key_number=0, pressed=False, released=True))


            # --- EXPANDED BUTTON SIGNAL INJECTION ---
            if event.type == pygame.KEYDOWN or event.type == pygame.KEYUP:
                is_pressed = (event.type == pygame.KEYDOWN)

                # Map Q, W, E, R to MCP Pins 0, 1, 2, 3
                key_map = {pygame.K_q: 0, pygame.K_w: 1, pygame.K_e: 2, pygame.K_r: 3}

                if event.key in key_map and jeb_emulator.HardwareMocks.mcp:
                    pin_num = key_map[event.key]
                    # Simulate active-low buttons (pressed = False)
                    jeb_emulator.HardwareMocks.mcp.get_pin(pin_num).value = not is_pressed

        # 2. Render Background
        screen.fill((40, 40, 50))

        # 3. SPY ON THE REAL DISPLAY MANAGER (OLED)
        pygame.draw.rect(screen, (15, 15, 20), oled_bg_rect) # Draw OLED background

        if hasattr(core, 'display') and core.display and hasattr(core.display, 'root'):

            def render_display_tree(element, base_x, base_y):
                # Skip hidden elements
                if hasattr(element, 'hidden') and element.hidden:
                    return

                # Get local coordinates
                ex = getattr(element, 'x', 0)
                ey = getattr(element, 'y', 0)

                # Is it a Group? (Crawl its children)
                if hasattr(element, '_items'):
                    for child in element._items:
                        render_display_tree(child, base_x + ex, base_y + ey)

                # Is it a Label? (Render it)
                elif hasattr(element, 'text') and element.text:
                    # Scale coordinates slightly to fit Pygame screen better (e.g., x2 multiplier)
                    screen_x = base_x + (ex * 2.5)
                    screen_y = base_y + (ey * 1.5)

                    text_surface = oled_font.render(str(element.text), True, (150, 200, 255))
                    screen.blit(text_surface, (screen_x, screen_y))

            # Trigger the recursive render starting from the DisplayManager's root group
            render_display_tree(core.display.root, oled_margin_x, oled_margin_y)

        # 4. SPY ON THE REAL MATRIX MANAGER
        if hasattr(core, 'matrix') and core.matrix:
            for y in range(8):
                for x in range(8):
                    # Use the REAL JEB serpentine math!
                    idx = core.matrix._get_idx(x, y)

                    # Read the color directly from the REAL JEBPixel wrapper
                    color = core.matrix.pixels[idx]

                    # Draw it
                    rect = (margin_x + (x * cell_size), margin_y + (y * cell_size), cell_size - 2, cell_size - 2)

                    # Ensure it's Pygame safe (0-255) in case real animations push floats
                    try:
                        safe_color = tuple(max(0, min(255, int(c))) for c in color)
                    except TypeError:
                        safe_color = (0, 0, 0) # Fallback if animation state is weird

                    pygame.draw.rect(screen, safe_color, rect)

        pygame.display.flip()

        # Limit to ~60fps and yield to CircuitPython's asyncio loop
        clock.tick(60)
        await asyncio.sleep(0.001)


async def main():
    # 1. Initialize the UI
    pygame.init()
    screen = pygame.display.set_mode((400, 500))
    pygame.display.set_caption("JEB Hardware-in-the-Loop Emulator")

    print("========================================")
    print("      BOOTING REAL CORE MANAGER...      ")
    print("========================================")

    # 2. Instantiate the REAL Core Manager!
    core = CoreManager()

    # 3. Start the Pygame spy loop in the background
    render_task = asyncio.create_task(run_hardware_spy_loop(core, screen))

    # 4. Run the real core loop
    try:
        await core.start()
    except Exception as e:
        print(f"System crashed: {e}")
    finally:
        render_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
