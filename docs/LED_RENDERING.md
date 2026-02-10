# LED / Neopixel Rendering and Frame Sync

This document describes the LED rendering architecture and frame synchronization system for coordinating LED animations between the Core unit and Satellites.

## Overview

The JEB system implements a centralized LED rendering architecture where:
- Each device (Core and Satellites) has a dedicated `render_loop()` that runs at 60Hz
- The render loop is the ONLY place where `pixels.show()` is called (hardware write)
- LED animations update memory buffers asynchronously
- Frame sync protocol allows coordinated animations across devices

## Architecture

### Centralized Rendering

Both CoreManager and Satellite firmware implement the same rendering pattern:

```python
# Render loop configuration - runs at 60Hz for smooth LED updates
RENDER_FRAME_TIME = 1.0 / 60.0  # ~0.0167 seconds per frame

async def render_loop(self):
    """Centralized hardware write task for NeoPixel LEDs.
    
    This is the ONLY place where self.root_pixels.show() should be called.
    Runs at 60Hz to provide smooth, flicker-free LED updates while preventing
    race conditions from multiple async tasks writing to the hardware simultaneously.
    """
    while True:
        # Write the current buffer state to hardware
        self.root_pixels.show()
        # Increment local frame counter for sync tracking
        self.frame_counter += 1
        # Run at configured frame rate (default 60Hz)
        await asyncio.sleep(self.RENDER_FRAME_TIME)
```

### Why Centralized Rendering?

1. **Prevents Race Conditions**: Only one task writes to hardware, eliminating interleaved partial updates
2. **Smooth Animation**: Consistent 60Hz refresh rate provides flicker-free updates
3. **Separation of Concerns**: Animation logic updates memory buffers, rendering handles hardware writes
4. **Predictable Performance**: Known frame timing makes animation development easier

### Animation Flow

```
Animation Tasks (e.g., breathe, flash, rainbow)
    ↓
Update JEBPixel memory buffer (self.pixels[i] = (r, g, b))
    ↓
render_loop() reads buffer and calls pixels.show() at 60Hz
    ↓
Hardware LED update
```

## Frame Synchronization

### Purpose

Frame sync allows multiple devices to coordinate LED animations by sharing timing information:
- Synchronized color changes across Core and Satellites
- Phase-aligned animations (e.g., all devices pulse together)
- Time-based effects that span multiple devices

### Protocol

The Core broadcasts `SYNC_FRAME` commands periodically (every 1 second):

```
Command: SYNC_FRAME
Payload: "frame_number,time_seconds"
Example: "3600,60.123" (frame 3600 at 60.123 seconds)
```

### Implementation

#### Core Side (CoreManager)

```python
# State variables
self.frame_counter = 0
self.last_sync_broadcast = 0.0

# In render_loop()
self.frame_counter += 1

# Broadcast frame sync every 1 second
current_time = ticks_ms() / 1000.0
if current_time - self.last_sync_broadcast >= 1.0:
    self.sat_network.send_all("SYNC_FRAME", f"{self.frame_counter},{current_time}")
    self.last_sync_broadcast = current_time
```

#### Satellite Side (IndustrialSatelliteFirmware)

```python
# State variables
self.frame_counter = 0
self.last_sync_frame = 0
self.time_offset = 0.0  # Estimated time difference from Core

# In process_local_cmd()
elif cmd == "SYNC_FRAME":
    values = parse_values(val)
    core_frame = get_int(values, 0, 0)
    core_time = get_float(values, 1, 0.0)
    
    # Update sync state
    self.last_sync_frame = core_frame
    # Calculate time offset (positive means satellite is ahead)
    current_time = time.monotonic()
    self.time_offset = current_time - core_time
```

### Using Frame Sync in Animations

To create synchronized animations:

1. **Use frame counters for phase alignment**:
   ```python
   # All devices will be in phase
   phase = (self.frame_counter % 60) / 60.0  # 0-1 over 60 frames (1 second)
   brightness = 0.5 + 0.5 * math.sin(phase * 2 * math.pi)
   ```

2. **Use time offset for precise timing**:
   ```python
   # Adjust animation timing based on sync
   adjusted_time = time.monotonic() - self.time_offset
   ```

3. **Detect sync loss**:
   ```python
   # Check if sync is recent
   frames_since_sync = self.frame_counter - self.last_sync_frame
   if frames_since_sync > 300:  # 5 seconds at 60Hz
       # Fall back to local timing
   ```

## Key Design Decisions

### 60Hz Frame Rate

- **Why 60Hz?**: 
  - Smooth animations (standard video frame rate)
  - Fast enough for responsive UI
  - Low enough CPU overhead for CircuitPython
  - Matches common display refresh rates

### Advisory Sync (Not Blocking)

- Frame sync is **advisory**, not blocking
- Satellites don't wait for sync commands to render
- Prevents cascading delays if communication is slow
- Animations work fine without sync, just not coordinated

### Periodic Broadcast (1 Hz)

- Sync broadcast every 1 second (not every frame)
- Reduces communication overhead
- Sufficient for most animation coordination
- Can be adjusted based on needs

### Backward Compatibility

- Existing LED commands work unchanged
- Sync is transparent to existing code
- Satellites render independently if sync is unavailable

## Performance Characteristics

### CPU Usage

- Render loop: ~1.67ms per frame at 60Hz
- Frame sync: negligible (1 message per second)
- Animation updates: depends on complexity

### Latency

- Render latency: max 16.7ms (one frame)
- Sync latency: ~1 second update interval
- Animation response: immediate (buffer updates)

### Memory

- Minimal overhead: 3 integers per device
- No additional buffers required
- Same memory usage as before

## Testing

Run the test suite to verify the implementation:

```bash
python tests/test_satellite_render_loop.py
python tests/test_watchdog_flag_pattern.py
```

## Future Enhancements

Possible improvements for future versions:

1. **Adaptive Sync Rate**: Adjust broadcast frequency based on network quality
2. **Sync ACK**: Satellites acknowledge sync receipt for monitoring
3. **Sync Groups**: Different sync domains for independent animation groups
4. **Frame Prediction**: Extrapolate timing between sync updates
5. **Quality Metrics**: Track sync accuracy and drift

## References

- `src/core/core_manager.py` - Core render loop and sync broadcast
- `src/satellites/sat_01_firmware.py` - Satellite render loop and sync handler
- `src/protocol.py` - SYNC_FRAME command definition
- `src/managers/base_pixel_manager.py` - Animation logic
- `src/utilities/jeb_pixel.py` - LED buffer wrapper
