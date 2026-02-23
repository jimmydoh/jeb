"""Test module for EmojiRevealMode game.

Tests verify:
- emoji_reveal.py file exists and has valid Python syntax
- EmojiRevealMode is correctly registered in the manifest
- SKULL, GHOST, SWORD, SHIELD icons are registered in ICON_LIBRARY as 16x16 icons
- EMOJI_REVEAL icon is registered in ICON_LIBRARY as a 16x16 icon
- animate_random_pixel_reveal illuminates active pixels and respects the matrix bounds
- animate_random_pixel_reveal can be cancelled mid-way
- EmojiRevealMode._calculate_score returns MAX at t=0 and MIN at t=full duration
- EmojiRevealMode._show_choices embeds all four choice labels in the display call
"""

import sys
import os
import asyncio
from unittest.mock import MagicMock, call

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ---------------------------------------------------------------------------
# Stub out CircuitPython-specific modules before any src imports
# ---------------------------------------------------------------------------
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

# Provide ticks_ms / ticks_diff stubs used by emoji_reveal
import time as _time
sys.modules['adafruit_ticks'].ticks_ms = lambda: int(_time.monotonic() * 1000)
sys.modules['adafruit_ticks'].ticks_diff = lambda a, b: a - b


# ---------------------------------------------------------------------------
# File / manifest checks
# ---------------------------------------------------------------------------

def test_emoji_reveal_file_exists():
    """emoji_reveal.py must exist in src/modes/."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'emoji_reveal.py')
    assert os.path.exists(path), "emoji_reveal.py does not exist"


def test_emoji_reveal_valid_syntax():
    """emoji_reveal.py must have valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'emoji_reveal.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    compile(code, path, 'exec')


