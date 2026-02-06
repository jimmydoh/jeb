# Synthio Generative Audio Engine Implementation

## Overview

The synthio generative audio engine provides procedurally generated audio for the JEB (JADNET Electronics Box) system using CircuitPython's `synthio` module. This implementation eliminates the need for static WAV files for UI sounds and background ambience, providing zero-latency audio with negligible RAM usage.

## Architecture

### Component Structure

```
┌─────────────────────────────────────────────────────────────┐
│                      CoreManager                            │
│  ┌───────────────┐  ┌─────────────┐  ┌────────────────┐   │
│  │ AudioManager  │  │ SynthManager │  │ BuzzerManager  │   │
│  │ (I2S Output)  │◄─┤ (synthio)    │  │ (PWM Buzzer)   │   │
│  └───────────────┘  └─────────────┘  └────────────────┘   │
│         ▲                   ▲                               │
│         │                   │                               │
│    4 Mixer Channels    Waveforms &                         │
│    ┌─────────────┐      Envelopes                          │
│    │ 0: ATMO     │                                          │
│    │ 1: SFX      │                                          │
│    │ 2: VOICE    │                                          │
│    │ 3: SYNTH    │◄─────────┐                              │
│    └─────────────┘           │                              │
│                              │                              │
│         ┌────────────────────┴──────────────┐              │
│         │  utilities/synth_registry.py      │              │
│         │  - Waveforms (Sine, Square, etc.) │              │
│         │  - Envelopes (ADSR parameters)    │              │
│         │  - Patches (Wave + Envelope)      │              │
│         └───────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

### Core Implementation Files

1. **`src/managers/synth_manager.py`**
   - Main SynthManager class
   - Note playback and sequencing
   - Generative drone system

2. **`src/utilities/synth_registry.py`**
   - Waveform generation (Sine, Square, Saw, Triangle)
   - ADSR envelope definitions
   - Patch presets (combining waveforms and envelopes)

3. **`src/utilities/tones.py`**
   - Note frequency constants
   - Musical sequences and scores
   - Synthio-specific compositions

4. **`src/managers/audio_manager.py`**
   - Mixer channel management
   - Synth attachment via `attach_synth()` method
   - Integration with WAV file playback

5. **`src/core/core_manager.py`**
   - SynthManager initialization
   - Generative drone startup
   - Integration with main event loop

## Key Features

### 1. Real-Time Synthesis

```python
# Play a single note
core.synth.play_note(440.0, "UI_SELECT", duration=0.1)

# Play a chord
note1 = core.synth.play_note(261.63)  # C4
note2 = core.synth.play_note(329.63)  # E4
note3 = core.synth.play_note(392.00)  # G4
await asyncio.sleep(1.0)
core.synth.release_all()
```

### 2. Sequence Playback

```python
from utilities.tones import SUCCESS, POWER_UP

# Play a predefined sequence
await core.synth.play_sequence(SUCCESS, patch_name="SCANNER")

# Play power-up sound
await core.synth.play_sequence(POWER_UP, patch_name="UI_SELECT")
```

### 3. Generative Drone

The generative drone creates evolving background ambience:

```python
# Started automatically in CoreManager.start()
asyncio.create_task(self.synth.start_generative_drone())
```

**Characteristics:**
- Random note selection from C Minor chord (C3, Eb3, G3)
- Frequency jittering (+/- 2 Hz) for analog character
- Variable duration (3-6 seconds per note)
- Overlapping notes create harmonic texture
- Uses ENGINE_HUM patch with long attack/release

### 4. Audio Mixing

The synthio output is mixed with WAV file channels:

```python
# Initialize audio system
self.audio = AudioManager(Pins.I2S_SCK, Pins.I2S_WS, Pins.I2S_SD)
self.synth = SynthManager()

# Attach synth to mixer channel 3
self.audio.attach_synth(self.synth.source)

