"""Test module for OTA updater emulator support.

Verifies:
- ota_updater.py file exists with valid Python syntax
- OTA_UPDATER is registered in the manifest as an ADMIN mode requiring WIFI
- AsyncOTAEngine.is_core_writable() correctly tests write access via the sandbox
- AsyncOTAEngine.fetch_manifest() parses version.json and manifest.json payloads
- AsyncOTAEngine.verify_files() detects the "update available" state
- AsyncOTAEngine.verify_files() correctly identifies the "up to date" state
- AsyncOTAEngine.download_file() writes files to the configured download_dir
- OtaUpdater display transitions: CONNECTING → CHECKING → SCANNING → DOWNLOADING → COMPLETE
- The OTA download directory is sandboxed (not inside the source repository)
"""

import sys
import os
import asyncio
import hashlib
import json
import tempfile
import traceback
import types

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# ---------------------------------------------------------------------------
# CircuitPython module stubs required before importing ota_updater
# ---------------------------------------------------------------------------

class _GenericMock:
    """Catch-all stub for any CircuitPython module attribute."""
    def __getattr__(self, name):
        return _GenericMock()
    def __call__(self, *a, **kw):
        return _GenericMock()
    def __iter__(self):
        return iter([])
    def __bool__(self):
        return False


def _inject_cp_stubs():
    stubs = [
        'microcontroller', 'board', 'busio', 'digitalio', 'analogio',
        'neopixel', 'audiocore', 'audiobusio', 'audiomixer', 'synthio',
        'displayio', 'terminalio', 'adafruit_displayio_ssd1306',
        'adafruit_display_text', 'adafruit_display_text.label',
        'adafruit_ticks', 'adafruit_ht16k33', 'adafruit_ht16k33.segments',
        'adafruit_mcp230xx', 'adafruit_mcp230xx.mcp23017',
        'adafruit_mcp230xx.mcp23008', 'adafruit_pixel_framebuf',
        'keypad', 'rotaryio', 'storage', 'supervisor', 'pwmio',
        'sdcardio', 'adafruit_httpserver', 'adafruit_requests',
    ]
    for mod in stubs:
        if mod not in sys.modules:
            sys.modules[mod] = _GenericMock()

    # microcontroller.reset() must be callable without crashing the test process
    mc = types.ModuleType('microcontroller')
    mc.reset = lambda: (_ for _ in ()).throw(SystemExit(0))
    sys.modules['microcontroller'] = mc


_inject_cp_stubs()

# ---------------------------------------------------------------------------
# Lightweight mock hardware (mirrors the pattern in other test_*.py files)
# ---------------------------------------------------------------------------

class MockDisplay:
    """Records all display API calls for assertion in tests."""

    def __init__(self):
        self.header = ""
        self.status_main = ""
        self.status_sub = ""
        self.footer = ""
        self.layout = "standard"
        self.history = []   # Ordered log of (method, *args)

    def use_standard_layout(self):
        self.layout = "standard"
        self.history.append(('use_standard_layout',))

    def update_header(self, text):
        self.header = text
        self.history.append(('update_header', text))

    def update_status(self, main, sub=None):
        self.status_main = main
        if sub is not None:
            self.status_sub = sub
        self.history.append(('update_status', main, sub))

    def update_footer(self, text):
        self.footer = text
        self.history.append(('update_footer', text))


class MockAudio:
    """Records play() calls without touching real audio hardware."""
    CH_SFX = 1

    def __init__(self):
        self.plays = []

    def play(self, path, channel, level=1.0):
        self.plays.append(path)


class MockHID:
    """Programmatic encoder / button simulator."""

    def __init__(self):
        self._enc_pos = 0
        self._enc_tap = False
        self._btn_state = {}

    def flush(self): pass
    def reset_encoder(self, ch): self._enc_pos = 0
    def encoder_position(self): return self._enc_pos
    def is_encoder_button_pressed(self, action="tap", duration=0):
        if action == "tap":
            v = self._enc_tap
            self._enc_tap = False   # auto-clear after read
            return v
        return False
    def is_button_pressed(self, index, action="tap", duration=0):
        return self._btn_state.get((index, action), False)


