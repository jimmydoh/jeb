import sys
import time
import pygame
import os
import builtins

from utilities.logger import JEBLogger

# ==========================================
# SAFE AUDIO INITIALIZATION
# ==========================================
AUDIO_AVAILABLE = False
try:
    # Pre-init the mixer to avoid a slight delay when the first sound plays
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.mixer.init()
    AUDIO_AVAILABLE = True
    JEBLogger.emulator("MOCK", "🔊 Hardware Audio Device found")
except Exception as e:
    JEBLogger.emulator("MOCK", f"⚠️ No audio device available")

# ==========================================
# FILESYSTEM / SD CARD MOCK
# ==========================================
# Intercept file operations to map CircuitPython paths to the local Windows repo

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../'))
SRC_DIR = os.path.join(PROJECT_ROOT, 'src')
SD_DIR = os.path.join(PROJECT_ROOT, 'sd') # <--- Get absolute path to the SD folder

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

_orig_stat = os.stat
_orig_mkdir = os.mkdir
_orig_open = builtins.open

def smart_path_mapper(path):
    if not isinstance(path, str):
        return path

    # If the code is looking for the SD card, route it absolutely to the repo's SD folder
    if path.lower().startswith('/sd/') or path.lower().startswith('sd/'):
        # Strip the '/sd/' prefix and append the rest to our absolute SD_DIR
        clean_path = path[4:] if path.lower().startswith('/sd/') else path[3:]
        JEBLogger.emulator("MOCK", f"Path {path} mapped -> {os.path.join(SD_DIR, clean_path)}")
        return os.path.join(SD_DIR, clean_path)

    return path

# Patch the file operations
def _mock_stat(path, *args, **kwargs):
    JEBLogger.emulator("MOCK", f"Intercepted os.stat for path: {path}")
    return _orig_stat(smart_path_mapper(path), *args, **kwargs)

def _mock_open(file, *args, **kwargs):
    JEBLogger.emulator("MOCK", f"Intercepted open for file: {file}")
    return _orig_open(smart_path_mapper(file), *args, **kwargs)

def _mock_mkdir(path, *args, **kwargs):
    JEBLogger.emulator("MOCK", f"Intercepted os.mkdir for path: {path}")
    return _orig_mkdir(smart_path_mapper(path), *args, **kwargs)

class MockStorage:
    @staticmethod
    def getmount(path):
        if path == "/sd":
            return True # Simulate SD card being mounted
        raise OSError("Mount not found")

sys.modules['storage'] = MockStorage()

# Apply the patches globally for the emulator session
os.stat = _mock_stat
os.mkdir = _mock_mkdir
builtins.open = _mock_open

# Console Mocks
class MockRuntime:
    serial_bytes_available = False

class MockSupervisor:
    runtime = MockRuntime()
    @staticmethod
    def reload():
        JEBLogger.emulator("MOCK", "⚠️ supervisor.reload() called. Exiting...")
        sys.exit(0)

sys.modules['supervisor'] = MockSupervisor()

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
    """Context-Aware Registry for multi-device hardware emulation."""
    _current_context = "CORE"

    # Store devices in isolated "namespaces"
    devices = {
        "CORE": {},
        "SAT_01": {}
    }

    # Global state (Not tied to a specific microcontroller)
    satellite_plugged_in = False
    satbus_detect_pin = None
    satbus_mosfet_pin = None

    @classmethod
    def set_context(cls, context_name):
        """Called right before booting a specific system's firmware."""
        cls._current_context = context_name
        if context_name not in cls.devices:
            cls.devices[context_name] = {}

    @classmethod
    def register(cls, mock_type, instance, key=None):
        """Mocks call this during __init__ to register themselves."""
        if key is not None:
            # Handle multiple identical items (like I2C Segment Displays)
            if mock_type not in cls.devices[cls._current_context]:
                cls.devices[cls._current_context][mock_type] = {}
            cls.devices[cls._current_context][mock_type][key] = instance
        else:
            cls.devices[cls._current_context][mock_type] = instance

    @classmethod
    def get(cls, context, mock_type, key=None):
        """Pygame UI calls this to retrieve the specific hardware state."""
        device_dict = cls.devices.get(context, {})
        if key is not None:
            return device_dict.get(mock_type, {}).get(key)
        return device_dict.get(mock_type)

