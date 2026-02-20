#!/usr/bin/env python3
"""Unit tests for WiFiManager."""

import sys
import os
import types

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_wifi_module(connected=False, ip="192.168.1.100"):
    """Create a fresh mock wifi module."""
    wifi_mod = types.ModuleType('wifi')

    class MockRadio:
        def __init__(self):
            self.connected = connected
            self.ipv4_address = ip
            self.enabled = True
            self.connect_calls = []

        def connect(self, ssid, password, timeout=30):
            self.connect_calls.append((ssid, password, timeout))
            self.connected = True

    wifi_mod.radio = MockRadio()
    return wifi_mod


def _make_socketpool_module():
    """Create a fresh mock socketpool module."""
    sp_mod = types.ModuleType('socketpool')

    class MockSocketPool:
        def __init__(self, radio):
            self.radio = radio

    sp_mod.SocketPool = MockSocketPool
    return sp_mod


def _make_ssl_module():
    ssl_mod = types.ModuleType('ssl')
    ssl_mod.create_default_context = lambda: object()
    return ssl_mod


def _make_requests_module():
    req_mod = types.ModuleType('adafruit_requests')

    class MockSession:
        def __init__(self, pool, context):
            self.pool = pool
            self.context = context

    req_mod.Session = MockSession
    return req_mod


def _inject_wifi_mocks(connected=False, ip="192.168.1.100"):
    """Inject wifi/socketpool mocks into sys.modules, return the mock radio."""
    wifi_mod = _make_wifi_module(connected=connected, ip=ip)
    sp_mod = _make_socketpool_module()
    sys.modules['wifi'] = wifi_mod
    sys.modules['socketpool'] = sp_mod
    return wifi_mod.radio


def _inject_http_mocks():
    """Inject ssl/adafruit_requests mocks into sys.modules."""
    sys.modules['ssl'] = _make_ssl_module()
    sys.modules['adafruit_requests'] = _make_requests_module()


def _remove_wifi_mocks():
    """Remove injected WiFi mocks from sys.modules."""
    for mod in ('wifi', 'socketpool', 'ssl', 'adafruit_requests'):
        sys.modules.pop(mod, None)


# ---------------------------------------------------------------------------
# Import the module under test *after* helpers are defined but we import
# it fresh for each test by reloading, so just import once here.
# ---------------------------------------------------------------------------

# Ensure no stale wifi mocks from other test files bleed in
_remove_wifi_mocks()

import importlib
import importlib.util

def _load_wifi_manager():
    """Load a fresh copy of the WiFiManager module."""
    spec = importlib.util.spec_from_file_location(
        "wifi_manager",
        os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'wifi_manager.py')
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_initialization():
    """WiFiManager stores credentials and starts with no connections."""
    print("Testing WiFiManager initialization...")

    wm_mod = _load_wifi_manager()
    config = {"wifi_ssid": "MySSID", "wifi_password": "MyPassword"}
    wm = wm_mod.WiFiManager(config)

    assert wm.ssid == "MySSID"
    assert wm.password == "MyPassword"
    assert wm._wifi is None, "WiFi module should not be imported at init time"
    assert wm._pool is None
    assert wm.is_connected is False
    assert wm.ip_address is None
    assert wm.pool is None

    print("✓ initialization test passed")


def test_initialization_empty_credentials():
    """WiFiManager accepts empty credentials without raising."""
    print("Testing WiFiManager with empty credentials...")

    wm_mod = _load_wifi_manager()
    wm = wm_mod.WiFiManager({})
    assert wm.ssid == ""
    assert wm.password == ""

    print("✓ empty credentials test passed")


def test_connect_success():
    """connect() lazily imports wifi, connects, and sets pool."""
    print("Testing connect() success path...")

    radio = _inject_wifi_mocks(connected=False)
    try:
        wm_mod = _load_wifi_manager()
        config = {"wifi_ssid": "TestSSID", "wifi_password": "TestPass"}
        wm = wm_mod.WiFiManager(config)

        # WiFi module not imported yet
        assert wm._wifi is None

        result = wm.connect(timeout=5)

        assert result is True
        assert wm._wifi is not None, "WiFi module should be imported after connect()"
        assert wm._pool is not None, "Socket pool should be set after connect()"
        assert wm.is_connected is True
        assert wm.ip_address == "192.168.1.100"
        assert wm.pool is not None

        # Verify connection was made with correct credentials
        assert len(radio.connect_calls) == 1
        assert radio.connect_calls[0][0] == "TestSSID"
        assert radio.connect_calls[0][1] == "TestPass"
    finally:
        _remove_wifi_mocks()

    print("✓ connect() success test passed")


