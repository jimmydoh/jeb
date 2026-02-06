#!/usr/bin/env python3
"""Unit tests for DataManager (game data persistence)."""

import sys
import os
import json
import tempfile
import shutil

# Add src/managers to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'managers'))

# Import DataManager module directly
import data_manager
DataManager = data_manager.DataManager


def test_data_manager_initialization():
    """Test DataManager initialization with temp directory."""
    print("Testing DataManager initialization...")
    
    # Create a temporary directory for testing
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Initialize DataManager (add trailing slash for proper path construction)
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Check that data directory was created
        data_dir = os.path.join(temp_dir, 'data')
        assert os.path.exists(data_dir), "Data directory should be created"
        
        # Check initial data is empty dict
        assert isinstance(dm.data, dict), "Initial data should be a dictionary"
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
    
    print("✓ DataManager initialization test passed")


def test_save_and_load_data():
    """Test saving and loading data."""
    print("\nTesting save and load...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create and populate DataManager
        dm = DataManager(root_dir=temp_dir + "/")
        dm.data = {"test_key": "test_value", "number": 42}
        dm.save()
        
        # Create new instance to load the saved data
        dm2 = DataManager(root_dir=temp_dir + "/")
        
        # Verify data was loaded correctly
        assert "test_key" in dm2.data, "Saved data should be loaded"
        assert dm2.data["test_key"] == "test_value", "Loaded data should match saved data"
        assert dm2.data["number"] == 42, "Numbers should be preserved"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Save and load test passed")


def test_get_high_score_nonexistent():
    """Test getting high score for non-existent game."""
    print("\nTesting get high score for non-existent game...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Get high score for game that doesn't exist
        score = dm.get_high_score("NonExistentGame", "variant1")
        assert score == 0, "Non-existent game should return 0"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Get non-existent high score test passed")


def test_save_high_score_new():
    """Test saving a new high score."""
    print("\nTesting save new high score...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Save a new high score
        result = dm.save_high_score("TestGame", "easy", 100)
        
        # Should return True (new high score)
        assert result == True, "Saving first score should return True"
        
        # Verify the score was saved
        saved_score = dm.get_high_score("TestGame", "easy")
        assert saved_score == 100, f"Expected score 100, got {saved_score}"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Save new high score test passed")


def test_save_high_score_improvement():
    """Test saving an improved high score."""
    print("\nTesting save improved high score...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Save initial score
        dm.save_high_score("TestGame", "normal", 50)
        
        # Try to save a higher score
        result = dm.save_high_score("TestGame", "normal", 75)
        assert result == True, "Higher score should return True"
        
        # Verify the score was updated
        saved_score = dm.get_high_score("TestGame", "normal")
        assert saved_score == 75, f"Score should be updated to 75, got {saved_score}"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Save improved high score test passed")


def test_save_high_score_not_improvement():
    """Test that lower scores don't replace high scores."""
    print("\nTesting lower score doesn't replace high score...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Save initial high score
        dm.save_high_score("TestGame", "hard", 100)
        
        # Try to save a lower score
        result = dm.save_high_score("TestGame", "hard", 50)
        assert result == False, "Lower score should return False"
        
        # Verify the score wasn't changed
        saved_score = dm.get_high_score("TestGame", "hard")
        assert saved_score == 100, f"Score should remain 100, got {saved_score}"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Lower score doesn't replace test passed")


def test_multiple_game_variants():
    """Test storing scores for multiple game variants."""
    print("\nTesting multiple game variants...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Save scores for different variants
        dm.save_high_score("Simon", "easy", 10)
        dm.save_high_score("Simon", "medium", 20)
        dm.save_high_score("Simon", "hard", 30)
        dm.save_high_score("Jebris", "classic", 5000)
        
        # Verify all scores are stored independently
        assert dm.get_high_score("Simon", "easy") == 10
        assert dm.get_high_score("Simon", "medium") == 20
        assert dm.get_high_score("Simon", "hard") == 30
        assert dm.get_high_score("Jebris", "classic") == 5000
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Multiple game variants test passed")


def test_get_setting_default():
    """Test getting a setting with default value."""
    print("\nTesting get setting with default...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Get non-existent setting with default
        value = dm.get_setting("TestGame", "volume", default=50)
        assert value == 50, f"Should return default value 50, got {value}"
        
        # Get non-existent setting without default
        value = dm.get_setting("TestGame", "other_setting")
        assert value is None, f"Should return None when no default, got {value}"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Get setting with default test passed")


def test_set_and_get_setting():
    """Test setting and getting configuration values."""
    print("\nTesting set and get settings...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Set a setting
        dm.set_setting("TestGame", "difficulty", "hard")
        
        # Get the setting back
        value = dm.get_setting("TestGame", "difficulty")
        assert value == "hard", f"Expected 'hard', got {value}"
        
        # Set multiple settings
        dm.set_setting("TestGame", "sound_enabled", True)
        dm.set_setting("TestGame", "brightness", 80)
        
        # Verify all settings
        assert dm.get_setting("TestGame", "sound_enabled") == True
        assert dm.get_setting("TestGame", "brightness") == 80
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Set and get settings test passed")


def test_persistence_across_instances():
    """Test that data persists across DataManager instances."""
    print("\nTesting persistence across instances...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # First instance: save data
        dm1 = DataManager(root_dir=temp_dir + "/")
        dm1.save_high_score("PersistGame", "test", 999)
        dm1.set_setting("PersistGame", "config_value", "test123")
        
        # Second instance: load and verify
        dm2 = DataManager(root_dir=temp_dir + "/")
        score = dm2.get_high_score("PersistGame", "test")
        setting = dm2.get_setting("PersistGame", "config_value")
        
        assert score == 999, f"Score should persist, expected 999, got {score}"
        assert setting == "test123", f"Setting should persist, expected 'test123', got {setting}"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Persistence across instances test passed")


def test_data_structure():
    """Test the internal data structure is correctly formatted."""
    print("\nTesting data structure format...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        dm = DataManager(root_dir=temp_dir + "/")
        
        # Save some data
        dm.save_high_score("Game1", "variant1", 100)
        dm.set_setting("Game1", "setting1", "value1")
        
        # Check structure
        assert "Game1" in dm.data, "Game name should be top-level key"
        assert "variant1" in dm.data["Game1"], "Variant should be under game"
        assert "high_score" in dm.data["Game1"]["variant1"], "High score should be under variant"
        assert "CONFIG" in dm.data["Game1"], "CONFIG should be under game"
        assert "setting1" in dm.data["Game1"]["CONFIG"], "Setting should be under CONFIG"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ Data structure format test passed")


def run_all_tests():
    """Run all DataManager tests."""
    print("=" * 60)
    print("DataManager Test Suite")
    print("=" * 60)
    
    try:
        test_data_manager_initialization()
        test_save_and_load_data()
        test_get_high_score_nonexistent()
        test_save_high_score_new()
        test_save_high_score_improvement()
        test_save_high_score_not_improvement()
        test_multiple_game_variants()
        test_get_setting_default()
        test_set_and_get_setting()
        test_persistence_across_instances()
        test_data_structure()
        
        print("\n" + "=" * 60)
        print("✓ All DataManager tests passed!")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
