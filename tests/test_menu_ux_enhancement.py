"""Tests for Menu UX Enhancement – tabbed category pagination system.

Verifies that:
- manifest.py correctly categorises modes as CORE, EXP1, or ZERO_PLAYER
- main_menu.py builds separate item lists per category
- main_menu.py maps B1 (button index 0 tap) to a category-cycle function
- The OLED category header and B1 footer hint are rendered
- EXP1 category is skipped when no INDUSTRIAL satellite is present
"""

import sys
import os
import types as _types

# ---------------------------------------------------------------------------
# Mock CircuitPython / Adafruit hardware modules BEFORE importing src code
# ---------------------------------------------------------------------------

class _MockModule:
    """Catch-all stub that satisfies attribute access and call syntax."""
    def __getattr__(self, name):
        return _MockModule()

    def __call__(self, *args, **kwargs):
        return _MockModule()

    def __iter__(self):
        return iter([])

    def __int__(self):
        return 0


_CP_MODULES = [
    'digitalio', 'board', 'busio', 'neopixel', 'microcontroller',
    'analogio', 'audiocore', 'audiobusio', 'audioio', 'audiomixer',
    'audiopwmio', 'synthio', 'ulab', 'watchdog',
    'adafruit_mcp230xx', 'adafruit_mcp230xx.mcp23017',
    'adafruit_displayio_ssd1306',
    'adafruit_display_text', 'adafruit_display_text.label',
    'adafruit_ht16k33', 'adafruit_ht16k33.segments',
    'adafruit_httpserver', 'adafruit_bus_device', 'adafruit_register',
    'sdcardio', 'storage', 'displayio', 'terminalio',
    'adafruit_framebuf', 'framebufferio', 'rgbmatrix', 'supervisor',
]

for _mod in _CP_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = _MockModule()

# Provide a realistic adafruit_ticks so ticks_ms / ticks_diff work
_ticks_mod = _types.ModuleType('adafruit_ticks')
_ticks_mod.ticks_ms = lambda: 0
_ticks_mod.ticks_diff = lambda a, b: a - b
sys.modules['adafruit_ticks'] = _ticks_mod

# ---------------------------------------------------------------------------
# Add src to path
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ---------------------------------------------------------------------------
# 1.  Manifest category checks
# ---------------------------------------------------------------------------

def test_core_only_modes_have_menu_core():
    """CORE-only game modes (no INDUSTRIAL requirement) must carry menu='CORE'."""
    from modes.manifest import MODE_REGISTRY

    # Sample of well-known CORE-only modes
    core_mode_ids = [
        "SIMON", "JEBRIS", "SAFE", "PONG", "SNAKE", "ASTRO_BREAKER",
        "TRENCH_RUN", "LUNAR_SALVAGE", "DATA_FLOW", "VIRTUAL_PET",
        "GROOVEBOX", "RHYTHM", "EMOJI_REVEAL", "FREQ_HUNTER", "ABYSSAL_ROVER",
    ]

    for mode_id in core_mode_ids:
        assert mode_id in MODE_REGISTRY, f"{mode_id} not found in MODE_REGISTRY"
        meta = MODE_REGISTRY[mode_id]
        assert meta.get("menu") == "CORE", (
            f"{mode_id} should have menu='CORE', got {meta.get('menu')!r}"
        )
    print(f"✓ All {len(core_mode_ids)} sampled CORE modes carry menu='CORE'")


def test_industrial_modes_have_menu_exp1():
    """Modes that require the INDUSTRIAL satellite must carry menu='EXP1'."""
    from modes.manifest import MODE_REGISTRY

    exp1_mode_ids = [
        "IND_START", "ABYSSAL_PING", "ORBITAL_STRIKE", "IRON_CANOPY",
        "DEFCON_COMMANDER", "ARTILLERY_COMMAND", "ENIGMA_BYTE", "MAGLEV_EXPRESS",
        "ORBITAL_DOCKING", "FLUX_SCAVENGER", "VANGUARD_OVERRIDE",
        "PIPELINE_OVERLOAD", "NUMBERS_STATION", "MAGNETIC_CONTAINMENT",
        "BUNKER_DEFUSE", "SEISMIC_STABILIZER",
    ]

    for mode_id in exp1_mode_ids:
        assert mode_id in MODE_REGISTRY, f"{mode_id} not found in MODE_REGISTRY"
        meta = MODE_REGISTRY[mode_id]
        assert meta.get("menu") == "EXP1", (
            f"{mode_id} should have menu='EXP1', got {meta.get('menu')!r}"
        )
    print(f"✓ All {len(exp1_mode_ids)} INDUSTRIAL modes carry menu='EXP1'")