def test_emoji_reveal_in_manifest():
    """EMOJI_REVEAL must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "EMOJI_REVEAL" in MODE_REGISTRY, "EMOJI_REVEAL not found in MODE_REGISTRY"
    entry = MODE_REGISTRY["EMOJI_REVEAL"]
    assert entry["id"] == "EMOJI_REVEAL"
    assert entry["name"] == "EMOJI REVEAL"
    assert entry["module_path"] == "modes.emoji_reveal"
    assert entry["class_name"] == "EmojiRevealMode"
    assert entry["icon"] == "EMOJI_REVEAL"
    assert "CORE" in entry["requires"]
    assert entry.get("menu") == "MAIN"


def test_emoji_reveal_manifest_settings():
    """EMOJI_REVEAL must have difficulty and rounds settings."""
    from modes.manifest import MODE_REGISTRY
    entry = MODE_REGISTRY["EMOJI_REVEAL"]
    settings = entry.get("settings", [])

    difficulty = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty is not None, "Missing 'difficulty' setting"
    assert "EASY" in difficulty["options"]
    assert "NORMAL" in difficulty["options"]
    assert "HARD" in difficulty["options"]
    assert difficulty["default"] == "NORMAL"

    rounds = next((s for s in settings if s["key"] == "rounds"), None)
    assert rounds is not None, "Missing 'rounds' setting"
    assert "5" in rounds["options"]
    assert rounds["default"] == "5"


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_emoji_reveal_icon_exists_and_is_16x16():
    """EMOJI_REVEAL icon must be a 16x16 (256-pixel) icon."""
    from utilities.icons import Icons
    assert "EMOJI_REVEAL" in Icons.ICON_LIBRARY
    assert len(Icons.ICON_LIBRARY["EMOJI_REVEAL"]) == 256


def test_skull_icon_exists_and_is_16x16():
    from utilities.icons import Icons
    assert "SKULL" in Icons.ICON_LIBRARY
    assert len(Icons.ICON_LIBRARY["SKULL"]) == 256


def test_ghost_icon_exists_and_is_16x16():
    from utilities.icons import Icons
    assert "GHOST" in Icons.ICON_LIBRARY
    assert len(Icons.ICON_LIBRARY["GHOST"]) == 256


def test_sword_icon_exists_and_is_16x16():
    from utilities.icons import Icons
    assert "SWORD" in Icons.ICON_LIBRARY
    assert len(Icons.ICON_LIBRARY["SWORD"]) == 256


def test_shield_icon_exists_and_is_16x16():
    from utilities.icons import Icons
    assert "SHIELD" in Icons.ICON_LIBRARY
    assert len(Icons.ICON_LIBRARY["SHIELD"]) == 256


def test_question_pool_uses_registered_icons():
    """Every icon referenced by QUESTION_POOL must exist in ICON_LIBRARY."""
    from utilities.icons import Icons
    from modes.emoji_reveal import EmojiRevealMode
    for entry in EmojiRevealMode.QUESTION_POOL:
        assert entry["icon"] in Icons.ICON_LIBRARY, (
            f"Icon '{entry['icon']}' not found in ICON_LIBRARY"
        )


# ---------------------------------------------------------------------------
# animate_random_pixel_reveal tests
# ---------------------------------------------------------------------------

class _FakeMatrix:
    """Minimal matrix stub for animation tests."""

    def __init__(self, width=16, height=16):
        self.width = width
        self.height = height
        self.palette = {v: (v * 3, v * 2, v) for v in range(1, 75)}
        self.drawn = []  # list of (x, y, color, brightness) tuples

    def draw_pixel(self, x, y, color, brightness=1.0):
        self.drawn.append((x, y, color, brightness))


def test_animate_random_pixel_reveal_illuminates_active_pixels():
    """Every active pixel in the icon must be drawn exactly once."""
    from utilities.matrix_animations import animate_random_pixel_reveal

    # 4x4 simple icon with 4 active pixels
    icon = [
        1, 0, 0, 1,
        0, 1, 1, 0,
        0, 0, 0, 0,
        0, 0, 0, 0,
    ]
    matrix = _FakeMatrix(width=4, height=4)

    asyncio.run(animate_random_pixel_reveal(matrix, icon, duration=0.01))

    # Four active pixels must have been drawn
    assert len(matrix.drawn) == 4, f"Expected 4 drawn pixels, got {len(matrix.drawn)}"


def test_animate_random_pixel_reveal_stays_within_bounds():
    """All drawn pixel coordinates must be inside the matrix dimensions."""
    from utilities.matrix_animations import animate_random_pixel_reveal
    from utilities.icons import Icons

    icon = Icons.SKULL
    matrix = _FakeMatrix(width=16, height=16)
    asyncio.run(animate_random_pixel_reveal(matrix, icon, duration=0.01))

    for x, y, _color, _bri in matrix.drawn:
        assert 0 <= x < matrix.width,  f"x={x} out of bounds"
        assert 0 <= y < matrix.height, f"y={y} out of bounds"


def test_animate_random_pixel_reveal_skips_zero_pixels():
    """Zero-value (background) pixels must never be drawn."""
    from utilities.matrix_animations import animate_random_pixel_reveal

    # All zeros – nothing should be drawn
    icon = [0] * 16
    matrix = _FakeMatrix(width=4, height=4)
    asyncio.run(animate_random_pixel_reveal(matrix, icon, duration=0.01))
    assert matrix.drawn == [], "Background-only icon should draw nothing"


def test_animate_random_pixel_reveal_cancellable():
    """animate_random_pixel_reveal must propagate CancelledError cleanly."""
    from utilities.matrix_animations import animate_random_pixel_reveal

    icon = [1] * 64  # 8x8 all-active icon
    matrix = _FakeMatrix(width=8, height=8)

    async def _run():
        task = asyncio.create_task(
            animate_random_pixel_reveal(matrix, icon, duration=60.0)
        )
        await asyncio.sleep(0.02)  # let a few pixels be drawn
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Some pixels should have been drawn before cancellation
        return len(matrix.drawn)

    drawn = asyncio.run(_run())
    assert drawn > 0, "Some pixels should have been drawn before cancellation"
    assert drawn < 64, "Not all pixels should have been drawn (task was cancelled)"


# ---------------------------------------------------------------------------
# Scoring logic tests
# ---------------------------------------------------------------------------

def _make_mode():
    """Create a minimal EmojiRevealMode with a fully-mocked core."""
    core = MagicMock()
    core.data.get_setting.return_value = "NORMAL"
    from modes.emoji_reveal import EmojiRevealMode
    mode = EmojiRevealMode(core)
    return mode


def test_calculate_score_max_at_zero_elapsed():
    """Score at elapsed=0 must equal MAX_ROUND_SCORE."""
    mode = _make_mode()
    score = mode._calculate_score(elapsed_ms=0, reveal_duration=12.0)
    from modes.emoji_reveal import EmojiRevealMode
    assert score == EmojiRevealMode.MAX_ROUND_SCORE


def test_calculate_score_min_at_full_duration():
    """Score at elapsed=full duration must equal MIN_ROUND_SCORE."""
    mode = _make_mode()
    from modes.emoji_reveal import EmojiRevealMode
    score = mode._calculate_score(
        elapsed_ms=int(12.0 * 1000),
        reveal_duration=12.0
    )
    assert score == EmojiRevealMode.MIN_ROUND_SCORE


def test_calculate_score_decreases_over_time():
    """Score must be monotonically non-increasing as elapsed time grows."""
    mode = _make_mode()
    reveal_duration = 12.0
    scores = [
        mode._calculate_score(elapsed_ms=t, reveal_duration=reveal_duration)
        for t in range(0, int(reveal_duration * 1000) + 100, 500)
    ]
    for i in range(1, len(scores)):
        assert scores[i] <= scores[i - 1], (
            f"Score increased from {scores[i-1]} to {scores[i]} at step {i}"
        )


def test_calculate_score_never_below_min():
    """Score must never go below MIN_ROUND_SCORE."""
    mode = _make_mode()
    from modes.emoji_reveal import EmojiRevealMode
    # elapsed way beyond the reveal window
    score = mode._calculate_score(elapsed_ms=999999, reveal_duration=12.0)
    assert score >= EmojiRevealMode.MIN_ROUND_SCORE


# ---------------------------------------------------------------------------
# _show_choices display test
# ---------------------------------------------------------------------------

def test_show_choices_includes_all_labels():
    """_show_choices must pass all four choice labels to the display."""
    mode = _make_mode()
    choices = ["SKULL", "GHOST", "SWORD", "SHIELD"]
    mode._show_choices(round_num=1, total_rounds=5, choices=choices)

    # Capture the calls made to update_status
    update_calls = mode.core.display.update_status.call_args_list
    assert update_calls, "update_status was never called"

    # Flatten all string arguments across all calls
    all_text = " ".join(
        arg for c in update_calls for arg in c.args if isinstance(arg, str)
    )
    for label in choices:
        assert label in all_text, f"Choice '{label}' not found in display output"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
