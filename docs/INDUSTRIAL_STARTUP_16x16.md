# Industrial Startup Mode — 16×16 Matrix Investigation

## Overview

This document captures the findings, implemented changes, and future recommendations
from investigating the 16×16 LED matrix opportunities in the Industrial Startup game
mode (`src/modes/industrial_startup.py`).

The mode is a multi-phase startup sequence with five steps:

| Step | Name | Matrix Usage (original) |
|------|------|------------------------|
| 0 | Initialization | None |
| 1 | Dual Input | None |
| 2 | Toggle Sequence | ❌ TODO — no animation |
| 3 | Auth Code Entry | ❌ TODO — no animation |
| 4 | Align Brackets | ✅ Active — but hardcoded 8×8 |

---

## Implemented Changes

### Step 2: Toggle Sequence — Progress Animation

**Problem:** Each successful toggle round completed with no matrix feedback.
The code had a `# TODO Add progress animation for matrix` comment.

**Solution:** After each successful toggle confirmation the matrix now renders a
rising-fluid progress bar via `show_progress_grid()`:

```python
self.core.matrix.show_progress_grid(iteration, total_iterations, color=Palette.GREEN)
```

On an 8×8 matrix this fills 6.4 pixels per round (10 rounds × 64 pixels).
On a 16×16 matrix this fills 25.6 pixels per round, giving a much more dramatic
visual sweep across all 256 pixels.

### Step 2: Toggle Sequence — Phase Completion Victory Animation

**Problem:** Completing all 10 toggle rounds had no matrix celebration.
The code had a `# TODO Play Victory Animation` comment.

**Solution:** The `show_icon("SUCCESS")` call that was already used in `victory()`
now also fires at the end of the toggle phase:

```python
self.core.matrix.show_icon("SUCCESS", anim_mode="PULSE", speed=2.0)
```

This is consistent with the icon display patterns used in `game_over()` and `victory()`.

### Step 4: Align Brackets — Dynamic Matrix Dimensions

**Problem:** All coordinates in the bracket alignment puzzle were hardcoded for an
8×8 matrix:

```python
# Before
self.core.hid.reset_encoder(7)
target_pos = random.randint(2, 5)
new_target = max(1, min(6, target_pos + move))
left_pos  = self.sat.get_scaled_encoder_pos(multiplier=1.0, wrap=8)
right_pos = self.core.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=8)
for y in range(2, 6): ...   # target column height
for y in range(1, 7): ...   # bracket column height
```

On a 16×16 matrix the brackets only occupied a narrow 8-pixel-wide band in the
top-left corner and the encoder wrap-around was wrong.

**Solution:** Local variables `w` and `h` are derived from `self.core.matrix` at
runtime, and all positions are computed proportionally:

```python
w = self.core.matrix.width
h = self.core.matrix.height
target_y_start = h // 4          # 8x8 → 2,  16x16 → 4
target_y_end   = h * 3 // 4      # 8x8 → 6,  16x16 → 12
bracket_y_start = h // 8         # 8x8 → 1,  16x16 → 2
bracket_y_end   = h - h // 8     # 8x8 → 7,  16x16 → 14

self.core.hid.reset_encoder(w - 1)
target_pos = random.randint(2, w - 3)
new_target = max(1, min(w - 2, target_pos + move))
left_pos   = self.sat.get_scaled_encoder_pos(multiplier=1.0, wrap=w)
right_pos  = self.core.hid.get_scaled_encoder_pos(multiplier=1.0, wrap=w)
```

**Backward Compatibility:** The proportional relationships are mathematically
identical to the original hardcoded values for an 8×8 matrix, so existing
8×8 hardware is unaffected.

---

## New Opportunities Unlocked by 16×16

### Align Brackets — Richer Puzzle Design

With 16 columns instead of 8 the bracket puzzle gains significant depth:

- **Wider search space:** The target can now appear anywhere in columns 2–13 (12
  positions) instead of 2–5 (4 positions). Players must scan a larger field.
