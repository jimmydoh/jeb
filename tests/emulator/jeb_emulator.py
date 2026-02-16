import sys
import time
import pygame

#region --- Hardware Mocks ---

# adafruit_ticks
class MockTicksModule:
    @staticmethod
    def ticks_ms(): return int(time.monotonic() * 1000)
    @staticmethod
    def ticks_add(ticks, delta): return ticks + delta
    @staticmethod
    def ticks_diff(ticks1, ticks2): return ticks1 - ticks2

sys.modules['adafruit_ticks'] = MockTicksModule()

class HardwareMocks:
    """Globally accessible registry of hardware mock instances for Pygame to talk to."""
    buttons = None          # Will hold the keypad.Keys instance for main buttons
    encoder_btn = None      # Will hold the keypad.Keys instance for the dial push
    encoder = None          # Will hold the rotaryio.IncrementalEncoder instance
    estop = None            # Will hold the digitalio.DigitalInOut instance
    mcp = None              # Will hold the MCP expander instance if configured
    expanded_buttons = None # Will hold the MCP expander buttons if configured

# --- KEYPAD MOCK ---
class MockKeypadEvent:
    def __init__(self, key_number=0, pressed=True, released=False):
        self.key_number = key_number
        self.pressed = pressed
        self.released = released

class MockEventQueue:
    def __init__(self):
        self.queue = []

    def get_into(self, event):
        """Simulates the hardware buffer popping the oldest event."""
        if self.queue:
            q_evt = self.queue.pop(0)
            event.key_number = q_evt.key_number
            event.pressed = q_evt.pressed
            event.released = q_evt.released
            return True
        return False

class MockKeys:
    def __init__(self, pins, value_when_pressed=False, pull=True):
        self.pins = pins
        self.events = MockEventQueue()

        # Heuristic: HIDManager initializes buttons (4+ pins) and the encoder btn (1 pin)
        if pins and len(pins) >= 4:
            HardwareMocks.buttons = self
        elif pins and len(pins) == 1:
            HardwareMocks.encoder_btn = self

sys.modules['keypad'] = type('MockKeypadModule', (), {
    'Event': MockKeypadEvent,
    'Keys': MockKeys,
    'Keypad': MockKeys # Alias matrix keypads to standard keys for now
})

# --- ROTARYIO MOCK ---
class MockIncrementalEncoder:
    def __init__(self, pin_a, pin_b):
        self.position = 0
        HardwareMocks.encoder = self

sys.modules['rotaryio'] = type('MockRotaryIO', (), {'IncrementalEncoder': MockIncrementalEncoder})

# --- DIGITALIO MOCK ---
class MockPull:
    UP = 1
    DOWN = 2

class MockDirection:
    INPUT = 1
    OUTPUT = 2

class MockDigitalInOut:
    def __init__(self, pin):
        self.pin = pin
        self.pull = None
        self.direction = MockDirection.INPUT  # Added to prevent attribute errors
        self._value = True # Default UP (E-Stop is usually active low)

        # Only assign this to the E-Stop mock if it's actually the E-Stop pin
        # You may want to check the specific pin if PowerManager uses other digital pins
        HardwareMocks.estop = self

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val

sys.modules['digitalio'] = type('MockDigitalIO', (), {
    'DigitalInOut': MockDigitalInOut,
    'Pull': MockPull,
    'Direction': MockDirection   # <--- Added here!
})

# --- BOARD PINS MOCK ---
class MockPin:
    def __init__(self, name): self.name = name
    def __repr__(self): return f"board.{self.name}"
    def __hash__(self): return hash(self.name)
    def __eq__(self, other): return getattr(other, 'name', None) == self.name

class MockBoard:
    def __getattr__(self, name): return MockPin(name)

sys.modules['board'] = MockBoard()
sys.modules['microcontroller'] = type('MockMicrocontroller', (), {'pin': MockBoard()})()

