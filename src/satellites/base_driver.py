"""
Base driver class for all satellite boxes.

A class representing a satellite expansion box
used by the Satellite Network Manager to store
state without hardware init.
"""

import asyncio

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
        self.was_offline = False
        self._retry_tasks = []
        self._retry_task_max = 5

    @property
    def sid(self):
        """Returns the satellite's unique ID."""
        return self.id

    def update_heartbeat(self, increment=None):
        """Update the last seen timestamp."""
        if increment is not None:
            self.last_seen += ticks_ms() + increment
        else:
            self.last_seen = ticks_ms()
        self.is_active = True

    async def _retry_send(self, message, retry_count=5, retry_delay=0.05):
        """Retry sending a message with a delay between attempts.

        Parameters:
            message (Message): The message to send.
            retry_count (int): Maximum number of retry attempts.
            retry_delay (float): Delay in seconds between retries.
        """
        for _ in range(retry_count):
            if self.transport.send(message):
                return True
            await asyncio.sleep(retry_delay)
        return False

    def _cleanup_task(self, task):
        """Callback to remove completed tasks from the retry list."""
        try:
            self._retry_tasks.remove(task)
        except ValueError:
            pass  # Task might have been removed already, which is fine

    def send(self, cmd, val, retry_count=5, retry_delay=0.05):
        """
        Send a formatted command via the transport layer,
        targetting this satellite's real hardware via self.id.

         Parameters:
            cmd (str): Command type - LED | DSP.
            val (str): Command value.
        """
        message = Message("DRIV", self.id, cmd, val)
        if not self.transport.send(message):
            if len(self._retry_tasks) < self._retry_task_max:
                task = asyncio.create_task(
                    self._retry_send(message, retry_count, retry_delay)
                )
                task.add_done_callback(self._cleanup_task)
                self._retry_tasks.append(task)
            else:
                print(f"Warning: Max retry tasks reached for {self.id}. Dropping message: {message}")