# --- KEYPAD MOCK ---
class MockKeypadEvent:
    def __init__(self, key_number=0, pressed=True, released=False):
        self.key_number = key_number
        self.pressed = pressed
        self.released = released

class MockEventQueue:
    def __init__(self):
        self.queue = []

    def get(self):
        """Returns a new event, or None if the queue is empty."""
        if self.queue:
            return self.queue.pop(0)
        return None

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
            HardwareMocks.register('buttons', self)
        elif pins and len(pins) == 1:
            HardwareMocks.register('encoder_btn', self)

class MockKeypad:
    """Explicitly handles matrix keypads (row x col) for the Satellite."""
    def __init__(self, row_pins, column_pins, **kwargs):
        self.events = MockEventQueue()
        HardwareMocks.register('matrix_keypad', self)

sys.modules['keypad'] = type('MockKeypadModule', (), {
    'Event': MockKeypadEvent,
    'Keys': MockKeys,
    'Keypad': MockKeypad
})

# --- ROTARYIO MOCK ---
class MockIncrementalEncoder:
    def __init__(self, pin_a, pin_b):
        self.position = 0
        HardwareMocks.register('encoder', self)

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

        # Identify the pin based on the board constant
        # Note: 'board.GP15' is the standard MCP_INT pin in your Pins class
        if str(pin) == "board.GP11":
            HardwareMocks.register('mcp_int', self)
        elif str(pin) == "board.GP13":  # Expander 2 INT
            HardwareMocks.register('mcp2_int', self)
        elif str(pin) == "board.GP7": # Example E-Stop pin
            HardwareMocks.register('estop', self)
        elif str(pin) == "board.GP15": # Example SATBUS Detect pin
            HardwareMocks.register('satbus_detect_pin', self)
            self._value = True  # Assuming True = Pulled Up = Disconnected
            JEBLogger.emulator("MOCK","Registered GP15 as SATBUS DETECT")
        elif str(pin) == "board.GP14": # Example SATBUS MOSFET control pin
            HardwareMocks.register('satbus_mosfet_pin', self)
            self._value = False # Start with MOSFET off
            JEBLogger.emulator("MOCK","Registered GP14 as SATBUS MOSFET CONTROL")

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = val

sys.modules['digitalio'] = type('MockDigitalIO', (), {
    'DigitalInOut': MockDigitalInOut,
    'Pull': MockPull,
    'Direction': MockDirection
})

# --- BOARD PINS MOCK ---
class MockPin:
    def __init__(self, name): self.name = name
    def __repr__(self): return f"board.{self.name}"
    def __hash__(self): return hash(self.name)
    def __eq__(self, other): return getattr(other, 'name', None) == self.name

class MockBoard:
    def __getattr__(self, name): return MockPin(name)

# --- WATCHDOG MOCK ---
class MockWatchdog:
    class WatchDogMode:
        RESET = 1
        RAISE = 2

    def __init__(self):
        self.timeout = 10
        self.mode = self.WatchDogMode.RESET

    def feed(self):
        # Optional: uncomment to see the heartbeat in the console
        # JEBLogger.note("MOCK", "[WATCHDOG] Fed", "EMUL")
        pass

mock_watchdog = MockWatchdog()

sys.modules['board'] = MockBoard()
sys.modules['microcontroller'] = type('MockMicrocontroller', (), {
    'pin': type('MockPin', (), {})(),
    'watchdog': mock_watchdog,
    'WatchDogMode': MockWatchdog.WatchDogMode # Some versions use this path
})

# busio (UART and I2C)
class MockUARTEndpoint:
    """A single end of a virtual UART cable."""
    def __init__(self, name):
        self.name = name
        self.rx_buffer = bytearray()
        self.peer = None  # The other end of the cable

    @property
    def in_waiting(self):
        return len(self.rx_buffer)

    def readinto(self, buf):
        length = min(len(buf), len(self.rx_buffer))
        if length > 0:
            # Copy bytes into the requested buffer
            buf[:length] = self.rx_buffer[:length]
            # Remove read bytes from our queue
            self.rx_buffer = self.rx_buffer[length:]
        return length

    def write(self, data):
        # Check if the Master has physically energized the bus
        mosfet = HardwareMocks.get("CORE", "satbus_mosfet_pin")
        is_powered = mosfet and mosfet.value
        if self.peer and is_powered:
            self.peer.rx_buffer.extend(data)
        return len(data)

    def reset_input_buffer(self):
        self.rx_buffer.clear()

