"""Tests for the PowerTelemetryMode admin mode.

Verifies:
- power_telemetry.py file exists with valid Python syntax
- POWER_TELEMETRY is registered in the manifest as an ADMIN mode with required fields
- PowerTelemetryMode class can be instantiated with a mock core
- Text and waveform rendering helpers behave correctly
- Graceful no-buses fallback works
- Voltage normalization logic is correct
"""

import sys
import os
import asyncio
import traceback

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ---------------------------------------------------------------------------
# Lightweight mocks  (no real hardware or CircuitPython required)
# ---------------------------------------------------------------------------

class MockDigitalInOut:
    def __init__(self, pin=None):
        self.pin = pin
        self.direction = None
        self.pull = None
        self.value = False


class MockDigitalioModule:
    Direction = type('Direction', (), {'OUTPUT': 'OUTPUT', 'INPUT': 'INPUT'})()
    Pull = type('Pull', (), {'UP': 'UP', 'DOWN': 'DOWN'})()

    @staticmethod
    def DigitalInOut(pin):
        return MockDigitalInOut(pin)


class MockModule:
    """Generic mock for any missing CircuitPython module."""
    def __getattr__(self, name):
        return MockModule()

    def __call__(self, *args, **kwargs):
        return MockModule()


# Install mocks before importing project modules
for mod in ('digitalio', 'board', 'microcontroller', 'watchdog',
            'adafruit_ticks', 'busio', 'displayio', 'terminalio',
            'i2cdisplaybus', 'adafruit_displayio_ssd1306',
            'adafruit_display_text', 'adafruit_display_text.label'):
    if mod not in sys.modules:
        sys.modules[mod] = MockDigitalioModule() if mod == 'digitalio' else MockModule()


class MockADC:
    """Minimal ADC manager mock that returns a fixed voltage per channel."""
    def __init__(self, readings=None):
        self.readings = readings or {
            "input_20v": 19.5,
            "satbus_20v": 18.8,
            "main_5v": 5.0,
        }

    def read(self, name):
        return self.readings.get(name, 0.0)


class MockDisplay:
    """Records display calls without touching real hardware."""
    def __init__(self):
        self.layout = "standard"
        self.header = ""
        self.status_main = ""
        self.status_sub = ""
        self.footer = ""
        self.waveform_samples = None

    def use_standard_layout(self):
        self.layout = "standard"

    def use_custom_layout(self):
        self.layout = "custom"

    def update_header(self, text):
        self.header = text

    def update_status(self, main, sub=None):
        self.status_main = main
        if sub is not None:
            self.status_sub = sub

    def update_footer(self, text):
        self.footer = text

    def show_waveform(self, samples):
        self.layout = "custom"
        self.waveform_samples = list(samples)

    def set_custom_content(self, group):
        pass


class MockAudio:
    """Records the last audio play request."""
    CH_SFX = 1

    def __init__(self):
        self.last_play = None

    async def play(self, path, channel, level=1.0):
        self.last_play = path


class MockHID:
    """Simulates button/encoder state for a single test step."""
    def __init__(self):
        self._enc_pos = 0
        self._enc_tap = False
        self._btn_state = {}

    def flush(self):
        pass

    def reset_encoder(self, channel):
        self._enc_pos = 0

    def encoder_position(self):
        return self._enc_pos

    def is_encoder_button_pressed(self, action="tap", duration=0):
        if action == "tap":
            return self._enc_tap
        return False

    def is_button_pressed(self, index, action="tap", duration=0):
        return self._btn_state.get((index, action), False)


class MockPower:
    """Minimal PowerManager mock with configurable buses."""
    def __init__(self, buses=None):
        self.buses = buses or {}

    def is_healthy(self):
        return True, "mock healthy"

    def get_telemetry_payload(self):
        return {name: bus.get_telemetry() for name, bus in self.buses.items()}


class MockCore:
    """Aggregates all mocks into a core-like object."""
    def __init__(self, buses=None):
        self.display = MockDisplay()
        self.hid = MockHID()
        self.audio = MockAudio()
        self.power = MockPower(buses)
        self.mode = "POWER_TELEMETRY"


# ---------------------------------------------------------------------------
# Import project modules after mocks are in place
# ---------------------------------------------------------------------------

from utilities.power_bus import ADCSensorWrapper, PowerBus


def _make_bus(mock_adc, name, min_threshold=1.0):
    return PowerBus(name, ADCSensorWrapper(mock_adc, name), min_threshold=min_threshold)


# ---------------------------------------------------------------------------
# File / syntax checks
# ---------------------------------------------------------------------------

def test_power_telemetry_file_exists():
    """power_telemetry.py must exist in modes/."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'power_telemetry.py')
    assert os.path.exists(path), "power_telemetry.py not found"
    print("✓ power_telemetry.py exists")


def test_power_telemetry_syntax():
    """power_telemetry.py must be valid Python."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'power_telemetry.py')
    with open(path) as f:
        code = f.read()
    compile(code, path, 'exec')
    print("✓ power_telemetry.py syntax is valid")