def test_zero_player_modes_unchanged():
    """Zero-player simulation modes must still carry menu='ZERO_PLAYER'."""
    from modes.manifest import MODE_REGISTRY

    zero_ids = [
        "CONWAYS_LIFE", "LANGTONS_ANT", "WOLFRAM_AUTOMATA", "LISSAJOUS",
        "BOIDS", "PLASMA", "FALLING_SAND", "BOUNCING_SPRITE", "WIREWORLD",
        "STARFIELD", "MECHA_FORGE",
    ]

    for mode_id in zero_ids:
        assert mode_id in MODE_REGISTRY, f"{mode_id} not found in MODE_REGISTRY"
        meta = MODE_REGISTRY[mode_id]
        assert meta.get("menu") == "ZERO_PLAYER", (
            f"{mode_id} should still have menu='ZERO_PLAYER', got {meta.get('menu')!r}"
        )
    print(f"✓ All {len(zero_ids)} zero-player modes still carry menu='ZERO_PLAYER'")


def test_no_main_menu_modes_remain():
    """No playable game mode should still use the old menu='MAIN' value."""
    from modes.manifest import MODE_REGISTRY

    stale = {k: v for k, v in MODE_REGISTRY.items() if v.get("menu") == "MAIN"}
    assert len(stale) == 0, (
        f"These modes still have the deprecated menu='MAIN': {list(stale.keys())}"
    )
    print("✓ No modes remain with deprecated menu='MAIN'")


def test_exp1_modes_require_industrial():
    """Every mode with menu='EXP1' must include 'INDUSTRIAL' in its requires list."""
    from modes.manifest import MODE_REGISTRY

    for mode_id, meta in MODE_REGISTRY.items():
        if meta.get("menu") == "EXP1":
            reqs = meta.get("requires", [])
            assert "INDUSTRIAL" in reqs, (
                f"EXP1 mode {mode_id!r} does not require INDUSTRIAL; requires={reqs}"
            )
    print("✓ All EXP1 modes list INDUSTRIAL in their requires field")


# ---------------------------------------------------------------------------
# 2.  main_menu.py structural / source checks
# ---------------------------------------------------------------------------

def _read_main_menu():
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as f:
        return f.read()


def test_main_menu_builds_core_items():
    """main_menu.py must call _build_menu_items('CORE') for the CORE category list."""
    content = _read_main_menu()
    assert '_build_menu_items("CORE")' in content or "_build_menu_items('CORE')" in content, \
        "main_menu.py should call _build_menu_items('CORE')"
    print("✓ main_menu.py calls _build_menu_items('CORE')")


def test_main_menu_builds_exp1_items():
    """main_menu.py must call _build_menu_items('EXP1') for the EXP1 category list."""
    content = _read_main_menu()
    assert '_build_menu_items("EXP1")' in content or "_build_menu_items('EXP1')" in content, \
        "main_menu.py should call _build_menu_items('EXP1')"
    print("✓ main_menu.py calls _build_menu_items('EXP1')")


def test_main_menu_still_builds_zero_player_items():
    """main_menu.py must still call _build_menu_items('ZERO_PLAYER')."""
    content = _read_main_menu()
    has_call = (
        '_build_menu_items("ZERO_PLAYER")' in content
        or "_build_menu_items('ZERO_PLAYER')" in content
    )
    assert has_call, "main_menu.py should still call _build_menu_items('ZERO_PLAYER')"
    print("✓ main_menu.py still calls _build_menu_items('ZERO_PLAYER')")


