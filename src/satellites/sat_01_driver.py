"""
Industrial Satellite Driver (Core-side)

Handles telemetry parsing and command serialization for the Industrial Satellite
when running on the Core. This class represents the Core's view of a remote
Industrial Satellite and does not include hardware-specific code.

Expected HID Layout (mirrors IndustrialSatelliteFirmware hardware):
    Latching Toggles  (12 total):
        [0-7]  — 8x Small latching toggles (Expander 1, pins 0-7)
        [8]    — Guarded latching toggle / Master Arm (Expander 2, pin 2)
        [9]    — 2-Position key switch / Secure State (Expander 2, pin 3)
        [10]   — 3-Position rotary switch, Position A (Expander 2, pin 4)
        [11]   — 3-Position rotary switch, Position B (Expander 2, pin 5)
    Momentary Toggles (1 pair):
        [0]    — On-Off-On toggle, UP/DOWN directions (Expander 2, pins 0-1)
    Encoders          (1):
        [0]    — Rotary encoder with integrated push button (GP2/GP3/GP12)
    Buttons           (1):
        [0]    — Large momentary button / Panic or Execute (Expander 2, pin 6)
    Matrix Keypads    (1):
        [0]    — 9-digit 3x3 keypad (rows GP16-18, cols GP19-21)
"""

from managers.hid_manager import HIDManager

from utilities.logger import JEBLogger
from utilities.payload_parser import parse_values, get_int
from utilities.pins import Pins

from .base_driver import SatelliteDriver

TYPE_ID = "01"
TYPE_NAME = "INDUSTRIAL"


class IndustrialSatelliteDriver(SatelliteDriver):
    """Core-side driver for Industrial Satellite.

    Handles telemetry parsing and command serialization.
    Does not load hardware libraries or perform hardware I/O.
    """

    def __init__(self, sid, transport):
        """Initialize the Industrial Satellite Driver.

        Parameters:
            sid (str): Satellite ID assigned by the Core.
            transport: Transport layer for communication.
        """
        super().__init__(sid=sid, sat_type_id=TYPE_ID, sat_type_name=TYPE_NAME, transport=transport)

        # Initialize HIDManager in monitor-only mode (no hardware)

        # Define PLACEHOLDERS for State Sizing
        # Latching toggles: 8 small (Exp1) + 1 guarded arm + 1 key switch + 2 rotary positions (Exp2)
        latching_toggles = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        # Momentary Toggle: 1x On-Off-On toggle (UP / DOWN pair)
        momentary_toggles = [0]

        # Encoders: 1x rotary encoder with integrated push button
        encoders = [0]

        # Buttons: 1x large momentary button (Panic / Execute)
        buttons = [0]

        # Matrix Keypads: 1x 9-digit 3x3 keypad
        matrix_keypads = [(
            Pins.KEYPAD_MAP_3x3,
            [],
            []
        )]

        self.hid = HIDManager(
            latching_toggles=latching_toggles,
            momentary_toggles=momentary_toggles,
            encoders=encoders,
            matrix_keypads=matrix_keypads,
            monitor_only=True
        )

    def update_from_packet(self, val):
        """Updates driver state from a received STATUS payload."""
        try:
            self.update_heartbeat()

            # 1. Safely unwrap the binary optimization (handles tuples, bytes, or strings)
            if isinstance(val, tuple):
                val_str = bytes(val).decode('utf-8')
            elif isinstance(val, (bytes, bytearray)):
                val_str = val.decode('utf-8')
            else:
                val_str = str(val)

            # 2. Split directly to preserve leading zeros! (DO NOT use parse_values)
            data = val_str.strip().split(",")

            # 3. Map to the true default order of HIDManager.get_status_bytes():
            # [buttons, toggles, momentary, keypads, encoders, encoder_btns, estop]
            if len(data) >= 7:
                self.hid.set_remote_state(
                    buttons=data[0],
                    latching_toggles=data[1],
                    momentary_toggles=data[2],
                    matrix_keypads=data[3],
                    encoders=data[4],
                    encoder_buttons=data[5],
                    estop=data[6],
                    sid=self.sid
                )
                #JEBLogger.debug("DRIV", f"Update From Packet | {data}", src=self.sid)
            else:
                JEBLogger.warning("DRIV", f"Sent incomplete status payload: {val_str}", src=self.sid)

        except Exception as e:
            JEBLogger.error("DRIV", f"Malformed packet: {e}", src=self.sid)
