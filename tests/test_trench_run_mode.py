"""Test module for Trench Run mode registry entry.

This test verifies the Trench Run mode is correctly registered in the manifest
without importing the actual mode class (which has hardware dependencies).
"""

import sys
import os
import re

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_trench_run_mode_file_exists():
    """Test that trench_run.py file exists."""
    trench_run_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'trench_run.py')
    assert os.path.exists(trench_run_path), "trench_run.py file does not exist"
    print("✓ Trench Run mode file exists")

def test_trench_run_in_manifest():
    """Test that Trench Run mode is registered in manifest."""
    from modes.manifest import MODE_REGISTRY
    
    assert "TRENCH_RUN" in MODE_REGISTRY, "TRENCH_RUN mode not found in MODE_REGISTRY"
    print("✓ TRENCH_RUN mode found in registry")
    
    trench_run_metadata = MODE_REGISTRY["TRENCH_RUN"]
    
    # Check required fields
    assert trench_run_metadata["id"] == "TRENCH_RUN", "TRENCH_RUN mode ID incorrect"
    assert trench_run_metadata["name"] == "TRENCH RUN", "TRENCH_RUN mode name incorrect"
    assert trench_run_metadata["module_path"] == "modes.trench_run", "TRENCH_RUN module path incorrect"
    assert trench_run_metadata["class_name"] == "TrenchRun", "TRENCH_RUN class name incorrect"
    assert trench_run_metadata["icon"] == "TRENCH_RUN", "TRENCH_RUN icon incorrect"
    assert "CORE" in trench_run_metadata["requires"], "TRENCH_RUN should require CORE"
    
    print("✓ TRENCH_RUN mode metadata is correct")

def test_trench_run_difficulty_settings():
    """Test that Trench Run mode has difficulty settings."""
    from modes.manifest import MODE_REGISTRY
    
    trench_run_metadata = MODE_REGISTRY["TRENCH_RUN"]
    assert "settings" in trench_run_metadata, "TRENCH_RUN mode missing settings"
    
    settings = trench_run_metadata["settings"]
    assert len(settings) >= 2, "TRENCH_RUN mode should have at least two settings (difficulty and perspective)"
    
    # Check for difficulty setting
    difficulty_setting = next((s for s in settings if s["key"] == "difficulty"), None)
    assert difficulty_setting is not None, "TRENCH_RUN mode should have difficulty setting"
    assert difficulty_setting["label"] == "DIFF", "Difficulty label should be 'DIFF'"
    assert "NORMAL" in difficulty_setting["options"], "Difficulty should include NORMAL option"
    assert "HARD" in difficulty_setting["options"], "Difficulty should include HARD option"
    assert "INSANE" in difficulty_setting["options"], "Difficulty should include INSANE option"
    assert difficulty_setting["default"] == "NORMAL", "Default difficulty should be NORMAL"
    
    print("✓ TRENCH_RUN mode difficulty settings are correct")

def test_trench_run_perspective_settings():
    """Test that Trench Run mode has perspective settings."""
    from modes.manifest import MODE_REGISTRY
    
    trench_run_metadata = MODE_REGISTRY["TRENCH_RUN"]
    settings = trench_run_metadata["settings"]
    
    # Check for perspective setting
    perspective_setting = next((s for s in settings if s["key"] == "perspective"), None)
    assert perspective_setting is not None, "TRENCH_RUN mode should have perspective setting"
    assert perspective_setting["label"] == "VIEW", "Perspective label should be 'VIEW'"
    assert "3RD_PERSON" in perspective_setting["options"], "Perspective should include 3RD_PERSON option"
    assert "1ST_PERSON" in perspective_setting["options"], "Perspective should include 1ST_PERSON option"
    assert perspective_setting["default"] == "3RD_PERSON", "Default perspective should be 3RD_PERSON"
    
    print("✓ TRENCH_RUN mode perspective settings are correct")

def test_trench_run_matrix_dimensions():
    """Test that Trench Run mode uses 16x16 matrix dimensions with no hardcoded 8s."""
    trench_run_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'trench_run.py')
    with open(trench_run_path) as f:
        source = f.read()

    # Verify MATRIX_WIDTH and MATRIX_HEIGHT are set to 16
    assert re.search(r'MATRIX_WIDTH\s*=\s*16', source), "MATRIX_WIDTH should be 16"
    assert re.search(r'MATRIX_HEIGHT\s*=\s*16', source), "MATRIX_HEIGHT should be 16"

    # Verify the old 8x8 constant definitions no longer exist
    assert not re.search(r'MATRIX_WIDTH\s*=\s*8', source), "MATRIX_WIDTH should not be 8"
    assert not re.search(r'MATRIX_HEIGHT\s*=\s*8', source), "MATRIX_HEIGHT should not be 8"

    # Verify no hardcoded column index 3 for the 1ST_PERSON ship anchor
    assert not re.search(r'draw_pixel\s*\(\s*3\s*,', source), \
        "draw_pixel(3, ...) should not be hardcoded; use MATRIX_WIDTH // 2"
    assert not re.search(r'player_pos\s*\+\s*3\s*\)', source), \
        "Hardcoded offset '+ 3)' in 1ST_PERSON gap shift should use MATRIX_WIDTH // 2"

    print("✓ TRENCH_RUN mode uses 16x16 matrix dimensions with no hardcoded 8s or column 3s")

if __name__ == "__main__":
    test_trench_run_mode_file_exists()
    test_trench_run_in_manifest()
    test_trench_run_difficulty_settings()
    test_trench_run_perspective_settings()
    test_trench_run_matrix_dimensions()
    print("\nAll tests passed! ✓")
