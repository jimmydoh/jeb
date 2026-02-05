"""
Industrial Satellite Driver (Core-side)

Handles telemetry parsing and command serialization for the Industrial Satellite
when running on the Core. This class represents the Core's view of a remote
Industrial Satellite and does not include hardware-specific code.
"""

from .base import Satellite

TYPE_ID = "01"
TYPE_NAME = "INDUSTRIAL"


class IndustrialSatelliteDriver(Satellite):
    """Core-side driver for Industrial Satellite.
    
    Handles telemetry parsing and command serialization.
    Does not load hardware libraries or perform hardware I/O.
    """
    
    def __init__(self, sid, uart):
        """Initialize the Industrial Satellite Driver.
        
        Parameters:
            sid (str): Satellite ID assigned by the Core.
            uart: UART manager for communication.
        """
        super().__init__(sid=sid, sat_type_id=TYPE_ID, sat_type_name=TYPE_NAME, uart=uart)
        
        # Initialize HIDManager in monitor-only mode (no hardware)
        from managers import HIDManager
        from utilities import Pins
        
        # Define PLACEHOLDERS for State Sizing
        # Toggle Pins
        latching_toggles = [0, 0, 0, 0]
        
        # Momentary Toggle Pins
        momentary_toggles = [0]
        
        # Encoders
        encoders = [0]
        
        # Matrix Keypads
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

    def update_from_packet(self, data_str):
        """Updates the attribute states in the HIDManager based on the received data string.
        
        This method parses telemetry data from the satellite and updates local state.

        Example:
            0000,C,N,0,0
            1111,U,4014*,1,1
        """
        try:
            self.update_heartbeat()
            data = data_str.split(",")

            self.hid.set_remote_state(
                buttons=None,
                latching_toggles=data[0],   # e.g. "0001",
                momentary_toggles=data[1],  # e.g. "U" or "D"
                encoders=data[3],           # e.g. "0", "22", "97"
                encoder_buttons=data[4],    # e.g. "0" or "1"
                matrix_keypads=data[2],     # e.g. "N" or "4014*"
                estop=None
            )

        except (IndexError, ValueError):
            print(f"Malformed packet from Sat {self.id}")