- **More dramatic collision zone:** Brackets meeting in the centre of 16 columns
  feels more natural than on an 8-wide grid.
- **Multi-band targets:** The taller column area (12 pixels high vs 6) opens the
  door to drawing horizontal bands or multiple target indicators.
- **Sub-pixel refinement:** For an advanced difficulty mode, the target could span
  two columns, requiring both brackets to straddle a 2-wide zone.

### Toggle Sequence — Progress Visualization

The `show_progress_grid` fill is far more impactful at 256 pixels: each of the 10
rounds fills a 4×6 block, producing clear visual milestones. Consider colour
ramping from cool (blue/cyan) on early rounds to warm (green/gold) on later rounds
to reinforce urgency.

### Auth Code Entry — Digit Display on Matrix

Step 3 still has a `# TODO Display on matrix as well` comment. On a 16×16 matrix
it becomes practical to render the current digit as a large glyph (up to 8×8 within
the 16×16 space) while the OLED shows the accumulating entry string. Potential
implementation:

```python
# Show current digit as a centered icon during readout
self.core.matrix.show_icon(f"DIGIT_{digit}", anim_mode=None)
```

This would require 10 digit icons (0–9) to be added to `Icons.ICON_LIBRARY`, each
designed as an 8×8 sprite that `show_icon` will auto-centre on the 16×16 canvas.

### Initialization / Dual Input — Boot Splash

Steps 0 and 1 currently have no matrix output. A boot-sequence animation (e.g.,
column-by-column sweep or radial wipe) would complement the audio narration and
make the hardware feel alive before any interaction is required. The `animate_slide_left`
animation in `matrix_animations.py` could display an "IND" identifier label.

---

## Technical Considerations

### Encoder Range

On 16×16 hardware each encoder wraps at `w = 16`. The satellite encoder and the
core HID encoder must both be configured (or verified) to generate enough ticks to
comfortably traverse 16 positions. If the physical encoders have low CPR (counts per
revolution), a `multiplier` adjustment on `get_scaled_encoder_pos()` may be needed.

### Render Loop Performance

Step 4's inner loop re-draws up to three columns every 50 ms. On a 16-pixel-tall
matrix each column draw is now 14 `draw_pixel` calls instead of 6, totalling up to
42 calls per frame instead of 18. This is well within the RP2350's capability but
should be monitored if additional visual elements are added.

### Icon Centering

`show_icon()` auto-centres 8×8 icons on larger matrices. The "SUCCESS" and
"FAILURE" icons used in `victory()`, `game_over()`, and the new Step 2 celebration
will appear correctly centred on a 16×16 canvas without any code changes.

### Power Budget

Switching from 8×8 (64 pixels) to 16×16 (256 pixels) quadruples the pixel count.
Avoid full-white fills and keep animation brightness under 50% to stay within the
system's power budget (see `MATRIX_ARBITRARY_CONFIGURATIONS.md` § Hardware
Considerations).

---

## Summary of Recommendations

| Priority | Recommendation | Effort |
|----------|---------------|--------|
| ✅ Done | Dynamic bounds in Step 4 Align Brackets | Low |
| ✅ Done | Progress animation in Step 2 Toggle Sequence | Low |
| ✅ Done | Victory animation at end of Step 2 | Low |
| Medium | Digit icons (0–9) for Step 3 Auth Code matrix display | Medium |
| Medium | Boot splash animation in Steps 0–1 | Medium |
| Low | Multi-width target bracket for advanced difficulty | High |
| Low | Colour-ramped progress bar in Toggle Sequence | Low |

---

## Related Files

- `src/modes/industrial_startup.py` — mode implementation
- `src/managers/matrix_manager.py` — MatrixManager with dynamic dimensions
- `src/utilities/matrix_animations.py` — animation helpers
- `docs/MATRIX_ARBITRARY_CONFIGURATIONS.md` — 16×16 hardware and API reference
