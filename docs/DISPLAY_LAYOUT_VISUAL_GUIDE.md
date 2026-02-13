# DisplayManager Layout Visual Guide

## Display Hardware Specifications

- **Resolution**: 128x64 pixels
- **Font**: terminalio.FONT (monospace, ~6x8 pixels per character)
- **Visible Area**: ~21 characters wide × ~8 lines tall
- **Controller**: SSD1306 (I2C)

## Layout Mode Comparison

### Legacy Layout (Default - Backward Compatible)

```
┌─────────────────────────────────────┐ y=0
│                                     │
│                                     │
│                                     │
│         (Status Label)              │ y=30
│  "Main status message text here"   │
│                                     │
│         (Sub-Status Label)          │ y=45
│    "Sub-status message text"       │
│                                     │
│     [Viewport Group Area]           │
│   (Mode-specific content can       │
│    be loaded here via load_view)   │
│                                     │
└─────────────────────────────────────┘ y=64

Components:
- status (label at y=30)
- sub_status (label at y=45)  
- viewport (displayio.Group)
```

### Standard Layout (Recommended for New Modes)

```
┌─────────────────────────────────────┐ y=0
│ ┌─ HEADER ZONE (~15px) ───────────┐ │
│ │ MODE: GAME | RAM: 120KB         │ │ y=5 (baseline)
│ └─────────────────────────────────┘ │
├─────────────────────────────────────┤ y=15
│                                     │
│ ┌─ MAIN ZONE (~35px) ─────────────┐ │
│ │                                 │ │
│ │  "Primary status message"       │ │ y=30 (baseline)
│ │  "Secondary status message"     │ │ y=45 (baseline)
│ │                                 │ │
│ └─────────────────────────────────┘ │
├─────────────────────────────────────┤ y=50
│ ┌─ FOOTER ZONE (~14px) ───────────┐ │
│ │ Score saved | Log message       │ │ y=60 (baseline)
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘ y=64

Components:
- header_group containing header_label
- main_group containing status + sub_status
- footer_group containing footer_label

Zone Heights:
- Header: ~15px (y=0 to y=15)
- Main: ~35px (y=15 to y=50)
- Footer: ~14px (y=50 to y=64)
```

### Custom Layout (Advanced - Full Control)

```
┌─────────────────────────────────────┐ y=0
│                                     │
│     ┌────────────────────┐          │
│     │   CUSTOM GAME      │ y=10     │
│     └────────────────────┘          │
│                                     │
│            SCORE: 1500              │ y=28
│                                     │
│       ┌──┐  ┌──┐  ┌──┐  ┌──┐       │
│       │██│  │  │  │██│  │  │       │ y=40
│       └──┘  └──┘  └──┘  └──┘       │
│                                     │
│         Playing... Level 3          │ y=55
│                                     │
└─────────────────────────────────────┘ y=64

Components:
- custom_group (mode provides entire displayio.Group)
- Mode has full control over all UI elements
- Pixel-perfect positioning available
```

## Text Positioning Examples

### Character Grid Reference

```
         1         2
12345678901234567890123  (column positions)
╔═══════════════════════╗
║H: SYS STATS | RAM 120K║ y=5  (Header - 21 chars max)
╠═══════════════════════╣
║                       ║
║                       ║
║Main Status Text Here  ║ y=30 (Main line 1 - 21 chars max)
║Sub-status text here   ║ y=45 (Main line 2 - 21 chars max)
║                       ║
╠═══════════════════════╣
║F: Log message here    ║ y=60 (Footer - 21 chars max)
╚═══════════════════════╝
```

### Y-Position Reference

```
y=0  ─┬─ Display Top
      │
y=5  ─┼─ Header Text Baseline ◄── update_header()
      │
y=15 ─┼─ Header/Main Divider
      │
y=30 ─┼─ Main Text Line 1 ◄── update_status() main_text
      │
y=45 ─┼─ Main Text Line 2 ◄── update_status() sub_text
      │
y=50 ─┼─ Main/Footer Divider
      │
y=60 ─┼─ Footer Text Baseline ◄── update_footer()
      │
y=64 ─┴─ Display Bottom
```

## Usage Patterns

### Pattern 1: Simple Status Updates (All Modes)

```python
# Works in all layout modes
display.update_status("Ready", "Press button")
```