# busio (UART and I2C)
class MockUART:
    def __init__(self, *args, **kwargs): self.in_waiting = 0
    def readinto(self, buf): return 0
    def write(self, buf): return len(buf)
    def reset_input_buffer(self): pass

class MockI2C:
    def __init__(self, *args, **kwargs): pass

class MockBusioModule:
    UART = MockUART
    I2C = MockI2C

sys.modules['busio'] = MockBusioModule()

# --- ANALOGIO MOCK (For Power Monitoring) ---
class MockAnalogIn:
    def __init__(self, pin):
        self.pin = pin

    @property
    def value(self):
        # CircuitPython ADC returns a 16-bit int (0 to 65535).
        # 60000 simulates a healthy ~3.0V reading on the rail.
        return 60000

sys.modules['analogio'] = type('MockAnalogIO', (), {'AnalogIn': MockAnalogIn})



# neopixels
class MockNeoPixel:
    def __init__(self, pin, n, **kwargs):
        self.pin = pin
        self.n = n
        self.auto_write = kwargs.get('auto_write', True)
        self.brightness = kwargs.get('brightness', 1.0)

        # The internal hardware buffer holding (R,G,B) tuples
        self.pixels = [(0, 0, 0)] * n

    def __setitem__(self, index, val):
        self.pixels[index] = val

    def __getitem__(self, index):
        return self.pixels[index]

    def fill(self, color):
        self.pixels = [color] * self.n

    def show(self):
        pass

class MockNeopixelModule:
    NeoPixel = MockNeoPixel

sys.modules['neopixel'] = MockNeopixelModule()

# --- AUDIOBUSIO MOCK (I2S Hardware) ---
class MockI2SOut:
    def __init__(self, bit_clock, word_select, data, **kwargs):
        self.playing = False

    def play(self, sample, loop=False):
        self.playing = True

    def stop(self):
        self.playing = False

    def deinit(self): pass

sys.modules['audiobusio'] = type('MockAudioBusIO', (), {'I2SOut': MockI2SOut})

# --- AUDIOPWMIO MOCK (PWM Hardware Fallback) ---
class MockPWMAudioOut:
    def __init__(self, pin, **kwargs):
        self.playing = False

    def play(self, sample, loop=False):
        self.playing = True

    def stop(self):
        self.playing = False

    def deinit(self): pass

sys.modules['audiopwmio'] = type('MockAudioPWMIO', (), {'PWMAudioOut': MockPWMAudioOut})

# --- AUDIOCORE MOCK (.wav File Decoder) ---
class MockWaveFile:
    def __init__(self, file_obj, buffer=None):
        self.file_obj = file_obj
        self.sample_rate = 22050
        # Try to extract the real filename from the PC file object for our console logs
        self.filename = getattr(file_obj, 'name', 'unknown_stream')

    def deinit(self): pass

sys.modules['audiocore'] = type('MockAudioCore', (), {'WaveFile': MockWaveFile})

# --- AUDIOMIXER MOCK (Multi-channel Audio Router) ---
class MockMixerVoice:
    def __init__(self, index):
        self.index = index
        self._level = 1.0
        self.playing = False

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, val):
        self._level = val
        # Optional: print(f"[HW AUDIO] Channel {self.index} Vol -> {val:.2f}")

    def play(self, sample, loop=False):
        self.playing = True
        filename = getattr(sample, 'filename', 'synth/stream')
        print(f"[HW AUDIO] Channel {self.index} Playing -> {filename}")

    def stop(self):
        self.playing = False

class MockMixer:
    def __init__(self, voice_count=1, **kwargs):
        self.voice = [MockMixerVoice(i) for i in range(voice_count)]
        self.playing = False

    def play(self, sample, voice=0, loop=False):
        self.voice[voice].play(sample, loop)

    def stop_voice(self, voice):
        self.voice[voice].stop()

sys.modules['audiomixer'] = type('MockAudioMixer', (), {'Mixer': MockMixer})