# ---------------------------------------------------------------------------
# Manifest registration
# ---------------------------------------------------------------------------

def test_power_telemetry_in_manifest():
    """POWER_TELEMETRY must be registered in MODE_REGISTRY as an ADMIN mode."""
    from modes.manifest import MODE_REGISTRY

    assert "POWER_TELEMETRY" in MODE_REGISTRY, "POWER_TELEMETRY not in MODE_REGISTRY"
    meta = MODE_REGISTRY["POWER_TELEMETRY"]

    assert meta["id"] == "POWER_TELEMETRY"
    assert meta["name"] == "PWR TELEMETRY"
    assert meta["module_path"] == "modes.power_telemetry"
    assert meta["class_name"] == "PowerTelemetryMode"
    assert meta["menu"] == "ADMIN", "POWER_TELEMETRY must have menu='ADMIN'"
    assert "CORE" in meta["requires"]
    assert "settings" in meta
    print("✓ POWER_TELEMETRY registered correctly in manifest")


def test_power_telemetry_has_required_metadata_fields():
    """All required manifest fields must be present for POWER_TELEMETRY."""
    from modes.manifest import MODE_REGISTRY

    required = ["id", "name", "module_path", "class_name", "icon", "menu", "requires", "settings"]
    meta = MODE_REGISTRY["POWER_TELEMETRY"]
    for field in required:
        assert field in meta, f"POWER_TELEMETRY missing manifest field '{field}'"
    print("✓ POWER_TELEMETRY has all required manifest fields")


def test_admin_mode_count_increased():
    """There should now be at least 4 admin modes (including POWER_TELEMETRY)."""
    from modes.manifest import MODE_REGISTRY

    admin_modes = [k for k, v in MODE_REGISTRY.items() if v.get("menu") == "ADMIN"]
    assert len(admin_modes) >= 4, f"Expected ≥4 admin modes, found {len(admin_modes)}"
    assert "POWER_TELEMETRY" in admin_modes
    print(f"✓ {len(admin_modes)} admin modes registered (including POWER_TELEMETRY)")


# ---------------------------------------------------------------------------
# Class-level tests
# ---------------------------------------------------------------------------

def test_power_telemetry_instantiation():
    """PowerTelemetryMode must instantiate without errors given a mock core."""
    from modes.power_telemetry import PowerTelemetryMode

    core = MockCore()
    mode = PowerTelemetryMode(core)

    assert mode.name == "PWR TELEMETRY"
    assert mode._view == "TEXT"
    assert mode._histories == {}
    assert mode.HISTORY_SIZE == 128
    assert mode.SAMPLE_INTERVAL == 0.5
    print("✓ PowerTelemetryMode instantiation OK")


def test_get_buses_with_no_power():
    """_get_buses must return {} when power has no buses attribute."""
    from modes.power_telemetry import PowerTelemetryMode

    core = MockCore()
    del core.power.buses          # simulate missing attribute
    mode = PowerTelemetryMode(core)

    assert mode._get_buses() == {}
    print("✓ _get_buses() returns {} when buses attribute absent")


def test_get_buses_with_none():
    """_get_buses must return {} when power.buses is None."""
    from modes.power_telemetry import PowerTelemetryMode

    core = MockCore()
    core.power.buses = None
    mode = PowerTelemetryMode(core)

    assert mode._get_buses() == {}
    print("✓ _get_buses() returns {} when buses is None")


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def test_normalize_empty():
    from modes.power_telemetry import PowerTelemetryMode

    mode = PowerTelemetryMode(MockCore())
    assert mode._normalize([]) == []
    print("✓ _normalize([]) returns []")


def test_normalize_flat_signal():
    """A constant voltage should produce a centred 0.5 flat line."""
    from modes.power_telemetry import PowerTelemetryMode

    mode = PowerTelemetryMode(MockCore())
    flat = [19.5] * 10
    result = mode._normalize(flat)
    assert len(result) == 10
    assert all(v == 0.5 for v in result)
    print("✓ _normalize() flat signal → 0.5 midline")


def test_normalize_range():
    """Normalised output must always be in [0.0, 1.0] and span the full range."""
    from modes.power_telemetry import PowerTelemetryMode

    mode = PowerTelemetryMode(MockCore())
    samples = [18.0, 19.0, 20.0, 19.5, 18.5]
    result = mode._normalize(samples)
    assert len(result) == len(samples)
    assert abs(min(result)) < 1e-9       # min maps to 0.0
    assert abs(max(result) - 1.0) < 1e-9  # max maps to 1.0
    assert all(0.0 <= v <= 1.0 for v in result)
    print("✓ _normalize() correctly maps voltage range to [0, 1]")


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def test_sample_voltages_builds_history():
    """_sample_voltages() must append v_now to each bus history buffer."""
    from modes.power_telemetry import PowerTelemetryMode

    mock_adc = MockADC()
    buses = {
        "input_20v": _make_bus(mock_adc, "input_20v"),
        "main_5v": _make_bus(mock_adc, "main_5v"),
    }
    core = MockCore(buses)
    mode = PowerTelemetryMode(core)

    mode._sample_voltages()

    assert len(mode._histories["input_20v"]) == 1
    assert abs(mode._histories["input_20v"][0] - 19.5) < 0.01
    assert len(mode._histories["main_5v"]) == 1
    assert abs(mode._histories["main_5v"][0] - 5.0) < 0.01
    print("✓ _sample_voltages() correctly populates histories")