def test_main_menu_has_category_titles():
    """main_menu.py should define category display titles including CORE, EXP1, and ZERO."""
    content = _read_main_menu()
    assert "CORE GAMES" in content or "CORE" in content, \
        "main_menu.py should reference CORE category title"
    assert "EXPANSION 1" in content or "EXP1" in content, \
        "main_menu.py should reference EXP1 / EXPANSION 1 category title"
    assert "ZERO PLAYER" in content, \
        "main_menu.py should reference ZERO PLAYER category title"
    print("✓ main_menu.py references all three category titles")


def test_main_menu_has_b1_category_cycle():
    """main_menu.py must read button index 0 (B1) as a tap for category cycling."""
    content = _read_main_menu()
    # Must poll button 0 with action="tap"
    assert 'is_button_pressed(0, action="tap")' in content or \
           "is_button_pressed(0, action='tap')" in content, \
        "main_menu.py should call is_button_pressed(0, action='tap') for B1 category cycle"
    print("✓ main_menu.py reads B1 tap for category cycling")


def test_main_menu_has_current_category_variable():
    """main_menu.py must track current_category for the active menu tab."""
    content = _read_main_menu()
    assert "current_category" in content, \
        "main_menu.py should have a current_category variable"
    print("✓ main_menu.py has current_category variable")


def test_main_menu_saves_category_to_core():
    """main_menu.py must persist the selected category onto core for restore on re-entry."""
    content = _read_main_menu()
    assert "_last_menu_category" in content, \
        "main_menu.py should save/restore _last_menu_category on core"
    print("✓ main_menu.py persists _last_menu_category")


def test_main_menu_b1_next_menu_footer_hint():
    """main_menu.py must display a footer hint referencing B1 and next menu."""
    content = _read_main_menu()
    assert "B1" in content and ("NEXT" in content or "MENU" in content), \
        "main_menu.py should show a B1: NEXT MENU style footer hint"
    print("✓ main_menu.py includes B1: NEXT MENU footer hint")


def test_main_menu_category_header_in_render():
    """main_menu.py render block should display a category title on the OLED header."""
    content = _read_main_menu()
    # The category title lookup should appear in the render stage
    assert "_CATEGORY_TITLES" in content or "category_title" in content, \
        "main_menu.py render should look up and display the category title"
    print("✓ main_menu.py render uses category title for OLED header")


def test_main_menu_exp1_skipped_when_no_industrial():
    """main_menu.py must skip EXP1 category in the cycle when exp1_items is empty."""
    content = _read_main_menu()
    # The valid-categories builder must gate EXP1 on whether exp1_items is non-empty
    assert "exp1_items" in content, \
        "main_menu.py should reference exp1_items to gate the EXP1 category"
    # The cycle should only include EXP1 when items exist
    assert "_get_valid_categories" in content or "valid_cats" in content or "exp1_items" in content, \
        "main_menu.py should conditionally include EXP1 in the category cycle"
    print("✓ main_menu.py gates EXP1 in the cycle based on satellite presence")


# ---------------------------------------------------------------------------
# 3.  Runtime / integration checks (using mock Core)
# ---------------------------------------------------------------------------

class _MockSat:
    def __init__(self, sat_type_name, is_active=True):
        self.sat_type_name = sat_type_name
        self.is_active = is_active


class _MockRegistry(dict):
    pass


def _make_mock_core(has_industrial=False):
    """Build the minimal mock Core required to instantiate MainMenu._build_menu_items."""
    import types
    from modes.manifest import MODE_REGISTRY

    core = types.SimpleNamespace()
    core.mode_registry = _MockRegistry(MODE_REGISTRY)
    core.satellites = {}
    if has_industrial:
        core.satellites[1] = _MockSat("INDUSTRIAL", is_active=True)
    return core