def test_connect_already_connected():
    """connect() returns True immediately if already connected, no re-connect."""
    print("Testing connect() when already connected...")

    radio = _inject_wifi_mocks(connected=True)
    try:
        wm_mod = _load_wifi_manager()
        config = {"wifi_ssid": "TestSSID", "wifi_password": "TestPass"}
        wm = wm_mod.WiFiManager(config)

        result = wm.connect(timeout=5)

        assert result is True
        assert wm.is_connected is True
        assert wm._pool is not None
        # Should not have called radio.connect() since already connected
        assert len(radio.connect_calls) == 0
    finally:
        _remove_wifi_mocks()

    print("✓ connect() already-connected test passed")


def test_connect_no_wifi_module():
    """connect() returns False gracefully when wifi module is unavailable."""
    print("Testing connect() when wifi module is unavailable...")

    # Ensure wifi is not in sys.modules
    _remove_wifi_mocks()

    wm_mod = _load_wifi_manager()
    config = {"wifi_ssid": "TestSSID", "wifi_password": "TestPass"}
    wm = wm_mod.WiFiManager(config)

    # wifi module is not available (not in sys.modules, not on the real system)
    # The import will raise ImportError
    result = wm.connect(timeout=5)

    assert result is False
    assert wm._wifi is None
    assert wm.is_connected is False

    print("✓ connect() missing module test passed")


def test_connect_timeout():
    """connect() returns False when connection times out."""
    print("Testing connect() timeout path...")

    wifi_mod = _make_wifi_module(connected=False)
    sp_mod = _make_socketpool_module()

    # Override connect so it does NOT set connected=True
    def mock_incomplete_connect(ssid, password, timeout=30):
        pass  # Simulate a connection attempt that never completes

    wifi_mod.radio.connect = mock_incomplete_connect
    sys.modules['wifi'] = wifi_mod
    sys.modules['socketpool'] = sp_mod

    try:
        wm_mod = _load_wifi_manager()
        config = {"wifi_ssid": "TestSSID", "wifi_password": "TestPass"}
        wm = wm_mod.WiFiManager(config)

        # Use 0 timeout so loop exits immediately
        result = wm.connect(timeout=0)

        assert result is False
        assert wm.is_connected is False
        assert wm._pool is None
    finally:
        _remove_wifi_mocks()

    print("✓ connect() timeout test passed")


def test_disconnect():
    """disconnect() turns off radio and clears pool."""
    print("Testing disconnect()...")

    radio = _inject_wifi_mocks(connected=True)
    try:
        wm_mod = _load_wifi_manager()
        config = {"wifi_ssid": "TestSSID", "wifi_password": "TestPass"}
        wm = wm_mod.WiFiManager(config)
        wm.connect(timeout=5)

        assert wm.is_connected is True
        assert wm._pool is not None

        wm.disconnect()

        assert radio.enabled is False, "radio.enabled should be False after disconnect"
        assert wm._pool is None, "Pool should be cleared after disconnect"
    finally:
        _remove_wifi_mocks()

    print("✓ disconnect() test passed")


def test_disconnect_when_not_connected():
    """disconnect() is safe to call when not connected."""
    print("Testing disconnect() when not connected...")

    _inject_wifi_mocks(connected=False)
    try:
        wm_mod = _load_wifi_manager()
        wm = wm_mod.WiFiManager({"wifi_ssid": "X", "wifi_password": "Y"})

        # Should not raise
        wm.disconnect()
        assert wm._pool is None
    finally:
        _remove_wifi_mocks()

    print("✓ disconnect() when not connected test passed")


def test_disconnect_without_connect():
    """disconnect() is safe to call before connect() is ever called."""
    print("Testing disconnect() before connect()...")

    _remove_wifi_mocks()
    wm_mod = _load_wifi_manager()
    wm = wm_mod.WiFiManager({"wifi_ssid": "X", "wifi_password": "Y"})

    # Should not raise
    wm.disconnect()

    print("✓ disconnect() before connect() test passed")


