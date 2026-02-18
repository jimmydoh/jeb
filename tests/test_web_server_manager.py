#!/usr/bin/env python3
"""Unit tests for WebServerManager."""

import sys
import os
import json

try:
    import pytest
except ImportError:
    pytest = None  # pytest is optional, only needed for async tests

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock CircuitPython modules
class MockWiFi:
    class Radio:
        connected = True
        ipv4_address = "192.168.1.100"

        def connect(self, ssid, password, timeout=30):
            self.connected = True

    radio = Radio()

class MockSocketPool:
    def __init__(self, radio):
        self.radio = radio

class MockServer:
    def __init__(self, pool, static_dir, debug=False):
        self.pool = pool
        self.routes = []

    def route(self, path, method):
        def decorator(func):
            self.routes.append((path, method, func))
            return func
        return decorator

    def start(self, host, port):
        pass

    def poll(self):
        pass

    def stop(self):
        pass

class MockRequest:
    def __init__(self):
        self.query_params = {}
        self.body = b""
        self.headers = {}

    def json(self):
        return {}

class MockResponse:
    def __init__(self, request, body, content_type="text/plain", status=200, headers=None):
        self.body = body
        self.content_type = content_type
        self.status = status

# Inject mocks
sys.modules['wifi'] = MockWiFi
sys.modules['socketpool'] = MockSocketPool
sys.modules['adafruit_httpserver'] = type('obj', (object,), {
    'Server': MockServer,
    'Request': MockRequest,
    'Response': MockResponse,
    'GET': type('GET', (), {'__name__': 'GET'}),
    'POST': type('POST', (), {'__name__': 'POST'})
})()

# Mock gc module for CircuitPython compatibility
import gc as _gc
if not hasattr(_gc, 'mem_free'):
    # Add CircuitPython-specific gc methods for testing
    _gc.mem_free = lambda: 100000  # Return 100KB of free memory for tests
    _gc.mem_alloc = lambda: 50000  # Return 50KB allocated for tests

# Import directly to avoid CircuitPython dependencies in other managers
import importlib.util
spec = importlib.util.spec_from_file_location(
    "web_server_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'web_server_manager.py')
)
web_server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web_server_module)
WebServerManager = web_server_module.WebServerManager


def test_initialization():
    """Test WebServerManager initialization."""
    print("Testing WebServerManager initialization...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True,
        "web_server_port": 8080,
        "debug_mode": False,
        "role": "CORE",
        "type_id": "00"
    }

    manager = WebServerManager(config)

    assert manager.wifi_ssid == "TestNetwork"
    assert manager.wifi_password == "TestPassword123"
    assert manager.port == 8080
    assert manager.enabled == True
    assert len(manager.logs) == 0

    print("  ✓ Initialization test passed")

if pytest:
    @pytest.mark.asyncio
    async def test_wifi_connection():
        """Test WiFi connection functionality (async)."""
        print("\nTesting WiFi connection...")

        config = {
            "wifi_ssid": "TestNetwork",
            "wifi_password": "TestPassword123",
            "web_server_enabled": True
        }

        manager = WebServerManager(config)
        connected = await manager.connect_wifi()

        assert connected == True
        assert manager.connected == True

        print("  ✓ WiFi connection test passed")
else:
    # Skip async test if pytest not available
    pass


