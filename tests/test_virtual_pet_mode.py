"""Test module for the Virtual Pet mode.

Verifies:
- virtual_pet.py file exists and has valid syntax
- VirtualPet is correctly registered in the manifest
- All three animated states are implemented (IDLE, EATING, SLEEPING)
- Hunger and happiness stats are tracked
- All four icons are present in Icons.ICON_LIBRARY with correct dimensions
- Audio sequences are defined for meow, alert, and sleep cues
"""

import sys
import os
import types
import time as _time

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# ---------------------------------------------------------------------------
# Stub out CircuitPython-specific modules at module import time so that any
# subsequent imports (including matrix_animations) get proper ticks stubs.
# ---------------------------------------------------------------------------
_ticks_stub = types.ModuleType('adafruit_ticks')
_ticks_stub.ticks_ms   = lambda: int(_time.monotonic() * 1000)
_ticks_stub.ticks_diff = lambda a, b: a - b
sys.modules['adafruit_ticks'] = _ticks_stub


# ---------------------------------------------------------------------------
# File / syntax checks
# ---------------------------------------------------------------------------

def test_virtual_pet_file_exists():
    """virtual_pet.py must exist in src/modes/."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'virtual_pet.py')
    assert os.path.exists(path), "virtual_pet.py does not exist in src/modes/"
    print("✓ virtual_pet.py file exists")


def test_virtual_pet_valid_syntax():
    """virtual_pet.py must have valid Python syntax."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'virtual_pet.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    compile(code, path, 'exec')
    print("✓ virtual_pet.py has valid Python syntax")


# ---------------------------------------------------------------------------
# Manifest registration
# ---------------------------------------------------------------------------

def test_virtual_pet_in_manifest():
    """VIRTUAL_PET must be registered in MODE_REGISTRY."""
    from modes.manifest import MODE_REGISTRY
    assert "VIRTUAL_PET" in MODE_REGISTRY, "VIRTUAL_PET not found in MODE_REGISTRY"
    entry = MODE_REGISTRY["VIRTUAL_PET"]
    assert entry["id"] == "VIRTUAL_PET"
    assert entry["name"] == "VIRTUAL PET"
    assert entry["module_path"] == "modes.virtual_pet"
    assert entry["class_name"] == "VirtualPet"
    assert entry["icon"] == "VIRTUAL_PET"
    assert "CORE" in entry["requires"]
    assert entry.get("menu") == "MAIN"
    print("✓ VIRTUAL_PET correctly registered in manifest")


# ---------------------------------------------------------------------------
# State constants
# ---------------------------------------------------------------------------

def test_virtual_pet_has_three_required_states():
    """VirtualPet source must define STATE_IDLE, STATE_EATING, STATE_SLEEPING."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'virtual_pet.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    assert 'STATE_IDLE' in code,     "VirtualPet missing STATE_IDLE"
    assert 'STATE_EATING' in code,   "VirtualPet missing STATE_EATING"
    assert 'STATE_SLEEPING' in code, "VirtualPet missing STATE_SLEEPING"
    print("✓ All three required states (IDLE, EATING, SLEEPING) are defined")


def test_virtual_pet_has_stat_tracking():
    """VirtualPet source must track hunger and happiness."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'virtual_pet.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    assert 'hunger' in code,    "VirtualPet must track hunger stat"
    assert 'happiness' in code, "VirtualPet must track happiness stat"
    print("✓ Hunger and happiness stat tracking is present")


# ---------------------------------------------------------------------------
# Audio cues
# ---------------------------------------------------------------------------

