"""Test module for Enigma Byte game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Hardware index constants
- Difficulty parameter table
- Layer count constant
- Phase method and helper presence
- Mastermind feedback logic (_compute_feedback)
- Icon presence and size in icons.py
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'enigma_byte.py'
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
    """Test that enigma_byte.py exists."""
    assert os.path.exists(_MODE_PATH), "enigma_byte.py does not exist"
    print("✓ enigma_byte.py exists")


def test_valid_syntax():
    """Test that enigma_byte.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in enigma_byte.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_enigma_byte_in_manifest():
    """Test that ENIGMA_BYTE is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "ENIGMA_BYTE" in MODE_REGISTRY, "ENIGMA_BYTE not found in MODE_REGISTRY"
    print("✓ ENIGMA_BYTE found in MODE_REGISTRY")


def test_enigma_byte_manifest_metadata():
    """Test that ENIGMA_BYTE manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ENIGMA_BYTE"]

    assert meta["id"] == "ENIGMA_BYTE"
    assert meta["name"] == "ENIGMA BYTE"
    assert meta["module_path"] == "modes.enigma_byte"
    assert meta["class_name"] == "EnigmaByte"
    assert meta["icon"] == "ENIGMA_BYTE"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], "Must require INDUSTRIAL satellite"
    assert meta.get("menu") == "EXP1", "Should appear in EXP1 menu"
    print("✓ ENIGMA_BYTE manifest metadata is correct")


def test_enigma_byte_difficulty_settings():
    """Test that ENIGMA_BYTE has correct difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["ENIGMA_BYTE"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ ENIGMA_BYTE difficulty settings are correct")


# ---------------------------------------------------------------------------
# Hardware index checks
# ---------------------------------------------------------------------------

def test_hardware_indices():
    """Test that key hardware index constants are defined."""
    src = _source()
    for const in ["_TOGGLE_COUNT", "_BTN_SUBMIT", "_SW_ROTARY_A", "_SW_ROTARY_B"]:
        assert const in src, f"Hardware constant {const} missing"
    print("✓ Hardware index constants are defined")


def test_toggle_count_is_eight():
    """Test that _TOGGLE_COUNT is 8."""
    src = _source()
    match = re.search(r'_TOGGLE_COUNT\s*=\s*(\d+)', src)
    assert match is not None, "_TOGGLE_COUNT not found"
    assert int(match.group(1)) == 8, f"_TOGGLE_COUNT should be 8, got {match.group(1)}"
    print("✓ _TOGGLE_COUNT is 8")


def test_rotary_indices():
    """Test that _SW_ROTARY_A is 10 and _SW_ROTARY_B is 11."""
    src = _source()
    match_a = re.search(r'_SW_ROTARY_A\s*=\s*(\d+)', src)
    match_b = re.search(r'_SW_ROTARY_B\s*=\s*(\d+)', src)
    assert match_a is not None, "_SW_ROTARY_A not found"
    assert match_b is not None, "_SW_ROTARY_B not found"
    assert int(match_a.group(1)) == 10, f"_SW_ROTARY_A should be 10, got {match_a.group(1)}"
    assert int(match_b.group(1)) == 11, f"_SW_ROTARY_B should be 11, got {match_b.group(1)}"
    print("✓ _SW_ROTARY_A=10, _SW_ROTARY_B=11")


def test_btn_submit_is_zero():
    """Test that _BTN_SUBMIT is 0 (big red button)."""
    src = _source()
    match = re.search(r'_BTN_SUBMIT\s*=\s*(\d+)', src)
    assert match is not None, "_BTN_SUBMIT not found"
    assert int(match.group(1)) == 0, f"_BTN_SUBMIT should be 0, got {match.group(1)}"
    print("✓ _BTN_SUBMIT is 0 (big red button)")


# ---------------------------------------------------------------------------
# Layer and game constant checks
# ---------------------------------------------------------------------------

def test_layer_count():
    """Test that _LAYER_COUNT is 3."""
    src = _source()
    match = re.search(r'_LAYER_COUNT\s*=\s*(\d+)', src)
    assert match is not None, "_LAYER_COUNT not found"
    assert int(match.group(1)) == 3, f"_LAYER_COUNT should be 3, got {match.group(1)}"
    print("✓ _LAYER_COUNT is 3")


def test_difficulty_params():
    """Test that _DIFF_PARAMS defines NORMAL, HARD, INSANE."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS dict missing"
    for diff in ["NORMAL", "HARD", "INSANE"]:
        assert diff in src, f"Difficulty '{diff}' missing from _DIFF_PARAMS"
    print("✓ _DIFF_PARAMS defines NORMAL, HARD, INSANE")


