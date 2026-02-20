#!/usr/bin/env python3
"""Unit tests for AudioAnalyzer utility."""

import sys
import os
import array

# ---------------------------------------------------------------------------
# Mock CircuitPython modules BEFORE any production imports
# ---------------------------------------------------------------------------

class MockModule:
    """Generic mock module."""
    def __getattr__(self, name):
        return MockModule()

    def __call__(self, *args, **kwargs):
        return MockModule()


class MockBufferedIn:
    """Mock analogbufio.BufferedIn – fills buffer with synthetic audio data."""

    def __init__(self, pin, sample_rate=10000):
        self.pin = pin
        self.sample_rate = sample_rate
        self._fill_value = 32768  # ~1.65 V mid-scale (silence)

    def readinto(self, buf):
        """Fill buf with a simple sine-like pattern centred at mid-scale."""
        import math
        n = len(buf)
        for i in range(n):
            # 1 kHz tone at 10 kHz sample rate → 10 samples per cycle
            buf[i] = int(32768 + 10000 * math.sin(2 * math.pi * i / 10))

    def deinit(self):
        pass


class MockAnalogbufioModule:
    @staticmethod
    def BufferedIn(pin, sample_rate=10000):
        return MockBufferedIn(pin, sample_rate)


class MockNumpyArray:
    """List wrapper that supports the arithmetic operations ulab.numpy arrays do."""

    def __init__(self, data):
        self._data = [float(v) for v in data]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)

    def __getitem__(self, key):
        if isinstance(key, slice):
            return MockNumpyArray(self._data[key])
        return self._data[key]

    def __sub__(self, other):
        if isinstance(other, MockNumpyArray):
            return MockNumpyArray([a - b for a, b in zip(self._data, other._data)])
        return MockNumpyArray([v - other for v in self._data])

    def __add__(self, other):
        if isinstance(other, MockNumpyArray):
            return MockNumpyArray([a + b for a, b in zip(self._data, other._data)])
        return MockNumpyArray([v + other for v in self._data])

    def __mul__(self, other):
        if isinstance(other, MockNumpyArray):
            return MockNumpyArray([a * b for a, b in zip(self._data, other._data)])
        return MockNumpyArray([v * other for v in self._data])

    def __pow__(self, exp):
        return MockNumpyArray([v ** exp for v in self._data])

    def __truediv__(self, other):
        return MockNumpyArray([v / other for v in self._data])

    def __float__(self):
        if len(self._data) == 1:
            return self._data[0]
        raise TypeError("only length-1 arrays can be converted to scalar")


class MockNumpyModule:
    """Minimal ulab.numpy mock that supports the operations AudioAnalyzer uses."""

    float = float

    @staticmethod
    def array(data, dtype=None):
        return MockNumpyArray(data)

    @staticmethod
    def mean(data):
        if isinstance(data, MockNumpyArray):
            items = list(data)
        else:
            items = list(data)
        return sum(items) / len(items) if items else 0.0

    @staticmethod
    def sqrt(data):
        import math
        if isinstance(data, MockNumpyArray):
            return MockNumpyArray([math.sqrt(abs(v)) for v in data])
        return math.sqrt(abs(data))

    class fft:
        @staticmethod
        def fft(data):
            """Trivial DFT returning real/imag arrays of the same length."""
            n = len(data)
            real = MockNumpyArray([float(v) for v in data])
            imag = MockNumpyArray([0.0] * n)
            return real, imag


class MockUlabModule:
    numpy = MockNumpyModule()


# Patch sys.modules before importing production code
sys.modules['analogbufio'] = MockAnalogbufioModule()
sys.modules['ulab'] = MockUlabModule()
sys.modules['ulab.numpy'] = MockNumpyModule()
sys.modules['digitalio'] = MockModule()
sys.modules['busio'] = MockModule()
sys.modules['board'] = MockModule()
sys.modules['analogio'] = MockModule()
sys.modules['microcontroller'] = MockModule()

# ---------------------------------------------------------------------------
# Add src to path and import production code
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utilities.audio_analyzer import AudioAnalyzer  # noqa: E402


# ---------------------------------------------------------------------------
# Helper – build an AudioAnalyzer with mocked hardware
# ---------------------------------------------------------------------------

class MockPin:
    pass