def test_virtual_pet_has_audio_sequences():
    """VirtualPet must define audio sequences for meow, alert, and sleep."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'virtual_pet.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    assert '_MEOW' in code,   "VirtualPet missing _MEOW audio sequence"
    assert '_ALERT' in code,  "VirtualPet missing _ALERT audio sequence"
    assert '_SLEEP_TONE' in code, "VirtualPet missing _SLEEP_TONE audio sequence"
    print("✓ Audio sequences (_MEOW, _ALERT, _SLEEP_TONE) are defined")


# ---------------------------------------------------------------------------
# HID input handling
# ---------------------------------------------------------------------------

def test_virtual_pet_has_input_handling():
    """VirtualPet must handle button inputs for feeding and playing."""
    path = os.path.join(os.path.dirname(__file__), '..', 'src', 'modes', 'virtual_pet.py')
    with open(path, 'r', encoding='utf-8') as fh:
        code = fh.read()
    assert 'is_button_pressed' in code, "VirtualPet must use is_button_pressed for input"
    assert '_feed' in code,  "VirtualPet must have a _feed method"
    assert '_play' in code,  "VirtualPet must have a _play method"
    print("✓ HID input handling (_feed, _play) is present")


# ---------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------

def test_virtual_pet_icon_exists():
    """VIRTUAL_PET icon must be in Icons.ICON_LIBRARY with 256 pixels (16x16)."""
    from utilities.icons import Icons
    assert "VIRTUAL_PET" in Icons.ICON_LIBRARY, "VIRTUAL_PET icon not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["VIRTUAL_PET"]
    assert len(icon) == 256, f"VIRTUAL_PET icon must be 256 pixels (16x16), got {len(icon)}"
    print(f"✓ VIRTUAL_PET icon exists ({len(icon)} pixels)")


def test_cat_idle_icon_exists():
    """CAT_IDLE icon must be in Icons.ICON_LIBRARY with 256 pixels (16x16)."""
    from utilities.icons import Icons
    assert "CAT_IDLE" in Icons.ICON_LIBRARY, "CAT_IDLE icon not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["CAT_IDLE"]
    assert len(icon) == 256, f"CAT_IDLE icon must be 256 pixels (16x16), got {len(icon)}"
    print(f"✓ CAT_IDLE icon exists ({len(icon)} pixels)")


def test_cat_eat_icon_exists():
    """CAT_EAT icon must be in Icons.ICON_LIBRARY with 256 pixels (16x16)."""
    from utilities.icons import Icons
    assert "CAT_EAT" in Icons.ICON_LIBRARY, "CAT_EAT icon not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["CAT_EAT"]
    assert len(icon) == 256, f"CAT_EAT icon must be 256 pixels (16x16), got {len(icon)}"
    print(f"✓ CAT_EAT icon exists ({len(icon)} pixels)")


def test_cat_sleep_icon_exists():
    """CAT_SLEEP icon must be in Icons.ICON_LIBRARY with 256 pixels (16x16)."""
    from utilities.icons import Icons
    assert "CAT_SLEEP" in Icons.ICON_LIBRARY, "CAT_SLEEP icon not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["CAT_SLEEP"]
    assert len(icon) == 256, f"CAT_SLEEP icon must be 256 pixels (16x16), got {len(icon)}"
    print(f"✓ CAT_SLEEP icon exists ({len(icon)} pixels)")


# ---------------------------------------------------------------------------
# Behavioural unit tests (no hardware required)
# ---------------------------------------------------------------------------

class _MockBuzzer:
    def __init__(self):
        self.last_sequence = None

    def play_sequence(self, seq):
        self.last_sequence = seq

    def play_note(self, freq, duration=None):
        pass

    async def stop(self):
        pass


class _MockDisplay:
    def __init__(self):
        self.line1 = ""
        self.line2 = ""

    def update_status(self, line1, line2=""):
        self.line1 = line1
        self.line2 = line2


class _MockMatrix:
    def __init__(self):
        self.last_icon = None
        self.last_anim = None

    def show_icon(self, icon_name, clear=True, anim_mode=None, speed=1.0, **kwargs):
        self.last_icon = icon_name
        self.last_anim = anim_mode

    def fill(self, *args, **kwargs):
        pass

    def clear(self):
        pass


class _MockHID:
    def __init__(self):
        self._taps = {}

    def set_tap(self, index):
        self._taps[index] = True

    def is_button_pressed(self, index, long=False, duration=2000, action=None):
        if action == "tap":
            return self._taps.pop(index, False)
        return False


class _MockCore:
    def __init__(self):
        self.display = _MockDisplay()
        self.matrix  = _MockMatrix()
        self.buzzer  = _MockBuzzer()
        self.hid     = _MockHID()

    async def clean_slate(self):
        pass

    @property
    def current_mode_step(self):
        return 0

    @current_mode_step.setter
    def current_mode_step(self, v):
        pass


def _make_pet():
    """Import VirtualPet with hardware stubs patched."""
    import types
    # Stub out adafruit_ticks (always override to ensure correct ticks_diff behaviour)
    # Note: this stub uses simple subtraction (a - b).  The real CircuitPython
    # ticks_diff handles 32-bit millisecond wraparound, but that edge case is
    # not exercised by these tests, so the simplified stub is adequate here.
    ticks_stub = types.ModuleType('adafruit_ticks')
    ticks_stub.ticks_ms   = lambda: 0
    ticks_stub.ticks_diff = lambda a, b: a - b
    sys.modules['adafruit_ticks'] = ticks_stub

    # Stub out utilities.logger
    if 'utilities.logger' not in sys.modules:
        logger_stub = types.ModuleType('utilities.logger')
        logger_stub.JEBLogger = type('JEBLogger', (), {
            'info':    staticmethod(lambda *a: None),
            'error':   staticmethod(lambda *a: None),
            'warning': staticmethod(lambda *a: None),
        })()
        sys.modules['utilities.logger'] = logger_stub

    # Reload with stubs in place
    import importlib
    if 'modes.virtual_pet' in sys.modules:
        del sys.modules['modes.virtual_pet']
    if 'modes.base' in sys.modules:
        del sys.modules['modes.base']

    from modes.virtual_pet import VirtualPet
    return VirtualPet(_MockCore())


def test_initial_stats():
    """Pet must start with sensible default hunger and happiness."""
    pet = _make_pet()
    assert 0 <= pet.hunger    <= 100, "Hunger must be 0-100"
    assert 0 <= pet.happiness <= 100, "Happiness must be 0-100"
    assert pet.hunger    < pet.HUNGER_THRESHOLD, "Pet should not start hungry"
    assert pet.happiness > pet.HAPPY_LOW,        "Pet should start reasonably happy"
    print(f"✓ Initial stats: hunger={pet.hunger}, happiness={pet.happiness}")


def test_feed_reduces_hunger_and_triggers_eating():
    """Feeding must reduce hunger and switch state to EATING."""
    pet = _make_pet()
    pet.hunger = 50
    now = 0
    pet._feed(now)
    assert pet.hunger < 50,                  "Feeding must reduce hunger"
    assert pet.state == pet.STATE_EATING,    "State must be EATING after feed"
    assert pet.core.matrix.last_icon == "CAT_EAT", "CAT_EAT icon must be shown"
    print("✓ _feed() reduces hunger and triggers EATING state")


def test_play_increases_happiness_and_triggers_playing():
    """Playing must increase happiness and switch state to PLAYING."""
    pet = _make_pet()
    pet.happiness = 50
    now = 0
    pet._play(now)
    assert pet.happiness > 50,               "Playing must boost happiness"
    assert pet.state == pet.STATE_PLAYING,   "State must be PLAYING after play"
    print("✓ _play() boosts happiness and triggers PLAYING state")


def test_action_states_expire():
    """EATING and PLAYING states must revert to IDLE after ACTION_DUR_MS."""
    pet = _make_pet()
    pet.state = pet.STATE_EATING
    pet._state_start_ms = 0
    # Simulate time past ACTION_DUR_MS
    now = pet.ACTION_DUR_MS + 1
    pet._update_state(now)
    assert pet.state == pet.STATE_IDLE, "EATING must expire to IDLE"
    print("✓ Action states expire correctly to IDLE")


def test_hungry_state_triggered_by_high_hunger():
    """IDLE cat must transition to HUNGRY when hunger exceeds threshold."""
    pet = _make_pet()
    pet.state   = pet.STATE_IDLE
    pet.hunger  = pet.HUNGER_THRESHOLD + 1
    pet._last_input_ms = 0
    now = 1000  # well within SLEEP_IDLE_MS
    pet._update_state(now)
    assert pet.state == pet.STATE_HUNGRY, "High hunger must trigger HUNGRY state"
    print("✓ High hunger correctly triggers HUNGRY state")


def test_sleeping_state_after_idle_timeout():
    """Cat must fall asleep after SLEEP_IDLE_MS of inactivity."""
    pet = _make_pet()
    pet.state   = pet.STATE_IDLE
    pet.hunger  = 10  # not hungry
    pet._last_input_ms = 0
    now = pet.SLEEP_IDLE_MS + 1
    pet._update_state(now)
    assert pet.state == pet.STATE_SLEEPING, "Cat must sleep after idle timeout"
    print("✓ Cat transitions to SLEEPING after inactivity")


def test_hungry_state_clears_when_fed():
    """HUNGRY state must return to IDLE once hunger drops below threshold."""
    pet = _make_pet()
    pet.state  = pet.STATE_HUNGRY
    pet.hunger = pet.HUNGER_THRESHOLD - 1
    pet._update_state(1000)
    assert pet.state == pet.STATE_IDLE, "HUNGRY must resolve to IDLE when fed"
    print("✓ HUNGRY state resolves to IDLE when hunger is satisfied")


def test_stats_display_toggle():
    """Button 2 tap must toggle the stats display flag."""
    pet = _make_pet()
    assert not pet._show_stats
    pet.core.hid.set_tap(2)
    pet._handle_input(0)
    assert pet._show_stats, "_show_stats must be True after Button 2 tap"
    pet.core.hid.set_tap(2)
    pet._handle_input(0)
    assert not pet._show_stats, "_show_stats must toggle back to False"
    print("✓ Button 2 toggles stats display")


# ---------------------------------------------------------------------------
# Sprite sheet (CAT_WALK) icon tests
# ---------------------------------------------------------------------------

def test_cat_walk_icon_exists():
    """CAT_WALK sprite sheet must be in ICON_LIBRARY with 512 bytes (2 × 16x16)."""
    from utilities.icons import Icons
    assert "CAT_WALK" in Icons.ICON_LIBRARY, "CAT_WALK not found in ICON_LIBRARY"
    icon = Icons.ICON_LIBRARY["CAT_WALK"]
    assert len(icon) == 512, f"CAT_WALK must be 512 bytes (2 frames × 256), got {len(icon)}"
    print(f"✓ CAT_WALK sprite sheet exists ({len(icon)} bytes, 2 frames)")


def test_cat_walk_frame_count():
    """CAT_WALK must contain exactly 2 animation frames."""
    from utilities.icons import Icons
    icon = Icons.ICON_LIBRARY["CAT_WALK"]
    frame_size = 16 * 16
    frame_count = len(icon) // frame_size
    assert frame_count == 2, f"Expected 2 frames in CAT_WALK, got {frame_count}"
    print("✓ CAT_WALK has exactly 2 frames")


def test_cat_walk_frames_differ():
    """The two CAT_WALK frames must not be identical (different paw positions)."""
    from utilities.icons import Icons
    icon = Icons.ICON_LIBRARY["CAT_WALK"]
    frame0 = icon[0:256]
    frame1 = icon[256:512]
    assert frame0 != frame1, "CAT_WALK frame 0 and frame 1 must differ"
    print("✓ CAT_WALK frames are distinct")


# ---------------------------------------------------------------------------
# animate_sprite_sheet unit tests
# ---------------------------------------------------------------------------

import asyncio as _asyncio

class _MockMatrixForAnim:
    """Minimal matrix mock for testing animate_sprite_sheet."""
    def __init__(self, w=16, h=16):
        self.width  = w
        self.height = h
        self.palette = {v: (v, v, v) for v in range(256)}
        self.pixels_drawn = []
        self.fills = 0
        self.frames_shown = 0

    def fill(self, color, show=False, **kwargs):
        self.fills += 1

    def draw_pixel(self, x, y, color, brightness=1.0, **kwargs):
        self.pixels_drawn.append((x, y, color))

    def show_frame(self, frame, clear=True, color=None, brightness=1.0):
        self.frames_shown += 1


def test_animate_sprite_sheet_renders_frames():
    """animate_sprite_sheet must render the correct number of frames."""
    import sys, os, types, time as _time2
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    # Ensure adafruit_ticks is a real stub (other tests may have replaced it with MagicMock)
    _ts = types.ModuleType('adafruit_ticks')
    _ts.ticks_ms   = lambda: int(_time2.monotonic() * 1000)
    _ts.ticks_diff = lambda a, b: a - b
    sys.modules['adafruit_ticks'] = _ts
    # Force full re-import so matrix_animations binds to the correct ticks stubs.
    # Must also remove the attribute from the parent package so Python re-executes the module.
    sys.modules.pop('utilities.matrix_animations', None)
    _utils = sys.modules.get('utilities')
    if _utils is not None and hasattr(_utils, 'matrix_animations'):
        delattr(_utils, 'matrix_animations')
    from utilities import matrix_animations

    # 2-frame sprite: frame0 = all 1s, frame1 = all 2s
    frame0 = bytes([1] * 256)
    frame1 = bytes([2] * 256)
    sprite = frame0 + frame1

    matrix = _MockMatrixForAnim()

    async def run():
        # timing_data=(1,) = 1 ms per frame — plays through both frames almost instantly
        task = _asyncio.create_task(
            matrix_animations.animate_sprite_sheet(matrix, sprite, timing_data=(1,), loop=False)
        )
        await task

    _asyncio.run(run())

    # Should have called show_frame twice (once per frame)
    assert matrix.frames_shown == 2, f"Expected 2 show_frame() calls (one per frame), got {matrix.frames_shown}"
    print(f"✓ animate_sprite_sheet rendered 2 frames ({matrix.frames_shown} show_frame calls)")


def test_animate_sprite_sheet_cancellable():
    """animate_sprite_sheet must stop cleanly when cancelled."""
    import sys, os, types, time as _time2
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
    _ts = types.ModuleType('adafruit_ticks')
    _ts.ticks_ms   = lambda: int(_time2.monotonic() * 1000)
    _ts.ticks_diff = lambda a, b: a - b
    sys.modules['adafruit_ticks'] = _ts
    sys.modules.pop('utilities.matrix_animations', None)
    _utils = sys.modules.get('utilities')
    if _utils is not None and hasattr(_utils, 'matrix_animations'):
        delattr(_utils, 'matrix_animations')
    from utilities import matrix_animations

    sprite = bytes([1] * 256 + [2] * 256)
    matrix = _MockMatrixForAnim()

    async def run():
        # timing_data=(10000,) = very slow (10 s per frame) so we have time to cancel
        task = _asyncio.create_task(
            matrix_animations.animate_sprite_sheet(matrix, sprite, timing_data=(10000,), loop=True)
        )
        await _asyncio.sleep(0.05)  # let it start and render the first frame
        task.cancel()
        try:
            await task
        except _asyncio.CancelledError:
            pass

    _asyncio.run(run())
    # Task should have rendered at least one frame before being cancelled
    assert matrix.frames_shown >= 1, "Should have rendered at least one frame before cancel"
    print("✓ animate_sprite_sheet cancels cleanly")


def test_playing_state_uses_animated_mode():
    """VirtualPet PLAYING state must request CAT_WALK with anim_mode='ANIMATED'."""
    pet = _make_pet()
    pet._play(0)
    assert pet.core.matrix.last_icon == "CAT_WALK",  "PLAYING must use CAT_WALK icon"
    assert pet.core.matrix.last_anim == "ANIMATED",  "PLAYING must use anim_mode='ANIMATED'"
    print("✓ PLAYING state uses CAT_WALK with ANIMATED mode")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running Virtual Pet mode tests...\n")
    tests = [
        test_virtual_pet_file_exists,
        test_virtual_pet_valid_syntax,
        test_virtual_pet_in_manifest,
        test_virtual_pet_has_three_required_states,
        test_virtual_pet_has_stat_tracking,
        test_virtual_pet_has_audio_sequences,
        test_virtual_pet_has_input_handling,
        test_virtual_pet_icon_exists,
        test_cat_idle_icon_exists,
        test_cat_eat_icon_exists,
        test_cat_sleep_icon_exists,
        test_cat_walk_icon_exists,
        test_cat_walk_frame_count,
        test_cat_walk_frames_differ,
        test_initial_stats,
        test_feed_reduces_hunger_and_triggers_eating,
        test_play_increases_happiness_and_triggers_playing,
        test_action_states_expire,
        test_hungry_state_triggered_by_high_hunger,
        test_sleeping_state_after_idle_timeout,
        test_hungry_state_clears_when_fed,
        test_stats_display_toggle,
        test_animate_sprite_sheet_renders_frames,
        test_animate_sprite_sheet_cancellable,
        test_playing_state_uses_animated_mode,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"\n✗ {t.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n✗ {t.__name__} ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    if failed == 0:
        print(f"✅ All {passed} tests passed!")
        sys.exit(0)
    else:
        print(f"❌ {failed} test(s) failed, {passed} passed.")
        sys.exit(1)