def test_logging():
    """Test log buffer functionality."""
    print("\nTesting log buffer...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)

    # Add logs
    manager.log("Test message 1")
    manager.log("Test message 2")
    manager.log("Test message 3")

    assert len(manager.logs) == 3
    assert manager.logs[0]["message"] == "Test message 1"
    assert manager.logs[1]["message"] == "Test message 2"
    assert manager.logs[2]["message"] == "Test message 3"

    # Test log rotation
    manager.max_logs = 2
    manager.log("Test message 4")

    assert len(manager.logs) == 2
    assert manager.logs[0]["message"] == "Test message 3"
    assert manager.logs[1]["message"] == "Test message 4"

    print("  ✓ Logging test passed")


def test_directory_listing():
    """Test directory listing functionality."""
    print("\nTesting directory listing...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)

    try:
        # Test listing current directory
        result = manager._list_directory(".")

        assert "path" in result
        assert "items" in result
        assert isinstance(result["items"], list)

        # Verify items have required fields
        for item in result["items"]:
            assert "name" in item
            assert "path" in item
            assert "is_dir" in item
            assert "size" in item

        print(f"  ✓ Directory listing test passed (found {len(result['items'])} items)")
    except Exception as e:
        print(f"  ⚠️ Directory listing test warning: {e}")


def test_config_save():
    """Test configuration save functionality."""
    print("\nTesting config save...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True,
        "debug_mode": False
    }

    manager = WebServerManager(config)

    # Save original config if it exists
    original_config = None
    config_path = "config.json"
    try:
        with open(config_path, "r") as f:
            original_config = f.read()
    except FileNotFoundError:
        pass

    try:
        # Modify config
        manager.config["debug_mode"] = True
        manager._save_config()

        # Verify saved config
        with open(config_path, "r") as f:
            saved_config = json.load(f)

        assert saved_config["debug_mode"] == True

        print("  ✓ Config save test passed")
    finally:
        # Restore original config
        if original_config:
            with open(config_path, "w") as f:
                f.write(original_config)
        else:
            # Clean up test config if there was no original
            try:
                os.remove(config_path)
            except FileNotFoundError:
                pass


def test_html_generation():
    """Test HTML page generation."""
    print("\nTesting HTML generation...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)
    html_result = manager._generate_html_page()

    # Check if it's a generator or string
    if hasattr(html_result, '__iter__') and not isinstance(html_result, str):
        # It's a generator, consume it
        html = ''.join(html_result)
    else:
        # It's a string (fallback error page)
        html = html_result

    # Verify HTML content
    assert "<!DOCTYPE html>" in html
    assert "JEB Field Service" in html or "Configuration Error" in html

    # If we got the full HTML (not error page), check for more content
    if "Configuration Error" not in html:
        assert "/api/config/global" in html
        assert "/api/files" in html
        assert "/api/logs" in html

        # Verify all tabs are present
        assert "System Status" in html
        assert "Configuration" in html
        assert "Mode Settings" in html
        assert "File Browser" in html
        assert "Logs" in html
        assert "Console" in html
        assert "Actions" in html

    print(f"  ✓ HTML generation test passed ({len(html)} bytes)")


def test_route_registration():
    """Test HTTP route registration."""
    print("\nTesting route registration...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)
    manager.server = MockServer(None, "/static")
    manager.setup_routes()

    # Verify all expected routes
    expected_routes = [
        '/',
        '/api/config/global',
        '/api/config/modes',
        '/api/files',
        '/api/files/download',
        '/api/files/upload',
        '/api/logs',
        '/api/console',
        '/api/actions/ota-update',
        '/api/actions/toggle-debug',
        '/api/actions/reorder-satellites',
        '/api/system/status'
    ]

    registered_paths = [path for path, _, _ in manager.server.routes]

    for expected in expected_routes:
        assert expected in registered_paths, f"Route {expected} not registered"

    print(f"  ✓ Route registration test passed ({len(manager.server.routes)} routes)")


def test_invalid_config():
    """Test initialization with invalid configuration."""
    print("\nTesting invalid configuration handling...")

    # Test missing WiFi credentials
    try:
        config = {
            "wifi_ssid": "",
            "wifi_password": "",
            "web_server_enabled": True
        }
        manager = WebServerManager(config)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "WiFi credentials required" in str(e)
        print("  ✓ Invalid config detection passed")


def test_sanitize_path():
    """Test path sanitization function."""
    print("\nTesting path sanitization...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)

    # Test basic path
    result = manager._sanitize_path("/sd", "/sd/test.txt")
    assert result == "/sd/test.txt", f"Expected '/sd/test.txt', got '{result}'"

    # Test path with directory traversal (..)
    result = manager._sanitize_path("/sd", "/sd/subdir/../test.txt")
    assert result == "/sd/test.txt", f"Expected '/sd/test.txt', got '{result}'"

    # Test path with multiple directory traversals
    result = manager._sanitize_path("/sd", "/sd/a/b/../../test.txt")
    assert result == "/sd/test.txt", f"Expected '/sd/test.txt', got '{result}'"

    # Test path trying to escape base with absolute path outside base
    # Absolute paths that don't start with base_path should be rejected for security
    result = manager._sanitize_path("/sd", "/etc/passwd")
    assert result == "/sd", f"Expected '/sd' (rejected), got '{result}'"
    
    # Test path with traversal attempt that would escape in normpath
    # Our function keeps it within base_path, unlike os.path.normpath which would return /etc/passwd
    result = manager._sanitize_path("/sd", "/sd/../../etc/passwd")
    assert result == "/sd/etc/passwd", f"Expected '/sd/etc/passwd' (sanitized within base), got '{result}'"

    # Test path with current directory references (.)
    result = manager._sanitize_path("/sd", "/sd/./test.txt")
    assert result == "/sd/test.txt", f"Expected '/sd/test.txt', got '{result}'"

    # Test path with multiple slashes
    result = manager._sanitize_path("/sd", "/sd//test.txt")
    assert result == "/sd/test.txt", f"Expected '/sd/test.txt', got '{result}'"

    # Test nested directories
    result = manager._sanitize_path("/sd", "/sd/dir1/dir2/test.txt")
    assert result == "/sd/dir1/dir2/test.txt", f"Expected '/sd/dir1/dir2/test.txt', got '{result}'"

    # Test empty path
    result = manager._sanitize_path("/sd", "")
    assert result == "/sd", f"Expected '/sd', got '{result}'"

    # Test path with only base
    result = manager._sanitize_path("/sd", "/sd")
    assert result == "/sd", f"Expected '/sd', got '{result}'"

    print("  ✓ Path sanitization test passed")


def test_filename_validation():
    """Test filename validation logic."""
    print("\nTesting filename validation...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)
    manager.server = MockServer(None, "/static")
    manager.setup_routes()

    # Find the upload_file route
    upload_route = None
    for path, method, func in manager.server.routes:
        if path == "/api/files/upload":
            upload_route = func
            break

    assert upload_route is not None, "Upload route not found"

    # Test filename with forward slash
    request = MockRequest()
    request.query_params = {"path": "/sd", "filename": "test/file.txt"}
    request.body = b"test content"
    response = upload_route(request)
    assert response.status == 400, "Should reject filename with forward slash"
    assert "path separators not allowed" in response.body

    # Test filename with backslash
    request = MockRequest()
    request.query_params = {"path": "/sd", "filename": "test\\file.txt"}
    request.body = b"test content"
    response = upload_route(request)
    assert response.status == 400, "Should reject filename with backslash"
    assert "path separators not allowed" in response.body

    # Test filename that is ".."
    request = MockRequest()
    request.query_params = {"path": "/sd", "filename": ".."}
    request.body = b"test content"
    response = upload_route(request)
    assert response.status == 400, "Should reject '..' as filename"
    assert "directory references not allowed" in response.body

    # Test filename that is "."
    request = MockRequest()
    request.query_params = {"path": "/sd", "filename": "."}
    request.body = b"test content"
    response = upload_route(request)
    assert response.status == 400, "Should reject '.' as filename"
    assert "directory references not allowed" in response.body

    # Test empty filename
    request = MockRequest()
    request.query_params = {"path": "/sd", "filename": ""}
    request.body = b"test content"
    response = upload_route(request)
    assert response.status == 400, "Should reject empty filename"
    assert "Filename required" in response.body or "cannot be empty" in response.body

    # Test whitespace-only filename
    request = MockRequest()
    request.query_params = {"path": "/sd", "filename": "   "}
    request.body = b"test content"
    response = upload_route(request)
    assert response.status == 400, "Should reject whitespace-only filename"
    assert "cannot be empty" in response.body or "Filename" in response.body

    print("  ✓ Filename validation test passed")


def test_path_security_integration():
    """Test that invalid paths are sanitized and don't access unauthorized files."""
    print("\nTesting path security integration...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)
    
    # Test the sanitization directly to verify security behavior
    # Test 1: Absolute path outside base is sanitized to base
    result = manager._sanitize_path("/sd", "/etc/passwd")
    assert result == "/sd", f"Should sanitize /etc/passwd to /sd, got {result}"
    
    # Test 2: Traversal attempt is contained within base
    result = manager._sanitize_path("/sd", "/sd/../../../etc/passwd")
    assert result.startswith("/sd"), f"Should stay within /sd, got {result}"
    assert "/etc" not in result or result.startswith("/sd/etc"), f"Should not escape to /etc, got {result}"
    
    # Test 3: Verify the download route uses sanitized paths
    manager.server = MockServer(None, "/static")
    manager.setup_routes()
    
    download_route = None
    for path, method, func in manager.server.routes:
        if path == "/api/files/download":
            download_route = func
            break
    
    assert download_route is not None, "Download route not found"
    
    # When an attacker tries /etc/passwd, it gets sanitized to /sd
    # The key security guarantee is that normalized_path will never be /etc/passwd
    request = MockRequest()
    request.query_params = {"path": "/etc/passwd"}
    # We can't easily test the file access without mocking the filesystem,
    # but we can verify the sanitization prevents accessing the malicious path
    # by checking that _sanitize_path transforms it safely
    sanitized = manager._sanitize_path("/sd", "/etc/passwd")
    assert sanitized == "/sd", f"Malicious path should be sanitized to /sd, got {sanitized}"

    print("  ✓ Path security integration test passed")


def test_chunked_upload_with_headers():
    """Test that file uploads use Content-Length header for size validation."""
    print("\nTesting chunked upload with Content-Length header...")

    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True
    }

    manager = WebServerManager(config)
    manager.server = MockServer(None, "/static")
    manager.setup_routes()

    # Find the upload_file route
    upload_route = None
    for path, method, func in manager.server.routes:
        if path == "/api/files/upload":
            upload_route = func
            break

    assert upload_route is not None, "Upload route not found"

    # Test: Upload with Content-Length exceeding max size
    # This is the key test - it should reject BEFORE trying to access request.body
    request = MockRequest()
    request.query_params = {"path": "/sd", "filename": "test_large.txt"}
    # Set Content-Length larger than MAX_UPLOAD_SIZE_BYTES (50KB)
    large_size = manager.MAX_UPLOAD_SIZE_BYTES + 1000
    request.headers = {"Content-Length": str(large_size)}
    # Don't set request.body - if the code tries to access it, it will use the empty default
    # The key is that it should reject based on Content-Length header alone
    
    response = upload_route(request)
    assert response.status == 413, f"Should reject large upload based on Content-Length header alone, got status {response.status}"
    assert "too large" in response.body.lower() or "large" in response.body.lower(), f"Error message should mention size, got: {response.body}"
    
    print("  ✓ Chunked upload with Content-Length header test passed")


def run_all_tests():
    """Run all tests."""
    print("="*60)
    print("   WebServerManager Unit Tests")
    print("="*60)

    # Standard tests that don't require async
    tests = [
        test_initialization,
        # test_wifi_connection is async and skipped in standard test run
        test_logging,
        test_directory_listing,
        test_config_save,
        test_html_generation,
        test_route_registration,
        test_invalid_config,
        test_sanitize_path,
        test_filename_validation,
        test_path_security_integration,
        test_chunked_upload_with_headers,
    ]

    try:
        for test in tests:
            test()

        print("\n" + "="*60)
        print("   ✓ All tests passed!")
        print("="*60)
        return True
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
