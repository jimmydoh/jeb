# Matrix Manager - Arbitrary Configuration Support

## Overview

The `MatrixManager` has been extended to support arbitrary matrix configurations beyond the original 8x8 GlowBit 64 LED matrix. This enables flexible matrix layouts including dual, quad, strip-based, and custom configurations.

## Features

- **Backward Compatible**: Default 8x8 configuration works without changes to existing code
- **Arbitrary Dimensions**: Support for any width × height matrix configuration
- **Serpentine Layout**: Maintains efficient serpentine (zig-zag) pixel addressing
- **Automatic Scaling**: Methods like `show_progress_grid()` and `draw_quadrant()` adapt to matrix size
- **Bounds Checking**: Invalid coordinates are safely ignored

## Usage

### Default 8x8 Matrix (Backward Compatible)

```python
from managers.matrix_manager import MatrixManager

# Original usage - still works
matrix = MatrixManager(jeb_pixel)
# Defaults to width=8, height=8
```

### Custom Matrix Configurations

```python
# Dual 8x8 horizontal (16x8) - two matrices side-by-side
matrix = MatrixManager(jeb_pixel, width=16, height=8)

# Dual 8x8 vertical (8x16) - two matrices stacked
matrix = MatrixManager(jeb_pixel, width=8, height=16)

# Quad 8x8 (16x16) - four matrices in a 2x2 grid
matrix = MatrixManager(jeb_pixel, width=16, height=16)

# LED strips as matrix (8x4) - four 1x8 strips
matrix = MatrixManager(jeb_pixel, width=8, height=4)

# Small custom matrix (4x4)
matrix = MatrixManager(jeb_pixel, width=4, height=4)

# Large custom matrix (32x32)
matrix = MatrixManager(jeb_pixel, width=32, height=32)

# Non-square matrix (12x6)
matrix = MatrixManager(jeb_pixel, width=12, height=6)
```

## Supported Configurations

### Common Configurations

| Configuration | Width | Height | Total Pixels | Description |
|---------------|-------|--------|--------------|-------------|
| Single 8x8 | 8 | 8 | 64 | Original GlowBit 64 |
| Dual Horizontal | 16 | 8 | 128 | Two 8x8 side-by-side |
| Dual Vertical | 8 | 16 | 128 | Two 8x8 stacked |
| Quad | 16 | 16 | 256 | Four 8x8 in 2x2 grid |
| Strip Matrix | 8 | 4 | 32 | Four 1x8 strips |
| Small | 4 | 4 | 16 | Small custom matrix |
| Large | 32 | 32 | 1024 | Large display |

### Physical Layout Examples

#### Dual Horizontal (16x8)
```
┌─────────┬─────────┐
│ Matrix  │ Matrix  │
│   #1    │   #2    │
│  8x8    │  8x8    │
└─────────┴─────────┘
```

#### Quad (16x16)
```
┌─────────┬─────────┐
│ Matrix  │ Matrix  │
│   #1    │   #2    │
│  8x8    │  8x8    │
├─────────┼─────────┤
│ Matrix  │ Matrix  │
│   #3    │   #4    │
│  8x8    │  8x8    │
└─────────┴─────────┘
```

## Serpentine (Zig-Zag) Layout

The MatrixManager uses a serpentine layout where even rows go left-to-right and odd rows go right-to-left. This is optimized for common LED matrix wiring.

### Example: 4x4 Matrix Pixel Indices

```
Physical Layout:
┌──┬──┬──┬──┐
│ 0│ 1│ 2│ 3│  Row 0 (even): left→right
├──┼──┼──┼──┤
│ 7│ 6│ 5│ 4│  Row 1 (odd):  right→left
├──┼──┼──┼──┤
│ 8│ 9│10│11│  Row 2 (even): left→right
├──┼──┼──┼──┤
│15│14│13│12│  Row 3 (odd):  right→left
└──┴──┴──┴──┘
```

This layout minimizes wiring complexity when chaining LED strips together.

## API Methods

All existing MatrixManager methods work with arbitrary configurations:

### Basic Drawing

```python
# Draw a single pixel
matrix.draw_pixel(x, y, color, brightness=1.0)

# Fill entire matrix
matrix.fill(color)

# Clear matrix
matrix.clear()
```

### Adaptive Methods

These methods automatically adapt to the matrix dimensions:

```python
# Show progress (fills from bottom to top, adapting to size)
matrix.show_progress_grid(iterations, total=10, color=(100, 0, 200))

# Draw quadrant (quadrant size = width//2 × height//2)
matrix.draw_quadrant(quad_idx, color)  # 0=TL, 1=TR, 2=BL, 3=BR
```

### Icons

Icons are designed for 8x8 matrices. When used with different sizes:
- **Larger matrices**: Icon displays in top-left corner
- **Smaller matrices**: Icon is clipped to fit

```python
matrix.show_icon("DEFAULT", clear=True, anim_mode=None, color=None)
```

## Implementation Details

### Coordinate Mapping

The `_get_idx(x, y)` method maps 2D coordinates to 1D pixel indices:

```python
def _get_idx(self, x, y):
    """Maps 2D coordinates to Serpentine 1D index."""
    if y % 2 == 0:  # Even rows: left-to-right
        return (y * self.width) + x
    return (y * self.width) + (self.width - 1 - x)  # Odd rows: right-to-left
```

### Bounds Checking