# --- SYNTHIO MOCK ---
class MockEnvelope:
    def __init__(self, attack_time=0.0, decay_time=0.0, release_time=0.0, attack_level=1.0, sustain_level=1.0):
        pass

class MockNote:
    def __init__(self, frequency=440.0, waveform=None, envelope=None):
        self.frequency = frequency

class MockSynthesizer:
    def __init__(self, sample_rate=22050, channel_count=1):
        self.active_notes = set()
    def press(self, note):
        self.active_notes.add(note)
        print(f"[SYNTH] Pressed Note:  {note.frequency:>6.1f} Hz")
    def release(self, note):
        if note in self.active_notes:
            self.active_notes.remove(note)
            print(f"[SYNTH] Released Note: {note.frequency:>6.1f} Hz")
    def release_all(self):
        self.active_notes.clear()

class MockSynthioModule:
    Envelope = MockEnvelope
    Note = MockNote
    Synthesizer = MockSynthesizer

sys.modules['synthio'] = MockSynthioModule()

# --- DISPLAYIO MOCKS ---
class MockDisplayGroup:
    """Mocks displayio.Group to act as a list of UI elements."""
    def __init__(self, **kwargs):
        self._items = []
        self.hidden = False
        self.x = 0
        self.y = 0

    def append(self, item): self._items.append(item)
    def pop(self, i=-1): return self._items.pop(i)
    def __len__(self): return len(self._items)
    def __iter__(self): return iter(self._items)

class MockI2CDisplay:
    def __init__(self, *args, **kwargs): pass

sys.modules['displayio'] = type('MockDisplayIO', (), {
    'Group': MockDisplayGroup,
    'I2CDisplay': MockI2CDisplay,
    'release_displays': lambda: None
})

# --- TERMINALIO MOCK ---
sys.modules['terminalio'] = type('MockTerminalIO', (), {'FONT': 'default_font'})

# --- SSD1306 MOCK ---
class MockSSD1306:
    def __init__(self, *args, **kwargs):
        self.root_group = None

sys.modules['adafruit_displayio_ssd1306'] = type('MockSSD1306Mod', (), {'SSD1306': MockSSD1306})

# --- ADAFRUIT_DISPLAY_TEXT MOCK ---
class MockLabel:
    """Mocks adafruit_display_text.label.Label to hold text, coordinates, and visibility."""
    def __init__(self, font, text="", x=0, y=0, **kwargs):
        self.font = font
        self.text = text
        self.x = x
        self.y = y
        self.hidden = False

class MockLabelModule:
    Label = MockLabel

# Map both the package and the submodule to handle `from adafruit_display_text import label`
sys.modules['adafruit_display_text'] = type('MockAdatruitDisplayText', (), {'label': MockLabelModule})
sys.modules['adafruit_display_text.label'] = MockLabelModule

# --- MCP230XX EXPANDER MOCK ---
class MockMCPPin:
    def __init__(self, pin_num):
        self.pin = pin_num
        self.direction = None
        self.pull = None
        self._value = True # Default UP (assuming pull-ups)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val

class MockMCP:
    """Mocks the core MCP23008/MCP23017 chip."""
    def __init__(self, i2c, address):
        self.i2c = i2c
        self.address = address
        self.interrupt_enable = 0
        self.interrupt_configuration = 0
        self.pins = {} # Dictionary to track pin objects
        HardwareMocks.mcp = self

    def get_pin(self, pin_num):
        if pin_num not in self.pins:
            self.pins[pin_num] = MockMCPPin(pin_num)
        return self.pins[pin_num]

# Inject the parent package and the specific chip submodules
sys.modules['adafruit_mcp230xx'] = type('MockMCPMod', (), {})
sys.modules['adafruit_mcp230xx.mcp23017'] = type('MockMCP17', (), {'MCP23017': MockMCP})
sys.modules['adafruit_mcp230xx.mcp23008'] = type('MockMCP08', (), {'MCP23008': MockMCP})
#endregion
