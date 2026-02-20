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

    def get_eq_bands(self, num_bands=16, max_height=16, sensitivity=1000.0):
        """Capture audio and return per-band heights for EQ display.

        Performs a single DMA capture, removes the DC bias, runs an FFT,
        and maps the positive-frequency spectrum into ``num_bands`` buckets.

        Args:
            num_bands:   Number of frequency bands (default: 16 for 16×16 matrix)
            max_height:  Maximum bar height in pixels (default: 16)
            sensitivity: Divisor applied to raw FFT magnitude; lower values
                         make the bars react to quieter audio.

        Returns:
            List of ``num_bands`` integers, each clamped to [0, max_height].
        """
        try:
            import ulab.numpy as np

            self.adc.readinto(self.buffer)
            data = np.array(self.buffer, dtype=np.float)

            # Strip DC bias so silence ≈ 0
            data = data - np.mean(data)

            real, imag = np.fft.fft(data)
            magnitudes = np.sqrt(real ** 2 + imag ** 2)

            # Use positive-frequency half only; skip index 0 (DC residual)
            usable = (self.num_samples // 2) - 1
            bins_per_band = max(1, usable // num_bands)

            heights = []
            for i in range(num_bands):
                start = 1 + i * bins_per_band
                end = start + bins_per_band
                band_vol = np.mean(magnitudes[start:end])
                scaled = int(band_vol / sensitivity)
                heights.append(max(0, min(max_height, scaled)))

            return heights

        except Exception as e:
            print(f"AudioAnalyzer.get_eq_bands error: {e}")
            return [0] * num_bands

    def get_waveform(self, num_points=128):
        """Capture audio and return a normalized waveform for OLED display.

        Performs a single DMA capture, removes the DC bias, and downsamples
        to ``num_points`` values normalized to [0.0, 1.0] where 0.5 = silence.

        Args:
            num_points: Number of output points (default: 128 = OLED width)

        Returns:
            List of ``num_points`` floats in [0.0, 1.0].
        """
        try:
            import ulab.numpy as np

            self.adc.readinto(self.buffer)
            data = np.array(self.buffer, dtype=np.float)
            data = data - np.mean(data)

            # Downsample to num_points
            step = max(1, self.num_samples // num_points)
            samples = [float(data[i * step]) for i in range(num_points)]

            # Normalize: map [-peak, +peak] → [0.0, 1.0]; silence = 0.5
            peak = max(abs(v) for v in samples) or 1.0
            return [(v / peak + 1.0) / 2.0 for v in samples]

        except Exception as e:
            print(f"AudioAnalyzer.get_waveform error: {e}")
            return [0.5] * num_points

    def deinit(self):
        """Release the ADC hardware resource."""
        try:
            self.adc.deinit()
        except Exception:
            pass
