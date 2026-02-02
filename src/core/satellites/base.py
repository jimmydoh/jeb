""""""

from adafruit_ticks import ticks_ms

class Satellite:
    """Base class for all satellite boxes.
    A class representing a satellite expansion box.

    Attributes:
        id (str): Satellite ID.
        sat_type (str): Satellite type.
        last_seen (int): Timestamp of last heartbeat.
        is_active (bool): Satellite box active status.
    """
    def __init__(self, sid, sat_type, uart):
        """
        Initialize a Satellite object.

        Parameters:
            sid (str): Satellite ID.
            sat_type (str): Satellite type.
        """
        self.id = sid
        self.sat_type = sat_type
        self.uart = uart
        self.last_seen = 0
        self.is_active = True

    def update_heartbeat(self):
        """Update the last seen timestamp."""
        self.last_seen = ticks_ms()
        self.is_active = True

    def send_cmd(self, cmd, val):
        """Send a formatted command to this specific satellite via UART.

         Parameters:
            cmd (str): Command type - LED | DSP.
            val (str): Command value.
        """
        self.uart.write(f"{self.id}|{cmd}|{val}\n".encode())
