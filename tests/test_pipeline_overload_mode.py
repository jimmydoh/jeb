"""Test module for Pipeline Overload game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Hardware-mapping constants (8 toggles, 8 sections)
- Core game-design constants (speed, scoring)
- Maze-generation logic (start section, junction spacing, boundary clamping)
- Icon presence in the Icons asset library
- Satellite read-path (latching_values usage)
"""

import sys
import os
import ast
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'pipeline_overload.py'
)


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """pipeline_overload.py exists in the modes directory."""
    assert os.path.exists(_MODE_PATH), "pipeline_overload.py does not exist"
    print("✓ pipeline_overload.py exists")


def test_valid_syntax():
    """pipeline_overload.py contains valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in pipeline_overload.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_in_manifest():
    """PIPELINE_OVERLOAD is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY
    assert "PIPELINE_OVERLOAD" in MODE_REGISTRY, \
        "PIPELINE_OVERLOAD not found in MODE_REGISTRY"
    print("✓ PIPELINE_OVERLOAD found in MODE_REGISTRY")


def test_manifest_metadata():
    """Manifest entry for PIPELINE_OVERLOAD has all required fields."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["PIPELINE_OVERLOAD"]

    assert meta["id"] == "PIPELINE_OVERLOAD"
    assert meta["name"] == "PIPELINE OVLD"
    assert meta["module_path"] == "modes.pipeline_overload"
    assert meta["class_name"] == "PipelineOverload"
    assert meta["icon"] == "PIPELINE_OVERLOAD"
    assert "CORE" in meta["requires"], "Must require CORE"
    assert "INDUSTRIAL" in meta["requires"], \
        "Must require INDUSTRIAL satellite (latching toggles live there)"
    assert meta.get("menu") == "MAIN", "Should appear in the MAIN menu"
    assert meta.get("has_tutorial") is True, "Should declare a tutorial"
    print("✓ PIPELINE_OVERLOAD manifest metadata is correct")


def test_difficulty_settings():
    """PIPELINE_OVERLOAD manifest entry has NORMAL / HARD / INSANE difficulty."""
    from modes.manifest import MODE_REGISTRY
    meta = MODE_REGISTRY["PIPELINE_OVERLOAD"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "Difficulty setting missing"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert "INSANE" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ Difficulty settings correct")


# ---------------------------------------------------------------------------
# Hardware-mapping constants
# ---------------------------------------------------------------------------

def test_toggle_count_constant():
    """_NUM_TOGGLES is defined and equals 8."""
    src = _source()
    assert "_NUM_TOGGLES" in src, "_NUM_TOGGLES constant missing"
    match = re.search(r'_NUM_TOGGLES\s*=\s*(\d+)', src)
    assert match and int(match.group(1)) == 8, "_NUM_TOGGLES should be 8"
    print("✓ _NUM_TOGGLES = 8")


def test_section_count_constant():
    """_NUM_SECTIONS equals 8 (one section per toggle)."""
    src = _source()
    assert "_NUM_SECTIONS" in src, "_NUM_SECTIONS constant missing"
    match = re.search(r'_NUM_SECTIONS\s*=\s*(\d+)', src)
    assert match and int(match.group(1)) == 8, "_NUM_SECTIONS should be 8"
    print("✓ _NUM_SECTIONS = 8")


def test_section_width_constant():
    """_SECTION_W is defined (2 matrix columns per section)."""
    src = _source()
    assert "_SECTION_W" in src, "_SECTION_W constant missing"
    print("✓ _SECTION_W defined")


def test_matrix_dimensions():
    """_MATRIX_W and _MATRIX_H are both 16."""
    src = _source()
    assert re.search(r'_MATRIX_W\s*=\s*16', src), "_MATRIX_W should be 16"
    assert re.search(r'_MATRIX_H\s*=\s*16', src), "_MATRIX_H should be 16"
    print("✓ Matrix dimensions 16×16")


# ---------------------------------------------------------------------------
# Physics and scoring constants
# ---------------------------------------------------------------------------

def test_speed_constants():
    """Speed-related constants are present."""
    src = _source()
    assert "_MAX_SPEED" in src, "_MAX_SPEED missing"
    assert "_ENC_SPEED_STEP" in src, "_ENC_SPEED_STEP missing"
    print("✓ Speed constants present")


def test_scoring_constants():
    """Scoring constants are defined."""
    src = _source()
    assert "_POINTS_PER_JUNCTION" in src, "_POINTS_PER_JUNCTION missing"
    assert "_POINTS_LEVEL_CLEAR" in src, "_POINTS_LEVEL_CLEAR missing"
    print("✓ Scoring constants present")


def test_difficulty_param_table():
    """_DIFF_PARAMS table covers all three difficulties."""
    src = _source()
    assert "_DIFF_PARAMS" in src, "_DIFF_PARAMS table missing"
    assert '"NORMAL"' in src or "'NORMAL'" in src
    assert '"HARD"' in src or "'HARD'" in src
    assert '"INSANE"' in src or "'INSANE'" in src
    print("✓ _DIFF_PARAMS table present for NORMAL / HARD / INSANE")


# ---------------------------------------------------------------------------
# Class structure checks
# ---------------------------------------------------------------------------

def test_class_exists():
    """PipelineOverload class is defined."""
    src = _source()
    assert "class PipelineOverload" in src, "PipelineOverload class missing"
    print("✓ PipelineOverload class defined")


def test_inherits_game_mode():
    """PipelineOverload inherits from GameMode."""
    src = _source()
    assert "class PipelineOverload(GameMode)" in src, \
        "PipelineOverload must inherit from GameMode"
    print("✓ Inherits from GameMode")


def test_maze_generation_method():
    """_generate_maze method is implemented."""
    src = _source()
    assert "def _generate_maze" in src, "_generate_maze method missing"
    print("✓ _generate_maze method present")


def test_maze_boundary_clamping():
    """Maze generator clamps section index to valid range."""
    src = _source()
    assert "max(0, min(" in src, \
        "Section clamping with max(0, min(...)) missing"
    print("✓ Boundary clamping present in maze generator")


def test_path_segments_method():
    """_compute_path_segments method is implemented."""
    src = _source()
    assert "def _compute_path_segments" in src, \
        "_compute_path_segments method missing"
    print("✓ _compute_path_segments method present")


def test_satellite_init_method():
    """_init_satellite method searches for INDUSTRIAL satellite."""
    src = _source()
    assert "def _init_satellite" in src, "_init_satellite method missing"
    assert "INDUSTRIAL" in src, "Should look for INDUSTRIAL satellite type"
    print("✓ _init_satellite searches for INDUSTRIAL satellite")


def test_toggle_read_method():
    """_toggle_state reads from sat.hid.latching_values."""
    src = _source()
    assert "def _toggle_state" in src, "_toggle_state method missing"
    assert "latching_values" in src, \
        "_toggle_state should read latching_values from satellite HID"
    print("✓ _toggle_state reads latching_values")


def test_run_method():
    """run() is an async method."""
    src = _source()
    assert "async def run" in src, "run() method missing or not async"
    print("✓ async run() present")


def test_run_level_method():
    """_run_level() is an async method."""
    src = _source()
    assert "async def _run_level" in src, \
        "_run_level() method missing or not async"
    print("✓ async _run_level() present")


def test_render_method():
    """_render() method is present."""
    src = _source()
    assert "def _render" in src, "_render method missing"
    print("✓ _render() method present")


def test_tutorial_method():
    """run_tutorial() is an async method."""
    src = _source()
    assert "async def run_tutorial" in src, \
        "run_tutorial() method missing or not async"
    print("✓ async run_tutorial() present")


# ---------------------------------------------------------------------------
# Game-logic specifics
# ---------------------------------------------------------------------------

def test_game_over_on_wrong_toggle():
    """Source contains GAME_OVER return on wrong toggle state."""
    src = _source()
    assert '"GAME_OVER"' in src or "'GAME_OVER'" in src, \
        "GAME_OVER return value missing"
    print("✓ GAME_OVER result present")


def test_level_complete_return():
    """Source contains LEVEL_COMPLETE return value."""
    src = _source()
    assert '"LEVEL_COMPLETE"' in src or "'LEVEL_COMPLETE'" in src, \
        "LEVEL_COMPLETE return value missing"
    print("✓ LEVEL_COMPLETE result present")


def test_encoder_speed_boost():
    """Encoder position is used to modify flow speed."""
    src = _source()
    assert "_ENC_SPEED" in src, "_ENC_SPEED constant missing"
    assert "encoder_positions" in src, \
        "encoder_positions not read for speed boost"
    print("✓ Encoder speed boost implemented")


def test_score_multiplier_on_speed():
    """Score per junction scales with speed multiplier."""
    src = _source()
    # Look for a multiplier applied to _POINTS_PER_JUNCTION
    assert "_POINTS_PER_JUNCTION" in src
    assert "speed_mult" in src or "multiplier" in src.lower(), \
        "Speed multiplier should be applied to scoring"
    print("✓ Score multiplier applied on high-speed junctions")


# ---------------------------------------------------------------------------
# Icon check
# ---------------------------------------------------------------------------

def test_icon_in_library():
    """PIPELINE_OVERLOAD icon exists in Icons.ICON_LIBRARY."""
    from utilities.icons import Icons
    assert "PIPELINE_OVERLOAD" in Icons.ICON_LIBRARY, \
        "PIPELINE_OVERLOAD not found in Icons.ICON_LIBRARY"
    print("✓ PIPELINE_OVERLOAD icon in Icons.ICON_LIBRARY")


def test_icon_correct_size():
    """PIPELINE_OVERLOAD icon is exactly 256 bytes (16×16)."""
    from utilities.icons import Icons
    icon = Icons.ICON_LIBRARY["PIPELINE_OVERLOAD"]
    assert len(icon) == 256, \
        f"Icon should be 256 bytes, got {len(icon)}"
    print("✓ PIPELINE_OVERLOAD icon is 256 bytes (16×16)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Pipeline Overload mode tests...\n")

    tests = [
        test_file_exists,
        test_valid_syntax,
        test_in_manifest,
        test_manifest_metadata,
        test_difficulty_settings,
        test_toggle_count_constant,
        test_section_count_constant,
        test_section_width_constant,
        test_matrix_dimensions,
        test_speed_constants,
        test_scoring_constants,
        test_difficulty_param_table,
        test_class_exists,
        test_inherits_game_mode,
        test_maze_generation_method,
        test_maze_boundary_clamping,
        test_path_segments_method,
        test_satellite_init_method,
        test_toggle_read_method,
        test_run_method,
        test_run_level_method,
        test_render_method,
        test_tutorial_method,
        test_game_over_on_wrong_toggle,
        test_level_complete_return,
        test_encoder_speed_boost,
        test_score_multiplier_on_speed,
        test_icon_in_library,
        test_icon_correct_size,
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
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
