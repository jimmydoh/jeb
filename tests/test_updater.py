#!/usr/bin/env python3
"""Unit tests for OTA Updater module."""

import sys
import os
import json
import hashlib
import tempfile
import shutil

# Add src to path for direct module import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock CircuitPython modules that aren't available in regular Python
class MockRadio:
    def __init__(self):
        self.connected = False
        self.ipv4_address = "192.168.1.100"
        self.enabled = True
    
    def connect(self, ssid, password, timeout=30):
        self.connected = True

# Create mock modules
import types

wifi_module = types.ModuleType('wifi')
wifi_module.radio = MockRadio()
sys.modules['wifi'] = wifi_module

socketpool_module = types.ModuleType('socketpool')
class MockSocketPool:
    def __init__(self, radio):
        pass
socketpool_module.SocketPool = MockSocketPool
sys.modules['socketpool'] = socketpool_module

ssl_module = types.ModuleType('ssl')
def create_default_context():
    return None
ssl_module.create_default_context = create_default_context
sys.modules['ssl'] = ssl_module

adafruit_requests_module = types.ModuleType('adafruit_requests')
class MockSession:
    def __init__(self, pool, context):
        pass
    
    def get(self, url, timeout=10):
        pass
adafruit_requests_module.Session = MockSession
sys.modules['adafruit_requests'] = adafruit_requests_module

microcontroller_module = types.ModuleType('microcontroller')
def mock_reset():
    pass
microcontroller_module.reset = mock_reset
sys.modules['microcontroller'] = microcontroller_module

# Now import updater
import updater


def test_file_exists():
    """Test file_exists helper function."""
    print("Testing file_exists...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")
        
        # Change to temp directory
        original_dir = os.getcwd()
        os.chdir(temp_dir)
        
        assert updater.Updater.file_exists("test.txt"), "File should exist"
        assert not updater.Updater.file_exists("nonexistent.txt"), "File should not exist"
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ file_exists test passed")


def test_calculate_sha256():
    """Test SHA256 hash calculation."""
    print("\nTesting calculate_sha256...")
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test file with known content
        test_file = os.path.join(temp_dir, "test.txt")
        test_content = b"Hello, World!"
        with open(test_file, "wb") as f:
            f.write(test_content)
        
        # Calculate expected hash
        expected_hash = hashlib.sha256(test_content).hexdigest()
        
        # Test the function
        actual_hash = updater.Updater.calculate_sha256(test_file)
        
        assert actual_hash == expected_hash, f"Hash mismatch: expected {expected_hash}, got {actual_hash}"
        
        # Test non-existent file
        nonexistent_hash = updater.Updater.calculate_sha256(os.path.join(temp_dir, "nonexistent.txt"))
        assert nonexistent_hash is None, "Non-existent file should return None"
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ calculate_sha256 test passed")


def test_updater_initialization():
    """Test Updater initialization with config."""
    print("\nTesting Updater initialization...")
    
    # Test with valid config
    valid_config = {
        "wifi_ssid": "TestSSID",
        "wifi_password": "TestPassword",
        "update_url": "http://example.com/manifest.json"
    }
    
    try:
        updater_instance = updater.Updater(valid_config)
        assert updater_instance.wifi_ssid == "TestSSID"
        assert updater_instance.wifi_password == "TestPassword"
        assert updater_instance.update_url == "http://example.com/manifest.json"
        print("  ✓ Valid config accepted")
    except Exception as e:
        print(f"  ✗ Failed with valid config: {e}")
        raise
    
    # Test with missing config
    invalid_config = {
        "wifi_ssid": "TestSSID"
        # Missing password and url
    }
    
    try:
        updater.Updater(invalid_config)
        print("  ✗ Should have raised error for missing config")
        assert False, "Should have raised UpdaterError"
    except updater.UpdaterError as e:
        print(f"  ✓ Correctly rejected invalid config: {e}")
    
    print("✓ Updater initialization test passed")


