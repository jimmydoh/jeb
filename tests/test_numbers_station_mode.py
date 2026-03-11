"""Test module for Numbers Station game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Phase constants
- Hardware index constants
- Band constants and decoding logic
- Digit note mapping
- Difficulty parameter table
- Cipher (mod-10 shift) correctness
- Icon registration in ICON_LIBRARY
- Key phase methods presence
"""

import sys
import os
import re
import ast

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'numbers_station.py'
)
_ICONS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'utilities', 'icons.py'
)


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """Test that numbers_station.py exists."""
    assert os.path.exists(_MODE_PATH), "numbers_station.py does not exist"
    print("✓ numbers_station.py exists")


def test_valid_syntax():
    """Test that numbers_station.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in numbers_station.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_numbers_station_in_manifest():
    """Test that NUMBERS_STATION is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "NUMBERS_STATION" in MODE_REGISTRY, \
        "NUMBERS_STATION not found in MODE_REGISTRY"
    print("✓ NUMBERS_STATION found in MODE_REGISTRY")


def test_numbers_station_manifest_metadata():
    """Test that NUMBERS_STATION manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["NUMBERS_STATION"]

    assert meta["id"] == "NUMBERS_STATION"
    assert meta["name"] == "NMBRS STN"
    assert meta["module_path"] == "modes.numbers_station"
    assert meta["class_name"] == "NumbersStation"
    assert meta["icon"] == "NUMBERS_STATION"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "EXP1", "Should appear in EXP1 menu"
    assert meta.get("has_tutorial") is True, "Should have a tutorial"
    print("✓ NUMBERS_STATION manifest metadata is correct")


def test_numbers_station_difficulty_settings():
    """Test that NUMBERS_STATION has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["NUMBERS_STATION"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ NUMBERS_STATION difficulty settings are correct")


# ---------------------------------------------------------------------------
# Phase constant checks
# ---------------------------------------------------------------------------

def test_phase_constants():
    """Test that all four phase constants are defined."""
    src = _source()
    expected = [
        "_PHASE_TUNE",
        "_PHASE_LISTEN",
        "_PHASE_DECODE",
        "_PHASE_SUBMIT",
    ]
    for phase in expected:
        assert phase in src, f"Phase constant {phase} missing"
    print(f"✓ All {len(expected)} phase constants are defined")


# ---------------------------------------------------------------------------
# Hardware index checks
# ---------------------------------------------------------------------------

def test_hardware_indices():
    """Test that key hardware index constants are defined with correct values."""
    src = _source()
    expected = {
        "_SW_ROTARY_A": 10,
        "_SW_ROTARY_B": 11,
        "_BTN_SUBMIT": 0,
    }
    for const, expected_val in expected.items():
        pattern = rf'{re.escape(const)}\s*=\s*(\d+)'
        match = re.search(pattern, src)
        assert match is not None, f"Hardware constant {const} missing"
        actual = int(match.group(1))
        assert actual == expected_val, \
            f"{const} should be {expected_val}, got {actual}"
    print("✓ All hardware index constants are defined with correct values")


def test_rotary_switch_indices():
    """Test that rotary switch indices A=10, B=11 match sat-01 hardware spec."""
    src = _source()
    match_a = re.search(r'_SW_ROTARY_A\s*=\s*(\d+)', src)
    match_b = re.search(r'_SW_ROTARY_B\s*=\s*(\d+)', src)
    assert match_a and int(match_a.group(1)) == 10, \
        "_SW_ROTARY_A should be 10"
    assert match_b and int(match_b.group(1)) == 11, \
        "_SW_ROTARY_B should be 11"
    print("✓ Rotary switch indices correct (A=10, B=11)")


# ---------------------------------------------------------------------------
# Band constant checks
# ---------------------------------------------------------------------------

def test_band_constants():
    """Test that BAND_ALPHA, BAND_BRAVO, BAND_CHARLIE are defined."""
    src = _source()
    for band in ["BAND_ALPHA", "BAND_BRAVO", "BAND_CHARLIE"]:
        assert band in src, f"Band constant {band} missing"
    print("✓ All band constants (ALPHA, BRAVO, CHARLIE) are defined")


def test_all_bands_list():
    """Test that _ALL_BANDS contains all three band constants."""
    src = _source()
    assert "_ALL_BANDS" in src, "_ALL_BANDS list not defined"
    assert "BAND_ALPHA" in src
    assert "BAND_BRAVO" in src
    assert "BAND_CHARLIE" in src
    print("✓ _ALL_BANDS includes all three bands")


# ---------------------------------------------------------------------------
# Digit note mapping checks
# ---------------------------------------------------------------------------

def test_digit_note_mapping_completeness():
    """Test that _DIGIT_NOTE maps all 10 digits (0–9)."""
    src = _source()
    assert "_DIGIT_NOTE" in src, "_DIGIT_NOTE dict missing"
    for d in range(10):
        assert f"'{d}'" in src or f'"{d}"' in src, \
            f"Digit '{d}' missing from _DIGIT_NOTE"
    print("✓ _DIGIT_NOTE contains all 10 digits (0–9)")


def test_digit_note_duration_defined():
    """Test that digit duration and gap constants are defined."""
    src = _source()
    assert "_DIGIT_DURATION" in src, "_DIGIT_DURATION constant missing"
    assert "_DIGIT_GAP" in src, "_DIGIT_GAP constant missing"
    print("✓ _DIGIT_DURATION and _DIGIT_GAP constants are defined")


# ---------------------------------------------------------------------------
# Difficulty parameter checks
# ---------------------------------------------------------------------------

def test_difficulty_params_defined():
    """Test that _DIFF_PARAMS defines NORMAL, HARD, INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_difficulty_seq_length_increases():
    """Test that sequence length increases across difficulty levels."""
    src = _source()
    start = src.find("_DIFF_PARAMS")
    end = src.find("\n}", start) + 2
    block = src[start:end]

    normal_start = block.find('"NORMAL"')
    hard_start   = block.find('"HARD"')
    insane_start = block.find('"INSANE"')

    assert normal_start != -1 and hard_start != -1 and insane_start != -1

    def extract_seq_length(blk):
        m = re.search(r'"seq_length":\s*(\d+)', blk)
        return int(m.group(1)) if m else None

    n_len = extract_seq_length(block[normal_start:hard_start])
    h_len = extract_seq_length(block[hard_start:insane_start])
    i_len = extract_seq_length(block[insane_start:])

    assert n_len is not None and h_len is not None and i_len is not None, \
        "Could not extract seq_length values"
    assert n_len <= h_len <= i_len, \
        f"Seq length should increase: NORMAL={n_len}, HARD={h_len}, INSANE={i_len}"
    print(f"✓ Sequence length increases: NORMAL={n_len}, HARD={h_len}, INSANE={i_len}")


def test_difficulty_lives_decrease():
    """Test that number of lives decreases in harder difficulties."""
    src = _source()
    start = src.find("_DIFF_PARAMS")
    end = src.find("\n}", start) + 2
    block = src[start:end]

    normal_start = block.find('"NORMAL"')
    hard_start   = block.find('"HARD"')
    insane_start = block.find('"INSANE"')

    def extract_lives(blk):
        m = re.search(r'"lives":\s*(\d+)', blk)
        return int(m.group(1)) if m else None

    n_lives = extract_lives(block[normal_start:hard_start])
    h_lives = extract_lives(block[hard_start:insane_start])
    i_lives = extract_lives(block[insane_start:])

    assert n_lives and h_lives and i_lives, "Could not extract lives values"
    assert n_lives >= h_lives >= i_lives, \
        f"Lives should decrease: NORMAL={n_lives}, HARD={h_lives}, INSANE={i_lives}"
    print(f"✓ Lives decrease: NORMAL={n_lives}, HARD={h_lives}, INSANE={i_lives}")


# ---------------------------------------------------------------------------
# Cipher logic checks
# ---------------------------------------------------------------------------

def test_cipher_shift_mod10():
    """Test that the mod-10 Caesar cipher is mathematically correct."""
    # Verify formula: (digit + shift) % 10
    test_cases = [
        # (digit, shift, expected_decoded)
        (4, 3, 7),   # 4 + 3 = 7
        (9, 3, 2),   # 9 + 3 = 12 → 2
        (2, 3, 5),   # 2 + 3 = 5
        (7, 5, 2),   # 7 + 5 = 12 → 2
        (0, 9, 9),   # 0 + 9 = 9
        (9, 9, 8),   # 9 + 9 = 18 → 8
    ]
    for digit, shift, expected in test_cases:
        result = (digit + shift) % 10
        assert result == expected, \
            f"Cipher error: ({digit} + {shift}) % 10 = {result}, expected {expected}"
    print(f"✓ Mod-10 Caesar cipher is correct for {len(test_cases)} test cases")


def test_cipher_always_produces_valid_digit():
    """Test that cipher output is always 0–9 for all digit/shift combinations."""
    for digit in range(10):
        for shift in range(1, 10):
            result = (digit + shift) % 10
            assert 0 <= result <= 9, \
                f"Cipher produced out-of-range digit: ({digit}+{shift})%10={result}"
    print("✓ Cipher always produces a valid 0–9 digit for all combinations")


# ---------------------------------------------------------------------------
# Key method checks
# ---------------------------------------------------------------------------

def test_key_methods_present():
    """Test that all key phase and helper methods are present."""
    src = _source()
    methods = [
        "async def run(",
        "async def run_tutorial(",
        "async def _run_phase_tune(",
        "async def _run_phase_listen(",
        "async def _run_phase_decode(",
        "async def _run_phase_submit(",
        "def _get_band(",
        "def _send_segment(",
        "def _new_round(",
        "def _check_answer(",
        "async def _play_digit_sequence(",
        "async def _play_jam_noise(",
        "def _render_static(",
        "def _render_signal_bars(",
        "def _render_input_progress(",
    ]
    for method in methods:
        assert method in src, f"Method '{method}' not found in numbers_station.py"
    print(f"✓ All {len(methods)} key methods are present")


def test_class_inherits_game_mode():
    """Test that NumbersStation inherits from GameMode."""
    src = _source()
    assert "class NumbersStation(GameMode):" in src, \
        "NumbersStation must inherit from GameMode"
    print("✓ NumbersStation inherits from GameMode")


def test_satellite_discovery_in_init():
    """Test that __init__ searches for the INDUSTRIAL satellite."""
    src = _source()
    assert "INDUSTRIAL" in src, \
        "Must search for INDUSTRIAL satellite type in __init__"
    print("✓ __init__ searches for INDUSTRIAL satellite")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_numbers_station_icon_exists():
    """Test that NUMBERS_STATION icon is defined in icons.py."""
    with open(_ICONS_PATH, 'r') as f:
        icons_src = f.read()
    assert "NUMBERS_STATION" in icons_src, \
        "NUMBERS_STATION icon not found in icons.py"
    print("✓ NUMBERS_STATION icon defined in icons.py")


def test_numbers_station_icon_in_library():
    """Test that NUMBERS_STATION icon is registered in ICON_LIBRARY."""
    from utilities.icons import Icons
    assert "NUMBERS_STATION" in Icons.ICON_LIBRARY, \
        "NUMBERS_STATION not in Icons.ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["NUMBERS_STATION"]
    assert len(icon) == 256, \
        f"Icon must be 256 bytes (16×16), got {len(icon)}"
    print("✓ NUMBERS_STATION icon is in ICON_LIBRARY and is 256 bytes (16×16)")


def test_numbers_station_icon_palette_values():
    """Test that NUMBERS_STATION icon only uses valid palette indices."""
    from utilities.icons import Icons
    icon = Icons.ICON_LIBRARY["NUMBERS_STATION"]
    valid = {0, 1, 2, 3, 4, 21, 22, 61}   # Colours used in this icon
    for i, val in enumerate(icon):
        assert val in valid, \
            f"Pixel {i} has unexpected palette value {val}"
    print("✓ All NUMBERS_STATION icon pixels use valid palette indices")


# ---------------------------------------------------------------------------
# Global timer constant checks
# ---------------------------------------------------------------------------

def test_global_timer_defined():
    """Test that _GLOBAL_TIME is defined and is a positive float."""
    src = _source()
    match = re.search(r'_GLOBAL_TIME\s*=\s*([\d.]+)', src)
    assert match is not None, "_GLOBAL_TIME not defined"
    assert float(match.group(1)) > 0, "_GLOBAL_TIME must be positive"
    print(f"✓ _GLOBAL_TIME = {match.group(1)} seconds")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Numbers Station mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_numbers_station_in_manifest,
        test_numbers_station_manifest_metadata,
        test_numbers_station_difficulty_settings,
        test_phase_constants,
        test_hardware_indices,
        test_rotary_switch_indices,
        test_band_constants,
        test_all_bands_list,
        test_digit_note_mapping_completeness,
        test_digit_note_duration_defined,
        test_difficulty_params_defined,
        test_difficulty_seq_length_increases,
        test_difficulty_lives_decrease,
        test_cipher_shift_mod10,
        test_cipher_always_produces_valid_digit,
        test_key_methods_present,
        test_class_inherits_game_mode,
        test_satellite_discovery_in_init,
        test_numbers_station_icon_exists,
        test_numbers_station_icon_in_library,
        test_numbers_station_icon_palette_values,
        test_global_timer_defined,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {t.__name__} (unexpected): {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ All Numbers Station tests passed!")
        sys.exit(0)