class VirtualUARTBridge:
    """Holds the two endpoints of our simulation cable."""
    def __init__(self):
        self.master_hw = MockUARTEndpoint("CORE")
        self.sat_hw_up = MockUARTEndpoint("SAT_01_UP")
        self.sat_hw_down = MockUARTEndpoint("SAT_01_DOWN")

        # Cross-wire the TX to RX
        self.master_hw.peer = self.sat_hw_up
        self.sat_hw_up.peer = self.master_hw
        self.sat_hw_down.peer = None # No peer yet

# Create a global instance of our cable
VIRTUAL_CABLE = VirtualUARTBridge()

class MockBusioModule:
    class I2C:
        def __init__(self, *args, **kwargs): pass

    class UART:
        def __new__(cls, tx, rx, *args, **kwargs):
            ctx = HardwareMocks._current_context
            if ctx == "CORE":
                return VIRTUAL_CABLE.master_hw
            else:
                # Ask the registry if THIS specific satellite has assigned its upstream port yet
                if not HardwareMocks.get(ctx, "uart_up_assigned"):
                    # Upstream hasn't been assigned yet, this is it!
                    HardwareMocks.register("uart_up_assigned", True)
                    return VIRTUAL_CABLE.sat_hw_up

                else:
                    # The upstream is taken. This must be the downstream port!
                    HardwareMocks.register("uart_down_assigned", True)
                    return VIRTUAL_CABLE.sat_hw_down

sys.modules['busio'] = MockBusioModule()

# --- ANALOGIO MOCK (For Native ADC Power Monitoring) ---
class MockAnalogIn:
    def __init__(self, pin):
        self.pin = pin
        self._value = 49650  # Default ~2.5V raw

        # Register so the Pygame UI can dynamically manipulate rail voltages
        HardwareMocks.register('analog_pin', self, key=str(pin))

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, val):
        self._value = max(0, min(65535, int(val))) # Clamp to 16-bit int

sys.modules['analogio'] = type('MockAnalogIO', (), {'AnalogIn': MockAnalogIn})

# --- ADAFRUIT_ADS1X15 I2C ADC MOCK ---
class MockADS1115:
    def __init__(self, i2c, address=0x48):
        self.address = address
        self.i2c = i2c  # Stored to match real ADS1115 API signature
        # Adafruit pins mapping
        self.P0, self.P1, self.P2, self.P3 = 0, 1, 2, 3
        HardwareMocks.register('i2c_adc', self, key=address)

class MockADSAnalogIn:
    def __init__(self, ads, pin):
        self.ads = ads
        self.pin = pin
        self._voltage = 2.5 # Default 2.5V direct reading
        HardwareMocks.register('ads_channel', self, key=pin)

    @property
    def voltage(self):
        # I2C ADCs return calculated float voltages, unlike analogio's raw 16-bit value
        return self._voltage

    @voltage.setter
    def voltage(self, val):
        self._voltage = float(val)

# Create module objects that support both attribute access and importing
class MockADS1115Module:
    """Submodule mock for adafruit_ads1x15.ads1115"""
    ADS1115 = MockADS1115
    # Add pin constants at module level too
    P0 = 0
    P1 = 1
    P2 = 2
    P3 = 3

class MockAnalogInModule:
    """Submodule mock for adafruit_ads1x15.analog_in"""
    AnalogIn = MockADSAnalogIn

class MockADS1x15Module:
    """Parent package mock for adafruit_ads1x15"""
    def __init__(self):
        # Make submodules available as attributes
        self.ads1115 = MockADS1115Module()
        self.analog_in = MockAnalogInModule()