```
┌─────────────────────────┐
│                         │
│      Ready              │ ← main_text
│      Press button       │ ← sub_text
│                         │
└─────────────────────────┘
```

### Pattern 2: Standard Layout with All Zones

```python
display.use_standard_layout()
display.update_header("MODE: GAME | RAM: 120KB")
display.update_status("Level 5", "Score: 1500")
display.update_footer("High score saved!")
```

```
┌─────────────────────────────┐
│ MODE: GAME | RAM: 120KB     │ ← Header
├─────────────────────────────┤
│                             │
│ Level 5                     │ ← Main
│ Score: 1500                 │
│                             │
├─────────────────────────────┤
│ High score saved!           │ ← Footer
└─────────────────────────────┘
```

### Pattern 3: Custom Layout with Graphics

```python
display.use_custom_layout()

custom_group = displayio.Group()
# Add labels, shapes, etc.
display.set_custom_content(custom_group)
```

```
┌─────────────────────────────┐
│    [Custom UI Elements]     │
│                             │
│  Positioned exactly where   │
│  your mode needs them       │
│                             │
│    [Shapes, text, etc.]     │
└─────────────────────────────┘
```

## Common Use Cases

### Use Case 1: Debug/Utility Mode
```
┌─────────────────────────────┐
│ DEBUG MODE                  │ ← Header
├─────────────────────────────┤
│                             │
│ CPU: 45ms/loop              │ ← Main
│ RAM: 120KB free             │
│                             │
├─────────────────────────────┤
│ Diagnostics OK              │ ← Footer
└─────────────────────────────┘
```

### Use Case 2: Game with Stats
```
┌─────────────────────────────┐
│ SIMON SAYS | Lvl: 3         │ ← Header
├─────────────────────────────┤
│                             │
│ Ready!                      │ ← Main
│ Press any button            │
│                             │
├─────────────────────────────┤
│ High Score: 1500            │ ← Footer
└─────────────────────────────┘
```

### Use Case 3: Settings Menu
```
┌─────────────────────────────┐
│ SETTINGS                    │ ← Header
├─────────────────────────────┤
│                             │
│ Brightness: 80%             │ ← Main
│ > Volume: High              │
│   Auto-save: On             │
│                             │
├─────────────────────────────┤
│ Use ▲▼ to navigate         │ ← Footer
└─────────────────────────────┘
```

## Font and Size Reference

### Terminalio Font Characteristics
- **Width**: ~6 pixels per character
- **Height**: ~8 pixels per character
- **Style**: Monospace (all characters same width)
- **Line Spacing**: Typically 12-15 pixels between baselines

### Character Count Guide
```
21 characters max per line
├─────────────────────┤
"FULL WIDTH TEXT LINE"

Typical usage:
├───────────────┤
"Most text here"  (15-17 chars is comfortable)
```

## Best Practices

### Text Length Guidelines
- **Header**: 21 chars max, typically 15-18 for readability
- **Main Line 1**: 21 chars max
- **Main Line 2**: 21 chars max
- **Footer**: 21 chars max, can scroll if needed

### Positioning Tips
1. Always use text baselines (y position) not top coordinates
2. Leave 2-3 pixels margin from edges (x=2, not x=0)
3. Use multiples of font height (~8px) for vertical spacing
4. Test on actual hardware - emulators may differ

### Performance Notes
- Minimize full screen redraws
- Update only changed zones/labels
- Clear text by setting to empty string ""
- Reuse displayio.Group objects when possible

## Migration Cheat Sheet

### From Legacy to Standard Layout

**Before (Legacy):**
```python
display.update_status("Status", "Sub-status")
```

**After (Standard):**
```python
display.use_standard_layout()
display.update_header("MODE NAME")
display.update_status("Status", "Sub-status")
display.update_footer("Log message")
```

### From Custom Viewport to Custom Layout

**Before (Legacy Viewport):**
```python
custom_view = displayio.Group()
# Add elements
display.viewport.append(custom_view)
```

**After (Custom Layout):**
```python
display.use_custom_layout()
custom_view = displayio.Group()
# Add elements
display.set_custom_content(custom_view)
```

## Conclusion

The new layout system provides:
- **Legacy Mode**: No changes needed for existing code
- **Standard Layout**: Consistent, professional three-zone UI
- **Custom Layout**: Full flexibility for specialized needs

Choose the right mode for your use case and enjoy improved display management!