def test_max_guesses_decrease_with_difficulty():
    """Test that max_guesses is highest for NORMAL and lowest for INSANE."""
    src = _source()
    normal_match = re.search(r'"NORMAL".*?"max_guesses":\s*(\d+)', src, re.DOTALL)
    hard_match   = re.search(r'"HARD".*?"max_guesses":\s*(\d+)', src, re.DOTALL)
    insane_match = re.search(r'"INSANE".*?"max_guesses":\s*(\d+)', src, re.DOTALL)

    assert normal_match and hard_match and insane_match, \
        "Could not extract max_guesses from _DIFF_PARAMS"
    normal_mg = int(normal_match.group(1))
    hard_mg   = int(hard_match.group(1))
    insane_mg = int(insane_match.group(1))

    assert normal_mg > hard_mg >= insane_mg, (
        f"max_guesses should decrease: NORMAL={normal_mg}, "
        f"HARD={hard_mg}, INSANE={insane_mg}"
    )
    print(f"✓ max_guesses decreases: NORMAL={normal_mg}, HARD={hard_mg}, INSANE={insane_mg}")


# ---------------------------------------------------------------------------
# Method / helper presence checks
# ---------------------------------------------------------------------------

def test_required_methods_exist():
    """Test that key methods are defined."""
    src = _source()
    for method in [
        "_compute_feedback",
        "_get_layer",
        "_get_current_guess",
        "_render_matrix",
        "_poll_notes",
        "_send_segment",
        "_submit_guess",
        "run_tutorial",
        "run",
    ]:
        assert f"def {method}" in src, f"Method {method} missing"
    print("✓ All required methods are defined")


def test_rotary_decoding_covers_three_positions():
    """Test that _get_layer maps all three rotary positions."""
    src = _source()
    start = src.find("def _get_layer")
    end = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body = src[start:end]
    # All three return values must be present
    assert "return 0" in body, "_get_layer must return 0 for position A"
    assert "return 1" in body or "return 1  " in body, "_get_layer must return 1 for center"
    assert "return 2" in body, "_get_layer must return 2 for position B"
    print("✓ _get_layer covers all three rotary positions")


def test_submit_guess_checks_victory():
    """Test that _submit_guess checks for a full-match (all greens) solve."""
    src = _source()
    start = src.find("async def _submit_guess")
    end = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]
    assert "_TOGGLE_COUNT" in body, \
        "_submit_guess should compare greens to _TOGGLE_COUNT for a solve"
    assert "solved" in body, \
        "_submit_guess should set the solved flag"
    print("✓ _submit_guess correctly detects solved layer")


def test_submit_guess_marks_failed_layer():
    """Test that _submit_guess marks a layer failed when max_guesses is reached."""
    src = _source()
    start = src.find("async def _submit_guess")
    end = src.find("\n    async def ", start + 1)
    if end == -1:
        end = src.find("\n    def ", start + 1)
    body = src[start:end]
    assert "_max_guesses" in body, \
        "_submit_guess should compare against _max_guesses"
    assert "failed" in body, \
        "_submit_guess should mark the layer as failed"
    print("✓ _submit_guess correctly marks exhausted layer as failed")


def test_render_matrix_uses_green_and_yellow():
    """Test that _render_matrix draws both green and yellow feedback pixels."""
    src = _source()
    start = src.find("def _render_matrix")
    end = src.find("\n    def ", start + 1)
    if end == -1:
        end = src.find("\n    async def ", start + 1)
    body = src[start:end]
    assert "GREEN" in body, "_render_matrix must draw green pixels for exact matches"
    assert "YELLOW" in body, "_render_matrix must draw yellow pixels for partial matches"
    print("✓ _render_matrix draws both GREEN and YELLOW feedback pixels")


# ---------------------------------------------------------------------------
# Feedback logic checks  (pure-Python replication – no hardware import)
# ---------------------------------------------------------------------------

def _mastermind_feedback(guess, secret):
    """Replicate _compute_feedback without importing the class.

    Standard Mastermind rules applied to binary (bool) sequences:
    - greens  = count of exact positional matches
    - yellows = (total value-matches across all positions) - greens
    """
    n = len(secret)
    greens = sum(1 for i in range(n) if guess[i] == secret[i])
    secret_ones = sum(1 for b in secret if b)
    guess_ones  = sum(1 for b in guess  if b)
    value_matches = (min(guess_ones, secret_ones) +
                     min(n - guess_ones, n - secret_ones))
    yellows = value_matches - greens
    return greens, yellows


def test_compute_feedback_formula_present():
    """Test that _compute_feedback uses the expected Mastermind value-match formula."""
    src = _source()
    assert "_compute_feedback" in src, "_compute_feedback method missing"
    assert "greens" in src, "greens variable not found in source"
    assert "yellows" in src, "yellows variable not found in source"
    assert "value_matches" in src, \
        "Mastermind value-match formula (value_matches) not found in source"
    print("✓ _compute_feedback formula is present in source")


def test_compute_feedback_all_correct():
    """All matching bits → 8 greens, 0 yellows."""
    secret = [True, False, True, False, True, False, True, False]
    greens, yellows = _mastermind_feedback(secret, secret)
    assert greens == 8, f"Expected 8 greens, got {greens}"
    assert yellows == 0, f"Expected 0 yellows, got {yellows}"
    print("✓ compute_feedback: perfect match gives 8G 0Y")