# Register the modules in sys.modules
_ads1x15_parent = MockADS1x15Module()
sys.modules['adafruit_ads1x15'] = _ads1x15_parent
sys.modules['adafruit_ads1x15.ads1115'] = _ads1x15_parent.ads1115
sys.modules['adafruit_ads1x15.analog_in'] = _ads1x15_parent.analog_in



# neopixels
class MockNeoPixel:
    def __init__(self, pin, n, **kwargs):
        self.pin = pin
        self.n = n
        self.auto_write = kwargs.get('auto_write', True)
        self.brightness = kwargs.get('brightness', 1.0)

        # The internal hardware buffer holding (R,G,B) tuples
        self.pixels = [(0, 0, 0)] * n

        HardwareMocks.register('pixels', self)

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

# --- PIXEL FRAMEBUF MOCK ---
class MockPixelFramebuffer:
    """Mocks adafruit_pixel_framebuf to suppress warnings and allow text scrolling paths to execute."""
    def __init__(self, pixels, width, height, **kwargs):
        self.pixels = pixels
        self.width = width
        self.height = height

    def text(self, string, x, y, color, font_name=None):
        JEBLogger.emulator("MOCK", f"[FRAMEBUF] text('{string}', x={x}, y={y}, color={color}, font={font_name})")
        pass

    def display(self):
        pass

    def fill(self, color):
        pass

    def scroll(self, dx, dy):
        pass

sys.modules['adafruit_pixel_framebuf'] = type(
    'MockPixelFramebufModule', (), {'PixelFramebuffer': MockPixelFramebuffer}
)

# --- AUDIOBUSIO / AUDIOPWMIO MOCKS (Direct Playback Fallbacks) ---
class MockDirectAudioOut:
    """Handles cases where audio.play() is called without a mixer."""
    def __init__(self, *args, **kwargs):
        self.playing = False
        self._current_channel = None

    def play(self, sample, loop=False):
        self.playing = True
        filename = getattr(sample, 'filepath', 'synth/stream')

        if not AUDIO_AVAILABLE:
            JEBLogger.emulator("MOCK", f"🔊 Dummy play: {filename} (Loop: {loop})")
            return

        if hasattr(sample, 'sound') and sample.sound:
            # Find the first available open channel and play it
            self._current_channel = pygame.mixer.find_channel()
            if self._current_channel:
                self._current_channel.play(sample.sound, loops=-1 if loop else 0)

    def stop(self):
        self.playing = False
        if self._current_channel:
            self._current_channel.stop()

    def deinit(self): pass

sys.modules['audiobusio'] = type('MockAudioBusIO', (), {'I2SOut': MockDirectAudioOut})
sys.modules['audiopwmio'] = type('MockAudioPWMIO', (), {'PWMAudioOut': MockDirectAudioOut})

# --- PWMIO MOCK (For Buzzer/Piezo) ---
class MockPWMOut:
    def __init__(self, pin, duty_cycle=0, frequency=440, variable_frequency=True):
        self.pin = pin
        self._duty_cycle = duty_cycle
        self._frequency = frequency
        self.variable_frequency = variable_frequency
        self._is_playing = duty_cycle > 0

    @property
    def duty_cycle(self):
        return self._duty_cycle

    @duty_cycle.setter
    def duty_cycle(self, value):
        # Detect transition from silence to sound
        if value > 0 and self._duty_cycle == 0:
            JEBLogger.emulator("MOCK", f"[BUZZER] ON  ({self._frequency} Hz)")
        # Detect transition from sound to silence
        elif value == 0 and self._duty_cycle > 0:
            JEBLogger.emulator("MOCK", f"[BUZZER] OFF")

        self._duty_cycle = value

    @property
    def frequency(self):
        return self._frequency

    @frequency.setter
    def frequency(self, value):
        if value != self._frequency and self._duty_cycle > 0:
            JEBLogger.emulator("MOCK", f"[BUZZER] FREQ CHANGE -> {value} Hz")
        self._frequency = value

    def deinit(self):
        pass

sys.modules['pwmio'] = type('MockPWMIO', (), {'PWMOut': MockPWMOut})

