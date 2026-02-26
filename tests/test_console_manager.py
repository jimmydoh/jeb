#!/usr/bin/env python3
"""Unit tests for ConsoleManager."""

import sys
import os
import asyncio

try:
    import pytest
except ImportError:
    pytest = None

# ---------------------------------------------------------------------------
# Mock CircuitPython hardware modules before any src imports
# ---------------------------------------------------------------------------

class MockModule:
    """Generic mock for any CircuitPython module."""
    def __getattr__(self, name):
        return MockModule()

    def __call__(self, *args, **kwargs):
        return MockModule()

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return True


class MockWatchdog:
    def feed(self):
        pass


class MockMicrocontroller:
    watchdog = MockWatchdog()


class MockSupervisor:
    class _Runtime:
        serial_bytes_available = False
    runtime = _Runtime()

    def reload(self):
        pass


class MockI2C:
    def try_lock(self):
        return True

    def unlock(self):
        pass

    def scan(self):
        return [0x3C, 0x20]

    def deinit(self):
        pass


class MockBusio:
    @staticmethod
    def I2C(*args, **kwargs):
        return MockI2C()


mock_supervisor = MockSupervisor()
mock_microcontroller = MockMicrocontroller()

sys.modules['supervisor'] = mock_supervisor
sys.modules['microcontroller'] = mock_microcontroller
sys.modules['busio'] = MockBusio()
sys.modules['board'] = MockModule()
sys.modules['digitalio'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['pwmio'] = MockModule()
sys.modules['audiopwmio'] = MockModule()
sys.modules['audiobusio'] = MockModule()
sys.modules['audiocore'] = MockModule()
sys.modules['audiomixer'] = MockModule()
sys.modules['synthio'] = MockModule()
sys.modules['storage'] = MockModule()
sys.modules['watchdog'] = MockModule()
sys.modules['rotaryio'] = MockModule()
sys.modules['keypad'] = MockModule()
sys.modules['adafruit_ticks'] = MockModule()
sys.modules['adafruit_mcp230xx'] = MockModule()
sys.modules['adafruit_mcp230xx.mcp23017'] = MockModule()
sys.modules['neopixel'] = MockModule()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import utilities
import utilities.synth_registry
import managers

# ---------------------------------------------------------------------------
# Minimal mock app exposing all hardware manager attributes
# ---------------------------------------------------------------------------

class MockBuzzer:
    def __init__(self):
        self.last_note = None
        self.last_sequence = None
        self.stopped = False

    async def stop(self):
        self.stopped = True

    def play_note(self, frequency, duration=None):
        self.last_note = (frequency, duration)

    def play_sequence(self, sequence_data, loop=None):
        self.last_sequence = sequence_data


class MockDisplay:
    def __init__(self):
        self.status_text = ""
        self.header_text = ""
        self.footer_text = ""

    def update_status(self, main_text, sub_text=None):
        self.status_text = main_text

    def update_header(self, text):
        self.header_text = text

    def update_footer(self, text):
        self.footer_text = text


class MockLEDs:
    def __init__(self):
        self.last_set = None
        self.turned_off = False
        self.rainbow_started = False

    def set_led(self, index, color, brightness=1.0, anim=None, duration=None, priority=2, speed=1.0):
        self.last_set = (index, color, anim)

    def off_led(self, index, priority=99):
        self.turned_off = True

    def start_rainbow(self, duration=None, speed=0.01):
        self.rainbow_started = True


class MockMatrix:
    def __init__(self):
        self.fill_color = None

    def fill(self, color, show=True, anim_mode=None, speed=1.0, duration=None):
        self.fill_color = color

    def start_rainbow(self, duration=None, speed=0.01):
        pass


class MockAudio:
    CH_SFX = 1

    def __init__(self):
        self.last_played = None
        self.stopped_all = False

    async def play(self, file, channel=1, loop=False, level=1.0, wait=False, interrupt=True):
        self.last_played = (file, channel)

    def stop_all(self):
        self.stopped_all = True


class MockSynth:
    def __init__(self):
        self.last_note = None

    def play_note(self, frequency, patch=None, duration=None):
        self.last_note = (frequency, duration)


class MockSegment:
    def __init__(self):
        self.last_message = None
        self.last_command = None

    async def start_message(self, message, loop=False, speed=0.3, direction="L"):
        self.last_message = message

    async def apply_command(self, cmd, val):
        self.last_command = (cmd, val)


class MockPower:
    @property
    def status(self):
        return {"input_20v": 20.1, "main_5v": 5.0}

    @property
    def satbus_connected(self):
        return False

    @property
    def satbus_powered(self):
        return False


class MockRelay:
    num_relays = 2

    def __init__(self):
        self.relay_states = [False, False]
        self.triggered = False

    def get_state(self, index):
        if 0 <= index < self.num_relays:
            return self.relay_states[index]
        return False

    def set_relay(self, index, state):
        if index < 0:
            for i in range(self.num_relays):
                self.relay_states[i] = state
        elif 0 <= index < self.num_relays:
            self.relay_states[index] = state

    async def trigger_relay(self, index, duration=0.1, cycles=1):
        self.triggered = True


class MockHID:
    def get_status_string(self, order=None):
        return "BTN:0000,ENC:0"


class MockI2CBus:
    pass


class MockApp:
    """Mock application exposing all hardware manager attributes."""
    def __init__(self):
        self.buzzer = MockBuzzer()
        self.display = MockDisplay()
        self.leds = MockLEDs()
        self.matrix = MockMatrix()
        self.audio = MockAudio()
        self.synth = MockSynth()
        self.segment = MockSegment()
        self.power = MockPower()
        self.relay = MockRelay()
        self.hid = MockHID()
        self.i2c = MockI2CBus()

    async def start(self):
        while True:
            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# Import ConsoleManager using importlib to bypass managers/__init__.py
# ---------------------------------------------------------------------------

import importlib.util

spec = importlib.util.spec_from_file_location(
    "console_manager",
    os.path.join(os.path.dirname(__file__), '..', 'src', 'managers', 'console_manager.py')
)
console_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console_manager_module)
ConsoleManager = console_manager_module.ConsoleManager


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_init_without_app():
    """ConsoleManager can be initialised without an app reference."""
    cm = ConsoleManager("CORE", "00")
    assert cm.role == "CORE"
    assert cm.type_id == "00"
    assert cm.app is None


