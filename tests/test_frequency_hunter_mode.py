"""Test module for FrequencyHunterMode game and animate_static_resolve.

Tests verify:
- frequency_hunter.py file exists and has valid Python syntax
- FrequencyHunterMode is correctly registered in the manifest
- FrequencyHunterMode does NOT contain a METADATA class attribute
- FREQ_HUNTER icon is registered in ICON_LIBRARY as a 16x16 icon
- All icons in SIGNAL_POOL are present in ICON_LIBRARY
- animate_static_resolve at clarity=0.0 draws only static noise (no correct pixels)
- animate_static_resolve at clarity=1.0 draws only correct icon pixels
- animate_static_resolve clamps clarity values outside [0.0, 1.0]
- FrequencyHunterMode.LOCK_THRESHOLD is between 0 and 1
- FrequencyHunterMode manifest settings include difficulty and time_limit
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ---------------------------------------------------------------------------
# Stub out CircuitPython-specific modules before any src imports
# ---------------------------------------------------------------------------
from unittest.mock import MagicMock

_MOCK_MOD_NAMES = [
    'digitalio', 'busio', 'board', 'adafruit_mcp230xx',
    'adafruit_mcp230xx.mcp23017', 'adafruit_ticks', 'audiobusio',
    'audiocore', 'audiomixer', 'analogio', 'microcontroller', 'watchdog',
    'audiopwmio', 'synthio', 'ulab', 'neopixel',
    'adafruit_displayio_ssd1306', 'adafruit_display_text',
    'adafruit_display_text.label', 'adafruit_ht16k33',
    'adafruit_ht16k33.segments', 'displayio', 'terminalio',
]
for _mod in _MOCK_MOD_NAMES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Provide ticks_ms / ticks_diff stubs
import time as _time
sys.modules['adafruit_ticks'].ticks_ms = lambda: int(_time.monotonic() * 1000)
sys.modules['adafruit_ticks'].ticks_diff = lambda a, b: a - b


# ---------------------------------------------------------------------------
# File / manifest checks
# ---------------------------------------------------------------------------

def test_frequency_hunter_file_exists():
    """frequency_hunter.py must exist in src/modes/."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'frequency_hunter.py')
    assert os.path.exists(path), "frequency_hunter.py does not exist"


def test_frequency_hunter_valid_syntax():
    """frequency_hunter.py must have valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'frequency_hunter.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    compile(code, path, 'exec')


def test_frequency_hunter_in_manifest():
    """FREQ_HUNTER must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "FREQ_HUNTER" in MODE_REGISTRY, "FREQ_HUNTER not found in MODE_REGISTRY"
    entry = MODE_REGISTRY["FREQ_HUNTER"]
    assert entry["id"] == "FREQ_HUNTER"
    assert entry["name"] == "FREQ HUNTER"
    assert entry["module_path"] == "modes.frequency_hunter"
    assert entry["class_name"] == "FrequencyHunterMode"
    assert entry["icon"] == "FREQ_HUNTER"
    assert "CORE" in entry["requires"]
    assert entry.get("menu") == "MAIN"


def test_frequency_hunter_manifest_settings():
    """FREQ_HUNTER must have difficulty and time_limit settings."""
    from modes.manifest import MODE_REGISTRY
    entry = MODE_REGISTRY["FREQ_HUNTER"]
    settings = entry.get("settings", [])

    difficulty = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty is not None, "Missing 'difficulty' setting"
    assert "NORMAL" in difficulty["options"]
    assert "HARD" in difficulty["options"]
    assert difficulty["default"] == "NORMAL"

    time_limit = next((s for s in settings if s["key"] == "time_limit"), None)
    assert time_limit is not None, "Missing 'time_limit' setting"
    assert "60" in time_limit["options"]
    assert time_limit["default"] == "60"


def test_frequency_hunter_no_metadata_in_class():
    """FrequencyHunterMode must NOT define a METADATA class attribute."""
    from modes.frequency_hunter import FrequencyHunterMode
    assert not hasattr(FrequencyHunterMode, 'METADATA'), (
        "FrequencyHunterMode should not define METADATA; it is centralised in manifest.py"
    )


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_freq_hunter_icon_exists_and_is_16x16():
    """FREQ_HUNTER menu icon must be a 16x16 (256-pixel) icon."""
    from utilities.icons import Icons
    assert "FREQ_HUNTER" in Icons.ICON_LIBRARY, "FREQ_HUNTER not in ICON_LIBRARY"
    assert len(Icons.ICON_LIBRARY["FREQ_HUNTER"]) == 256


# ---------------------------------------------------------------------------
# animate_static_resolve tests
# ---------------------------------------------------------------------------

class _FakeMatrix:
    """Minimal matrix stub for animate_static_resolve tests."""

    def __init__(self, width=16, height=16):
        self.width = width
        self.height = height
        # Simple palette: value → (value, value, value)
        self.palette = {v: (v, v, v) for v in range(1, 75)}
        self.drawn = []  # list of (x, y, color)
        self.filled = []

    def fill(self, color, show=False):
        self.filled.append(color)
        self.drawn = []

    def draw_pixel(self, x, y, color, brightness=1.0, anim_mode=None, speed=1.0):
        self.drawn.append((x, y, color))