class MockWiFiManager:
    """Simulates WiFiManager with controllable success / failure."""

    def __init__(self, should_connect=True):
        self._should_connect = should_connect
        self._connected = False
        self._session = None

    def connect(self, timeout=30):
        self._connected = self._should_connect
        return self._connected

    def disconnect(self):
        self._connected = False

    def create_http_session(self):
        return self._session

    @property
    def is_connected(self):
        return self._connected


class MockHTTPResponse:
    """Configurable fake HTTP response for controlled test scenarios."""

    def __init__(self, status_code=200, json_data=None, content=b""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self._content = content
        self.closed = False

    def json(self):
        return self._json_data

    def iter_content(self, chunk_size=1024):
        data = self._content
        for i in range(0, len(data), chunk_size):
            yield data[i:i + chunk_size]

    def close(self):
        self.closed = True


class MockHTTPSession:
    """Allows tests to pre-configure per-URL responses."""

    def __init__(self, responses=None):
        # responses: dict mapping URL substring → MockHTTPResponse
        self._responses = responses or {}
        self.requests = []

    def get(self, url, timeout=10):
        self.requests.append(url)
        for key, resp in self._responses.items():
            if key in url:
                return resp
        return MockHTTPResponse(status_code=404)


class MockCore:
    """Assembles a minimal core-like object for testing mode classes."""

    def __init__(self, wifi_manager=None):
        self.display = MockDisplay()
        self.hid = MockHID()
        self.audio = MockAudio()
        self.wifi = wifi_manager or MockWiFiManager()
        self.mode = "OTA_UPDATER"
        self.config = {
            "update_url": "https://github.com/jimmydoh/jeb/releases/download/latest",
        }
        self.matrix = _GenericMock()
        self.led = _GenericMock()


# ---------------------------------------------------------------------------
# Import project modules after stubs are injected
# ---------------------------------------------------------------------------

from modes.manifest import MODE_REGISTRY  # noqa: E402 - must be after stubs


def _get_ota_module():
    """Import and return the ota_updater module (package-relative import safe)."""
    import importlib
    return importlib.import_module("modes.ota_updater")


# ===========================================================================
# Tests – File / Syntax
# ===========================================================================

def test_ota_updater_file_exists():
    """ota_updater.py must exist inside modes/."""
    path = os.path.join(SRC_DIR, "modes", "ota_updater.py")
    assert os.path.exists(path), "modes/ota_updater.py not found"
    print("✓ ota_updater.py exists")


def test_ota_updater_syntax():
    """ota_updater.py must contain valid Python."""
    path = os.path.join(SRC_DIR, "modes", "ota_updater.py")
    with open(path) as fh:
        code = fh.read()
    compile(code, path, 'exec')
    print("✓ ota_updater.py has valid Python syntax")


# ===========================================================================
# Tests – Manifest Registration
# ===========================================================================

def test_ota_updater_in_manifest():
    """OTA_UPDATER must be registered in MODE_REGISTRY."""
    assert "OTA_UPDATER" in MODE_REGISTRY, "OTA_UPDATER not found in MODE_REGISTRY"
    print("✓ OTA_UPDATER is registered in MODE_REGISTRY")


def test_ota_updater_is_admin_mode():
    """OTA_UPDATER must have menu='ADMIN'."""
    meta = MODE_REGISTRY["OTA_UPDATER"]
    assert meta.get("menu") == "ADMIN", (
        f"OTA_UPDATER should have menu='ADMIN', got {meta.get('menu')!r}"
    )
    print("✓ OTA_UPDATER has menu='ADMIN'")


def test_ota_updater_requires_wifi():
    """OTA_UPDATER must declare a WIFI dependency."""
    meta = MODE_REGISTRY["OTA_UPDATER"]
    requires = meta.get("requires", [])
    assert "WIFI" in requires, (
        f"OTA_UPDATER should require WIFI, got requires={requires!r}"
    )
    print("✓ OTA_UPDATER declares WIFI in 'requires'")


def test_ota_updater_manifest_fields():
    """OTA_UPDATER must have all required manifest metadata fields."""
    meta = MODE_REGISTRY["OTA_UPDATER"]
    required = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    for field in required:
        assert field in meta, f"OTA_UPDATER is missing required manifest field '{field}'"
    print("✓ OTA_UPDATER has all required manifest fields")


# ===========================================================================
# Tests – AsyncOTAEngine: write-permission check
# ===========================================================================

def test_engine_is_core_writable_true():
    """is_core_writable() returns True when the filesystem is writable."""
    ota_mod = _get_ota_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch the engine to use a writable temp path for the test file
        engine = ota_mod.AsyncOTAEngine("https://example.com", MockWiFiManager())

        # Monkeypatch open to redirect /.fs_test into the temp dir
        import builtins as _builtins
        _real_open = _builtins.open
        _test_path = os.path.join(tmpdir, '.fs_test')

        def _patched_open(file, *args, **kwargs):
            if file == '/.fs_test':
                file = _test_path
            return _real_open(file, *args, **kwargs)

        _builtins.open = _patched_open
        _real_remove = os.remove

        def _patched_remove(path):
            if path == '/.fs_test':
                path = _test_path
            return _real_remove(path)

        os.remove = _patched_remove
        try:
            result = engine.is_core_writable()
        finally:
            _builtins.open = _real_open
            os.remove = _real_remove

    assert result is True, "is_core_writable() should return True on a writable filesystem"
    print("✓ is_core_writable() returns True on writable filesystem")


def test_engine_is_core_writable_false():
    """is_core_writable() returns False when open raises OSError."""
    ota_mod = _get_ota_module()
    engine = ota_mod.AsyncOTAEngine("https://example.com", MockWiFiManager())

    import builtins as _builtins
    _real_open = _builtins.open

    def _raising_open(file, *args, **kwargs):
        if file == '/.fs_test':
            raise OSError("read-only filesystem")
        return _real_open(file, *args, **kwargs)

    _builtins.open = _raising_open
    try:
        result = engine.is_core_writable()
    finally:
        _builtins.open = _real_open

    assert result is False, "is_core_writable() should return False when write is denied"
    print("✓ is_core_writable() returns False on read-only filesystem")


# ===========================================================================
# Tests – AsyncOTAEngine: manifest fetching
# ===========================================================================

def test_engine_fetch_manifest_success():
    """fetch_manifest() populates remote_version and manifest from HTTP responses."""
    ota_mod = _get_ota_module()
    wifi = MockWiFiManager(should_connect=True)
    engine = ota_mod.AsyncOTAEngine("https://example.com/updates", wifi)

    version_data = {"version": "1.2.3", "file_count": 2}
    manifest_data = {
        "version": "1.2.3",
        "files": [
            {
                "path": "modes/ota_updater.mpy",
                "download_path": "modes/ota_updater.mpy",
                "sha256": "abc123",
                "size": 1024,
                "destination": "/modes/ota_updater.mpy",
            }
        ]
    }

    session = MockHTTPSession({
        "version.json": MockHTTPResponse(200, json_data=version_data),
        "manifest.json": MockHTTPResponse(200, json_data=manifest_data),
    })
    engine.http_session = session

    asyncio.run(engine.fetch_manifest())

    assert engine.remote_version == version_data, "remote_version not set correctly"
    assert engine.manifest == manifest_data, "manifest not set correctly"
    print("✓ fetch_manifest() populates remote_version and manifest")


def test_engine_fetch_manifest_http_error():
    """fetch_manifest() raises UpdaterError when version.json returns non-200."""
    ota_mod = _get_ota_module()
    engine = ota_mod.AsyncOTAEngine("https://example.com/updates", MockWiFiManager())

    session = MockHTTPSession({
        "version.json": MockHTTPResponse(404),
    })
    engine.http_session = session

    try:
        asyncio.run(engine.fetch_manifest())
        assert False, "Expected UpdaterError was not raised"
    except ota_mod.UpdaterError as e:
        assert "version.json" in str(e).lower() or "fetch" in str(e).lower(), (
            f"UpdaterError message not descriptive: {e}"
        )
    print("✓ fetch_manifest() raises UpdaterError on HTTP 404")


# ===========================================================================
# Tests – AsyncOTAEngine: file comparison (verify_files)
# ===========================================================================

def test_engine_verify_files_update_available():
    """verify_files() returns files whose hashes do not match local copies."""
    ota_mod = _get_ota_module()
    engine = ota_mod.AsyncOTAEngine("https://example.com/updates", MockWiFiManager())
    engine.remote_version = {"version": "1.2.3"}
    engine.manifest = {
        "version": "1.2.3",
        "files": [
            {
                "path": "modes/ota_updater.mpy",
                "download_path": "modes/ota_updater.mpy",
                "sha256": "deadbeef" * 8,  # intentionally wrong hash
                "size": 512,
                "destination": "/modes/ota_updater.mpy",
            }
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a local file with different content → hash will not match
        local_file = os.path.join(tmpdir, "ota_updater.mpy")
        with open(local_file, "wb") as fh:
            fh.write(b"old content")

        # Redirect the destination to our temp dir
        import builtins as _builtins
        _real_open = _builtins.open

        def _patched_open(file, *args, **kwargs):
            if file == '/modes/ota_updater.mpy':
                file = local_file
            return _real_open(file, *args, **kwargs)

        _builtins.open = _patched_open
        try:
            files_to_update = asyncio.run(engine.verify_files())
        finally:
            _builtins.open = _real_open

    assert len(files_to_update) == 1, (
        f"Expected 1 file needing update, got {len(files_to_update)}"
    )
    print("✓ verify_files() correctly identifies file needing update (mismatched hash)")


def test_engine_verify_files_up_to_date():
    """verify_files() returns an empty list when all hashes match."""
    ota_mod = _get_ota_module()
    engine = ota_mod.AsyncOTAEngine("https://example.com/updates", MockWiFiManager())
    engine.remote_version = {"version": "1.2.3"}

    # Write known content and compute its real SHA-256
    content = b"current firmware content"
    sha = hashlib.sha256(content).hexdigest()

    engine.manifest = {
        "version": "1.2.3",
        "files": [
            {
                "path": "modes/ota_updater.mpy",
                "download_path": "modes/ota_updater.mpy",
                "sha256": sha,
                "size": len(content),
                "destination": "/modes/ota_updater.mpy",
            }
        ]
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        local_file = os.path.join(tmpdir, "ota_updater.mpy")
        with open(local_file, "wb") as fh:
            fh.write(content)

        import builtins as _builtins
        _real_open = _builtins.open

        def _patched_open(file, *args, **kwargs):
            if file == '/modes/ota_updater.mpy':
                file = local_file
            return _real_open(file, *args, **kwargs)

        _builtins.open = _patched_open
        try:
            files_to_update = asyncio.run(engine.verify_files())
        finally:
            _builtins.open = _real_open

    assert len(files_to_update) == 0, (
        f"Expected 0 files needing update (up to date), got {len(files_to_update)}"
    )
    print("✓ verify_files() returns empty list when all hashes match (system up to date)")


def test_engine_verify_files_missing_local():
    """verify_files() treats a missing local file as needing an update."""
    ota_mod = _get_ota_module()
    engine = ota_mod.AsyncOTAEngine("https://example.com/updates", MockWiFiManager())
    engine.remote_version = {"version": "1.2.3"}
    engine.manifest = {
        "version": "1.2.3",
        "files": [
            {
                "path": "modes/new_feature.mpy",
                "download_path": "modes/new_feature.mpy",
                "sha256": "a" * 64,
                "size": 256,
                "destination": "/modes/new_feature.mpy",
            }
        ]
    }

    # No local file is created → open will raise OSError → treated as "missing"
    import builtins as _builtins
    _real_open = _builtins.open

    def _patched_open(file, *args, **kwargs):
        if file == '/modes/new_feature.mpy':
            raise OSError("file not found")
        return _real_open(file, *args, **kwargs)

    _builtins.open = _patched_open
    try:
        files_to_update = asyncio.run(engine.verify_files())
    finally:
        _builtins.open = _real_open

    assert len(files_to_update) == 1, (
        "Missing local file should be treated as needing an update"
    )
    print("✓ verify_files() treats missing local file as update-needed")


def test_engine_verify_files_ignores_frozen():
    """verify_files() skips files with action='ignore_if_frozen'."""
    ota_mod = _get_ota_module()
    engine = ota_mod.AsyncOTAEngine("https://example.com/updates", MockWiFiManager())
    engine.remote_version = {"version": "1.2.3"}
    engine.manifest = {
        "version": "1.2.3",
        "files": [
            {
                "path": "modes/frozen_file.mpy",
                "download_path": "modes/frozen_file.mpy",
                "sha256": "b" * 64,
                "size": 128,
                "destination": "/modes/frozen_file.mpy",
                "action": "ignore_if_frozen",
            }
        ]
    }

    files_to_update = asyncio.run(engine.verify_files())
    assert len(files_to_update) == 0, (
        "Files with action='ignore_if_frozen' should be skipped by verify_files()"
    )
    print("✓ verify_files() skips files with action='ignore_if_frozen'")


# ===========================================================================
# Tests – AsyncOTAEngine: download (sandbox safety)
# ===========================================================================

def test_engine_download_writes_to_download_dir():
    """download_file() writes the downloaded content to download_dir, not to /."""
    ota_mod = _get_ota_module()

    with tempfile.TemporaryDirectory() as tmpdir:
        content = b"firmware bytes " * 50
        sha = hashlib.sha256(content).hexdigest()

        engine = ota_mod.AsyncOTAEngine("https://example.com/updates", MockWiFiManager())
        engine.remote_version = {"version": "1.2.3"}
        engine.download_dir = tmpdir     # point to safe sandbox

        file_info = {
            "path": "modes/ota_updater.mpy",
            "download_path": "modes/ota_updater.mpy",
            "sha256": sha,
            "size": len(content),
            "destination": "/modes/ota_updater.mpy",
        }

        response = MockHTTPResponse(200, content=content)
        session = MockHTTPSession()
        session._responses = {"modes/ota_updater.mpy": response}
        engine.http_session = session

        progress_calls = []
        asyncio.run(engine.download_file(file_info, lambda b: progress_calls.append(b)))

        expected_path = os.path.join(tmpdir, "modes", "ota_updater.mpy")
        assert os.path.exists(expected_path), (
            f"Downloaded file not found at sandbox path: {expected_path}"
        )
        with open(expected_path, "rb") as fh:
            written = fh.read()
        assert written == content, "Downloaded content does not match original"
        assert len(progress_calls) > 0, "Progress callback was never invoked"

    print("✓ download_file() writes content to download_dir (sandboxed, not to /)")


def test_engine_download_dir_is_not_in_src():
    """The OTA engine's default download_dir must not overlap with SRC_DIR."""
    ota_mod = _get_ota_module()
    engine = ota_mod.AsyncOTAEngine("https://example.com/updates", MockWiFiManager())
    download_dir = engine.download_dir

    # Normalise both paths for comparison
    norm_dl = os.path.normpath(download_dir)
    norm_src = os.path.normpath(SRC_DIR)

    assert not norm_dl.startswith(norm_src), (
        f"download_dir ({norm_dl!r}) must not be inside SRC_DIR ({norm_src!r})"
    )
    print(f"✓ engine.download_dir ({download_dir!r}) is outside SRC_DIR")


def test_emulator_sandbox_constant_location():
    """The emulator OTA sandbox must be located at emulator_tmp/ota/ under PROJECT_ROOT."""
    expected_sandbox = os.path.normpath(os.path.join(PROJECT_ROOT, 'emulator_tmp', 'ota'))
    # Verify the constant exists in jeb_emulator.py source (by reading the file)
    emulator_path = os.path.join(PROJECT_ROOT, 'emulator', 'jeb_emulator.py')
    assert os.path.exists(emulator_path), "jeb_emulator.py not found"

    with open(emulator_path) as fh:
        source = fh.read()

    assert "OTA_SANDBOX_DIR" in source, (
        "jeb_emulator.py should define OTA_SANDBOX_DIR constant"
    )
    assert "emulator_tmp" in source, (
        "jeb_emulator.py should reference 'emulator_tmp' for the OTA sandbox"
    )
    print(f"✓ emulator defines OTA_SANDBOX_DIR pointing at emulator_tmp/ota/")


def test_emulator_path_mapper_redirects_sd_update():
    """smart_path_mapper() must redirect /sd/update to the OTA staging sandbox."""
    emulator_path = os.path.join(PROJECT_ROOT, 'emulator', 'jeb_emulator.py')
    with open(emulator_path) as fh:
        source = fh.read()

    # Verify the key redirection logic is present in the emulator source
    assert "/sd/update" in source, (
        "jeb_emulator.py smart_path_mapper should handle /sd/update paths"
    )
    assert "staging" in source, (
        "jeb_emulator.py should redirect /sd/update to a staging sandbox directory"
    )
    print("✓ jeb_emulator.py redirects /sd/update to OTA staging sandbox")


def test_emulator_adafruit_requests_mock_present():
    """jeb_emulator.py should include an adafruit_requests mock using urllib."""
    emulator_path = os.path.join(PROJECT_ROOT, 'emulator', 'jeb_emulator.py')
    with open(emulator_path) as fh:
        source = fh.read()

    assert "adafruit_requests" in source, (
        "jeb_emulator.py should mock adafruit_requests"
    )
    assert "urllib.request" in source, (
        "jeb_emulator.py adafruit_requests mock should delegate to urllib.request"
    )
    assert "iter_content" in source, (
        "Mock response should implement iter_content() for chunked downloads"
    )
    print("✓ jeb_emulator.py provides adafruit_requests mock via urllib.request")


# ===========================================================================
# Tests – OtaUpdater display state transitions
# ===========================================================================

def _make_ota_updater(core):
    mod = _get_ota_module()
    updater = mod.OtaUpdater(core)
    return updater, mod


def _extract_headers(display_history):
    """Extract header strings from MockDisplay history (flattens tuple arguments)."""
    return [args[0] for method, *args in display_history if method == 'update_header']


def _run_perform_update(updater, sd_only=False):
    """Run _perform_update with asyncio.sleep patched to be instant."""
    import asyncio as _asyncio

    async def _instant_sleep(_t):
        pass

    original_sleep = _asyncio.sleep
    _asyncio.sleep = _instant_sleep
    try:
        _asyncio.run(updater._perform_update(sd_only=sd_only))
    finally:
        _asyncio.sleep = original_sleep


def test_display_connecting_state():
    """_perform_update() must show 'CONNECTING...' header before WiFi connect."""
    core = MockCore()
    updater, mod = _make_ota_updater(core)

    header_at_connect = []

    async def _spy_connect():
        header_at_connect.append(core.display.header)
        raise mod.UpdaterError("Wi-Fi connection failed")

    updater.engine.connect = _spy_connect

    _run_perform_update(updater)

    assert header_at_connect, "connect() was never called"
    assert header_at_connect[0] == "CONNECTING...", (
        f"Expected 'CONNECTING...' before connect(), got {header_at_connect[0]!r}"
    )
    print("✓ _perform_update() shows 'CONNECTING...' before WiFi connect")


def test_display_checking_state():
    """_perform_update() must show 'CHECKING...' before fetching the manifest."""
    core = MockCore()
    updater, mod = _make_ota_updater(core)

    header_at_fetch = []

    async def _mock_connect():
        pass

    async def _spy_fetch():
        header_at_fetch.append(core.display.header)
        raise mod.UpdaterError("stop here")

    updater.engine.connect = _mock_connect
    updater.engine.fetch_manifest = _spy_fetch

    _run_perform_update(updater)

    assert header_at_fetch, "fetch_manifest() was never called"
    assert header_at_fetch[0] == "CHECKING...", (
        f"Expected 'CHECKING...' before fetch_manifest(), got {header_at_fetch[0]!r}"
    )
    print("✓ _perform_update() shows 'CHECKING...' before manifest fetch")


def test_display_up_to_date_state():
    """_perform_update() must show 'UP TO DATE' when version already matches."""
    core = MockCore()
    updater, mod = _make_ota_updater(core)

    matching_version = "1.2.3"

    async def _mock_connect():
        pass

    async def _mock_fetch():
        updater.engine.remote_version = {"version": matching_version}
        updater.engine.manifest = {"version": matching_version, "files": []}

    def _mock_get_local():
        return {"version": matching_version}

    updater.engine.connect = _mock_connect
    updater.engine.fetch_manifest = _mock_fetch
    updater.engine.get_local_version = _mock_get_local

    _run_perform_update(updater)

    headers = _extract_headers(core.display.history)
    assert "UP TO DATE" in headers, (
        f"'UP TO DATE' never appeared in headers: {headers}"
    )
    print("✓ _perform_update() shows 'UP TO DATE' when version already matches")


def test_display_scanning_state():
    """_perform_update() must show 'SCANNING...' while computing local file hashes."""
    core = MockCore()
    updater, mod = _make_ota_updater(core)

    header_at_verify = []

    async def _mock_connect():
        pass

    async def _mock_fetch():
        updater.engine.remote_version = {"version": "2.0.0"}
        updater.engine.manifest = {"version": "2.0.0", "files": []}

    async def _spy_verify(sd_only=False):
        header_at_verify.append(core.display.header)
        return []

    updater.engine.connect = _mock_connect
    updater.engine.fetch_manifest = _mock_fetch
    updater.engine.verify_files = _spy_verify
    # Return None so the version-match short-circuit does not fire
    updater.engine.get_local_version = lambda: None

    _run_perform_update(updater)

    assert header_at_verify, "verify_files() was never called"
    assert header_at_verify[0] == "SCANNING...", (
        f"Expected 'SCANNING...' before verify_files(), got {header_at_verify[0]!r}"
    )
    print("✓ _perform_update() shows 'SCANNING...' before local file hash check")


def test_display_downloading_state():
    """_perform_update() must show a 'DL [x/y]' header during file downloads."""
    core = MockCore()
    updater, mod = _make_ota_updater(core)

    dl_headers = []
    file_info = {
        "path": "modes/ota_updater.mpy",
        "download_path": "modes/ota_updater.mpy",
        "sha256": "a" * 64,
        "size": 100,
        "destination": "/modes/ota_updater.mpy",
    }

    async def _mock_connect(): pass

    async def _mock_fetch():
        updater.engine.remote_version = {"version": "2.0.0"}
        updater.engine.manifest = {"version": "2.0.0", "files": [file_info]}

    async def _mock_verify(sd_only=False):
        return [file_info]

    async def _spy_download(fi, progress_cb):
        # The DL header is set inside the progress callback; invoke it to trigger it
        progress_cb(50)
        dl_headers.append(core.display.header)

    async def _mock_install(fi):
        pass

    updater.engine.connect = _mock_connect
    updater.engine.fetch_manifest = _mock_fetch
    updater.engine.verify_files = _mock_verify
    updater.engine.download_file = _spy_download
    updater.engine.install_file = _mock_install
    updater.engine.check_disk_space = lambda files: None
    # Return None so the version-match short-circuit does not fire
    updater.engine.get_local_version = lambda: None

    import microcontroller as _mc
    _mc.reset = lambda: None

    _run_perform_update(updater)

    assert dl_headers, "download_file() was never called"
    assert any("DL [" in h for h in dl_headers), (
        f"No 'DL [x/y]' header found during download; headers: {dl_headers}"
    )
    print("✓ _perform_update() shows 'DL [x/y]' header during downloads")


def test_display_success_state():
    """_perform_update() must show 'SUCCESS' after all files are installed."""
    core = MockCore()
    updater, mod = _make_ota_updater(core)

    file_info = {
        "path": "modes/ota_updater.mpy",
        "download_path": "modes/ota_updater.mpy",
        "sha256": "a" * 64,
        "size": 100,
        "destination": "/modes/ota_updater.mpy",
    }

    async def _mock_connect(): pass

    async def _mock_fetch():
        updater.engine.remote_version = {"version": "2.0.0"}
        updater.engine.manifest = {"version": "2.0.0", "files": [file_info]}

    async def _mock_verify(sd_only=False):
        return [file_info]

    async def _mock_download(fi, progress_cb): pass
    async def _mock_install(fi): pass

    updater.engine.connect = _mock_connect
    updater.engine.fetch_manifest = _mock_fetch
    updater.engine.verify_files = _mock_verify
    updater.engine.download_file = _mock_download
    updater.engine.install_file = _mock_install
    updater.engine.check_disk_space = lambda files: None
    updater.engine.write_local_version = lambda: None
    # Return None so the version-match short-circuit does not fire
    updater.engine.get_local_version = lambda: None

    import microcontroller as _mc
    _mc.reset = lambda: None

    _run_perform_update(updater)

    headers = _extract_headers(core.display.history)
    assert "SUCCESS" in headers, (
        f"'SUCCESS' never appeared after install; headers: {headers}"
    )
    print("✓ _perform_update() shows 'SUCCESS' after all files are installed")


def test_display_error_state():
    """_perform_update() must show 'UPDATE FAILED' when an UpdaterError occurs."""
    core = MockCore()
    updater, mod = _make_ota_updater(core)

    async def _failing_connect():
        raise mod.UpdaterError("Wi-Fi connection failed")

    updater.engine.connect = _failing_connect

    _run_perform_update(updater)

    headers = _extract_headers(core.display.history)
    assert "UPDATE FAILED" in headers, (
        f"'UPDATE FAILED' never appeared after error; headers: {headers}"
    )
    print("✓ _perform_update() shows 'UPDATE FAILED' on UpdaterError")


# ===========================================================================
# Runner
# ===========================================================================

def run_all_tests():
    print("\n" + "=" * 65)
    print("   OTA EMULATOR TESTS")
    print("=" * 65 + "\n")

    tests = [
        # File / syntax
        test_ota_updater_file_exists,
        test_ota_updater_syntax,
        # Manifest
        test_ota_updater_in_manifest,
        test_ota_updater_is_admin_mode,
        test_ota_updater_requires_wifi,
        test_ota_updater_manifest_fields,
        # Engine – write permission
        test_engine_is_core_writable_true,
        test_engine_is_core_writable_false,
        # Engine – manifest fetch
        test_engine_fetch_manifest_success,
        test_engine_fetch_manifest_http_error,
        # Engine – file comparison
        test_engine_verify_files_update_available,
        test_engine_verify_files_up_to_date,
        test_engine_verify_files_missing_local,
        test_engine_verify_files_ignores_frozen,
        # Engine – download sandbox safety
        test_engine_download_writes_to_download_dir,
        test_engine_download_dir_is_not_in_src,
        # Emulator structural checks
        test_emulator_sandbox_constant_location,
        test_emulator_path_mapper_redirects_sd_update,
        test_emulator_adafruit_requests_mock_present,
        # Display state transitions
        test_display_connecting_state,
        test_display_checking_state,
        test_display_up_to_date_state,
        test_display_scanning_state,
        test_display_downloading_state,
        test_display_success_state,
        test_display_error_state,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as exc:
            print(f"❌ {test.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"❌ {test.__name__} (unexpected error): {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    return failed == 0


if __name__ == "__main__":
    ok = run_all_tests()
    sys.exit(0 if ok else 1)
