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

    def set_led(self, index, color, brightness=1.0, anim_mode=None, duration=None, priority=2, speed=1.0):
        self.last_set = (index, color, anim_mode)

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

    async def play(self, file, bus_id=1, loop=False, level=1.0, wait=False, interrupt=True):
        self.last_played = (file, bus_id)

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


class MockHIDMixin:
    """Shared SW-injection methods for mock HID managers."""

    def _sw_set_encoders(self, positions, override=False):
        parts = positions.split(":")
        for i, pos in enumerate(parts):
            if i < len(self.encoder_positions):
                try:
                    self.encoder_positions[i] = int(pos)
                except ValueError:
                    pass

    def _sw_set_buttons(self, buttons, override=False):
        for i, char in enumerate(buttons):
            if i < len(self.buttons_values):
                val = char == "1"
                prev = self.buttons_values[i]
                self.buttons_values[i] = val
                if prev and not val:
                    self.buttons_tapped[i] = True

    def _sw_set_latching_toggles(self, latching_toggles, override=False):
        for i, char in enumerate(latching_toggles):
            if i < len(self.latching_values):
                self.latching_values[i] = char == "1"

    def _sw_set_momentary_toggles(self, momentary_toggles, override=False):
        for i, char in enumerate(momentary_toggles):
            if i < len(self.momentary_values):
                self.momentary_values[i][0] = char == "U"
                self.momentary_values[i][1] = char == "D"


class MockHID(MockHIDMixin):
    def __init__(self):
        self.encoder_positions = [0, 0]
        self.buttons_values = [False, False]
        self.buttons_tapped = [False, False]
        self.latching_values = [False] * 8
        self.momentary_values = [[False, False]]
        self.momentary_tapped = [[False, False]]

    def get_status_string(self, order=None):
        return "BTN:0000,ENC:0"


class MockSatelliteHID(MockHIDMixin):
    def __init__(self):
        self.encoder_positions = [0]
        self.buttons_values = [False]
        self.buttons_tapped = [False]
        self.latching_values = [False] * 12
        self.momentary_values = [[False, False]]
        self.momentary_tapped = [[False, False]]


class MockSatellite:
    def __init__(self, is_active=True):
        self.is_active = is_active
        self.hid = MockSatelliteHID()


class MockI2CBus:
    pass


class MockActiveMode:
    """Mock game mode with some state variables."""
    def __init__(self):
        self.score = 0
        self.ship_hp = 100
        self._fuel = 1.0


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
        self.mode = "DASHBOARD"
        self._pending_mode_variant = None
        self.active_mode = None
        self.active_mode_task = None
        self.console_override_mode = None
        self.satellites = {"0101": MockSatellite()}
        self.mode_registry = {
            "SIMON": {
                "id": "SIMON",
                "name": "SIMON SAYS",
                "menu": "MAIN",
                "has_tutorial": True,
                "order": 100,
                "requires": ["CORE"],
                "settings": [],
            },
            "PIPELINE": {
                "id": "PIPELINE",
                "name": "PIPELINE OVERLOAD",
                "menu": "MAIN",
                "has_tutorial": False,
                "order": 200,
                "requires": ["CORE"],
                "settings": [],
            },
            "MAINMENU": {
                "id": "MAINMENU",
                "name": "MAIN MENU",
                "menu": "SYSTEM",
                "requires": ["CORE"],
                "settings": [],
            },
        }

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
    """test_display clears the display when '5' is chosen."""
    app = MockApp()
    app.display.update_header("OLD HEADER")
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["5", "0"]

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

    input_queue = ["4", "0"]

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


@pytest.mark.asyncio
async def test_mode_launcher_no_app():
    """test_mode_launcher prints an error and returns when app is None."""
    cm = ConsoleManager("CORE", "00")
    # Should not raise even with no app
    await cm.test_mode_launcher()


