"""Boids – Flocking Simulation (Zero Player Mode).

Implements the classic Boids algorithm by Craig Reynolds (1987).  Every boid
(simulated bird / fish) follows three simple local rules that together produce
realistic emergent flocking behaviour:

  - Separation : Steer to avoid crowding neighbours.
  - Alignment  : Steer towards the average heading of neighbours.
  - Cohesion   : Steer towards the average position of neighbours.

The RP2350's hardware floating-point unit keeps the per-frame vector maths
fast enough for smooth real-time animation even at the highest speed setting.

Controls:
    Encoder turn       : change simulation speed (slow ↔ turbo)
    Button 1 (tap)     : cycle boid colour
    Button 2 (tap)     : scatter / reset the flock
    Encoder long press : return to Zero Player menu
"""

import asyncio
import math
import random

from adafruit_ticks import ticks_ms, ticks_diff

from utilities import tones
from utilities.logger import JEBLogger

from .base import BaseMode

# ---------------------------------------------------------------------------
# Tunable constants
# ---------------------------------------------------------------------------

# Boid colour palette indices (Button 1 cycles through these).
# Mapping: 51=CYAN, 41=GREEN, 71=MAGENTA, 22=GOLD, 21=ORANGE, 4=WHITE
_BOID_COLOR_INDICES = [51, 41, 71, 22, 21, 4]

# Simulation update intervals in milliseconds (encoder selects index).
_SPEED_LEVELS_MS = [200, 100, 50, 25, 10]
_SPEED_NAMES = ["SLOW", "MED", "NORM", "FAST", "TURBO"]

# Number of boids in the flock.
_BOID_COUNT = 20

# Maximum and minimum boid speed (pixels per step).
_MAX_SPEED = 2.0
_MIN_SPEED = 0.3

# Neighbourhood distances used for the three steering rules.
_VISUAL_RANGE = 4.5      # Boids interact with others within this radius.
_SEPARATION_DIST = 2.0   # Steer away if closer than this.

# Rule weights – smaller value = gentler steering influence.
_SEP_WEIGHT = 0.08
_ALI_WEIGHT = 0.05
_COH_WEIGHT = 0.001

# Soft boundary – boids start turning when this many pixels from an edge.
_MARGIN = 2.0
_TURN_FACTOR = 0.3