def test_create_http_session_success():
    """create_http_session() returns a session after successful connect."""
    print("Testing create_http_session() success...")

    _inject_wifi_mocks(connected=False)
    _inject_http_mocks()
    try:
        wm_mod = _load_wifi_manager()
        config = {"wifi_ssid": "TestSSID", "wifi_password": "TestPass"}
        wm = wm_mod.WiFiManager(config)
        wm.connect(timeout=5)

        session = wm.create_http_session()

        assert session is not None
    finally:
        _remove_wifi_mocks()

    print("✓ create_http_session() success test passed")


def test_create_http_session_not_connected():
    """create_http_session() returns None when not connected."""
    print("Testing create_http_session() when not connected...")

    _remove_wifi_mocks()
    wm_mod = _load_wifi_manager()
    wm = wm_mod.WiFiManager({"wifi_ssid": "X", "wifi_password": "Y"})

    session = wm.create_http_session()
    assert session is None

    print("✓ create_http_session() not-connected test passed")


def test_create_http_session_no_requests_lib():
    """create_http_session() returns None gracefully when adafruit_requests is missing."""
    print("Testing create_http_session() with missing adafruit_requests...")

    _inject_wifi_mocks(connected=False)
    # Inject ssl but NOT adafruit_requests
    sys.modules['ssl'] = _make_ssl_module()
    sys.modules.pop('adafruit_requests', None)
    try:
        wm_mod = _load_wifi_manager()
        config = {"wifi_ssid": "TestSSID", "wifi_password": "TestPass"}
        wm = wm_mod.WiFiManager(config)
        wm.connect(timeout=5)

        session = wm.create_http_session()
        assert session is None
    finally:
        _remove_wifi_mocks()

    print("✓ create_http_session() missing-library test passed")


def test_is_connected_property():
    """is_connected reflects actual radio state."""
    print("Testing is_connected property...")

    radio = _inject_wifi_mocks(connected=False)
    try:
        wm_mod = _load_wifi_manager()
        wm = wm_mod.WiFiManager({"wifi_ssid": "X", "wifi_password": "Y"})

        # Before any connection
        assert wm.is_connected is False

        wm.connect(timeout=5)
        assert wm.is_connected is True

        # Simulate disconnection at radio level
        radio.connected = False
        assert wm.is_connected is False
    finally:
        _remove_wifi_mocks()

    print("✓ is_connected property test passed")


def test_ip_address_property():
    """ip_address returns radio IP when connected, None otherwise."""
    print("Testing ip_address property...")

    _inject_wifi_mocks(connected=False, ip="10.0.0.42")
    try:
        wm_mod = _load_wifi_manager()
        wm = wm_mod.WiFiManager({"wifi_ssid": "X", "wifi_password": "Y"})

        assert wm.ip_address is None

        wm.connect(timeout=5)
        assert str(wm.ip_address) == "10.0.0.42"
    finally:
        _remove_wifi_mocks()

    print("✓ ip_address property test passed")


def test_pool_property():
    """pool returns socket pool after connect, None before."""
    print("Testing pool property...")

    _inject_wifi_mocks(connected=False)
    try:
        wm_mod = _load_wifi_manager()
        wm = wm_mod.WiFiManager({"wifi_ssid": "X", "wifi_password": "Y"})

        assert wm.pool is None

        wm.connect(timeout=5)
        assert wm.pool is not None

        wm.disconnect()
        assert wm.pool is None
    finally:
        _remove_wifi_mocks()

    print("✓ pool property test passed")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests():
    """Run all WiFiManager tests."""
    print("\n" + "="*60)
    print("   WIFI MANAGER TESTS")
    print("="*60 + "\n")

    tests = [
        test_initialization,
        test_initialization_empty_credentials,
        test_connect_success,
        test_connect_already_connected,
        test_connect_no_wifi_module,
        test_connect_timeout,
        test_disconnect,
        test_disconnect_when_not_connected,
        test_disconnect_without_connect,
        test_create_http_session_success,
        test_create_http_session_not_connected,
        test_create_http_session_no_requests_lib,
        test_is_connected_property,
        test_ip_address_property,
        test_pool_property,
    ]

    passed = 0
    failed = 0

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