# Now both WAV files and synth can play simultaneously
self.audio.play("voice/welcome.wav", channel=self.audio.CH_VOICE)
self.synth.play_note(440.0, "UI_SELECT", duration=0.1)
```

## Waveforms

All waveforms use 512 samples for a single cycle:

### Sine Wave
- Smooth, pure tone
- Best for: Musical notes, clean tones

### Square Wave
- Rich in odd harmonics
- Best for: Retro beeps, harsh alerts

### Sawtooth Wave
- Rich in all harmonics
- Best for: Buzzy sounds, alarms

### Triangle Wave
- Softer than square, cleaner than saw
- Best for: Mellow tones, engine hums

## Envelopes (ADSR)

### CLICK
- Attack: 0.001s, Decay: 0.05s, Release: 0.05s
- Use: Fast UI feedback clicks

### BEEP
- Attack: 0.01s, Decay: 0s, Release: 0.1s
- Use: Standard UI beeps and confirmations

### PAD
- Attack: 0.5s, Decay: 0.2s, Release: 0.5s
- Use: Soft, ambient pads and backgrounds

### PUNCHY
- Attack: 0.005s, Decay: 0.1s, Release: 0.1s
- Use: Percussive sounds, alarms

## Patches (Waveform + Envelope Combinations)

### UI_SELECT
- Wave: SQUARE, Envelope: CLICK
- Use: Button selections, menu navigation

### UI_ERROR
- Wave: SAW, Envelope: PUNCHY
- Use: Error notifications

### ALARM
- Wave: SAW, Envelope: BEEP
- Use: Warning alarms

### IDLE_HUM
- Wave: SINE, Envelope: PAD
- Use: Idle background ambience

### SCANNER
- Wave: TRIANGLE, Envelope: BEEP
- Use: Scanning or processing sounds

### ENGINE_HUM
- Wave: TRIANGLE, Envelope: Custom (1.5s attack/release, 40% level)
- Use: Background drone, engine sounds

### DATA_STREAM
- Wave: SQUARE, Envelope: Custom (0.05s attack, 15% level)
- Use: Data transmission sounds

## Memory Usage

### Waveforms
- 4 waveforms × 512 samples × 2 bytes = **4KB total**

### Per-Note Overhead
- ~100 bytes per active note object
- Minimal ADSR envelope overhead

### Total Footprint
- Static allocation: ~4KB
- Dynamic allocation: ~100 bytes per note
- Max polyphony limited by RAM (typically 8-16 notes)

## Performance Considerations

### CPU Usage
- **Low**: synthio is optimized for microcontrollers
- Minimal impact on main event loop
- Hardware acceleration where available

### Sample Rate
- **22050 Hz**: Balanced quality vs performance
- Matches AudioManager configuration
- Adequate for UI sounds and ambience

### Polyphony
- Theoretically unlimited (POLYPHONIC mode)
- Practically limited by CPU and RAM
- Recommended max: 8-12 simultaneous notes

## Integration with Existing Audio System

### Coexistence with WAV Files

The synth operates on its own mixer channel (CH_SYNTH = 3):

```python
# Channel assignments
CH_ATMO  = 0  # Background atmosphere WAV files
CH_SFX   = 1  # Sound effects WAV files
CH_VOICE = 2  # Voice narration WAV files
CH_SYNTH = 3  # Synthio generated audio

# All channels can play simultaneously
```

### Audio Manager Integration

```python
class AudioManager:
    def __init__(self, sck, ws, sd, voice_count=4):
        self.mixer = audiomixer.Mixer(voice_count=4, ...)
        self.CH_SYNTH = 3
    
    def attach_synth(self, synth_source):
        """Attach synthio output to mixer."""
        self.mixer.voice[self.CH_SYNTH].play(synth_source)
```

## Usage Examples

### Basic UI Feedback

```python
# Button press sound
core.synth.play_note(1000.0, "UI_SELECT", duration=0.05)

# Error sound
core.synth.play_note(200.0, "UI_ERROR", duration=0.2)

# Success chime
await core.synth.play_sequence(SUCCESS, patch_name="SCANNER")
```

### Menu Navigation

```python
class MainMenu(BaseMode):
    async def run(self):
        while True:
            # Tick sound on encoder rotation
            if encoder_changed:
                core.synth.play_note(800.0, "UI_SELECT", duration=0.03)
            
            # Confirmation sound on button press
            if button_pressed:
                await core.synth.play_sequence(UI_CONFIRM)
```

### Alarm System

```python
# Start alarm
alarm_task = asyncio.create_task(self._play_alarm())

async def _play_alarm(self):
    while alarm_active:
        core.synth.play_note(1000.0, "ALARM", duration=0.2)
        await asyncio.sleep(0.3)
        core.synth.play_note(800.0, "ALARM", duration=0.2)
        await asyncio.sleep(0.3)
```

### Ambient Background

```python
# The generative drone runs continuously in the background
# Started in CoreManager.start():
asyncio.create_task(self.synth.start_generative_drone())