def test_should_check_for_updates():
    """Test update detection logic."""
    print("\nTesting should_check_for_updates...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        # Test 1: No flag, no version.json (first boot)
        assert updater.should_check_for_updates(), "Should check updates on first boot"
        print("  ✓ First boot detected correctly")
        
        # Test 2: Create version.json (normal boot)
        with open("version.json", "w") as f:
            json.dump({"version": "1.0.0"}, f)
        
        assert not updater.should_check_for_updates(), "Should not check updates with version.json"
        print("  ✓ Normal boot detected correctly")
        
        # Test 3: Create update flag (forced update)
        with open(".update_flag", "w") as f:
            f.write("1")
        
        assert updater.should_check_for_updates(), "Should check updates with flag"
        print("  ✓ Update flag detected correctly")
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ should_check_for_updates test passed")


def test_trigger_update():
    """Test update flag creation."""
    print("\nTesting trigger_update...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        # Trigger update
        result = updater.trigger_update()
        assert result, "trigger_update should return True"
        
        # Check flag was created
        assert os.path.exists(".update_flag"), "Update flag should be created"
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ trigger_update test passed")


def test_clear_update_flag():
    """Test update flag removal."""
    print("\nTesting clear_update_flag...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        # Create flag
        with open(".update_flag", "w") as f:
            f.write("1")
        
        # Clear flag
        updater.clear_update_flag()
        
        # Check flag was removed
        assert not os.path.exists(".update_flag"), "Update flag should be removed"
        
        # Should not error if flag doesn't exist
        updater.clear_update_flag()
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ clear_update_flag test passed")


def test_check_current_version():
    """Test reading current version information."""
    print("\nTesting check_current_version...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        config = {
            "wifi_ssid": "test",
            "wifi_password": "test",
            "update_url": "http://test.com/manifest.json"
        }
        updater_instance = updater.Updater(config)
        
        # Test 1: No version.json
        version = updater_instance.check_current_version()
        assert version is None, "Should return None when version.json doesn't exist"
        print("  ✓ Missing version.json handled correctly")
        
        # Test 2: With version.json
        version_data = {
            "version": "1.0.0",
            "build_timestamp": "2024-01-01T00:00:00Z"
        }
        with open("version.json", "w") as f:
            json.dump(version_data, f)
        
        version = updater_instance.check_current_version()
        assert version is not None, "Should return version data"
        assert version["version"] == "1.0.0", "Version should match"
        print("  ✓ version.json read correctly")
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ check_current_version test passed")


def test_verify_files():
    """Test file verification against manifest."""
    print("\nTesting verify_files...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        # Create test files
        test_content_1 = b"File 1 content"
        test_content_2 = b"File 2 content"
        
        with open("file1.mpy", "wb") as f:
            f.write(test_content_1)
        
        # Calculate hashes
        hash1 = hashlib.sha256(test_content_1).hexdigest()
        hash2 = hashlib.sha256(test_content_2).hexdigest()
        
        # Create manifest
        manifest = {
            "version": "1.0.0",
            "files": [
                {
                    "path": "file1.mpy",
                    "sha256": hash1,  # Correct hash
                    "size": len(test_content_1)
                },
                {
                    "path": "file2.mpy",
                    "sha256": hash2,  # File doesn't exist
                    "size": len(test_content_2)
                },
                {
                    "path": "file3.mpy",
                    "sha256": "wronghash123",  # Wrong hash
                    "size": 100
                }
            ]
        }
        
        # Create file3 with different content
        with open("file3.mpy", "wb") as f:
            f.write(b"Different content")
        
        # Create updater instance
        config = {
            "wifi_ssid": "test",
            "wifi_password": "test",
            "update_url": "http://test.com/manifest.json"
        }
        updater_instance = updater.Updater(config)
        updater_instance.manifest = manifest
        
        # Verify files
        files_to_update, files_ok = updater_instance.verify_files()
        
        # Check results
        assert len(files_ok) == 1, "Should have 1 OK file"
        assert files_ok[0]["path"] == "file1.mpy", "file1.mpy should be OK"
        
        assert len(files_to_update) == 2, "Should have 2 files to update"
        update_paths = [f["path"] for f in files_to_update]
        assert "file2.mpy" in update_paths, "file2.mpy should need update (missing)"
        assert "file3.mpy" in update_paths, "file3.mpy should need update (wrong hash)"
        
        print("  ✓ File verification logic correct")
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ verify_files test passed")


def test_write_version_info():
    """Test writing version information."""
    print("\nTesting write_version_info...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        # Create updater with manifest
        config = {
            "wifi_ssid": "test",
            "wifi_password": "test",
            "update_url": "http://test.com/manifest.json"
        }
        updater_instance = updater.Updater(config)
        updater_instance.manifest = {
            "version": "1.0.0",
            "build_timestamp": "2024-01-01T00:00:00Z",
            "files": []
        }
        
        # Write version info
        result = updater_instance.write_version_info()
        assert result, "write_version_info should return True"
        
        # Check file was created
        assert os.path.exists("version.json"), "version.json should be created"
        
        # Read and verify content
        with open("version.json", "r") as f:
            version_data = json.load(f)
        
        assert version_data["version"] == "1.0.0", "Version should match"
        assert "update_timestamp" in version_data, "Should have update timestamp"
        
        print("  ✓ version.json written correctly")
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ write_version_info test passed")


def run_all_tests():
    """Run all updater tests."""
    print("\n" + "="*60)
    print("   UPDATER MODULE TESTS")
    print("="*60 + "\n")
    
    tests = [
        test_file_exists,
        test_calculate_sha256,
        test_updater_initialization,
        test_should_check_for_updates,
        test_trigger_update,
        test_clear_update_flag,
        test_check_current_version,
        test_verify_files,
        test_write_version_info,
    ]
    
    failed = 0
    passed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n❌ Test failed: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"   RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
