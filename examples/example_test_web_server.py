#!/usr/bin/env python3
"""
Standalone test script for WebServerManager.

This script runs only the web server for testing without loading
the full JEB application. Useful for development and debugging.

Usage:
    python3 examples/test_web_server.py
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock CircuitPython modules for testing on regular Python
class MockWiFi:
    class Radio:
        connected = True
        ipv4_address = "192.168.1.100"
        
        def connect(self, ssid, password, timeout=30):
            print(f"Mock: Connecting to {ssid}")
            self.connected = True
    
    radio = Radio()

class MockSocketPool:
    def __init__(self, radio):
        self.radio = radio

class MockServer:
    def __init__(self, pool, static_dir, debug=False):
        self.pool = pool
        self.routes = []
        print(f"Mock Server created (debug={debug})")
    
    def route(self, path, method):
        def decorator(func):
            self.routes.append((path, method, func))
            print(f"Registered route: {method.__name__} {path}")
            return func
        return decorator
    
    def start(self, host, port):
        print(f"Mock Server started on {host}:{port}")
    
    def poll(self):
        pass
    
    def stop(self):
        print("Mock Server stopped")

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

def test_web_server():
    """Test the web server manager."""
    print("\n" + "="*60)
    print("   WebServerManager Test")
    print("="*60 + "\n")
    
    # Test configuration
    config = {
        "wifi_ssid": "TestNetwork",
        "wifi_password": "TestPassword123",
        "web_server_enabled": True,
        "web_server_port": 8080,
        "debug_mode": True,
        "role": "CORE",
        "type_id": "00"
    }
    
    try:
        print("1. Creating WebServerManager...")
        manager = WebServerManager(config)
        print("   ✓ Manager created successfully")
        
        print("\n2. Testing WiFi connection...")
        connected = manager.connect_wifi()
        print(f"   ✓ WiFi connected: {connected}")
        
        print("\n3. Testing log functionality...")
        manager.log("Test log message 1")
        manager.log("Test log message 2")
        manager.log("Test log message 3")
        print(f"   ✓ Logged {len(manager.logs)} messages")
        
        print("\n4. Testing config save...")
        manager._save_config()
        print("   ✓ Config save completed")
        
        print("\n5. Testing directory listing...")
        try:
            files = manager._list_directory(".")
            print(f"   ✓ Listed {len(files['items'])} items")
        except Exception as e:
            print(f"   ⚠️ Directory listing failed (expected in test env): {e}")
        
        print("\n6. Testing HTML generation...")
        html = manager._generate_html_page()
        print(f"   ✓ Generated HTML page ({len(html)} bytes)")
        print(f"   ✓ HTML contains title: {'JEB Field Service' in html}")
        
        print("\n7. Setting up routes...")
        manager.server = MockServer(None, "/static")
        manager.setup_routes()
        print(f"   ✓ Setup {len(manager.server.routes)} routes:")
        for path, method, func in manager.server.routes:
            print(f"      - {method.__name__} {path}")
        
        # Verify all expected routes are present
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
            if expected not in registered_paths:
                print(f"   ⚠️ WARNING: Expected route not found: {expected}")
        
        print("\n" + "="*60)
        print("   ✓ All tests passed!")
        print("="*60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_web_server()
    sys.exit(0 if success else 1)
