"""Test module for Flux Scavenger game mode.

Validates:
- Mode file existence and valid Python syntax
- Manifest registration with correct metadata
- Level data integrity (three 256-element tuples with valid tile types)
- Tile-toggle mapping completeness
- Physics and collision helper correctness
- Gravity mode constant definitions
- Hardware index constants
"""

import sys
import os
import ast

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

_MODE_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'src', 'modes', 'flux_scavenger.py'
)


def _source():
    with open(_MODE_PATH, 'r') as f:
        return f.read()


# ---------------------------------------------------------------------------
# File and syntax checks
# ---------------------------------------------------------------------------

def test_file_exists():
    """Test that flux_scavenger.py exists in the modes directory."""
    assert os.path.exists(_MODE_PATH), "flux_scavenger.py does not exist"
    print("✓ flux_scavenger.py exists")


def test_valid_syntax():
    """Test that flux_scavenger.py has valid Python syntax."""
    src = _source()
    try:
        ast.parse(src)
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in flux_scavenger.py: {e}")
    print("✓ Valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------

def test_flux_scavenger_in_manifest():
    """Test that FLUX_SCAVENGER is registered in the mode manifest."""
    from modes.manifest import MODE_REGISTRY

    assert "FLUX_SCAVENGER" in MODE_REGISTRY, (
        "FLUX_SCAVENGER not found in MODE_REGISTRY"
    )
    print("✓ FLUX_SCAVENGER found in MODE_REGISTRY")


def test_flux_scavenger_manifest_metadata():
    """Test that the FLUX_SCAVENGER manifest entry has all required fields."""
    from modes.manifest import MODE_REGISTRY

    meta = MODE_REGISTRY["FLUX_SCAVENGER"]

    assert meta["id"] == "FLUX_SCAVENGER"
    assert meta["name"] == "FLUX SCAVENGER"
    assert meta["module_path"] == "modes.flux_scavenger"
    assert meta["class_name"] == "FluxScavenger"
    assert meta["icon"] == "FLUX_SCAVENGER"
    assert "CORE" in meta["requires"], "FLUX_SCAVENGER must require CORE"
    assert "INDUSTRIAL" in meta["requires"], (
        "FLUX_SCAVENGER must require INDUSTRIAL satellite"
    )
    assert meta.get("menu") == "EXP1", "FLUX_SCAVENGER should appear in EXP1 menu"
    assert meta.get("has_tutorial") is True, "FLUX_SCAVENGER should have a tutorial"
    print("✓ FLUX_SCAVENGER manifest metadata is correct")


def test_flux_scavenger_difficulty_settings():
    """Test that FLUX_SCAVENGER has the expected difficulty setting."""
    from modes.manifest import MODE_REGISTRY

    meta = MODE_REGISTRY["FLUX_SCAVENGER"]
    settings = meta.get("settings", [])

    diff = next((s for s in settings if s["key"] == "difficulty"), None)
    assert diff is not None, "FLUX_SCAVENGER must have a difficulty setting"
    assert diff["label"] == "DIFF"
    assert "NORMAL" in diff["options"]
    assert "HARD" in diff["options"]
    assert diff["default"] == "NORMAL"
    print("✓ FLUX_SCAVENGER difficulty settings are correct")


# ---------------------------------------------------------------------------
# Class and constant checks (source inspection, no hardware imports)
# ---------------------------------------------------------------------------

def test_class_defined():
    """Test that the FluxScavenger class is defined in the module."""
    src = _source()
    assert "class FluxScavenger" in src, (
        "FluxScavenger class not found in flux_scavenger.py"
    )
    print("✓ FluxScavenger class is defined")


def test_gravity_mode_constants():
    """Test that all three gravity mode constants are defined."""
    src = _source()
    for const in ("GRAV_NORMAL", "GRAV_ZERO_G", "GRAV_CEILING"):
        assert const in src, f"Gravity constant {const} not found"
    print("✓ All gravity mode constants present (NORMAL, ZERO_G, CEILING)")


def test_tile_type_constants():
    """Test that all tile-type constants are defined."""
    src = _source()
    tile_consts = (
        "T_EMPTY", "T_SOLID",
        "T_CYN_SOL", "T_RED_HAZ",
        "T_BLU_SOL", "T_ORG_HAZ",
        "T_GRN_SOL", "T_YEL_HAZ",
        "T_MAG_SOL", "T_WHT_HAZ",
        "T_GOAL",
    )
    for const in tile_consts:
        assert const in src, f"Tile constant {const} not found"
    print(f"✓ All {len(tile_consts)} tile-type constants present")


def test_hardware_index_constants():
    """Test that hardware index constants for SAT-01 are present."""
    src = _source()
    for const in ("_SW_ROTARY_A", "_SW_ROTARY_B", "_MT_REWIND",
                  "_BTN_JUMP", "_ENC_MOVE"):
        assert const in src, f"Hardware constant {const} not found"
    print("✓ All hardware index constants present")


def test_history_buffer_constant():
    """Test that the rewind history buffer length is defined."""
    src = _source()
    assert "_HISTORY_LEN" in src, "_HISTORY_LEN constant not found"
    print("✓ _HISTORY_LEN (rewind buffer) constant is defined")


# ---------------------------------------------------------------------------
# Level data integrity checks
# ---------------------------------------------------------------------------

def _load_levels():
    """Import level tuples directly from the source module via exec."""
    src = _source()
    ns = {}
    # Only execute constant/data definitions, not hardware imports
    # Parse the AST and extract level tuple assignments
    tree = ast.parse(src)
    level_names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.startswith("_LV"):
                    level_names.append(target.id)
    return level_names


def test_three_levels_defined():
    """Test that exactly three level tuples (_LV1, _LV2, _LV3) are defined."""
    src = _source()
    for lv in ("_LV1", "_LV2", "_LV3"):
        assert lv in src, f"Level tuple {lv} not found in flux_scavenger.py"
    print("✓ All three level tuples (_LV1, _LV2, _LV3) are defined")


def test_level_catalogue_defined():
    """Test that _LEVELS and _STARTS catalogue variables are defined."""
    src = _source()
    assert "_LEVELS" in src, "_LEVELS catalogue not found"
    assert "_STARTS" in src, "_STARTS catalogue not found"
    assert "_LEVEL_NAMES" in src, "_LEVEL_NAMES catalogue not found"
    print("✓ Level catalogue variables (_LEVELS, _STARTS, _LEVEL_NAMES) defined")


def _extract_level_body(src, lv):
    """Return the stripped integer content of level tuple *lv* from *src*.

    The level tuples are multi-line and may contain inline comments.
    We match from ``_LVx = (`` to the closing ``)`` that sits alone on its
    own line (i.e. preceded only by optional whitespace).
    """
    import re
    # Match the opening, then capture everything up to a line that is
    # just optional-whitespace + closing-paren.
    pattern = rf"{lv}\s*=\s*\((.*?)\n\s*\)"
    m = re.search(pattern, src, re.DOTALL)
    if m is None:
        raise AssertionError(f"Could not find {lv} tuple in source")
    body = m.group(1)
    # Strip inline comments so their numbers don't pollute the count
    lines = [re.sub(r'#.*', '', ln) for ln in body.split('\n')]
    return ' '.join(lines)


def test_level_sizes():
    """Test that each level tuple contains exactly 256 elements (16×16)."""
    import re
    src = _source()

    for lv in ("_LV1", "_LV2", "_LV3"):
        cleaned = _extract_level_body(src, lv)
        ints = re.findall(r'\b\d+\b', cleaned)
        assert len(ints) == 256, (
            f"{lv} has {len(ints)} tile entries, expected 256 (16×16)"
        )
    print("✓ All three levels contain exactly 256 tile entries (16×16)")


def test_level_boundary_tiles():
    """Test that the outer border of each level is solid (T_SOLID=1)."""
    import re
    src = _source()

    for lv in ("_LV1", "_LV2", "_LV3"):
        cleaned = _extract_level_body(src, lv)
        tiles = [int(t) for t in re.findall(r'\b\d+\b', cleaned)]

        assert len(tiles) == 256, f"{lv}: unexpected tile count {len(tiles)}"

        # Row 0 (ceiling) and row 15 (floor) must be all 1s
        row0  = tiles[0:16]
        row15 = tiles[240:256]
        assert all(t == 1 for t in row0), (
            f"{lv}: ceiling row (y=0) is not entirely solid"
        )
        assert all(t == 1 for t in row15), (
            f"{lv}: floor row (y=15) is not entirely solid"
        )

        # Left (x=0) and right (x=15) columns must be all 1s
        left  = [tiles[y * 16 + 0]  for y in range(16)]
        right = [tiles[y * 16 + 15] for y in range(16)]
        assert all(t == 1 for t in left), (
            f"{lv}: left wall (x=0) is not entirely solid"
        )
        assert all(t == 1 for t in right), (
            f"{lv}: right wall (x=15) is not entirely solid"
        )

    print("✓ All levels have solid outer boundaries (ceiling, floor, side walls)")


def test_level_valid_tile_values():
    """Test that all tile values in the levels are within the valid range 0-10."""
    import re
    src = _source()

    valid_tiles = set(range(11))   # 0-10

    for lv in ("_LV1", "_LV2", "_LV3"):
        cleaned = _extract_level_body(src, lv)
        tiles = [int(t) for t in re.findall(r'\b\d+\b', cleaned)]
        invalid = [t for t in tiles if t not in valid_tiles]
        assert not invalid, (
            f"{lv}: invalid tile values found: {invalid[:10]}"
        )

    print("✓ All tile values in all levels are within valid range 0–10")


def test_each_level_has_goal_tile():
    """Test that every level contains at least one goal tile (T_GOAL=10)."""
    import re
    src = _source()

    for lv in ("_LV1", "_LV2", "_LV3"):
        cleaned = _extract_level_body(src, lv)
        tiles = [int(t) for t in re.findall(r'\b\d+\b', cleaned)]
        assert 10 in tiles, f"{lv}: no goal tile (value 10) found"

    print("✓ Every level contains at least one goal tile (T_GOAL=10)")


# ---------------------------------------------------------------------------
# Key method presence checks
# ---------------------------------------------------------------------------

def test_required_methods():
    """Test that all required game methods are present."""
    src = _source()
    methods = (
        "def run(",
        "def run_tutorial(",
        "def _read_toggles(",
        "def _get_gravity_mode(",
        "def _is_rewinding(",
        "def _get_tile(",
        "def _tile_is_solid(",
        "def _tile_is_hazard(",
        "def _step_physics(",
        "def _move_x(",
        "def _push_history(",
        "def _pop_history(",
        "def _render(",
        "def _update_oled(",
        "def _update_sat_leds(",
        "def _update_sat_display(",
    )
    missing = [m for m in methods if m not in src]
    assert not missing, f"Missing methods: {missing}"
    print(f"✓ All {len(methods)} required methods are present")


def test_all_hardware_mechanics_referenced():
    """Test that all five key hardware mechanics are used in run()."""
    src = _source()
    # Check that the run() method references key hardware interactions
    mechanics = {
        "encoder_positions": "encoder lateral movement",
        "is_button_pressed": "jump button",
        "_read_toggles":     "toggle environment hacking",
        "_get_gravity_mode": "gravity shift",
        "_is_rewinding":     "time rewind",
    }
    for symbol, description in mechanics.items():
        assert symbol in src, f"Mechanic '{description}' ({symbol}) not referenced"
    print("✓ All five key hardware mechanics are referenced in the mode")


def test_tile_toggle_map_covers_all_toggled_tiles():
    """Test that _TILE_TOGGLE_MAP covers all 8 toggleable tile types."""
    src = _source()
    # All 8 toggled tile types (T_CYN_SOL through T_WHT_HAZ) should be in map
    toggled_tiles = (
        "T_CYN_SOL", "T_RED_HAZ", "T_BLU_SOL", "T_ORG_HAZ",
        "T_GRN_SOL", "T_YEL_HAZ", "T_MAG_SOL", "T_WHT_HAZ",
    )
    for tile in toggled_tiles:
        assert tile in src, f"{tile} not found in source"
    # The map itself should appear
    assert "_TILE_TOGGLE_MAP" in src, "_TILE_TOGGLE_MAP not found"
    print("✓ _TILE_TOGGLE_MAP covers all 8 toggleable tile types")


if __name__ == "__main__":
    test_file_exists()
    test_valid_syntax()
    test_flux_scavenger_in_manifest()
    test_flux_scavenger_manifest_metadata()
    test_flux_scavenger_difficulty_settings()
    test_class_defined()
    test_gravity_mode_constants()
    test_tile_type_constants()
    test_hardware_index_constants()
    test_history_buffer_constant()
    test_three_levels_defined()
    test_level_catalogue_defined()
    test_level_sizes()
    test_level_boundary_tiles()
    test_level_valid_tile_values()
    test_each_level_has_goal_tile()
    test_required_methods()
    test_all_hardware_mechanics_referenced()
    test_tile_toggle_map_covers_all_toggled_tiles()
    print("\n✓ All Flux Scavenger tests passed")