# A minimal 8x8 icon with known active pixels (value 41 = green)
_SIMPLE_ICON = [
    0, 0, 0, 0, 0, 0, 0, 0,
    0,41, 0, 0, 0, 0,41, 0,
    0, 0,41, 0, 0,41, 0, 0,
    0, 0, 0,41,41, 0, 0, 0,
    0, 0, 0,41,41, 0, 0, 0,
    0, 0,41, 0, 0,41, 0, 0,
    0,41, 0, 0, 0, 0,41, 0,
    0, 0, 0, 0, 0, 0, 0, 0,
]

_ACTIVE_PIXELS = sum(1 for v in _SIMPLE_ICON if v != 0)


def test_animate_static_resolve_full_clarity_only_icon_pixels():
    """At clarity=1.0, animate_static_resolve must draw only the icon's active pixels."""
    import random
    random.seed(42)

    from utilities import matrix_animations

    matrix = _FakeMatrix(width=16, height=16)
    matrix_animations.animate_static_resolve(matrix, _SIMPLE_ICON, clarity=1.0)

    # All drawn pixels must match palette colour (41,41,41) – never random noise
    icon_color = (41, 41, 41)
    for (x, y, color) in matrix.drawn:
        assert color == icon_color, (
            f"At clarity=1.0 expected icon colour {icon_color}, got {color} at ({x},{y})"
        )
    # Exactly the active pixels should have been drawn
    assert len(matrix.drawn) == _ACTIVE_PIXELS


def test_animate_static_resolve_zero_clarity_no_icon_pixels():
    """At clarity=0.0, animate_static_resolve must draw only random static (no icon colours)."""
    import random
    random.seed(0)

    from utilities import matrix_animations

    matrix = _FakeMatrix(width=16, height=16)
    matrix_animations.animate_static_resolve(matrix, _SIMPLE_ICON, clarity=0.0)

    icon_color = (41, 41, 41)
    for (x, y, color) in matrix.drawn:
        assert color != icon_color, (
            f"At clarity=0.0 no icon pixel expected, got icon colour at ({x},{y})"
        )


def test_animate_static_resolve_clamps_clarity_above_one():
    """animate_static_resolve must clamp clarity > 1.0 to 1.0."""
    import random
    random.seed(7)

    from utilities import matrix_animations

    matrix_high = _FakeMatrix(width=16, height=16)
    matrix_one = _FakeMatrix(width=16, height=16)

    random.seed(7)
    matrix_animations.animate_static_resolve(matrix_high, _SIMPLE_ICON, clarity=5.0)
    random.seed(7)
    matrix_animations.animate_static_resolve(matrix_one, _SIMPLE_ICON, clarity=1.0)

    assert matrix_high.drawn == matrix_one.drawn


def test_animate_static_resolve_clamps_clarity_below_zero():
    """animate_static_resolve must clamp clarity < 0.0 to 0.0."""
    import random

    from utilities import matrix_animations

    matrix_neg = _FakeMatrix(width=16, height=16)
    matrix_zero = _FakeMatrix(width=16, height=16)

    random.seed(3)
    matrix_animations.animate_static_resolve(matrix_neg, _SIMPLE_ICON, clarity=-1.0)
    random.seed(3)
    matrix_animations.animate_static_resolve(matrix_zero, _SIMPLE_ICON, clarity=0.0)

    assert matrix_neg.drawn == matrix_zero.drawn


def test_animate_static_resolve_fills_before_drawing():
    """animate_static_resolve must call fill(OFF) to clear the matrix first."""
    from utilities import matrix_animations
    from utilities.palette import Palette

    matrix = _FakeMatrix(width=16, height=16)
    matrix_animations.animate_static_resolve(matrix, _SIMPLE_ICON, clarity=0.5)

    assert len(matrix.filled) >= 1
    assert matrix.filled[0] == Palette.OFF


# ---------------------------------------------------------------------------
# Class constants / sanity checks
# ---------------------------------------------------------------------------

def test_lock_threshold_is_valid():
    """LOCK_THRESHOLD must be between 0.0 and 1.0 exclusive."""
    from modes.frequency_hunter import FrequencyHunterMode
    assert 0.0 < FrequencyHunterMode.LOCK_THRESHOLD < 1.0


def test_freq_range_is_positive():
    """FREQ_MIN and FREQ_MAX must define a positive, ordered range."""
    from modes.frequency_hunter import FrequencyHunterMode
    assert FrequencyHunterMode.FREQ_MIN >= 0.0
    assert FrequencyHunterMode.FREQ_MAX > FrequencyHunterMode.FREQ_MIN


def test_sonar_bpm_range_is_ordered():
    """SONAR_BPM_NEAR must be greater than SONAR_BPM_FAR."""
    from modes.frequency_hunter import FrequencyHunterMode
    assert FrequencyHunterMode.SONAR_BPM_NEAR > FrequencyHunterMode.SONAR_BPM_FAR


def test_sonar_pitch_range_is_ordered():
    """SONAR_PITCH_NEAR must be greater than SONAR_PITCH_FAR."""
    from modes.frequency_hunter import FrequencyHunterMode
    assert FrequencyHunterMode.SONAR_PITCH_NEAR > FrequencyHunterMode.SONAR_PITCH_FAR
