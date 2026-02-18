# Matrix Manager - Arbitrary Configuration Support

## Overview

The `MatrixManager` has been extended to support arbitrary matrix configurations beyond the original 8x8 GlowBit 64 LED matrix. This enables flexible matrix layouts including dual, quad, strip-based, and custom configurations with proper panel-based addressing for tiled displays.

## Key Concept: Panel-Based Addressing

When multiple physical LED matrices (panels) are chained together, each panel maintains its own sequential pixel range. For example, with four 8×8 panels forming a 16×16 display:

- **Panel 0** (top-left): pixels 0-63
- **Panel 1** (top-right): pixels 64-127
- **Panel 2** (bottom-left): pixels 128-191
- **Panel 3** (bottom-right): pixels 192-255

Within each panel, serpentine (zig-zag) addressing applies where even rows go left-to-right and odd rows go right-to-left.

## Features

- **Backward Compatible**: Default 8×8 configuration works without changes to existing code
- **Panel-Based Addressing**: Correctly handles tiled panel configurations
- **Arbitrary Dimensions**: Support for any width × height matrix configuration
- **Serpentine Layout**: Efficient serpentine (zig-zag) pixel addressing within each panel
- **Automatic Scaling**: Methods like `show_progress_grid()` and `draw_quadrant()` adapt to matrix size
- **Bounds Checking**: Invalid coordinates are safely ignored

## Usage

### Default 8×8 Matrix (Backward Compatible)

```python
from managers.matrix_manager import MatrixManager

# Original usage - still works
matrix = MatrixManager(jeb_pixel)
# Defaults to width=8, height=8, panel_width=8, panel_height=8
```

### Tiled Panel Configurations

For tiled configurations (e.g., multiple 8×8 panels forming a larger display), you **must** specify the panel dimensions:

```python
# Four 8×8 panels forming a 16×16 display
matrix = MatrixManager(jeb_pixel, width=16, height=16, panel_width=8, panel_height=8)

# Two 8×8 panels side-by-side (16×8)
matrix = MatrixManager(jeb_pixel, width=16, height=8, panel_width=8, panel_height=8)

# Two 8×8 panels stacked vertically (8×16)
matrix = MatrixManager(jeb_pixel, width=8, height=16, panel_width=8, panel_height=8)
```

### Single Large Panel or Custom Configurations

For single panels or non-tiled configurations, panel dimensions default to display dimensions:

```python
# Single custom-sized matrix (no tiling)
matrix = MatrixManager(jeb_pixel, width=12, height=6)
# panel_width and panel_height default to 12 and 6

# LED strips as a single matrix (no panel subdivision)
matrix = MatrixManager(jeb_pixel, width=8, height=4)
# Treats the entire 8×4 as one panel
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

## Panel-Based Addressing in Detail

### Four 8×8 Panels as 16×16 Display

When four 8×8 panels are chained together to form a 16×16 display, the pixel indices are **not** a simple 16-wide serpentine. Instead, each panel maintains its own range:

```
Visual Layout (coordinates):
┌─────────────────┬─────────────────┐
│ Panel 0         │ Panel 1         │
│ (0,0) to (7,7)  │ (8,0) to (15,7) │
│ Pixels: 0-63    │ Pixels: 64-127  │
├─────────────────┼─────────────────┤
│ Panel 2         │ Panel 3         │
│ (0,8) to (7,15) │ (8,8) to (15,15)│
│ Pixels: 128-191 │ Pixels: 192-255 │
└─────────────────┴─────────────────┘
```

#### Example Pixel Indices

For a 16×16 display with `panel_width=8, panel_height=8`:

| Coordinate | Panel | Local Coord | Pixel Index | Explanation |
|------------|-------|-------------|-------------|-------------|
| (0, 0) | 0 | (0, 0) | 0 | Top-left of display |
| (7, 0) | 0 | (7, 0) | 7 | Top-right of panel 0 |
| (8, 0) | 1 | (0, 0) | **64** | Top-left of panel 1 (NOT 8!) |
| (15, 0) | 1 | (7, 0) | 71 | Top-right of display |
| (0, 1) | 0 | (0, 1) | 15 | Row 1 of panel 0 (serpentine) |
| (8, 1) | 1 | (0, 1) | 79 | Row 1 of panel 1 (serpentine) |
| (0, 8) | 2 | (0, 0) | **128** | Top-left of panel 2 |
| (15, 15) | 3 | (7, 7) | 248 | Bottom-right of display |

Note how pixel (8, 0) maps to index 64 (start of panel 1), **not** index 8 which would be the case with simple serpentine addressing.

### Serpentine Within Each Panel

Within each 8×8 panel, serpentine addressing applies:

```
Panel 0 (8×8) pixel indices:
┌──┬──┬──┬──┬──┬──┬──┬──┐
│ 0│ 1│ 2│ 3│ 4│ 5│ 6│ 7│  Row 0: left→right
├──┼──┼──┼──┼──┼──┼──┼──┤
│15│14│13│12│11│10│ 9│ 8│  Row 1: right→left
├──┼──┼──┼──┼──┼──┼──┼──┤
│16│17│18│19│20│21│22│23│  Row 2: left→right
├──┼──┼──┼──┼──┼──┼──┼──┤
│31│30│29│28│27│26│25│24│  Row 3: right→left
├──┼──┼──┼──┼──┼──┼──┼──┤
│32│33│34│35│36│37│38│39│  Row 4: left→right
├──┼──┼──┼──┼──┼──┼──┼──┤
│47│46│45│44│43│42│41│40│  Row 5: right→left
├──┼──┼──┼──┼──┼──┼──┼──┤
│48│49│50│51│52│53│54│55│  Row 6: left→right
├──┼──┼──┼──┼──┼──┼──┼──┤
│63│62│61│60│59│58│57│56│  Row 7: right→left
└──┴──┴──┴──┴──┴──┴──┴──┘
```

This same serpentine pattern applies within **every** panel, whether it's panel 0, 1, 2, or 3.

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
