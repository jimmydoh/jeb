"""Test module for Admin Menu UX refactor.

Verifies that:
- GLOBAL_SETTINGS and DEBUG are registered in the manifest with menu="ADMIN"
- global_settings.py placeholder file exists with valid syntax
- main_menu.py uses _build_menu_items("ADMIN") (no hardcoded admin lists)
- All existing admin modes remain correctly registered
"""

import sys
import os
import traceback

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def test_global_settings_file_exists():
    """Test that global_settings.py placeholder file exists."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'global_settings.py')
    assert os.path.exists(path), "global_settings.py file does not exist"
    print("✓ global_settings.py file exists")


def test_global_settings_syntax():
    """Test that global_settings.py has valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'global_settings.py')
    with open(path, 'r') as f:
        code = f.read()
    compile(code, path, 'exec')
    print("✓ global_settings.py has valid Python syntax")


def test_debug_mode_file_exists():
    """Test that debug.py file exists."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'debug.py')
    assert os.path.exists(path), "debug.py file does not exist"
    print("✓ debug.py file exists")


def test_global_settings_in_manifest():
    """Test that GLOBAL_SETTINGS is registered in manifest as an ADMIN mode."""
    from modes.manifest import MODE_REGISTRY

    assert "GLOBAL_SETTINGS" in MODE_REGISTRY, "GLOBAL_SETTINGS not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["GLOBAL_SETTINGS"]

    assert meta["id"] == "GLOBAL_SETTINGS"
    assert meta["name"] == "GLOBAL SETTINGS"
    assert meta["module_path"] == "modes.global_settings"
    assert meta["class_name"] == "GlobalSettings"
    assert meta["menu"] == "ADMIN", "GLOBAL_SETTINGS should have menu='ADMIN'"
    assert "CORE" in meta["requires"]
    print("✓ GLOBAL_SETTINGS registered correctly in manifest")


def test_debug_in_manifest():
    """Test that DEBUG is registered in manifest as an ADMIN mode."""
    from modes.manifest import MODE_REGISTRY

    assert "DEBUG" in MODE_REGISTRY, "DEBUG not found in MODE_REGISTRY"
    meta = MODE_REGISTRY["DEBUG"]

    assert meta["id"] == "DEBUG"
    assert meta["name"] == "DEBUG DASH"
    assert meta["module_path"] == "modes.debug"
    assert meta["class_name"] == "DebugMode"
    assert meta["menu"] == "ADMIN", "DEBUG should have menu='ADMIN'"
    assert "CORE" in meta["requires"]
    print("✓ DEBUG registered correctly in manifest")


def test_layout_configurator_still_in_manifest():
    """Test that the existing LAYOUT_CONFIGURATOR admin mode is still correctly registered."""
    from modes.manifest import MODE_REGISTRY

    assert "LAYOUT_CONFIGURATOR" in MODE_REGISTRY
    meta = MODE_REGISTRY["LAYOUT_CONFIGURATOR"]
    assert meta["menu"] == "ADMIN"
    print("✓ LAYOUT_CONFIGURATOR still correctly registered as ADMIN mode")


def test_all_admin_modes_have_required_fields():
    """Test that all ADMIN menu modes have the required metadata fields."""
    from modes.manifest import MODE_REGISTRY

    admin_modes = {k: v for k, v in MODE_REGISTRY.items() if v.get("menu") == "ADMIN"}
    assert len(admin_modes) >= 3, f"Expected at least 3 admin modes, found {len(admin_modes)}"

    required_fields = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for mode_id, meta in admin_modes.items():
        for field in required_fields:
            assert field in meta, f"Admin mode {mode_id} missing required field '{field}'"
    print(f"✓ All {len(admin_modes)} admin modes have required metadata fields")


def test_main_menu_no_hardcoded_admin_list():
    """Test that main_menu.py no longer contains the old hardcoded admin list."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as f:
        content = f.read()

    # Old hardcoded items should not be present
    assert '"Settings", "Debug Dash"' not in content, \
        "main_menu.py still contains old hardcoded admin_items list"
    assert '"SETTINGS", "DEBUG", "CALIB"' not in content, \
        "main_menu.py still contains old hardcoded admin_keys list"
    print("✓ main_menu.py no longer contains hardcoded admin item lists")


def test_main_menu_uses_build_menu_items_for_admin():
    """Test that main_menu.py uses _build_menu_items('ADMIN') for the admin carousel."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as f:
        content = f.read()

    assert '_build_menu_items("ADMIN")' in content, \
        "main_menu.py should call _build_menu_items('ADMIN') for admin mode list"
    print("✓ main_menu.py uses _build_menu_items('ADMIN') for admin carousel")


def test_main_menu_admin_render_uses_registry():
    """Test that main_menu.py render block uses mode registry for admin mode display."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as f:
        content = f.read()

    # Should reference mode_meta['name'] for dynamic display
    assert "mode_meta['name']" in content or 'mode_meta["name"]' in content, \
        "main_menu.py admin render should use mode_meta['name'] from registry"
    # Should use SLIDE_LEFT animation like the main menu
    assert "SLIDE_LEFT" in content
    print("✓ main_menu.py admin render uses registry data and SLIDE_LEFT animation")


def test_main_menu_last_rendered_admin_tracking():
    """Test that main_menu.py tracks last_rendered_admin for efficient re-rendering."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'main_menu.py')
    with open(path, 'r') as f:
        content = f.read()

    assert "last_rendered_admin" in content, \
        "main_menu.py should have last_rendered_admin tracking variable"
    print("✓ main_menu.py has last_rendered_admin render tracking")


if __name__ == "__main__":
    print("Running Admin Menu UX refactor tests...\n")

    tests = [
        test_global_settings_file_exists,
        test_global_settings_syntax,
        test_debug_mode_file_exists,
        test_global_settings_in_manifest,
        test_debug_in_manifest,
        test_layout_configurator_still_in_manifest,
        test_all_admin_modes_have_required_fields,
        test_main_menu_no_hardcoded_admin_list,
        test_main_menu_uses_build_menu_items_for_admin,
        test_main_menu_admin_render_uses_registry,
        test_main_menu_last_rendered_admin_tracking,
    ]

    passed = 0
    failed = 0
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

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed+failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
