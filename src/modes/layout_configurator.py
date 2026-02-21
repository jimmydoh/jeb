# File: src/modes/layout_configurator.py
"""Layout Configurator Mode for setting satellite spatial offsets."""

import asyncio
import json

from utilities.palette import Palette
from .utility_mode import UtilityMode

# Blue anchor colour for the Core's crosshair
_ANCHOR_COLOR = (0, 0, 200)


def _draw_crosshair(matrix):
    """Draw a static blue crosshair on the Core's local LED matrix.

    The crosshair is centred on the matrix and uses the full width/height,
    giving the user a fixed visual reference ("anchor") when positioning
    connected satellites on the global animation canvas.

    Args:
        matrix: MatrixManager instance.
    """
    cx = matrix.width // 2
    cy = matrix.height // 2

    for x in range(matrix.width):
        matrix.draw_pixel(x, cy, _ANCHOR_COLOR)
        if cy + 1 < matrix.height:
            matrix.draw_pixel(x, cy + 1, _ANCHOR_COLOR)

    for y in range(matrix.height):
        matrix.draw_pixel(cx, y, _ANCHOR_COLOR)
        if cx + 1 < matrix.width:
            matrix.draw_pixel(cx + 1, y, _ANCHOR_COLOR)


def save_satellite_offsets(offsets, config_path="config.json"):
    """Persist satellite spatial offsets to ``config.json``.

    Reads the existing ``config.json`` (if any), updates only the
    ``"satellites"`` key with the provided *offsets* dict, and writes the
    file back.  Silently swallows :exc:`OSError` so a read-only filesystem
    (e.g. USB-connected CircuitPython device) does not crash the caller.

    Args:
        offsets (dict): Mapping of satellite ID to
            ``{"offset_x": int, "offset_y": int}``.
        config_path (str): Path to the config file (default ``"config.json"``).

    Returns:
        bool: ``True`` if the file was written successfully, ``False`` otherwise.
    """
    try:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
        except (OSError, ValueError):
            config = {}

        config["satellites"] = offsets

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f)

        return True
    except OSError:
        return False