# --- AUDIOCORE MOCK (.wav File Decoder) ---
class MockWaveFile:
    def __init__(self, file_obj, buffer=None):
        self.filepath = getattr(file_obj, 'name', 'unknown_audio')
        if self.filepath.startswith("/"):
            self.filepath = self.filepath[1:]
        self.sound = None
        if AUDIO_AVAILABLE:
            try:
                self.sound = pygame.mixer.Sound(self.filepath)
            except Exception as e:
                JEBLogger.emulator("MOCK", f"❌ [AUDIO ERROR] Could not load '{self.filepath}': {e}")
    def deinit(self): pass

class MockRawSample(MockWaveFile):
    """Mocks RawSample used by AudioManager for preloaded UI sounds."""
    def __init__(self, file_obj, *args, **kwargs):
        super().__init__(file_obj)

sys.modules['audiocore'] = type('MockAudioCore', (), {
    'WaveFile': MockWaveFile,
    'RawSample': MockRawSample
})

# --- AUDIOMIXER MOCK (Multi-channel Audio Router) ---
class MockMixerVoice:
    def __init__(self, index):
        self.index = index
        self._level = 1.0
        self._playing_mock_state = False

        # [NEW] Map this voice to a physical Pygame Channel!
        self.channel = pygame.mixer.Channel(index) if AUDIO_AVAILABLE else None

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, val):
        self._level = val
        if self.channel:
            self.channel.set_volume(val)

    @property
    def playing(self):
        """Check if this voice is currently playing a sound."""
        if self.channel:
            return self.channel.get_busy()

        return self._playing_mock_state

    def play(self, sample, loop=False):
        self._playing_mock_state = True
        filename = getattr(sample, 'filepath', 'synth/stream')

        # 1. Fallback / VM Logging Mode
        if not AUDIO_AVAILABLE:
            JEBLogger.emulator("MOCK", f"🔊 Dummy play: {filename} (Loop: {loop})")
            self._playing_mock_state = False
            return

        # 2. Hardware Audio Mode
        if hasattr(sample, 'sound') and sample.sound:
            loops = -1 if loop else 0
            self.channel.play(sample.sound, loops=loops)
        else:
            JEBLogger.emulator("MOCK", f"⚠️ [HW AUDIO] Channel {self.index} skipped unsupported sample: {filename}")
            self._playing_mock_state = False

    def stop(self):
        self._playing_mock_state = False
        if self.channel:
            self.channel.stop()

class MockMixer:
    def __init__(self, voice_count=1, **kwargs):
        if AUDIO_AVAILABLE:
            current_channels = pygame.mixer.get_num_channels()
            if voice_count > current_channels:
                JEBLogger.emulator("MOCK", f"Expanding Pygame channels from {current_channels} to {voice_count}")
                pygame.mixer.set_num_channels(voice_count)
        self.voice = [MockMixerVoice(i) for i in range(voice_count)]
        self._playing_mock_state = False

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
        JEBLogger.emulator("MOCK", f"[SYNTH] Pressed Note:  {note.frequency:>6.1f} Hz")
    def release(self, note):
        if note in self.active_notes:
            self.active_notes.remove(note)
            JEBLogger.emulator("MOCK", f"[SYNTH] Released Note: {note.frequency:>6.1f} Hz")
    def release_all(self):
        self.active_notes.clear()

class MockSynthioModule:
    Envelope = MockEnvelope
    Note = MockNote
    Synthesizer = MockSynthesizer

sys.modules['synthio'] = MockSynthioModule()

# --- ANALOGBUFIO MOCK (Audio DMA) ---
class MockBufferedIn:
    def __init__(self, pin, sample_rate=10000):
        self.pin = pin
        self.sample_rate = sample_rate

    def readinto(self, buffer):
        # Fill the buffer with a simulated sine wave + noise so the OLED waveform looks alive
        import math, random, time
        t = time.time()
        for i in range(len(buffer)):
            # Base 1.65V (32768) + sine wave + noise
            val = 32768 + int(10000 * math.sin(t * 10 + i * 0.1)) + random.randint(-2000, 2000)
            buffer[i] = max(0, min(65535, val))

    def deinit(self): pass

sys.modules['analogbufio'] = type('MockAnalogBufIO', (), {'BufferedIn': MockBufferedIn})

