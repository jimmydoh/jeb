"""
Base driver class for all satellite boxes.

A class representing a satellite expansion box
used by the Satellite Network Manager to store
state without hardware init.
"""

from adafruit_ticks import ticks_ms

from transport import Message

class SatelliteDriver:
    """
    Base driver class for all satellite boxes.
    A class representing a satellite expansion box
    used by the Satellite Network Manager to store
    state without hardware init.
    """
    def __init__(self, sid, sat_type_id, sat_type_name, transport):
        """
        Initialize a Satellite Driver object.

        Parameters:
            sid (str): Satellite ID.
            sat_type_id (str): Satellite type ID.
            sat_type_name (str): Satellite type name.
            transport (Transport): Transport mechanism for communication.
        """
        self.id = sid
        self.sat_type_id = sat_type_id
        self.sat_type_name = sat_type_name
        self.transport = transport
        # State Variables
        self.last_tx = 0
        self.last_seen = 0
        self.is_active = True


    def update_heartbeat(self):
        """Update the last seen timestamp."""
        self.last_seen = ticks_ms()
        self.is_active = True

    def send_cmd(self, cmd, val):
        """Send a formatted command from this satellite to the core.

         Parameters:
            cmd (str): Command type - LED | DSP.
            val (str): Command value.
        """
        message = Message(self.id, cmd, val)
        self.transport.send(message)