@pytest.mark.asyncio
async def test_mode_launcher_lists_main_modes():
    """test_mode_launcher shows only MAIN-menu modes and backs out on '0'."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["0"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_mode_launcher()

    # No mode switch should have occurred
    assert app.mode == "DASHBOARD"
    assert app._pending_mode_variant is None


@pytest.mark.asyncio
async def test_mode_launcher_main_game():
    """test_mode_launcher sets app.console_override_mode when '1' (Main Game) is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    # SIMON is index 1 (first MAIN mode); pick main game
    input_queue = ["1", "1"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_mode_launcher()

    assert app.console_override_mode == "SIMON"
    assert app._pending_mode_variant is None


@pytest.mark.asyncio
async def test_mode_launcher_tutorial():
    """test_mode_launcher sets _pending_mode_variant='TUTORIAL' when '2' is selected."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    # SIMON is index 1 (first MAIN mode); pick tutorial
    input_queue = ["1", "2"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_mode_launcher()

    assert app.console_override_mode == "SIMON"
    assert app._pending_mode_variant == "TUTORIAL"


@pytest.mark.asyncio
async def test_mode_launcher_no_tutorial_skips_variant_prompt():
    """test_mode_launcher skips variant prompt for modes without a tutorial."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    # PIPELINE is index 2 (second MAIN mode) and has no tutorial
    input_queue = ["2"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_mode_launcher()

    assert app.console_override_mode == "PIPELINE"
    assert app._pending_mode_variant is None


@pytest.mark.asyncio
async def test_mode_launcher_invalid_index():
    """test_mode_launcher handles out-of-range mode selection gracefully."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["99"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_mode_launcher()

    assert app.mode == "DASHBOARD"
    assert app._pending_mode_variant is None


@pytest.mark.asyncio
async def test_mode_launcher_non_numeric_input():
    """test_mode_launcher handles non-numeric mode selection gracefully."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["abc"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_mode_launcher()

    assert app.mode == "DASHBOARD"
    assert app._pending_mode_variant is None


@pytest.mark.asyncio
async def test_mode_launcher_invalid_variant_choice():
    """test_mode_launcher handles an invalid variant choice without switching mode."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    # SIMON has tutorial; pick an invalid variant
    input_queue = ["1", "9"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "0"

    cm.get_input = fake_input
    await cm.test_mode_launcher()

    assert app.mode == "DASHBOARD"
    assert app._pending_mode_variant is None


# ---------------------------------------------------------------------------
# Live Debug Console tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_live_debug_console_no_app():
    """live_debug_console prints an error and returns when no app is attached."""
    cm = ConsoleManager("CORE", "00")
    # Should return immediately without raising
    await cm.live_debug_console()


@pytest.mark.asyncio
async def test_live_debug_console_exit():
    """live_debug_console exits cleanly when 'exit' is typed."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()  # Should return without raising


@pytest.mark.asyncio
async def test_live_debug_console_help():
    """live_debug_console prints help text without raising."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["help", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()


@pytest.mark.asyncio
async def test_live_debug_console_enc_core():
    """live_debug_console adjusts core encoder position by the given delta."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)
    app.hid.encoder_positions[0] = 10

    input_queue = ["enc 0 5", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.encoder_positions[0] == 15


@pytest.mark.asyncio
async def test_live_debug_console_enc_negative_delta():
    """live_debug_console can apply a negative encoder delta."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)
    app.hid.encoder_positions[0] = 10

    input_queue = ["enc 0 -3", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.encoder_positions[0] == 7


@pytest.mark.asyncio
async def test_live_debug_console_btn_core():
    """live_debug_console sets buttons_tapped for a core button tap."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["btn 0", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.buttons_tapped[0] is True


@pytest.mark.asyncio
async def test_live_debug_console_tog_core_on():
    """live_debug_console sets a core latching toggle to ON."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["tog 2 1", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.latching_values[2] is True


@pytest.mark.asyncio
async def test_live_debug_console_tog_core_off():
    """live_debug_console sets a core latching toggle to OFF."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)
    app.hid.latching_values[2] = True

    input_queue = ["tog 2 0", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.latching_values[2] is False


@pytest.mark.asyncio
async def test_live_debug_console_mom_core_up():
    """live_debug_console holds a core momentary toggle in the UP position."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["mom 0 U", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.momentary_values[0][0] is True


@pytest.mark.asyncio
async def test_live_debug_console_mom_core_down():
    """live_debug_console holds a core momentary toggle in the DOWN position."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["mom 0 D", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.momentary_values[0][1] is True


@pytest.mark.asyncio
async def test_live_debug_console_mom_core_centre():
    """live_debug_console clears both momentary values for centre position."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)
    app.hid.momentary_values[0] = [True, False]

    input_queue = ["mom 0 C", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.hid.momentary_values[0][0] is False
    assert app.hid.momentary_values[0][1] is False


@pytest.mark.asyncio
async def test_live_debug_console_sat_enc():
    """live_debug_console adjusts a satellite encoder position."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["sat enc 0 7", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.satellites["0101"].hid.encoder_positions[0] == 7


@pytest.mark.asyncio
async def test_live_debug_console_sat_btn():
    """live_debug_console taps a satellite button."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["sat btn 0", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.satellites["0101"].hid.buttons_tapped[0] is True


@pytest.mark.asyncio
async def test_live_debug_console_sat_tog():
    """live_debug_console sets a satellite latching toggle (the example from the issue)."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    # Mirrors the issue example: sat tog 3 1
    input_queue = ["sat tog 3 1", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.satellites["0101"].hid.latching_values[3] is True


@pytest.mark.asyncio
async def test_live_debug_console_sat_mom():
    """live_debug_console holds a satellite momentary toggle in the UP position."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["sat mom 0 U", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.satellites["0101"].hid.momentary_values[0][0] is True


@pytest.mark.asyncio
async def test_live_debug_console_god_mode_int():
    """live_debug_console sets an integer attribute on the active mode."""
    app = MockApp()
    app.active_mode = MockActiveMode()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["score = 5000", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.active_mode.score == 5000


@pytest.mark.asyncio
async def test_live_debug_console_god_mode_float():
    """live_debug_console sets a float attribute on the active mode."""
    app = MockApp()
    app.active_mode = MockActiveMode()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["_fuel = 0.0", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    await cm.live_debug_console()

    assert app.active_mode._fuel == 0.0


@pytest.mark.asyncio
async def test_live_debug_console_god_mode_no_active_mode():
    """live_debug_console prints an error when no mode is running."""
    app = MockApp()
    app.active_mode = None
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["score = 100", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    # Should not raise even without an active mode
    await cm.live_debug_console()


@pytest.mark.asyncio
async def test_live_debug_console_enc_out_of_range():
    """live_debug_console handles out-of-range encoder index gracefully."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["enc 99 5", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    # Should print an error but not raise
    await cm.live_debug_console()


@pytest.mark.asyncio
async def test_live_debug_console_unknown_command():
    """live_debug_console prints an error for unknown commands."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["unknowncmd foo", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    # Should not raise
    await cm.live_debug_console()


@pytest.mark.asyncio
async def test_live_debug_console_sat_no_satellites():
    """live_debug_console handles missing satellites gracefully."""
    app = MockApp()
    app.satellites = {}
    cm = ConsoleManager("CORE", "00", app=app)

    input_queue = ["sat tog 3 1", "exit"]

    async def fake_input(prompt):
        return input_queue.pop(0) if input_queue else "exit"

    cm.get_input = fake_input
    # Should not raise
    await cm.live_debug_console()


@pytest.mark.asyncio
async def test_live_debug_console_menu_entry():
    """The start() main menu includes the 'L' option for Live Debug Console."""
    app = MockApp()
    cm = ConsoleManager("CORE", "00", app=app)

    # 'L' should route to live_debug_console; immediately exit from it
    calls = []

    async def fake_live_debug():
        calls.append("live_debug_console")

    cm.live_debug_console = fake_live_debug

    input_count = [0]

    async def fake_input(prompt):
        input_count[0] += 1
        if input_count[0] == 1:
            return "L"
        raise asyncio.CancelledError()

    cm.get_input = fake_input
    try:
        await cm.start()
    except asyncio.CancelledError:
        pass

    assert "live_debug_console" in calls


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
        test_mode_launcher_no_app,
        test_mode_launcher_lists_main_modes,
        test_mode_launcher_main_game,
        test_mode_launcher_tutorial,
        test_mode_launcher_no_tutorial_skips_variant_prompt,
        test_mode_launcher_invalid_index,
        test_mode_launcher_non_numeric_input,
        test_mode_launcher_invalid_variant_choice,
        test_live_debug_console_no_app,
        test_live_debug_console_exit,
        test_live_debug_console_help,
        test_live_debug_console_enc_core,
        test_live_debug_console_enc_negative_delta,
        test_live_debug_console_btn_core,
        test_live_debug_console_tog_core_on,
        test_live_debug_console_tog_core_off,
        test_live_debug_console_mom_core_up,
        test_live_debug_console_mom_core_down,
        test_live_debug_console_mom_core_centre,
        test_live_debug_console_sat_enc,
        test_live_debug_console_sat_btn,
        test_live_debug_console_sat_tog,
        test_live_debug_console_sat_mom,
        test_live_debug_console_god_mode_int,
        test_live_debug_console_god_mode_float,
        test_live_debug_console_god_mode_no_active_mode,
        test_live_debug_console_enc_out_of_range,
        test_live_debug_console_unknown_command,
        test_live_debug_console_sat_no_satellites,
        test_live_debug_console_menu_entry,
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
