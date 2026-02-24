"""
A selection of colour palette classes for use in the JEB Project
"""

class Color(tuple):
    """A simple RGB color class for better readability."""
    def __new__(cls, index, name, r, g, b):
        return super(Color, cls).__new__(cls, (r, g, b))

    def __init__(self, index, name, r, g, b):
        self.index = index
        self.name = name

class Palette:
    """
    A 40-color logical palette.
    Usage: Use the index (e.g., 10) in your arrays.
    """

    # --- 00-09: GRAYSCALE & UTILITY ---
    OFF       = Color(0, "OFF", 0, 0, 0)
    CHARCOAL  = Color(1, "CHARCOAL", 30, 30, 30)    # Backgrounds
    GRAY      = Color(2, "GRAY", 100, 100, 100) # Metal/Stone
    SILVER    = Color(3, "SILVER", 180, 180, 180) # Bright Metal
    WHITE     = Color(4, "WHITE", 255, 255, 255)

    # --- 10-19: REDS ---
    MAROON    = Color(10, "MAROON", 100, 0, 0)     # Outline
    RED       = Color(11, "RED", 255, 0, 0)     # Main
    TOMATO    = Color(12, "TOMATO", 255, 80, 80)   # Highlight
    PINK      = Color(13, "PINK", 255, 180, 180) # Pastel
    LASER     = Color(14, "LASER", 255, 50, 50)   # Neon Red / Laser

    # --- 20-29: ORANGES / BROWNS ---
    BROWN     = Color(20, "BROWN", 90, 45, 0)     # Wood/Tree trunk
    ORANGE    = Color(21, "ORANGE", 255, 120, 0)   # Fire/Fruit
    GOLD      = Color(22, "GOLD", 255, 200, 0)   # Coin/Treasure
    PEACH     = Color(23, "PEACH", 255, 220, 180) # Skin tone
    EXPLODE   = Color(24, "EXPLODE", 255, 180, 50)  # Neon Orange / Explosion Core

    # --- 30-39: YELLOWS ---
    MUD       = Color(30, "MUD", 100, 100, 0)   # Dark Yellow/Camo
    YELLOW    = Color(31, "YELLOW", 255, 255, 0)   # Sun/Zap
    CREAM     = Color(32, "CREAM", 255, 255, 150) # Light Yellow
    WHEAT     = Color(33, "WHEAT", 255, 240, 200) # Very Pale
    SOLAR     = Color(34, "SOLAR", 255, 255, 200) # Neon Yellow / Solar Flare

    # --- 40-49: GREENS ---
    FOREST    = Color(40, "FOREST", 0, 80, 0)      # Leaves shadow
    GREEN     = Color(41, "GREEN", 0, 200, 0)     # Grass/Main
    LIME      = Color(42, "LIME", 100, 255, 50)  # Slime/Highlight
    MINT      = Color(43, "MINT", 180, 255, 180) # Pastel
    TOXIC     = Color(44, "TOXIC", 150, 255, 100) # Neon Green / Radioactive

    # --- 50-59: CYANS / TEALS ---
    TEAL      = Color(50, "TEAL", 0, 100, 100)   # Deep Water
    CYAN      = Color(51, "CYAN", 0, 200, 200)   # Ice/Diamond
    AQUA      = Color(52, "AQUA", 100, 255, 255) # Bright Water
    AZURE     = Color(53, "AZURE", 200, 255, 255) # Clouds
    FROST     = Color(54, "FROST", 180, 255, 255) # Electric Cyan / Frostbite

    # --- 60-69: BLUES ---
    NAVY      = Color(60, "NAVY", 0, 0, 80)      # Night Sky
    BLUE      = Color(61, "BLUE", 0, 0, 255)     # Water/Uniform
    SKY       = Color(62, "SKY", 60, 100, 255)  # Day Sky
    PERIWINKLE= Color(63, "PERIWINKLE", 180, 180, 255) # Pastel
    PLASMA    = Color(64, "PLASMA", 100, 150, 255) # Neon Blue / Plasma

    # --- 70-79: PURPLES ---
    INDIGO    = Color(70, "INDIGO", 60, 0, 100)    # Royal
    MAGENTA   = Color(71, "MAGENTA", 200, 0, 200)   # Magic/Poison
    VIOLET    = Color(72, "VIOLET", 200, 100, 255) # Bright
    LAVENDER  = Color(73, "LAVENDER", 230, 180, 255) # Pastel
    HYPER     = Color(74, "HYPER", 255, 100, 255) # Neon Magenta / Warp Core

    # The Lookup Table for the Driver
    LIBRARY = {
        0: OFF, 1: CHARCOAL, 2: GRAY, 3: SILVER, 4: WHITE,
        10: MAROON, 11: RED, 12: TOMATO, 13: PINK, 14: LASER,
        20: BROWN, 21: ORANGE, 22: GOLD, 23: PEACH, 24: EXPLODE,
        30: MUD, 31: YELLOW, 32: CREAM, 33: WHEAT, 34: SOLAR,
        40: FOREST, 41: GREEN, 42: LIME, 43: MINT, 44: TOXIC,
        50: TEAL, 51: CYAN, 52: AQUA, 53: AZURE, 54: FROST,
        60: NAVY, 61: BLUE, 62: SKY, 63: PERIWINKLE, 64: PLASMA,
        70: INDIGO, 71: MAGENTA, 72: VIOLET, 73: LAVENDER, 74: HYPER
    }

    PALETTE_LIBRARY = LIBRARY

    @staticmethod
    def get_color(index):
        """Get the color from the palette library by index."""
        return Palette.LIBRARY.get(index, Palette.OFF)

    @staticmethod
    def hsv_to_rgb(h, s, v):
        """Convert HSV to RGB color space.

        Args:
            h (float): Hue angle in degrees [0, 360).
            s (float): Saturation [0.0, 1.0].
            v (float): Value [0.0, 1.0].

        Returns:
            tuple: Corresponding RGB values as a tuple (r, g, b).
        """
        if s == 0.0:
            v_int = int(v * 255)
            return (v_int, v_int, v_int)

        h = h / 60.0
        i = int(h)
        f = h - i
        p = int(v * (1 - s) * 255)
        q = int(v * (1 - s * f) * 255)
        t = int(v * (1 - s * (1 - f)) * 255)
        v = int(v * 255)

        if i == 0:
            return (v, t, p)
        elif i == 1:
            return (q, v, p)
        elif i == 2:
            return (p, v, t)
        elif i == 3:
            return (p, q, v)
        elif i == 4:
            return (t, p, v)
        else:
            return (v, p, q)


class PicoPalette:
    """
    Standard Pico-8 Palette.
    Optimized for high contrast and readability on low-res displays.
    """
    BLACK      = (0, 0, 0)
    DARK_BLUE  = (29, 43, 83)
    DARK_PURPLE= (126, 37, 83)
    DARK_GREEN = (0, 135, 81)
    BROWN      = (171, 82, 54)
    DARK_GRAY  = (95, 87, 79)
    LIGHT_GRAY = (194, 195, 199)
    WHITE      = (255, 241, 232)
    RED        = (255, 0, 77)
    ORANGE     = (255, 163, 0)
    YELLOW     = (255, 236, 39)
    GREEN      = (0, 228, 54)
    BLUE       = (41, 173, 255)
    INDIGO     = (131, 118, 156)
    PINK       = (255, 119, 168)
    PEACH      = (255, 204, 170)

    LIBRARY = {
        0: BLACK, 1: DARK_BLUE, 2: DARK_PURPLE, 3: DARK_GREEN,
        4: BROWN, 5: DARK_GRAY, 6: LIGHT_GRAY, 7: WHITE,
        8: RED, 9: ORANGE, 10: YELLOW, 11: GREEN,
        12: BLUE, 13: INDIGO, 14: PINK, 15: PEACH
    }
