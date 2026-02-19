# tests/conftest.py
import os
import sys
from unittest import mock

src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if src_path not in sys.path:
    sys.path.append(src_path)

# Mock ALL CircuitPython modules that might be imported by the code under test.
circuitpython_mocks = [
    'digitalio', 'board', 'busio', 'neopixel', 'microcontroller',
    'analogio', 'audiocore', 'audiobusio', 'audioio', 'audiomixer',
    'adafruit_httpserver', 'adafruit_bus_device', 'adafruit_register',
    'sdcardio', 'storage', 'synthio', 'displayio', 'terminalio',
    'adafruit_framebuf', 'framebufferio', 'rgbmatrix', 'supervisor'
]

for module_name in circuitpython_mocks:
    sys.modules[module_name] = mock.MagicMock()
