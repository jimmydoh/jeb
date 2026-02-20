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

class MockWiFiManager:
    """Mock WiFiManager for testing."""
    def __init__(self, connected=True, ip="192.168.1.100", ssid="TestSSID"):
        self._connected = connected
        self._ip = ip
        self.ssid = ssid
        self.password = "TestPassword"
        self._pool = object()  # Simple truthy object to represent socket pool

    @property
    def is_connected(self):
        return self._connected

    @property
    def ip_address(self):
        return self._ip if self._connected else None

    @property
    def pool(self):
        return self._pool if self._connected else None

    def connect(self, timeout=30):
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    def create_http_session(self):
        # Import the mock session from the top-level mock
        return adafruit_requests_module.Session(None, None)

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
    
    # Test with valid config and SD mounted
    valid_config = {
        "wifi_ssid": "TestSSID",
        "wifi_password": "TestPassword",
        "update_url": "http://example.com"
    }
    
    try:
        updater_instance = updater.Updater(valid_config, MockWiFiManager(), sd_mounted=True)
        assert updater_instance.update_url == "http://example.com"
        assert updater_instance.sd_mounted == True
        assert updater_instance.download_dir == "/sd/update"
        print("  ✓ Valid config accepted")
    except Exception as e:
        print(f"  ✗ Failed with valid config: {e}")
        raise
    
    # Test with None wifi_manager
    try:
        updater.Updater(valid_config, None, sd_mounted=True)
        print("  ✗ Should have raised error for None wifi_manager")
        assert False, "Should have raised UpdaterError"
    except updater.UpdaterError as e:
        assert "Wi-FiManager instance is required for OTA updates" in str(e)
        print(f"  ✓ Correctly rejected None wifi_manager: {e}")
    
    # Test with missing update_url
    invalid_config = {
        "wifi_ssid": "TestSSID"
        # Missing update_url
    }
    
    try:
        updater.Updater(invalid_config, MockWiFiManager(), sd_mounted=True)
        print("  ✗ Should have raised error for missing config")
        assert False, "Should have raised UpdaterError"
    except updater.UpdaterError as e:
        assert "Missing required config: update_url" in str(e)
        print(f"  ✓ Correctly rejected invalid config: {e}")
    
    # Test without SD card
    try:
        updater.Updater(valid_config, MockWiFiManager(), sd_mounted=False)
        print("  ✗ Should have raised error for missing SD card")
        assert False, "Should have raised UpdaterError"
    except updater.UpdaterError as e:
        print(f"  ✓ Correctly rejected without SD card: {e}")
    
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
            "update_url": "http://test.com"
        }
        updater_instance = updater.Updater(config, MockWiFiManager(), sd_mounted=True)
        
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
            "update_url": "http://test.com"
        }
        updater_instance = updater.Updater(config, MockWiFiManager(), sd_mounted=True)
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
            "update_url": "http://test.com"
        }
        updater_instance = updater.Updater(config, MockWiFiManager(), sd_mounted=True)
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