All methods perform automatic bounds checking:

```python
if 0 <= x < self.width and 0 <= y < self.height:
    # Safe to access pixel
```

Invalid coordinates are silently ignored, preventing crashes.

## Testing

Comprehensive tests are available in `tests/test_matrix_arbitrary_configurations.py`:

- Single 8x8 matrix (backward compatibility)
- Dual horizontal/vertical configurations
- Quad configuration
- Strip-based matrices
- Small and large matrices
- Non-square matrices
- Progress grid adaptation
- Brightness scaling
- Bounds checking

Run tests:
```bash
python3 tests/test_matrix_arbitrary_configurations.py
```

## Hardware Considerations

### Pixel Count

Ensure the `jeb_pixel` object has sufficient pixels:
```python
# For 16x16 matrix, need 256 pixels
jeb_pixel = JEBPixel(root_pixels, start_idx=0, num_pixels=256)
matrix = MatrixManager(jeb_pixel, width=16, height=16)
```

### Power Requirements

Larger matrices require more power:
- 8x8 (64 pixels) ≈ 3.8A @ 5V (full white, full brightness)
- 16x16 (256 pixels) ≈ 15.4A @ 5V (full white, full brightness)

Ensure power supply can handle the load. Consider:
- Using lower global brightness
- Limiting simultaneous full-white pixels
- Using power-aware color palettes

### Memory Constraints

RP2350 has 520KB RAM total:
- Base CircuitPython: ~200KB
- Per-pixel animation state: ~48 bytes
- 256 pixels: ~12KB animation state
- 1024 pixels: ~49KB animation state

Large matrices are feasible but monitor available memory.

## Migration Guide

### From Original 8x8 Code

No changes needed! Default parameters maintain backward compatibility:

```python
# Old code - still works
matrix = MatrixManager(jeb_pixel)
matrix.draw_pixel(4, 4, (255, 0, 0))
```

### Adding New Configurations

Simply specify dimensions during initialization:

```python
# New code - 16x8 matrix
matrix = MatrixManager(jeb_pixel, width=16, height=8)
matrix.draw_pixel(10, 4, (255, 0, 0))  # Uses extended width
```

## Future Enhancements

Potential future additions:
- Icon scaling for different matrix sizes
- Animation scaling/tiling
- Multiple layout patterns (linear, spiral, etc.)
- Matrix composition (combining multiple physical matrices)
- Rotation and mirroring transforms

## Examples

### Example 1: Dual Matrix Initialization

```python
from utilities.jeb_pixel import JEBPixel
from managers.matrix_manager import MatrixManager

# Initialize with 128 pixels for dual 8x8 horizontal
root_pixels = neopixel.NeoPixel(board.GP0, 128)
jeb_pixel = JEBPixel(root_pixels, start_idx=0, num_pixels=128)

# Create 16x8 matrix manager
matrix = MatrixManager(jeb_pixel, width=16, height=8)

# Draw across both physical matrices
for x in range(16):
    matrix.draw_pixel(x, 4, (0, 255, 0))  # Green line across center
```

### Example 2: Progress Bar on Different Sizes

```python
# Works on any size - automatically adapts
def show_boot_progress(matrix, step, total=10):
    matrix.show_progress_grid(step, total, color=(0, 100, 255))

# 8x8 matrix: fills 64 pixels
matrix_8x8 = MatrixManager(jeb_pixel_64, width=8, height=8)
show_boot_progress(matrix_8x8, 5)

# 16x16 matrix: fills 256 pixels
matrix_16x16 = MatrixManager(jeb_pixel_256, width=16, height=16)
show_boot_progress(matrix_16x16, 5)
```

### Example 3: Quadrant Display

```python
# Works on any even-sized matrix
matrix = MatrixManager(jeb_pixel, width=16, height=16)

# Show different colors in each quadrant
matrix.draw_quadrant(0, (255, 0, 0))    # Top-left: Red
matrix.draw_quadrant(1, (0, 255, 0))    # Top-right: Green
matrix.draw_quadrant(2, (0, 0, 255))    # Bottom-left: Blue
matrix.draw_quadrant(3, (255, 255, 0))  # Bottom-right: Yellow
```

## Troubleshooting

### Issue: Pixels don't light up

**Check:**
1. Pixel count matches matrix dimensions: `width × height = num_pixels`
2. JEBPixel initialized with correct range
3. Power supply adequate for pixel count

### Issue: Incorrect pixel addressing

**Check:**
1. Matrix physical wiring matches serpentine pattern
2. Width and height parameters correct
3. Using 0-based coordinates (not 1-based)

### Issue: Icons look wrong on non-8x8 matrices

**Expected behavior:**
- Larger matrices: Icon shows in top-left corner
- Smaller matrices: Icon is clipped

**Solution:** Design custom icons for your matrix size, or use scaling logic.

## Related Documentation

- `LED_RENDERING.md` - LED rendering pipeline details
- `OPTIMIZATION_SUMMARY.md` - Performance optimization strategies
- `src/managers/base_pixel_manager.py` - Base class implementation
- `tests/test_matrix_arbitrary_configurations.py` - Comprehensive test suite

## Version History

- **v1.0** (2026-02-18): Initial arbitrary configuration support
  - Added width/height parameters to `__init__()`
  - Updated all methods for dimension-agnostic operation
  - Comprehensive test coverage
  - Backward compatible with existing 8x8 code