# To customize, modify the frequencies in start_generative_drone()
```

## Benefits vs Static WAV Files

### ✅ Zero Disk I/O Latency
- No file open/read operations
- Immediate audio response
- No SD card access delays

### ✅ Minimal RAM Usage
- 4KB for all waveforms
- No need to preload sound files
- Dynamic note allocation

### ✅ Infinite Variability
- Generate any frequency on demand
- Randomized parameters for uniqueness
- Procedural composition possibilities

### ✅ Perfect for Industrial Aesthetic
- Sci-fi UI beeps and boops
- Low-frequency hums and drones
- Retro computer sounds

### ✅ No File Management
- No WAV file creation required
- No file naming conventions
- No directory structure needed

## CircuitPython Compatibility

### Minimum Requirements
- **CircuitPython**: 8.x+ (10.x+ recommended)
- **Hardware**: RP2350 or compatible
- **RAM**: 520KB (RP2350 Pico 2)
- **Audio Output**: I2S DAC or built-in audio

### API Compatibility
All synthio API usage is standard and compatible with:
- CircuitPython 8.0+
- CircuitPython 9.0+
- CircuitPython 10.0+

### Tested Platforms
- ✅ Raspberry Pi Pico 2 (RP2350)

## Best Practices

### 1. Use Short Durations for UI Sounds
```python
# Good: Quick, responsive feedback
core.synth.play_note(1000.0, "UI_SELECT", duration=0.05)

# Avoid: Long UI sounds that delay interaction
core.synth.play_note(1000.0, "UI_SELECT", duration=1.0)  # Too long!
```

### 2. Release Notes to Prevent Memory Leaks
```python
# Good: Auto-release after duration
note = core.synth.play_note(440.0, duration=1.0)

# Requires manual cleanup if no duration:
note = core.synth.play_note(440.0)  # No auto-release
# ... later ...
core.synth.stop_note(note)  # Must manually release
```

### 3. Use Appropriate Patches for Context
```python
# Good: Use UI patches for UI sounds
core.synth.play_note(freq, "UI_SELECT")  # UI feedback

# Good: Use ENGINE_HUM for ambience
core.synth.play_note(freq, "ENGINE_HUM")  # Background drone
```

### 4. Handle Invalid Patch Names
The implementation now warns about invalid patches:
```python
# Warning logged if patch doesn't exist
core.synth.play_note(440.0, "TYPO_PATCH")
# Output: "Warning: Patch 'TYPO_PATCH' not found, using UI_SELECT"
```

## Troubleshooting

### Issue: No Audio Output
**Check:**
1. I2S pins correctly configured
2. SynthManager initialized and attached to AudioManager
3. Audio mixer channel not muted
4. Synth volume level not set to 0

### Issue: Distorted Audio
**Check:**
1. Sample rate matches (22050 Hz)
2. Waveform amplitude not clipping (MAX_AMP = 32000)
3. Too many simultaneous notes (reduce polyphony)
4. CPU overload (reduce background tasks)

### Issue: Memory Errors
**Check:**
1. Total active notes (should be < 16)
2. Memory fragmentation (call `gc.collect()`)
3. Large allocations elsewhere in code

## Future Enhancements

### Potential Improvements
1. **Volume Control**: Add per-note or global volume adjustment
2. **Drone Control**: Add start/stop methods for generative drone
3. **LFO/Modulation**: Add low-frequency oscillators for effects
4. **Filter Effects**: Add low-pass/high-pass filters
5. **Note Tracking**: Implement active note registry for debugging
6. **Type Hints**: Add type annotations for better IDE support

### Advanced Features
1. **Custom Waveforms**: User-defined waveform generation
2. **Multi-Drone**: Multiple simultaneous generative layers
3. **Rhythm Engine**: Pattern-based drum synthesis
4. **FM Synthesis**: Frequency modulation for complex timbres

## References

### CircuitPython Documentation
- [synthio Module](https://docs.circuitpython.org/en/latest/shared-bindings/synthio/)
- [audiomixer Module](https://docs.circuitpython.org/en/latest/shared-bindings/audiomixer/)
- [audiobusio Module](https://docs.circuitpython.org/en/latest/shared-bindings/audiobusio/)

### Related JEB Documentation
- [hardware-core.md](hardware-core.md) - Hardware specifications
- [README.md](../README.md) - Project overview

---

**Implementation**: Initial implementation
**Last Updated**: 2026-02-06
**Status**: ✅ Production Ready