# --- ULAB.NUMPY MOCK (FFT & Spectrum Analysis) ---
class MockUlabArray:
    """A very dumbed-down numpy array mock to support the math in AudioAnalyzer."""
    def __init__(self, data):
        self.data = list(data)
    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return MockUlabArray([x - other for x in self.data])
        return MockUlabArray([x - y for x, y in zip(self.data, other.data)])
    def __pow__(self, power):
        return MockUlabArray([x ** power for x in self.data])
    def __add__(self, other):
        return MockUlabArray([x + y for x, y in zip(self.data, other.data)])
    def __len__(self):
        return len(self.data)
    def __getitem__(self, key):
        if isinstance(key, slice): return MockUlabArray(self.data[key])
        return self.data[key]

class MockUlabFFT:
    @staticmethod
    def fft(array_obj):
        import random
        length = len(array_obj.data)
        # Generate fake bouncy magnitudes for the EQ display
        real = [random.uniform(0, 50000) for _ in range(length)]
        imag = [0] * length
        return MockUlabArray(real), MockUlabArray(imag)

class MockUlabNumpy:
    float = float
    fft = MockUlabFFT()

    @staticmethod
    def array(buf, dtype=None):
        return MockUlabArray(buf)

    @staticmethod
    def mean(array_obj):
        if not array_obj.data: return 0
        return sum(array_obj.data) / len(array_obj.data)

    @staticmethod
    def sqrt(array_obj):
        import math
        return MockUlabArray([math.sqrt(abs(x)) for x in array_obj.data])

mock_numpy = MockUlabNumpy()
sys.modules['ulab'] = type('MockUlab', (), {'numpy': mock_numpy})
sys.modules['ulab.numpy'] = mock_numpy

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

class MockBitmap:
    """Mocks displayio.Bitmap for drawing waveforms and EQ bars."""
    def __init__(self, width, height, value_count):
        self.width = width
        self.height = height
        self.value_count = value_count
        self._data = [0] * (width * height)

    def fill(self, value):
        self._data = [value] * (self.width * self.height)

    def __setitem__(self, index, value):
        if isinstance(index, tuple):
            x, y = index
            if 0 <= x < self.width and 0 <= y < self.height:
                self._data[y * self.width + x] = value
        else:
            self._data[index] = value

    def __getitem__(self, index):
        if isinstance(index, tuple):
            x, y = index
            if 0 <= x < self.width and 0 <= y < self.height:
                return self._data[y * self.width + x]
            return 0
        return self._data[index]

class MockPalette:
    """Mocks displayio.Palette."""
    def __init__(self, num_colors):
        self.colors = [0] * num_colors

    def __setitem__(self, index, color):
        self.colors[index] = color

    def __getitem__(self, index):
        return self.colors[index]

class MockTileGrid:
    """Mocks displayio.TileGrid to wrap the Bitmap and Palette."""
    def __init__(self, bitmap, pixel_shader=None, **kwargs):
        self.bitmap = bitmap
        self.pixel_shader = pixel_shader
        self.x = kwargs.get('x', 0)
        self.y = kwargs.get('y', 0)
        self.hidden = False

class MockI2CDisplay:
    def __init__(self, *args, **kwargs): pass

