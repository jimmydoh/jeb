"""Test module for mode registry pattern.

This test verifies the structure and content of the mode registry manifest
without importing the actual mode classes (which have hardware dependencies).
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_manifest_file_exists():
    """Test that manifest.py file exists."""
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'manifest.py')
    assert os.path.exists(manifest_path), "manifest.py file does not exist"
    print("✓ Manifest file exists")
    return True

def test_manifest_structure():
    """Test that manifest has the expected structure."""
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'manifest.py')
    
    with open(manifest_path, 'r') as f:
        content = f.read()
    
    # Check for expected imports
    assert "from .industrial_startup import IndustrialStartup" in content, "IndustrialStartup import missing"
    assert "from .jebris import JEBris" in content, "JEBris import missing"
    assert "from .main_menu import MainMenu" in content, "MainMenu import missing"
    assert "from .safe_cracker import SafeCracker" in content, "SafeCracker import missing"
    assert "from .simon import Simon" in content, "Simon import missing"
    
    # Check for AVAILABLE_MODES list
    assert "AVAILABLE_MODES = [" in content, "AVAILABLE_MODES list missing"
    assert "IndustrialStartup," in content, "IndustrialStartup not in AVAILABLE_MODES"
    assert "JEBris," in content, "JEBris not in AVAILABLE_MODES"
    assert "MainMenu," in content, "MainMenu not in AVAILABLE_MODES"
    assert "SafeCracker," in content, "SafeCracker not in AVAILABLE_MODES"
    assert "Simon," in content, "Simon not in AVAILABLE_MODES"
    
    print("✓ Manifest structure test passed")
    return True

def test_modes_init_updated():
    """Test that modes/__init__.py was updated to use manifest."""
    init_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', '__init__.py')
    
    with open(init_path, 'r') as f:
        content = f.read()
    
    # Check that manifest is imported
    assert "from .manifest import AVAILABLE_MODES" in content, "manifest import missing from __init__.py"
    
    # Check that AVAILABLE_MODES is exported
    assert "AVAILABLE_MODES" in content, "AVAILABLE_MODES not in __init__.py"
    
    print("✓ Modes __init__.py updated correctly")
    return True

def test_core_manager_updated():
    """Test that CoreManager was updated to use manifest."""
    core_manager_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'core', 'core_manager.py')
    
    with open(core_manager_path, 'r') as f:
        content = f.read()
    
    # Check that manifest import is present
    assert "from modes import AVAILABLE_MODES" in content, "AVAILABLE_MODES import missing from CoreManager"
    
    # Check that mode registry is built dynamically
    assert "_mode_registry" in content, "_mode_registry not found in CoreManager"
    assert "for mode_class in AVAILABLE_MODES:" in content, "Mode registry loop not found"
    
    # Check that old direct import is removed
    assert "from modes import IndustrialStartup, JEBris, MainMenu, SafeCracker, Simon" not in content, \
        "Old direct import still present in CoreManager"
    
    # Check that modes are not extracted to module-level variables
    assert 'IndustrialStartup = _mode_registry["IndustrialStartup"]' not in content, \
        "Mode extraction found - modes should be accessed dynamically"
    assert 'JEBris = _mode_registry["JEBris"]' not in content, \
        "Mode extraction found - modes should be accessed dynamically"
    assert 'MainMenu = _mode_registry["MainMenu"]' not in content, \
        "Mode extraction found - modes should be accessed dynamically"
    assert 'IndustrialStartup = self.modes[' not in content, \
        "Mode extraction found - modes should be accessed dynamically"
    assert 'JEBris = self.modes[' not in content, \
        "Mode extraction found - modes should be accessed dynamically"
    assert 'MainMenu = self.modes[' not in content, \
        "Mode extraction found - modes should be accessed dynamically"
    
    # Verify _mode_registry is populated (stored by class name)
    assert 'self._mode_registry[mode_class.__name__] = mode_class' in content, \
        "_mode_registry should be populated with mode classes by class name"
    
    # Verify self.modes is populated (stored by mode ID for runtime access)
    assert 'self.modes[meta["id"]] = mode_class' in content, \
        "self.modes should be populated with mode classes by mode ID"
    
    # Verify modes are accessed dynamically via self.modes dict in the main loop
    assert 'mode_class = self.modes[self.mode]' in content or 'self.modes[self.mode]' in content, \
        "Modes should be accessed dynamically via self.modes dict"
    
    print("✓ CoreManager updated correctly")
    return True

def test_documentation_in_manifest():
    """Test that manifest.py has proper documentation."""
    manifest_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'manifest.py')
    
    with open(manifest_path, 'r') as f:
        content = f.read()
    
    # Check for docstring
    assert '"""' in content, "Manifest missing docstring"
    assert "registry" in content.lower(), "Documentation should mention registry"
    
    # Check for instructions on adding new modes
    assert "To add a new mode" in content or "add a new" in content.lower(), \
        "Manifest should document how to add new modes"
    
    print("✓ Manifest documentation test passed")
    return True

if __name__ == "__main__":
    print("Running mode registry structure tests...\n")
    
    try:
        test_manifest_file_exists()
        test_manifest_structure()
        test_modes_init_updated()
        test_core_manager_updated()
        test_documentation_in_manifest()
        
        print("\n✅ All structure tests passed!")
        print("\nNote: Actual mode class imports require CircuitPython hardware dependencies,")
        print("but the registry pattern structure is correctly implemented.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
