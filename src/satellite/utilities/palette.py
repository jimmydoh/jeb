"""A simple color palette for use in visualizations."""



class Palette:
    """A simple color palette for us in visualizations."""
    # Binary Colors
    OFF    = (0, 0, 0)
    WHITE  = (150, 150, 150)

    # Basic Colors
    RED    = (200, 0, 0)
    BLUE   = (0, 0, 200)
    YELLOW = (200, 150, 0)
    GREEN  = (0, 200, 0)
    PURPLE = (150, 0, 150)
    ORANGE = (255, 100, 0)

    # Complex Colors
    PINK   = (255, 0, 150)
    CYAN   = (0, 200, 200)
    MAGENTA= (200, 0, 200)
    GOLD   = (255, 100, 0)
    SILVER = (192, 192, 192)
    AMBER  = (255, 191, 0)

    def __init__(self):
        pass

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
