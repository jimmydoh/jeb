"""Test module for Data Flow mode registry entry.

This test verifies the Data Flow mode is correctly registered in the manifest
without importing the actual mode class (which has hardware dependencies).
"""

import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_data_flow_mode_file_exists():
    """Test that data_flow.py file exists."""
    data_flow_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'data_flow.py')
    assert os.path.exists(data_flow_path), "data_flow.py file does not exist"
    print("✓ Data Flow mode file exists")

def test_data_flow_in_manifest():
    """Test that Data Flow mode is registered in manifest."""
    from modes.manifest import MODE_REGISTRY
    
    assert "DATA_FLOW" in MODE_REGISTRY, "DATA_FLOW mode not found in MODE_REGISTRY"
    print("✓ DATA_FLOW mode found in registry")
    
    data_flow_metadata = MODE_REGISTRY["DATA_FLOW"]
    
    # Check required fields
    assert data_flow_metadata["id"] == "DATA_FLOW", "DATA_FLOW mode ID incorrect"
    assert data_flow_metadata["name"] == "DATA FLOW", "DATA_FLOW mode name incorrect"
    assert data_flow_metadata["module_path"] == "modes.data_flow", "DATA_FLOW module path incorrect"
    assert data_flow_metadata["class_name"] == "DataFlowMode", "DATA_FLOW class name incorrect"
    assert data_flow_metadata["icon"] == "DATA_FLOW", "DATA_FLOW icon incorrect"
    assert "CORE" in data_flow_metadata["requires"], "DATA_FLOW should require CORE"
    
    print("✓ DATA_FLOW mode metadata is correct")

def test_data_flow_difficulty_settings():
    """Test that Data Flow mode has difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    
    data_flow_metadata = MODE_REGISTRY["DATA_FLOW"]
    assert "settings" in data_flow_metadata, "DATA_FLOW mode missing settings"
    
    settings = data_flow_metadata["settings"]
    assert len(settings) >= 1, "DATA_FLOW mode should have at least one setting (difficulty)"
    
    # Check for difficulty setting
    difficulty_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty_setting is not None, "DATA_FLOW mode should have difficulty setting"
    assert "NORMAL" in difficulty_setting["options"], "Missing NORMAL difficulty"
    assert "HARD" in difficulty_setting["options"], "Missing HARD difficulty"
    assert difficulty_setting["default"] == "NORMAL", "Default difficulty should be NORMAL"
    
    print("✓ DATA_FLOW mode settings are correct (difficulty)")

def test_data_flow_imports():
    """Test that the module can be imported without errors (syntax check)."""
    try:
        # Just check that the file has valid Python syntax by attempting to compile it
        data_flow_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'data_flow.py')
        with open(data_flow_path, 'r') as f:
            code = f.read()
        compile(code, data_flow_path, 'exec')
        print("✓ Data Flow module has valid Python syntax")
    except SyntaxError as e:
        raise AssertionError(f"Syntax error in data_flow.py: {e}")

def test_data_flow_icon_exists():
    """Test that DATA_FLOW icon exists in icon library."""
    from utilities.icons import Icons
    
    assert "DATA_FLOW" in Icons.ICON_LIBRARY, "DATA_FLOW icon not found in ICON_LIBRARY"
    
    data_flow_icon = Icons.ICON_LIBRARY["DATA_FLOW"]
    assert len(data_flow_icon) == 64, "DATA_FLOW icon should have 64 pixels (8x8 matrix)"
    
    print("✓ DATA_FLOW icon exists and has correct dimensions")

if __name__ == "__main__":
    test_data_flow_mode_file_exists()
    test_data_flow_in_manifest()
    test_data_flow_difficulty_settings()
    test_data_flow_imports()
    test_data_flow_icon_exists()
    print("\n✅ All Data Flow mode tests passed!")