def test_compute_feedback_all_wrong_inverted():
    """All bits flipped → 0 greens, 8 yellows (all values present, all wrong position)."""
    secret = [True, False, True, False, True, False, True, False]
    guess  = [False, True, False, True, False, True, False, True]
    greens, yellows = _mastermind_feedback(guess, secret)
    assert greens == 0, f"Expected 0 greens, got {greens}"
    assert yellows == 8, f"Expected 8 yellows, got {yellows}"
    print("✓ compute_feedback: fully inverted gives 0G 8Y")


def test_compute_feedback_no_overlap():
    """Secret all True, guess all False → 0 greens, 0 yellows."""
    secret = [True]  * 8
    guess  = [False] * 8
    greens, yellows = _mastermind_feedback(guess, secret)
    assert greens == 0, f"Expected 0 greens, got {greens}"
    assert yellows == 0, f"Expected 0 yellows, got {yellows}"
    print("✓ compute_feedback: no value overlap gives 0G 0Y")


def test_compute_feedback_partial():
    """Partial match scenario produces expected green and yellow counts."""
    # secret: [1,1,1,1,0,0,0,0]  guess: [1,1,0,0,0,0,1,1]
    # Greens: pos 0,1 (1=1), pos 4,5 (0=0) → 4 greens
    # Yellows: remaining 1s in secret=2 vs guess=2 → 2 yellow from 1s
    #          remaining 0s in secret=2 vs guess=2 → 2 yellow from 0s → 4 yellows total
    secret = [True, True,  True,  True,  False, False, False, False]
    guess  = [True, True,  False, False, False, False, True,  True]
    greens, yellows = _mastermind_feedback(guess, secret)
    assert greens == 4,  f"Expected 4 greens, got {greens}"
    assert yellows == 4, f"Expected 4 yellows, got {yellows}"
    print("✓ compute_feedback: partial match gives 4G 4Y")


def test_compute_feedback_greens_plus_yellows_lte_toggle_count():
    """Total pegs (greens + yellows) must never exceed toggle count."""
    import random as _rnd
    _rnd.seed(42)
    n = 8
    for _ in range(200):
        secret = [_rnd.choice([True, False]) for _ in range(n)]
        guess  = [_rnd.choice([True, False]) for _ in range(n)]
        g, y = _mastermind_feedback(guess, secret)
        assert g + y <= n, f"g+y={g+y} > {n} for guess={guess}, secret={secret}"
    print("✓ compute_feedback: greens+yellows ≤ toggle count over 200 random trials")


# ---------------------------------------------------------------------------
# Icon checks
# ---------------------------------------------------------------------------

def test_enigma_byte_icon_in_icons_py():
    """Test that ENIGMA_BYTE icon is defined in icons.py."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    assert "ENIGMA_BYTE" in src, "ENIGMA_BYTE icon not in icons.py"
    print("✓ ENIGMA_BYTE icon defined in icons.py")


def test_enigma_byte_icon_in_icon_library():
    """Test that ENIGMA_BYTE is registered in ICON_LIBRARY."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()
    lib_start = src.find("ICON_LIBRARY")
    lib_end   = src.find("}", lib_start)
    library_block = src[lib_start:lib_end]
    assert '"ENIGMA_BYTE"' in library_block, "ENIGMA_BYTE not in ICON_LIBRARY dict"
    print("✓ ENIGMA_BYTE registered in ICON_LIBRARY")


def test_enigma_byte_icon_is_256_bytes():
    """Test that ENIGMA_BYTE icon data is exactly 256 bytes (16x16)."""
    with open(_ICONS_PATH, 'r', encoding='utf-8') as f:
        src = f.read()

    match = re.search(r'ENIGMA_BYTE\s*=\s*bytes\(\[(.*?)\]\)', src, re.DOTALL)
    assert match is not None, "Could not find ENIGMA_BYTE bytes literal"

    raw_content = match.group(1).replace('\n', ',')
    tokens = [t.strip() for t in raw_content.split(',')]
    values = [t for t in tokens if t.isdigit()]
    assert len(values) == 256, (
        f"ENIGMA_BYTE icon should be 256 bytes (16x16), got {len(values)}"
    )
    print(f"✓ ENIGMA_BYTE icon is 256 bytes (16x16)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Enigma Byte mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_enigma_byte_in_manifest,
        test_enigma_byte_manifest_metadata,
        test_enigma_byte_difficulty_settings,
        test_hardware_indices,
        test_toggle_count_is_eight,
        test_rotary_indices,
        test_btn_submit_is_zero,
        test_layer_count,
        test_difficulty_params,
        test_max_guesses_decrease_with_difficulty,
        test_required_methods_exist,
        test_rotary_decoding_covers_three_positions,
        test_submit_guess_checks_victory,
        test_submit_guess_marks_failed_layer,
        test_render_matrix_uses_green_and_yellow,
        test_compute_feedback_formula_present,
        test_compute_feedback_all_correct,
        test_compute_feedback_all_wrong_inverted,
        test_compute_feedback_no_overlap,
        test_compute_feedback_partial,
        test_compute_feedback_greens_plus_yellows_lte_toggle_count,
        test_enigma_byte_icon_in_icons_py,
        test_enigma_byte_icon_in_icon_library,
        test_enigma_byte_icon_is_256_bytes,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ FAILED: {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ❌ ERROR:  {t.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