class BoidsMode(BaseMode):
    """Boids – Flocking Simulation.

    Simulates the emergent flocking behaviour discovered by Craig Reynolds.
    Each boid follows three simple local rules (separation, alignment,
    cohesion) that together produce realistic schooling and murmuration
    patterns on the LED matrix.

    The simulation uses the RP2350's hardware FPU for fast floating-point
    vector math, enabling smooth animation even with many simultaneous agents.

    Controls:
        Encoder turn       : change simulation speed (slow ↔ turbo)
        Button 1 (tap)     : cycle boid colour
        Button 2 (tap)     : scatter / reset the flock
        Encoder long press : return to Zero Player menu
    """

    def __init__(self, core):
        super().__init__(core, "BOIDS", "Flocking Simulation")
        self.width = 0
        self.height = 0
        self._boids = []         # list of [x, y, vx, vy] mutable lists
        self._frame = None       # bytearray: palette-indexed render buffer
        self._color_idx = 0      # index into _BOID_COLOR_INDICES
        self._speed_idx = 2      # default NORM (50 ms)
        self._tick = 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _reset(self):
        """Scatter all boids to random positions with random initial velocities."""
        self._tick = 0
        w, h = self.width, self.height
        self._boids = []
        for _ in range(_BOID_COUNT):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(_MIN_SPEED, _MAX_SPEED)
            self._boids.append([
                random.uniform(1.0, w - 1.0),
                random.uniform(1.0, h - 1.0),
                math.cos(angle) * speed,
                math.sin(angle) * speed,
            ])

    def _step(self):
        """Advance the flock by one simulation step.

        For each boid, accumulate the three steering forces from its
        neighbours and update position/velocity accordingly.
        """
        w = self.width
        h = self.height
        vis_sq = _VISUAL_RANGE * _VISUAL_RANGE
        sep_sq = _SEPARATION_DIST * _SEPARATION_DIST

        for i, boid in enumerate(self._boids):
            bx, by, bvx, bvy = boid[0], boid[1], boid[2], boid[3]

            # Accumulators for the three steering rules.
            sep_x = 0.0
            sep_y = 0.0
            avg_vx = 0.0
            avg_vy = 0.0
            avg_px = 0.0
            avg_py = 0.0
            neighbours = 0
            too_close = 0

            for j, other in enumerate(self._boids):
                if i == j:
                    continue
                dx = other[0] - bx
                dy = other[1] - by
                dist_sq = dx * dx + dy * dy

                if dist_sq < sep_sq:
                    # Separation: accumulate repulsion vector.
                    sep_x -= dx
                    sep_y -= dy
                    too_close += 1

                if dist_sq < vis_sq:
                    avg_vx += other[2]
                    avg_vy += other[3]
                    avg_px += other[0]
                    avg_py += other[1]
                    neighbours += 1

            # Apply separation.
            if too_close:
                bvx += sep_x * _SEP_WEIGHT
                bvy += sep_y * _SEP_WEIGHT

            # Apply alignment and cohesion.
            if neighbours:
                inv = 1.0 / neighbours
                # Alignment: steer towards the average heading.
                bvx += (avg_vx * inv - bvx) * _ALI_WEIGHT
                bvy += (avg_vy * inv - bvy) * _ALI_WEIGHT
                # Cohesion: steer towards the average position.
                bvx += (avg_px * inv - bx) * _COH_WEIGHT
                bvy += (avg_py * inv - by) * _COH_WEIGHT

            # Soft-boundary avoidance (keeps boids inside the matrix).
            if bx < _MARGIN:
                bvx += _TURN_FACTOR
            elif bx > w - 1 - _MARGIN:
                bvx -= _TURN_FACTOR
            if by < _MARGIN:
                bvy += _TURN_FACTOR
            elif by > h - 1 - _MARGIN:
                bvy -= _TURN_FACTOR

            # Enforce speed limits.
            speed_sq = bvx * bvx + bvy * bvy
            if speed_sq > _MAX_SPEED * _MAX_SPEED:
                inv_spd = _MAX_SPEED / math.sqrt(speed_sq)
                bvx *= inv_spd
                bvy *= inv_spd
            elif speed_sq < _MIN_SPEED * _MIN_SPEED:
                if speed_sq > 1e-6:
                    inv_spd = _MIN_SPEED / math.sqrt(speed_sq)
                    bvx *= inv_spd
                    bvy *= inv_spd
                else:
                    # Nearly stopped – give a random nudge.
                    angle = random.uniform(0, 2 * math.pi)
                    bvx = math.cos(angle) * _MIN_SPEED
                    bvy = math.sin(angle) * _MIN_SPEED

            # Update boid state.
            boid[0] = max(0.0, min(w - 0.001, bx + bvx))
            boid[1] = max(0.0, min(h - 0.001, by + bvy))
            boid[2] = bvx
            boid[3] = bvy

        self._tick += 1

    def _build_frame(self):
        """Write boid positions into the palette-indexed frame buffer."""
        color = _BOID_COLOR_INDICES[self._color_idx]
        w = self.width
        # Clear the frame.
        for i in range(len(self._frame)):
            self._frame[i] = 0
        # Draw each boid as a single pixel.
        for boid in self._boids:
            px = int(boid[0])
            py = int(boid[1])
            self._frame[py * w + px] = color

    def _status_line(self):
        """Return a two-line status tuple for the current simulation state."""
        name = _SPEED_NAMES[self._speed_idx]
        ms = _SPEED_LEVELS_MS[self._speed_idx]
        return f"{name} ({ms}ms)", f"BOIDS:{_BOID_COUNT}"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        """Main Boids simulation loop."""
        JEBLogger.info("BOIDS", "[RUN] BoidsMode starting")

        self.width = self.core.matrix.width
        self.height = self.core.matrix.height
        size = self.width * self.height

        self._frame = bytearray(size)
        self._color_idx = 0
        self._speed_idx = 2
        self._tick = 0

        self._reset()

        self.core.display.use_standard_layout()
        self.core.display.update_header("BOIDS")
        line1, line2 = self._status_line()
        self.core.display.update_status(line1, line2)
        self.core.display.update_footer("B1:Color  B2:Reset")

        self.core.hid.flush()
        self.core.hid.reset_encoder(self._speed_idx)
        last_enc = self.core.hid.encoder_position()
        last_step_tick = ticks_ms()

        while True:
            now = ticks_ms()

            # --- Encoder: adjust simulation speed ---
            enc = self.core.hid.encoder_position()
            diff = enc - last_enc
            if diff != 0:
                delta = 1 if diff > 0 else -1
                new_idx = max(0, min(len(_SPEED_LEVELS_MS) - 1, self._speed_idx + delta))
                self._speed_idx = new_idx
                self.core.hid.reset_encoder(self._speed_idx)
                last_enc = self._speed_idx
                line1, line2 = self._status_line()
                self.core.display.update_status(line1, line2)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 1: cycle boid colour ---
            if self.core.hid.is_button_pressed(0, action="tap"):
                self._color_idx = (self._color_idx + 1) % len(_BOID_COLOR_INDICES)
                self.core.buzzer.play_sequence(tones.UI_TICK)

            # --- Button 2: scatter / reset the flock ---
            if self.core.hid.is_button_pressed(1, action="tap"):
                self._reset()
                line1, _ = self._status_line()
                self.core.display.update_status(line1, "SCATTERED!")
                self.core.buzzer.play_sequence(tones.UI_CONFIRM)

            # --- Encoder long press (2 s): exit to Zero Player menu ---
            if self.core.hid.is_encoder_button_pressed(long=True, duration=2000):
                JEBLogger.info("BOIDS", "[EXIT] Returning to Zero Player menu")
                return "SUCCESS"

            # --- Simulation step on interval ---
            interval = _SPEED_LEVELS_MS[self._speed_idx]
            if ticks_diff(now, last_step_tick) >= interval:
                self._step()
                self._build_frame()
                self.core.matrix.show_frame(self._frame)
                last_step_tick = now

            await asyncio.sleep(0.01)