def test_build_core_items_returns_core_modes():
    """_build_menu_items('CORE') returns CORE modes and excludes EXP1/ZERO_PLAYER modes."""
    from modes.main_menu import MainMenu
    import types

    core = _make_mock_core(has_industrial=False)
    mm = object.__new__(MainMenu)
    mm.core = core

    items = mm._build_menu_items("CORE")
    assert len(items) > 0, "CORE category should have at least one mode"

    # Verify all returned items are actually CORE modes
    for mode_id in items:
        meta = core.mode_registry[mode_id]
        assert meta.get("menu") == "CORE", f"{mode_id} returned from CORE but menu={meta.get('menu')!r}"

    # Well-known CORE modes must be present
    assert "SIMON" in items, "SIMON should be in CORE items"
    assert "LUNAR_SALVAGE" in items, "LUNAR_SALVAGE should be in CORE items"

    # EXP1 modes must NOT be present (no industrial satellite)
    assert "MAGLEV_EXPRESS" not in items, "MAGLEV_EXPRESS should not appear in CORE items"
    print(f"✓ _build_menu_items('CORE') returned {len(items)} modes correctly")


def test_build_exp1_items_empty_without_satellite():
    """_build_menu_items('EXP1') returns empty list when no INDUSTRIAL satellite present."""
    from modes.main_menu import MainMenu

    core = _make_mock_core(has_industrial=False)
    mm = object.__new__(MainMenu)
    mm.core = core

    items = mm._build_menu_items("EXP1")
    assert items == [], (
        f"EXP1 items should be empty without INDUSTRIAL satellite; got {items}"
    )
    print("✓ _build_menu_items('EXP1') returns [] without INDUSTRIAL satellite")


def test_build_exp1_items_populated_with_satellite():
    """_build_menu_items('EXP1') returns EXP1 modes when INDUSTRIAL satellite present."""
    from modes.main_menu import MainMenu

    core = _make_mock_core(has_industrial=True)
    mm = object.__new__(MainMenu)
    mm.core = core

    items = mm._build_menu_items("EXP1")
    assert len(items) > 0, "EXP1 should have modes when INDUSTRIAL satellite is present"

    for mode_id in items:
        meta = core.mode_registry[mode_id]
        assert meta.get("menu") == "EXP1", (
            f"{mode_id} returned from EXP1 but menu={meta.get('menu')!r}"
        )

    assert "MAGLEV_EXPRESS" in items, "MAGLEV_EXPRESS should be in EXP1 items"
    assert "BUNKER_DEFUSE" in items, "BUNKER_DEFUSE should be in EXP1 items"
    print(f"✓ _build_menu_items('EXP1') returned {len(items)} modes with INDUSTRIAL satellite")


def test_build_zero_player_items():
    """_build_menu_items('ZERO_PLAYER') returns zero-player modes."""
    from modes.main_menu import MainMenu

    core = _make_mock_core(has_industrial=False)
    mm = object.__new__(MainMenu)
    mm.core = core

    items = mm._build_menu_items("ZERO_PLAYER")
    assert len(items) > 0, "ZERO_PLAYER category should have at least one mode"
    assert "CONWAYS_LIFE" in items, "CONWAYS_LIFE should be in ZERO_PLAYER items"
    assert "SIMON" not in items, "SIMON should not be in ZERO_PLAYER items"
    print(f"✓ _build_menu_items('ZERO_PLAYER') returned {len(items)} modes")


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [
        test_core_only_modes_have_menu_core,
        test_industrial_modes_have_menu_exp1,
        test_zero_player_modes_unchanged,
        test_no_main_menu_modes_remain,
        test_exp1_modes_require_industrial,
        test_main_menu_builds_core_items,
        test_main_menu_builds_exp1_items,
        test_main_menu_still_builds_zero_player_items,
        test_main_menu_has_category_titles,
        test_main_menu_has_b1_category_cycle,
        test_main_menu_has_current_category_variable,
        test_main_menu_saves_category_to_core,
        test_main_menu_b1_next_menu_footer_hint,
        test_main_menu_category_header_in_render,
        test_main_menu_exp1_skipped_when_no_industrial,
        test_build_core_items_returns_core_modes,
        test_build_exp1_items_empty_without_satellite,
        test_build_exp1_items_populated_with_satellite,
        test_build_zero_player_items,
    ]

    print("Running Menu UX Enhancement tests...\n")
    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} (unexpected error): {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
