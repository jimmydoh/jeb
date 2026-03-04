"""
Real-time Audio Spectrum Analyzer.

Uses analogbufio (DMA) for ADC capture and ulab.numpy (FFT) for analysis.

Hardware setup (DC-bias bridge on ADC pin):
    - 10kΩ resistor from 3.3V to GP26  (bias anchor)
    - 10kΩ resistor from GND to GP26   (bias ground)
    - 0.1µF–1µF capacitor from DAC audio output to GP26  (AC coupling)

This lifts the audio signal so silence sits at ~1.65 V, keeping the
full AC swing within the Pico ADC's 0–3.3 V range.
"""

import array


class AudioAnalyzer:
    """Real-time audio spectrum analyzer using hardware loopback via ADC.

    Captures audio through a DC-biased ADC pin using DMA (analogbufio),
    then performs FFT analysis (ulab.numpy) to produce EQ band data
    suitable for an LED matrix display and waveform data for an OLED display.

    Args:
        adc_pin:     ADC-capable board pin (e.g., board.GP26)
        sample_rate: Sampling rate in Hz (default: 10000)
        num_samples: Samples per capture; must be a power of 2 (e.g., 256)
    """

    def __init__(self, adc_pin, sample_rate=10000, num_samples=256):
        self.num_samples = num_samples
        self._sample_rate = sample_rate
        # Unsigned 16-bit buffer for analogbufio DMA reads
        self.buffer = array.array('H', [0] * num_samples)

        import analogbufio
        self.adc = analogbufio.BufferedIn(adc_pin, sample_rate=sample_rate)

        # State for EQ smoothing
        self._prev_eq_floats = []

    def capture(self):
        """Performs a single, blocking DMA capture to fill the buffer."""
        self.adc.readinto(self.buffer)

    def get_eq_bands(self, num_bands=16, max_height=16, sensitivity=1000.0, smoothing=0.6):
        """Return per-band heights for EQ display from the current buffer.

        Assumes ``capture()`` has already been called to fill the buffer.
        Removes the DC bias, runs an FFT, maps the positive-frequency spectrum
        into ``num_bands`` buckets, and applies exponential moving average
        smoothing so bars glide rather than jump.

        Args:
            num_bands:   Number of frequency bands (default: 16 for 16×16 matrix)
            max_height:  Maximum bar height in pixels (default: 16)
            sensitivity: Divisor applied to raw FFT magnitude; lower values
                         make the bars react to quieter audio.
            smoothing:   Float from 0.0 to 1.0. Higher = smoother/slower,
                         lower = jumpier/faster. (default: 0.6)

        Returns:
            List of ``num_bands`` integers, each clamped to [0, max_height].
        """
        try:
            import ulab.numpy as np

            # ASSUMES buffer is already filled via capture()
            data = np.array(self.buffer, dtype=np.float)

            # Strip DC bias so silence ≈ 0
            data = data - np.mean(data)

            real, imag = np.fft.fft(data)
            magnitudes = np.sqrt(real ** 2 + imag ** 2)

            # Use positive-frequency half only; skip index 0 (DC residual)
            usable = (self.num_samples // 2) - 1
            bins_per_band = max(1, usable // num_bands)

            # Initialize smoothing state if empty or resized
            if not self._prev_eq_floats or len(self._prev_eq_floats) != num_bands:
                self._prev_eq_floats = [0.0] * num_bands

            heights = []
            for i in range(num_bands):
                start = 1 + i * bins_per_band
                end = start + bins_per_band
                band_vol = np.mean(magnitudes[start:end])
                raw_scaled = band_vol / sensitivity

                # Apply Exponential Moving Average smoothing
                smoothed = (raw_scaled * (1.0 - smoothing)) + (self._prev_eq_floats[i] * smoothing)
                self._prev_eq_floats[i] = smoothed

                heights.append(max(0, min(max_height, int(smoothed))))

            return heights

        except Exception as e:
            print(f"AudioAnalyzer.get_eq_bands error: {e}")
            return [0] * num_bands

    def get_waveform(self, num_points=128):
        """Return a normalized waveform for OLED display from the current buffer.

        Assumes ``capture()`` has already been called to fill the buffer.
        Removes the DC bias and downsamples to ``num_points`` values
        normalized to [0.0, 1.0] where 0.5 = silence.

        Args:
            num_points: Number of output points (default: 128 = OLED width)

        Returns:
            List of ``num_points`` floats in [0.0, 1.0].
        """
        try:
            import ulab.numpy as np

            # ASSUMES buffer is already filled via capture()
            data = np.array(self.buffer, dtype=np.float)
            data = data - np.mean(data)

            # C-speed downsampling via array slicing
            step = max(1, self.num_samples // num_points)
            samples = data[::step][:num_points]

            # C-speed vectorized normalization
            peak = np.max(np.abs(samples))
            if peak == 0.0:
                peak = 1.0

            normalized = (samples / peak + 1.0) / 2.0
            return normalized.tolist()

        except Exception as e:
            print(f"AudioAnalyzer.get_waveform error: {e}")
            return [0.5] * num_points

    def deinit(self):
        """Release the ADC hardware resource."""
        try:
            self.adc.deinit()
        except Exception:
            pass
