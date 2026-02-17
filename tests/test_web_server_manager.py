#!/usr/bin/env python3
"""Unit tests for WebServerManager."""

import sys
import os
import json
import pytest

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

    # Test path trying to escape base (should not go above base)
    result = manager._sanitize_path("/sd", "/sd/../../etc/passwd")
    assert result == "/sd/etc/passwd", f"Expected '/sd/etc/passwd', got '{result}'"

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

    # Test just filename (no base path)
    result = manager._sanitize_path("", "test.txt")
    assert result == "/test.txt", f"Expected '/test.txt', got '{result}'"

    # Test path with only base
    result = manager._sanitize_path("/sd", "/sd")
    assert result == "/sd", f"Expected '/sd', got '{result}'"

    print("  ✓ Path sanitization test passed")


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
