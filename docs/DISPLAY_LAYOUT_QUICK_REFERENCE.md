# Display Layout Quick Reference

## Three Layout Modes

### 1. Legacy (Default - Backward Compatible)
```python
# No changes needed - existing code works as-is
display.update_status("Main text", "Sub text")
display.load_view("dashboard")
```

### 2. Standard Layout (Recommended)
```python
# Enable standard layout
display.use_standard_layout()

# Update zones
display.update_header("MODE: GAME | RAM: 120KB")  # Top zone
display.update_status("Ready", "Press button")    # Middle zone
display.update_footer("Score saved")              # Bottom zone
```

### 3. Custom Layout (Advanced)
```python
# Enable custom layout
display.use_custom_layout()

# Create your UI
import displayio
from adafruit_display_text import label
import terminalio

custom_group = displayio.Group()
my_label = label.Label(terminalio.FONT, text="Custom UI", x=20, y=32)
custom_group.append(my_label)

# Display it
display.set_custom_content(custom_group)
```

## Zone Specifications

| Zone   | Y Position | Height | Purpose                    |
|--------|-----------|--------|----------------------------|
| Header | 5         | ~15px  | System stats, mode name    |
| Main   | 30, 45    | ~35px  | Primary content (2 lines)  |
| Footer | 60        | ~14px  | Logs, messages             |

Display: 128x64 pixels (~21 chars x 8 lines)

## Common Patterns

### Standard Mode Template
```python
async def enter(self):
    self.core.display.use_standard_layout()
    self.core.display.update_header("MODE: YOUR_MODE")
    self.core.display.update_status("Initializing...", "")
    self.core.display.update_footer("Ready")

async def run(self):
    self.core.display.update_status("Running", "Press to exit")
    # Your logic here
    
async def exit(self):
    self.core.display.update_status("", "")
```

### Custom Mode Template
```python
async def enter(self):
    self.core.display.use_custom_layout()
    self.custom_ui = displayio.Group()
    # Build your UI
    self.core.display.set_custom_content(self.custom_ui)

async def run(self):
    # Update your custom UI elements directly
    # No need to call display methods
    
async def exit(self):
    self.core.display.set_custom_content(None)
```

## Decision Guide

**Use Standard Layout if:**
- Mode is utility/menu-based
- You only need text status updates
- You want consistent UI across modes
- You want system stats visible

**Use Custom Layout if:**
- Game with complex graphics
- Pixel-perfect positioning required
- Mode needs full 128x64 canvas
- Specialized visualization

**Use Legacy if:**
- Updating existing mode
- Want minimal changes
- Current behavior is sufficient

## API Reference

### Layout Mode Selection
- `use_standard_layout()` - Switch to three-zone layout
- `use_custom_layout()` - Switch to custom layout

### Standard Layout Updates
- `update_header(text)` - Update header zone
- `update_status(main, sub=None)` - Update main zone
- `update_footer(text)` - Update footer zone

### Custom Layout Content
- `set_custom_content(group)` - Set displayio.Group as content

### Legacy Methods (Still Available)
- `load_view(name)` - Load pre-built view
- `update_game_menu(...)` - Update game settings view
- `update_admin_menu(...)` - Update admin menu view
- `update_debug_stats(...)` - Update debug stats view

## Examples

See:
- `examples/display_standard_layout.py` - Standard layout demo
- `examples/display_custom_layout.py` - Custom layout demo
- `docs/DISPLAY_LAYOUT_SYSTEM.md` - Full documentation
