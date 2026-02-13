# Display Layout System

## Overview

The DisplayManager now supports flexible layout modes to accommodate both standardized UI patterns and custom display requirements. This document describes the new layout system and how to use it in your modes.

## Display Hardware

- **Controller**: SSD1306 (I2C, default address 0x3C)
- **Resolution**: 128x64 pixels
- **Font**: terminalio.FONT (built-in monospace)
- **Character dimensions**: ~6x8 pixels per character
- **Visible area**: ~21 chars wide, ~8 lines tall

## Layout Modes

### 1. Legacy Layout (Default)

For backward compatibility, the display manager initializes in legacy mode, which maintains the original behavior:
- Two persistent status labels (status, sub_status) at fixed positions
- A viewport group for mode-specific content
- Pre-built mode groups (dashboard, game_info, admin_menu, debug_menu)

**No changes required for existing modes** - they will continue to work as before.

### 2. Standard Layout (Recommended for New Modes)

The standard layout provides a consistent three-zone design:

```
┌────────────────────────────────┐ y=0
│  HEADER ZONE (~15px height)    │
│  System stats, mode indicators │ y=5 (text baseline)
├────────────────────────────────┤ y=15
│                                 │
│  MAIN/CENTRAL ZONE (~35px)     │
│  Mode content, status messages │ y=30, y=45 (text baselines)
│                                 │
├────────────────────────────────┤ y=50
│  FOOTER ZONE (~14px height)    │
│  Logs, console messages        │ y=60 (text baseline)
└────────────────────────────────┘ y=64
```

#### Usage Example

```python
async def enter(self):
    """Mode entry with standard layout."""
    # Switch to standard layout
    self.core.display.use_standard_layout()
    
    # Set header content
    self.core.display.update_header("MODE: SIMON")
    
    # Set main content
    self.core.display.update_status("Ready", "Press button to start")
    
    # Set footer (optional)
    self.core.display.update_footer("High Score: 1500")

async def run(self):
    """Update content during gameplay."""
    # Update main zone
    self.core.display.update_status(f"Level {self.level}", f"Score: {self.score}")
    
    # Update header with stats
    ram_free = gc.mem_free() / 1024
    self.core.display.update_header(f"RAM: {ram_free:.0f}KB")
    
    # Update footer with messages
    self.core.display.update_footer("Great job!")
```

#### Methods

- **`use_standard_layout()`**: Switch to standard three-zone layout
- **`update_header(text)`**: Update header zone text
- **`update_status(main_text, sub_text=None)`**: Update main zone (works in all modes)
- **`update_footer(text)`**: Update footer zone text

### 3. Custom Layout (For Specialized Modes)

When a mode needs full control over the display (e.g., games with bespoke UI), use custom layout:

```python
async def enter(self):
    """Mode entry with custom layout."""
    import displayio
    from adafruit_display_text import label
    import terminalio
    
    # Switch to custom mode
    self.core.display.use_custom_layout()
    
    # Build custom UI
    custom_group = displayio.Group()
    
    # Add custom elements
    title = label.Label(terminalio.FONT, text="CUSTOM GAME", x=20, y=10)
    custom_group.append(title)
    
    score_label = label.Label(terminalio.FONT, text="SCORE: 0", x=30, y=30)
    custom_group.append(score_label)
    
    # Set the custom content
    self.core.display.set_custom_content(custom_group)
```

#### Methods

- **`use_custom_layout()`**: Switch to custom layout mode
- **`set_custom_content(content_group)`**: Set a displayio.Group as the display content

**Note**: In custom mode, you're responsible for all display management. The standard header/main/footer methods won't affect the display.

## Switching Between Modes

You can switch layout modes at any time during a mode's lifecycle:

```python
async def enter(self):
    # Start with standard layout
    self.core.display.use_standard_layout()
    self.core.display.update_status("Loading...")

async def run(self):
    # Switch to custom for gameplay
    self.core.display.use_custom_layout()
    # ... custom UI ...
    
async def exit(self):
    # Return to standard for cleanup messages
    self.core.display.use_standard_layout()
    self.core.display.update_status("Exiting...")
```