def test_history_capped_at_history_size():
    """Rolling history must not exceed HISTORY_SIZE entries."""
    from modes.power_telemetry import PowerTelemetryMode

    mock_adc = MockADC({"input_20v": 19.5})
    buses = {"input_20v": _make_bus(mock_adc, "input_20v")}
    core = MockCore(buses)
    mode = PowerTelemetryMode(core)

    for _ in range(mode.HISTORY_SIZE + 20):
        mode._sample_voltages()

    assert len(mode._histories["input_20v"]) == mode.HISTORY_SIZE
    print(f"✓ History capped at {mode.HISTORY_SIZE} samples")


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def test_render_text_calls_display():
    """_render_text() must use standard layout with correct header/status/footer."""
    from modes.power_telemetry import PowerTelemetryMode

    mock_adc = MockADC({"input_20v": 19.5})
    buses = {"input_20v": _make_bus(mock_adc, "input_20v")}
    core = MockCore(buses)
    mode = PowerTelemetryMode(core)
    mode._sample_voltages()

    mode._render_text(["input_20v"], 0)

    assert core.display.layout == "standard"
    assert core.display.header == "PWR TELEMETRY"
    assert "INPUT_20V" in core.display.status_main
    assert "19.5" in core.display.status_sub or "19.50" in core.display.status_sub
    print("✓ _render_text() calls display correctly")


def test_render_wave_calls_show_waveform():
    """_render_wave() must call display.show_waveform with 128 normalised samples."""
    from modes.power_telemetry import PowerTelemetryMode

    mock_adc = MockADC({"input_20v": 19.5})
    buses = {"input_20v": _make_bus(mock_adc, "input_20v")}
    core = MockCore(buses)
    mode = PowerTelemetryMode(core)

    # Populate a few samples
    for _ in range(10):
        mode._sample_voltages()

    mode._render_wave(["input_20v"], 0)

    assert core.display.waveform_samples is not None
    assert len(core.display.waveform_samples) == 128
    assert all(0.0 <= s <= 1.0 for s in core.display.waveform_samples)
    print("✓ _render_wave() passes 128 normalised samples to show_waveform()")


# ---------------------------------------------------------------------------
# Run-loop: no-buses fallback
# ---------------------------------------------------------------------------

def test_run_exits_gracefully_with_no_buses():
    """run() must set core.mode='DASHBOARD' and return 'NO_BUSES' when no buses are configured."""
    from modes.power_telemetry import PowerTelemetryMode

    core = MockCore(buses={})
    mode = PowerTelemetryMode(core)

    result = asyncio.run(mode.run())

    assert result == "NO_BUSES"
    assert core.mode == "DASHBOARD"
    assert core.display.header == "PWR TELEMETRY"
    assert "NO BUSES" in core.display.status_main
    print("✓ run() exits gracefully with NO_BUSES when buses={}")


# ---------------------------------------------------------------------------
# Dummy PowerManager
# ---------------------------------------------------------------------------

def test_dummy_power_manager_has_buses():
    """The dummy PowerManager must expose a 'buses' attribute."""
    from dummies.power_manager import PowerManager as DummyPowerManager

    dummy = DummyPowerManager()
    assert hasattr(dummy, "buses")
    assert dummy.buses == {} or dummy.buses is not None
    print("✓ Dummy PowerManager exposes 'buses' attribute")


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running PowerTelemetryMode tests...\n")

    tests = [
        test_power_telemetry_file_exists,
        test_power_telemetry_syntax,
        test_power_telemetry_in_manifest,
        test_power_telemetry_has_required_metadata_fields,
        test_admin_mode_count_increased,
        test_power_telemetry_instantiation,
        test_get_buses_with_no_power,
        test_get_buses_with_none,
        test_normalize_empty,
        test_normalize_flat_signal,
        test_normalize_range,
        test_sample_voltages_builds_history,
        test_history_capped_at_history_size,
        test_render_text_calls_display,
        test_render_wave_calls_show_waveform,
        test_run_exits_gracefully_with_no_buses,
        test_dummy_power_manager_has_buses,
    ]

    passed = failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as exc:
            print(f"❌ {test.__name__}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"❌ {test.__name__} (unexpected): {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'✅' if failed == 0 else '❌'} {passed}/{passed + failed} tests passed")
    sys.exit(0 if failed == 0 else 1)