def test_install_file():
    """Test installing a file from SD staging to flash.
    
    This test exercises the real Updater.install_file() method with an
    injectable dest_root parameter to verify path handling, directory
    creation, and error handling work correctly.
    """
    print("\nTesting install_file...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    
    try:
        os.chdir(temp_dir)
        
        # Create SD staging directory structure
        os.makedirs("sd/update/lib")
        
        # Create a test file in staging
        test_content = b"Test file content for installation"
        test_hash = hashlib.sha256(test_content).hexdigest()
        
        staging_file = "sd/update/lib/test.mpy"
        with open(staging_file, "wb") as f:
            f.write(test_content)
        
        # Create updater instance
        config = {
            "wifi_ssid": "test",
            "wifi_password": "test",
            "update_url": "http://test.com"
        }
        updater_instance = updater.Updater(config, MockWiFiManager(), sd_mounted=True)
        # Use relative paths within temp directory
        updater_instance.download_dir = "sd/update"
        
        # Create file info
        file_info = {
            "path": "lib/test.mpy",
            "sha256": test_hash,
            "size": len(test_content)
        }
        
        # Install the file using the real install_file method with temp_dir as dest_root
        result = updater_instance.install_file(file_info, dest_root=temp_dir)
        assert result, "install_file should return True"
        
        # Check destination file was created
        dest_file = os.path.join(temp_dir, "lib/test.mpy")
        assert os.path.exists(dest_file), "Destination file should exist"
        
        # Verify content
        with open(dest_file, "rb") as f:
            dest_content = f.read()
        
        assert dest_content == test_content, "Installed content should match"
        
        # Verify hash
        actual_hash = updater.Updater.calculate_sha256(dest_file)
        assert actual_hash == test_hash, "Installed file hash should match"
        
        print("  ✓ File installed and verified correctly")
        
        # Test with absolute path (should be handled correctly)
        os.makedirs("sd/update/modules", exist_ok=True)
        test_content_2 = b"Another test file"
        test_hash_2 = hashlib.sha256(test_content_2).hexdigest()
        staging_file_2 = "sd/update/modules/core.mpy"
        with open(staging_file_2, "wb") as f:
            f.write(test_content_2)
        
        file_info_2 = {
            "path": "/modules/core.mpy",  # Absolute path with leading slash
            "sha256": test_hash_2,
            "size": len(test_content_2)
        }
        
        result_2 = updater_instance.install_file(file_info_2, dest_root=temp_dir)
        assert result_2, "install_file should return True for absolute path"
        
        dest_file_2 = os.path.join(temp_dir, "modules/core.mpy")
        assert os.path.exists(dest_file_2), "File with absolute path should be installed correctly"
        
        with open(dest_file_2, "rb") as f:
            dest_content_2 = f.read()
        assert dest_content_2 == test_content_2, "Content should match for absolute path"
        
        print("  ✓ Absolute path handling verified correctly")
        
        os.chdir(original_dir)
        
    finally:
        shutil.rmtree(temp_dir)
    
    print("✓ install_file test passed")


def test_fetch_version_socket_cleanup_on_error():
    """Test that response.close() is called even when errors occur in fetch_remote_version."""
    print("\nTesting fetch_remote_version socket cleanup on error...")
    
    # Track if close() was called
    close_called = False
    
    class MockResponse:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json_data = json_data or {}
        
        def json(self):
            if self._json_data.get("error"):
                raise ValueError("JSON parse error")
            return self._json_data
        
        def close(self):
            nonlocal close_called
            close_called = True
    
    class MockSessionWithErrors:
        def __init__(self, pool, context):
            pass
        
        def get(self, url, timeout=10):
            # Return response with bad status code
            return MockResponse(status_code=404)
    
    # Save original session class
    original_session = adafruit_requests_module.Session
    
    try:
        # Mock session for HTTP error test
        adafruit_requests_module.Session = MockSessionWithErrors
        
        config = {
            "wifi_ssid": "test",
            "wifi_password": "test",
            "update_url": "http://test.com"
        }
        
        updater_instance = updater.Updater(config, MockWiFiManager(), sd_mounted=True)
        updater_instance.http_session = MockSessionWithErrors(None, None)
        
        # Test HTTP error path
        close_called = False
        try:
            updater_instance.fetch_remote_version()
            assert False, "Should have raised UpdaterError for HTTP 404"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on HTTP error"
        print("  ✓ Socket cleanup verified for HTTP error path")
        
        # Test JSON parsing error path
        class MockSessionJSONError:
            def __init__(self, pool, context):
                pass
            
            def get(self, url, timeout=10):
                return MockResponse(status_code=200, json_data={"error": True})
        
        adafruit_requests_module.Session = MockSessionJSONError
        updater_instance.http_session = MockSessionJSONError(None, None)
        
        close_called = False
        try:
            updater_instance.fetch_remote_version()
            assert False, "Should have raised UpdaterError for JSON parse error"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on JSON error"
        print("  ✓ Socket cleanup verified for JSON error path")
        
        # Test validation error path
        class MockSessionValidation:
            def __init__(self, pool, context):
                pass
            
            def get(self, url, timeout=10):
                return MockResponse(status_code=200, json_data={"no_version": "1.0.0"})
        
        adafruit_requests_module.Session = MockSessionValidation
        updater_instance.http_session = MockSessionValidation(None, None)
        
        close_called = False
        try:
            updater_instance.fetch_remote_version()
            assert False, "Should have raised UpdaterError for validation error"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on validation error"
        print("  ✓ Socket cleanup verified for validation error path")
        
    finally:
        # Restore original session
        adafruit_requests_module.Session = original_session
    
    print("✓ fetch_remote_version socket cleanup test passed")


def test_fetch_manifest_socket_cleanup_on_error():
    """Test that response.close() is called even when errors occur in fetch_manifest."""
    print("\nTesting fetch_manifest socket cleanup on error...")
    
    close_called = False
    
    class MockResponse:
        def __init__(self, status_code=200, json_data=None):
            self.status_code = status_code
            self._json_data = json_data or {}
        
        def json(self):
            if self._json_data.get("error"):
                raise ValueError("JSON parse error")
            return self._json_data
        
        def close(self):
            nonlocal close_called
            close_called = True
    
    class MockSessionWithErrors:
        def __init__(self, pool, context):
            pass
        
        def get(self, url, timeout=10):
            return MockResponse(status_code=500)
    
    original_session = adafruit_requests_module.Session
    
    try:
        adafruit_requests_module.Session = MockSessionWithErrors
        
        config = {
            "wifi_ssid": "test",
            "wifi_password": "test",
            "update_url": "http://test.com"
        }
        
        updater_instance = updater.Updater(config, MockWiFiManager(), sd_mounted=True)
        updater_instance.http_session = MockSessionWithErrors(None, None)
        updater_instance.remote_version = {"version": "1.0.0"}
        
        # Test HTTP error path
        close_called = False
        try:
            updater_instance.fetch_manifest()
            assert False, "Should have raised UpdaterError for HTTP 500"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on HTTP error"
        print("  ✓ Socket cleanup verified for HTTP error path")
        
        # Test JSON parsing error path
        class MockSessionJSONError:
            def __init__(self, pool, context):
                pass
            
            def get(self, url, timeout=10):
                return MockResponse(status_code=200, json_data={"error": True})
        
        adafruit_requests_module.Session = MockSessionJSONError
        updater_instance.http_session = MockSessionJSONError(None, None)
        
        close_called = False
        try:
            updater_instance.fetch_manifest()
            assert False, "Should have raised UpdaterError for JSON parse error"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on JSON error"
        print("  ✓ Socket cleanup verified for JSON error path")
        
        # Test validation error path
        class MockSessionValidation:
            def __init__(self, pool, context):
                pass
            
            def get(self, url, timeout=10):
                return MockResponse(status_code=200, json_data={"version": "1.0.0"})  # Missing "files"
        
        adafruit_requests_module.Session = MockSessionValidation
        updater_instance.http_session = MockSessionValidation(None, None)
        
        close_called = False
        try:
            updater_instance.fetch_manifest()
            assert False, "Should have raised UpdaterError for validation error"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on validation error"
        print("  ✓ Socket cleanup verified for validation error path")
        
    finally:
        adafruit_requests_module.Session = original_session
    
    print("✓ fetch_manifest socket cleanup test passed")


def test_download_file_socket_cleanup_on_error():
    """Test that response.close() is called even when errors occur in download_file."""
    print("\nTesting download_file socket cleanup on error...")
    
    temp_dir = tempfile.mkdtemp()
    original_dir = os.getcwd()
    close_called = False
    
    class MockResponse:
        def __init__(self, status_code=200, content=b"test"):
            self.status_code = status_code
            self._content = content
        
        def iter_content(self, chunk_size):
            if self.status_code == 200:
                yield self._content
        
        def close(self):
            nonlocal close_called
            close_called = True
    
    class MockSessionWithErrors:
        def __init__(self, pool, context):
            pass
        
        def get(self, url, timeout=10):
            return MockResponse(status_code=403)
    
    original_session = adafruit_requests_module.Session
    
    try:
        os.chdir(temp_dir)
        os.makedirs("sd/update")
        
        adafruit_requests_module.Session = MockSessionWithErrors
        
        config = {
            "wifi_ssid": "test",
            "wifi_password": "test",
            "update_url": "http://test.com"
        }
        
        updater_instance = updater.Updater(config, MockWiFiManager(), sd_mounted=True)
        updater_instance.http_session = MockSessionWithErrors(None, None)
        updater_instance.remote_version = {"version": "1.0.0"}
        updater_instance.download_dir = "sd/update"
        
        file_info = {
            "path": "test.txt",
            "download_path": "test.txt",
            "sha256": "abc123",
            "size": 100
        }
        
        # Test HTTP error path
        close_called = False
        try:
            updater_instance.download_file(file_info)
            assert False, "Should have raised UpdaterError for HTTP 403"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on HTTP error"
        print("  ✓ Socket cleanup verified for HTTP error path")
        
        # Test hash mismatch path
        class MockSessionHashMismatch:
            def __init__(self, pool, context):
                pass
            
            def get(self, url, timeout=10):
                return MockResponse(status_code=200, content=b"test content")
        
        adafruit_requests_module.Session = MockSessionHashMismatch
        updater_instance.http_session = MockSessionHashMismatch(None, None)
        
        close_called = False
        try:
            updater_instance.download_file(file_info)
            assert False, "Should have raised UpdaterError for hash mismatch"
        except updater.UpdaterError:
            pass
        
        assert close_called, "response.close() should be called even on hash mismatch"
        print("  ✓ Socket cleanup verified for hash mismatch path")
        
    finally:
        os.chdir(original_dir)
        shutil.rmtree(temp_dir)
        adafruit_requests_module.Session = original_session
    
    print("✓ download_file socket cleanup test passed")


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
        test_install_file,
        test_fetch_version_socket_cleanup_on_error,
        test_fetch_manifest_socket_cleanup_on_error,
        test_download_file_socket_cleanup_on_error,
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