## Layout Guidelines

### When to Use Standard Layout

Use standard layout for:
- Most utility modes (debug, settings, admin)
- Games that only need status text
- Modes that benefit from consistent UI
- Quick prototypes and simple modes

**Benefits**:
- Consistent look and feel across modes
- Automatic system stats in header
- Log/message area in footer
- Less code to maintain

### When to Use Custom Layout

Use custom layout for:
- Games with complex graphics or animations
- Modes requiring pixel-perfect positioning
- Visualizations or special effects
- Modes that need the full 128x64 canvas

**Considerations**:
- More code to write and maintain
- Responsibility for all display updates
- May feel different from other modes
- Test thoroughly on actual hardware

## Best Practices

1. **Initialize Early**: Call layout mode methods in your mode's `enter()` function
2. **Be Consistent**: Stick to one layout mode per mode unless there's a good reason to switch
3. **Clean Text**: Keep header/footer text concise (max ~21 characters)
4. **Clear on Exit**: The mode framework handles cleanup, but you can optionally clear messages
5. **Test Text Length**: Verify your text fits within the visible area
6. **Update Efficiently**: Only update zones when content actually changes

## Zone Specifications

### Header Zone
- **Y position**: 5 (text baseline)
- **Height**: ~15 pixels
- **Typical content**: Mode name, system stats, indicators
- **Max chars**: ~21

### Main Zone
- **Y positions**: 30, 45 (two text baselines)
- **Height**: ~35 pixels
- **Typical content**: Status messages, user prompts, game state
- **Max chars per line**: ~21
- **Lines**: 2 (status and sub_status)

### Footer Zone
- **Y position**: 60 (text baseline)
- **Height**: ~14 pixels
- **Typical content**: Logs, console messages, hints
- **Max chars**: ~21

## Migration Guide

### Existing Modes (No Action Required)

Existing modes using `update_status()` and `load_view()` will continue to work without modification. The display manager starts in legacy mode for backward compatibility.

### Updating to Standard Layout

If you want to adopt the new standard layout:

1. Add `use_standard_layout()` in your mode's `enter()` method
2. Replace custom viewport management with `update_header()`, `update_status()`, and `update_footer()`
3. Remove any manual displayio.Group creation if you're now using standard layout
4. Test thoroughly

Example migration:

```python
# Before (legacy)
async def enter(self):
    self.core.display.load_view("dashboard")
    self.core.display.update_status("Ready")

# After (standard layout)
async def enter(self):
    self.core.display.use_standard_layout()
    self.core.display.update_header("MODE: DASHBOARD")
    self.core.display.update_status("Ready")
```

## Implementation Details

The DisplayManager maintains three distinct layer systems:

1. **Legacy Layer**: status labels + viewport (for backward compatibility)
2. **Standard Layer**: header_group + main_group + footer_group
3. **Custom Layer**: custom_group (full user control)

Only one layer system is active at a time, determined by the `_layout_mode` state:
- `"legacy"`: Original behavior (default on startup)
- `"standard"`: Three-zone layout
- `"custom"`: User-controlled layout

Switching between modes clears the root group and rebuilds it with the appropriate layer structure.

## Examples

See the `examples/` directory for complete examples:
- `examples/display_standard_layout.py` - Standard layout demonstration
- `examples/display_custom_layout.py` - Custom layout demonstration
- `examples/display_mode_switching.py` - Switching between layout modes

## Future Enhancements

Potential future additions to the layout system:
- Configurable zone heights
- Multi-line footer with scrolling
- Header/footer templates
- Layout themes
- Zone visibility toggling
- Automatic stats collection for header

## Support

For questions or issues with the display layout system:
1. Check this documentation
2. Review example code
3. File an issue on the repository with display manager logs