def _make_analyzer(num_samples=256):
    """Create an AudioAnalyzer backed by the MockBufferedIn."""
    return AudioAnalyzer(adc_pin=MockPin(), sample_rate=10000, num_samples=num_samples)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_initialization():
    """AudioAnalyzer stores constructor parameters and creates a buffer."""
    analyzer = _make_analyzer(num_samples=128)

    assert analyzer.num_samples == 128
    assert analyzer._sample_rate == 10000
    assert isinstance(analyzer.buffer, array.array)
    assert analyzer.buffer.typecode == 'H'
    assert len(analyzer.buffer) == 128


def test_get_eq_bands_returns_correct_length():
    """get_eq_bands returns a list of length num_bands."""
    analyzer = _make_analyzer()

    bands = analyzer.get_eq_bands(num_bands=16)
    assert len(bands) == 16


def test_get_eq_bands_values_clamped():
    """All returned band heights are within [0, max_height]."""
    analyzer = _make_analyzer()
    max_h = 16

    bands = analyzer.get_eq_bands(num_bands=16, max_height=max_h)
    for i, h in enumerate(bands):
        assert 0 <= h <= max_h, f"Band {i} height {h} out of range [0, {max_h}]"


def test_get_eq_bands_custom_num_bands():
    """num_bands parameter controls the output list length."""
    analyzer = _make_analyzer()

    for nb in (4, 8, 16):
        bands = analyzer.get_eq_bands(num_bands=nb)
        assert len(bands) == nb, f"Expected {nb} bands, got {len(bands)}"


def test_get_waveform_returns_correct_length():
    """get_waveform returns a list of length num_points."""
    analyzer = _make_analyzer()

    waveform = analyzer.get_waveform(num_points=128)
    assert len(waveform) == 128


def test_get_waveform_values_normalized():
    """All waveform values are within [0.0, 1.0]."""
    analyzer = _make_analyzer()

    waveform = analyzer.get_waveform(num_points=64)
    for i, v in enumerate(waveform):
        assert 0.0 <= v <= 1.0, f"Sample {i} value {v} out of [0.0, 1.0]"


def test_get_waveform_custom_num_points():
    """num_points parameter controls the output list length."""
    analyzer = _make_analyzer()

    for np_ in (32, 64, 128):
        waveform = analyzer.get_waveform(num_points=np_)
        assert len(waveform) == np_


def test_deinit_does_not_raise():
    """deinit() can be called without raising an exception."""
    analyzer = _make_analyzer()
    analyzer.deinit()  # Should not raise


def test_get_eq_bands_graceful_on_error():
    """If an exception occurs during analysis, return a list of zeros."""
    analyzer = _make_analyzer()

    # Break the ADC so readinto raises
    class BrokenADC:
        def readinto(self, buf):
            raise RuntimeError("simulated hardware failure")
        def deinit(self):
            pass

    analyzer.adc = BrokenADC()
    bands = analyzer.get_eq_bands(num_bands=16)

    assert bands == [0] * 16


def test_get_waveform_graceful_on_error():
    """If an exception occurs during capture, return a list of 0.5 values."""
    analyzer = _make_analyzer()

    class BrokenADC:
        def readinto(self, buf):
            raise RuntimeError("simulated hardware failure")
        def deinit(self):
            pass

    analyzer.adc = BrokenADC()
    waveform = analyzer.get_waveform(num_points=32)

    assert waveform == [0.5] * 32


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("AudioAnalyzer Test Suite")
    print("=" * 60)

    test_initialization()
    print("✓ test_initialization")

    test_get_eq_bands_returns_correct_length()
    print("✓ test_get_eq_bands_returns_correct_length")

    test_get_eq_bands_values_clamped()
    print("✓ test_get_eq_bands_values_clamped")

    test_get_eq_bands_custom_num_bands()
    print("✓ test_get_eq_bands_custom_num_bands")

    test_get_waveform_returns_correct_length()
    print("✓ test_get_waveform_returns_correct_length")

    test_get_waveform_values_normalized()
    print("✓ test_get_waveform_values_normalized")

    test_get_waveform_custom_num_points()
    print("✓ test_get_waveform_custom_num_points")

    test_deinit_does_not_raise()
    print("✓ test_deinit_does_not_raise")

    test_get_eq_bands_graceful_on_error()
    print("✓ test_get_eq_bands_graceful_on_error")

    test_get_waveform_graceful_on_error()
    print("✓ test_get_waveform_graceful_on_error")

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