def test_init_with_app():
    """ConsoleManager stores the app reference and does not re-initialise pins."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)
    assert cm.app is app


def test_get_manager_from_app():
    """_get_manager returns the manager attribute from the app."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)
    assert cm._get_manager('buzzer') is app.buzzer
    assert cm._get_manager('display') is app.display
    assert cm._get_manager('nonexistent') is None


def test_get_manager_without_app():
    """_get_manager returns None when no app is attached."""
    cm = ConsoleManager("CORE", "00")
    assert cm._get_manager('buzzer') is None


def test_get_tone_presets():
    """get_tone_presets returns a sorted list of (name, dict) tuples."""
    cm = ConsoleManager("CORE", "00")
    presets = cm.get_tone_presets()
    assert isinstance(presets, list)
    for name, data in presets:
        assert isinstance(name, str)
        assert "sequence" in data


@pytest.mark.asyncio
async def test_test_buzzer_play_tone():
    """test_buzzer plays a 440Hz tone when '1' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_buzzer()

    assert app.buzzer.last_note is not None
    assert app.buzzer.last_note[0] == 440


@pytest.mark.asyncio
async def test_test_buzzer_play_scale():
    """test_buzzer plays the C-major scale when '2' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["2", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_buzzer()

    assert app.buzzer.last_sequence is not None
    assert "sequence" in app.buzzer.last_sequence


@pytest.mark.asyncio
async def test_test_display_status():
    """test_display updates the display status when '1' is chosen."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_display()

    assert "Console Test" in app.display.status_text or app.display.status_text == "Console Test"


@pytest.mark.asyncio
async def test_test_display_clear():
    """test_display clears the display when '4' is chosen."""
    app = MockApp()
    app.display.update_header("OLD HEADER")
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["4", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_display()

    assert app.display.header_text == ""


@pytest.mark.asyncio
async def test_test_leds_solid_color():
    """test_leds sets all LEDs to a solid color."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    # Choose option 1 (solid color) then select color 1 (Red), then exit
    input_queue = ["1", "1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_leds()

    assert app.leds.last_set is not None
    assert app.leds.last_set[0] == -1  # All LEDs


@pytest.mark.asyncio
async def test_test_leds_rainbow():
    """test_leds starts a rainbow animation."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["4", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_leds()

    assert app.leds.rainbow_started


@pytest.mark.asyncio
async def test_test_leds_no_manager():
    """test_leds prints a message and returns when no manager is available."""
    cm = ConsoleManager("CORE", "00")  # no app
    # Should not raise
    await cm.test_leds()


@pytest.mark.asyncio
async def test_test_matrix_fill():
    """test_matrix fills the matrix with red when '1' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_matrix()

    assert app.matrix.fill_color is not None


@pytest.mark.asyncio
async def test_test_matrix_clear():
    """test_matrix clears the matrix when '6' is selected."""
    app = MockApp()
    from utilities.palette import Palette
    app.matrix.fill_color = Palette.RED
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["6", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_matrix()

    assert tuple(app.matrix.fill_color) == (0, 0, 0)


@pytest.mark.asyncio
async def test_test_audio_play_tick():
    """test_audio plays menu_tick.wav on CH_SFX."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_audio()

    assert app.audio.last_played is not None
    assert "tick" in app.audio.last_played[0]


@pytest.mark.asyncio
async def test_test_audio_stop_all():
    """test_audio calls stop_all when '3' is chosen."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["3", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_audio()

    assert app.audio.stopped_all


@pytest.mark.asyncio
async def test_test_synth_play_note():
    """test_synth plays C4 when '1' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_synth()

    assert app.synth.last_note is not None
    freq, duration = app.synth.last_note
    assert abs(freq - 261.63) < 0.1


@pytest.mark.asyncio
async def test_test_synth_arpeggio():
    """test_synth plays an arpeggio when '4' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["4", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_synth()

    # last_note will be the last note of the arpeggio (C5)
    assert app.synth.last_note is not None


@pytest.mark.asyncio
async def test_test_segment_hello():
    """test_segment shows HELLO when '1' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_segment()

    assert app.segment.last_message == "HELLO"


@pytest.mark.asyncio
async def test_test_segment_custom_text():
    """test_segment shows custom text when '2' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["2", "TEST", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_segment()

    assert app.segment.last_message == "TEST"


@pytest.mark.asyncio
async def test_test_power_voltages():
    """test_power reads and prints all voltage rails."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    # Should not raise - power.status returns a dict
    await cm.test_power()


@pytest.mark.asyncio
async def test_test_power_no_manager():
    """test_power prints a message and returns when no manager is available."""
    cm = ConsoleManager("CORE", "00")
    await cm.test_power()


@pytest.mark.asyncio
async def test_test_relay_trigger_all():
    """test_relay triggers all relays when '1' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["1", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_relay()

    assert app.relay.triggered


@pytest.mark.asyncio
async def test_test_relay_all_off():
    """test_relay turns all relays off when '3' is selected."""
    app = MockApp()
    app.relay.relay_states = [True, True]
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["3", "0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_relay()

    assert all(not s for s in app.relay.relay_states)


@pytest.mark.asyncio
async def test_test_hid_no_manager():
    """test_hid prints a message and returns when no manager is available."""
    cm = ConsoleManager("CORE", "00")
    await cm.test_hid()


@pytest.mark.asyncio
async def test_test_i2c_scan_uses_app_i2c():
    """test_i2c_scan reuses the app's I2C bus when available."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)
    # Should not raise or call busio.I2C()
    await cm.test_i2c_scan()


@pytest.mark.asyncio
async def test_test_i2c_scan_standalone():
    """test_i2c_scan creates its own I2C when no app is provided."""
    cm = ConsoleManager("CORE", "00")
    # MockBusio.I2C returns a MockI2C which scans cleanly
    await cm.test_i2c_scan()


def test_invalid_menu_selection():
    """ConsoleManager handles invalid menu choices without raising."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    inputs = ["Z", "R"]
    call_count = [0]

    async def run():
        async def fake_input(prompt):
            call_count[0] += 1
            if call_count[0] <= len(inputs):
                return inputs[call_count[0] - 1]
            # Raise to stop the loop cleanly
            raise asyncio.CancelledError()

        cm.get_input = fake_input
        try:
            await cm.start()
        except asyncio.CancelledError:
            pass

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Runner for direct execution
# ---------------------------------------------------------------------------

def run_all_tests():
    """Run all console manager tests."""
    print("=" * 60)
    print("Running ConsoleManager Tests")
    print("=" * 60)

    sync_tests = [
        test_init_without_app,
        test_init_with_app,
        test_get_manager_from_app,
        test_get_manager_without_app,
        test_get_tone_presets,
        test_invalid_menu_selection,
    ]

    async_tests = [
        test_test_buzzer_play_tone,
        test_test_buzzer_play_scale,
        test_test_display_status,
        test_test_display_clear,
        test_test_leds_solid_color,
        test_test_leds_rainbow,
        test_test_leds_no_manager,
        test_test_matrix_fill,
        test_test_matrix_clear,
        test_test_audio_play_tick,
        test_test_audio_stop_all,
        test_test_synth_play_note,
        test_test_synth_arpeggio,
        test_test_segment_hello,
        test_test_segment_custom_text,
        test_test_power_voltages,
        test_test_power_no_manager,
        test_test_relay_trigger_all,
        test_test_relay_all_off,
        test_test_hid_no_manager,
        test_test_i2c_scan_uses_app_i2c,
        test_test_i2c_scan_standalone,
    ]

    passed = 0
    failed = 0

    for test in sync_tests:
        try:
            test()
            print(f"✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} ERROR: {e}")
            failed += 1

    for test in async_tests:
        try:
            asyncio.run(test())
            print(f"✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {test.__name__} ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