sys.modules['displayio'] = type('MockDisplayIO', (), {
    'Group': MockDisplayGroup,
    'I2CDisplay': MockI2CDisplay,
    'Bitmap': MockBitmap,
    'Palette': MockPalette,
    'TileGrid': MockTileGrid,
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
    """Mocks adafruit_display_text.label.Label to hold text, coordinates, visibility, and colors."""
    def __init__(self, font, text="", x=0, y=0, **kwargs):
        self.font = font
        self.text = text
        self.x = x
        self.y = y
        self.hidden = False
        self.color = kwargs.get('color', 0xFFFFFF)
        self.background_color = kwargs.get('background_color', None)

class MockLabelModule:
    Label = MockLabel

sys.modules['adafruit_display_text'] = type('MockAdatruitDisplayText', (), {'label': MockLabelModule})
sys.modules['adafruit_display_text.label'] = MockLabelModule

# --- MCP230XX EXPANDER MOCK ---
class MockMCPPin:
    def __init__(self, pin_num, mcp_instance):
        self.pin = pin_num
        self._mcp = mcp_instance
        self._direction = None
        self._pull = None
        self._value = True # Default UP

    @property
    def direction(self):
        return self._direction

    @direction.setter
    def direction(self, val):
        self._direction = val

    @property
    def pull(self):
        return self._pull

    @pull.setter
    def pull(self, val):
        self._pull = val
        # Simulate the physical electrical pull resistor
        if val == MockPull.UP:
            self._value = True
        elif val == MockPull.DOWN:
            self._value = False

    @property
    def value(self):
        # THE FIRMWARE DOOR: Reading the GPIO register clears the interrupt (Active LOW -> pulls back True)
        int_key = 'mcp2_int' if self._mcp.address == 0x21 else 'mcp_int'
        mcp_int = HardwareMocks.get(self._mcp._context, int_key)
        if mcp_int:
            mcp_int.value = True

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
        self._context = HardwareMocks._current_context
        if address == 0x21:
            HardwareMocks.register('mcp2', self)
        else:
            HardwareMocks.register('mcp', self)

    @property
    def gpio(self):
        # Check on number of pins to determine if this is the 23008 or 23017 variant
        if len(self.pins) <= 8:
            # Return a byte representing the state of all 8 pins (MCP23008)
            value = 0
            for pin_num, pin in self.pins.items():
                if pin.value:
                    value |= (1 << pin_num)
            return value
        else:
            # For MCP23017, we need to return a 16-bit value. We'll assume pins 0-7 are GPIOA and 8-15 are GPIOB.
            value_a = 0
            value_b = 0
            for pin_num, pin in self.pins.items():
                if pin.value:
                    if pin_num < 8:
                        value_a |= (1 << pin_num)
                    else:
                        value_b |= (1 << (pin_num - 8))
            return (value_b << 8) | value_a

    def get_pin(self, pin_num):
        if pin_num not in self.pins:
            self.pins[pin_num] = MockMCPPin(pin_num, self)
        return self.pins[pin_num]

    def peek_pin(self, pin_num):
        # Backwards compatibility method used by the firmware to read pin state without clearing interrupts
        return self.get_pin(pin_num)

# Inject the parent package and the specific chip submodules
sys.modules['adafruit_mcp230xx'] = type('MockMCPMod', (), {})
sys.modules['adafruit_mcp230xx.mcp23017'] = type('MockMCP17', (), {'MCP23017': MockMCP})
sys.modules['adafruit_mcp230xx.mcp23008'] = type('MockMCP08', (), {'MCP23008': MockMCP})

# --- HT16K33 SEGMENT DISPLAY MOCK ---
class MockSeg14x4:
    def __init__(self, i2c, address=0x70, **kwargs):
        self.i2c = i2c
        self.address = address
        self._brightness = 1.0

        # State tracking for Pygame rendering
        self.chars = [" ", " ", " ", " "] # The 4 alphanumeric characters
        self.raw_digits = [0, 0, 0, 0]    # The 4 raw 16-bit bitmasks

        # Register this specific display with the global HardwareMocks
        HardwareMocks.register('segments', self, key=address)

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, val):
        self._brightness = val

    def fill(self, val):
        """Fills or clears the display. Usually called with 0 to clear."""
        char = " " if val == 0 else "*"
        self.chars = [char] * 4
        self.raw_digits = [val] * 4

    def print(self, value):
        """Prints a string to the 4 digits."""
        text = str(value)
        # Pad or truncate to exactly 4 characters
        text = text.ljust(4)[:4]
        self.chars = list(text)
        self.raw_digits = [0] * 4 # Clear raw data when printing text

    def set_digit_raw(self, index, bitmask):
        """Used by the corruption and matrix animations."""
        if 0 <= index < 4:
            self.raw_digits[index] = bitmask
            # Replace character with a block to signify raw animation
            self.chars[index] = "■" if bitmask > 0 else " "

    def show(self):
        """Called to flush raw digit updates."""
        pass

# Inject the package and submodule
sys.modules['adafruit_ht16k33'] = type('MockHT16K33', (), {})
sys.modules['adafruit_ht16k33.segments'] = type('MockHTSegments', (), {'Seg14x4': MockSeg14x4})
#endregion