class LayoutConfigurator(UtilityMode):
    """On-device calibration menu for setting satellite spatial offsets.

    Allows the operator to visually dial in the ``(X, Y)`` position of each
    connected satellite on the global animation canvas using the rotary
    encoder, with live visual feedback.

    Controls
    --------
    * **Encoder rotate** – adjust the active axis value (X or Y).
    * **Encoder tap**    – toggle between adjusting X and Y.
    * **Button D tap**   – cycle to the next connected satellite.
    * **Encoder long press (2 s)** – save offsets to ``config.json`` and exit.
    * **Button B long press (2 s)** – exit without saving.
    """

    METADATA = {
        "id": "LAYOUT_CONFIGURATOR",
        "name": "LAYOUT CONFIG",
        "module_path": "modes.layout_configurator",
        "class_name": "LayoutConfigurator",
        "icon": "ADMIN",
        "requires": ["CORE"],
        "settings": [],
    }

    def __init__(self, core):
        super().__init__(core, name="LAYOUT CONFIG", description="Set satellite positions", timeout=None)

    async def run(self):
        """Run the Layout Configurator."""
        # --- Gather connected satellites ---
        sat_ids = [sid for sid, sat in self.core.satellites.items() if sat.is_active]

        if not sat_ids:
            self.core.display.use_standard_layout()
            self.core.display.update_header("LAYOUT CONFIG")
            self.core.display.update_status("NO SATELLITES", "CONNECT A SAT FIRST")
            self.core.display.update_footer("Hold 'W' to exit")
            await asyncio.sleep(3)
            self.core.mode = "DASHBOARD"
            return "NO_SATS"

        # --- Show anchor crosshair on Core matrix ---
        self.core.matrix.clear()
        _draw_crosshair(self.core.matrix)

        # --- Initial state ---
        sat_idx = 0
        axis = "X"   # "X" or "Y"

        # Load current offsets from the network manager
        offsets = {}
        for sid in sat_ids:
            stored = self.core.sat_network.satellite_offsets.get(sid, {})
            offsets[sid] = {
                "offset_x": int(stored.get("offset_x", 0)),
                "offset_y": int(stored.get("offset_y", 0)),
            }

        def _current_sat():
            return sat_ids[sat_idx]

        def _highlight_satellite(sid):
            """Command the target satellite to show solid red."""
            if sid in self.core.satellites:
                self.core.satellites[sid].send("LED", [255, 0, 0, 200])

        def _unhighlight_satellite(sid):
            """Return the satellite to a neutral idle state."""
            if sid in self.core.satellites:
                self.core.satellites[sid].send("LED", [0, 0, 0, 0])

        def _render():
            """Update the Core's OLED display."""
            sid = _current_sat()
            ox = offsets[sid]["offset_x"]
            oy = offsets[sid]["offset_y"]
            axis_indicator = f"[X={ox}]  Y={oy}" if axis == "X" else f"X={ox}  [Y={oy}]"
            self.core.display.use_standard_layout()
            self.core.display.update_header("LAYOUT CONFIG")
            self.core.display.update_status(f"SAT {sid}", axis_indicator)
            self.core.display.update_footer("Tap=axis  Hold=save")

        # Highlight the first satellite and render initial UI
        _highlight_satellite(_current_sat())
        _render()

        self.core.hid.flush()
        self.core.hid.reset_encoder(0)
        last_pos = 0

        while True:
            curr_pos = self.core.hid.encoder_position()
            encoder_diff = curr_pos - last_pos
            encoder_tap = self.core.hid.is_encoder_button_pressed(action="tap")
            encoder_long = self.core.hid.is_encoder_button_pressed(action="hold", duration=2000)
            btn_d_tap = self.core.hid.is_button_pressed(3, action="tap")
            btn_b_long = self.core.hid.is_button_pressed(1, long=True, duration=2000)

            needs_render = False

            # --- ENCODER ROTATION: adjust active axis ---
            if encoder_diff != 0:
                self.touch()
                sid = _current_sat()
                if axis == "X":
                    offsets[sid]["offset_x"] += encoder_diff
                else:
                    offsets[sid]["offset_y"] += encoder_diff
                # Send live SETOFF so the satellite repositions in real-time
                self.core.sat_network.set_satellite_offset(
                    sid,
                    offsets[sid]["offset_x"],
                    offsets[sid]["offset_y"],
                )
                needs_render = True

            # --- ENCODER TAP: toggle axis ---
            if encoder_tap:
                self.touch()
                axis = "Y" if axis == "X" else "X"
                needs_render = True
                await self.core.audio.play("audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.6)

            # --- BUTTON D TAP: cycle to next satellite ---
            if btn_d_tap:
                self.touch()
                _unhighlight_satellite(_current_sat())
                sat_idx = (sat_idx + 1) % len(sat_ids)
                _highlight_satellite(_current_sat())
                needs_render = True
                await self.core.audio.play("audio/menu/tick.wav", self.core.audio.CH_SFX, level=0.6)

            # --- ENCODER LONG PRESS: save and exit ---
            if encoder_long:
                # Save merged offsets back to config.json
                saved = save_satellite_offsets(offsets)
                _unhighlight_satellite(_current_sat())
                self.core.matrix.clear()
                self.core.display.use_standard_layout()
                self.core.display.update_header("LAYOUT CONFIG")
                if saved:
                    self.core.display.update_status("SAVED", "Offsets written to config")
                else:
                    self.core.display.update_status("SAVE FAILED", "Filesystem read-only?")
                self.core.display.update_footer("")
                await self.core.audio.play("audio/menu/select.wav", self.core.audio.CH_SFX, level=0.8)
                await asyncio.sleep(2)
                self.core.mode = "DASHBOARD"
                return "SAVED" if saved else "SAVE_FAILED"

            # --- BUTTON B LONG PRESS: exit without saving ---
            if btn_b_long:
                _unhighlight_satellite(_current_sat())
                self.core.matrix.clear()
                self.core.mode = "DASHBOARD"
                await self.core.audio.play("audio/menu/close.wav", self.core.audio.CH_SFX, level=0.8)
                return "CANCELLED"

            if needs_render:
                _render()

            last_pos = curr_pos
            await asyncio.sleep(0.02)
