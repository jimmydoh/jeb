"""Manages satellite network discovery, health monitoring, and communication."""

import asyncio
from adafruit_ticks import ticks_ms, ticks_diff

from transport import Message

from utilities.payload_parser import parse_values, get_float

class SatelliteNetworkManager:
    """Manages satellite discovery, health monitoring, and message handling.

    Responsibilities:
    - Satellite discovery via ID assignment
    - Health monitoring and link watchdog
    - Message routing and handling
    - Satellite registry management
    """

    def __init__(self, transport, display, audio):
        """Initialize the satellite network manager.

        Args:
            transport: UARTTransport instance for communication
            display: DisplayManager instance for status updates
            audio: AudioManager instance for audio feedback
        """
        self.transport = transport
        self.display = display
        self.audio = audio

        # Satellite Registry
        self.satellites = {}
        self.sat_telemetry = {}

        # Debug state
        self.last_message_debug = ""
        self._debug_mode = False

        # Task throttling: Single slot for status updates to prevent unbounded task spawning
        self._current_status_task = None
        self._current_audio_task = None

        # System command handlers (can be extended for common commands across satellites)
        self._system_handlers = {
            "STATUS": self._handle_status_command,
            "POWER": self._handle_power_command,
            "ERROR": self._handle_error_command,
            "HELLO": self._handle_hello_command,
            "NEW_SAT": self._handle_new_sat_command,
            "LOG": self._handle_log_command,
        }

    def set_debug_mode(self, debug_mode):
        """Enable or disable debug mode for message logging."""
        self._debug_mode = debug_mode

    def _spawn_status_task(self, coro_func, *args, **kwargs):
        """Spawn a status update task with throttling to prevent unbounded task creation.

        Only creates a new task if no status task is currently running, preventing
        memory issues from task flooding during satellite malfunctions.

        This method accepts a coroutine factory (callable + args) instead of a
        coroutine object to avoid "coroutine was never awaited" warnings when
        throttling skips task creation.

        Thread Safety: This method is called synchronously from the event loop in
        handle_message() (which is invoked by monitor_satellites()). Since asyncio
        is single-threaded, no locking is needed for the task tracking. The method
        itself executes synchronously but schedules asynchronous work via create_task().
        Do not call this method from multiple threads or outside the main event loop context.

        Args:
            coro_func: Coroutine function to execute for status update
            *args: Positional arguments to pass to the coroutine function
            **kwargs: Keyword arguments to pass to the coroutine function
        """
        if self._current_status_task is None or self._current_status_task.done():
            self._current_status_task = asyncio.create_task(coro_func(*args, **kwargs))

    def _spawn_audio_task(self, coro_func, *args, **kwargs):
        """Spawn an audio task with throttling.

        Prevents OOM (Out Of Memory) crashes if a satellite floods the bus with ERROR messages,
        which would otherwise spawn hundreds of 'play_wav' tasks in seconds.
        """
        if self._current_audio_task is None or self._current_audio_task.done():
            self._current_audio_task = asyncio.create_task(coro_func(*args, **kwargs))

    async def discover_satellites(self, sat_type_id="01"):
        """Triggers the ID assignment chain to discover satellites."""
        self.display.update_status("SCANNING BUS...", "ASSIGNING IDs")

        # Broadcast to discovered type, starting at index 00
        message = Message("ALL", "ID_ASSIGN", f"{sat_type_id}00")
        while not self.transport.send(message):
            # If the send fails (e.g., buffer full), wait briefly and retry.
            # This prevents flooding the transport with messages
            await asyncio.sleep(0.5)
        await asyncio.sleep(0.5)

    def get_sat(self, sid):
        """Retrieve a satellite by its ID.

        Args:
            sid: Satellite ID

        Returns:
            Satellite instance or None if not found
        """
        return self.satellites.get(sid)

    def send_all(self, cmd, val):
        """Broadcast a command to all connected satellites.

        Args:
            cmd: Command string (e.g., "LED", "DSP")
            val: Command value/payload
        """
        for sid in self.satellites:
            self.get_sat(sid).send_cmd(cmd, val)

    async def _process_inbound_cmd(self, sid, cmd, val):
        """
        Process a command received from a physical satellite into driver logic.

        Parameters:
            sid (str): Satellite ID the command is from.
            cmd (str): Command type.
            val (str or bytes): Command value.
        """
        handler = self._system_handlers.get(cmd)
        if handler:
            await handler(sid, val)
            return
        else:
            self._spawn_status_task(
                self.display.update_status, "UNKNOWN COMMAND", f"{sid} sent {cmd}"
            )

    async def _handle_status_command(self, sid, val):
        """
        Handle STATUS command from satellite,
        which primarily include HID status updates.
        """
        if sid in self.satellites:
            if not self.satellites[sid].is_active:
                self.satellites[sid].update_heartbeat()

                # TODO: Improve this logic to handle all sat types based on capability
                if self.satellites[sid].sat_type_name == "INDUSTRIAL":
                    self.satellites[sid].send_cmd("DSPANIMCORRECT", "1.5")
            self.satellites[sid].update_from_packet(val)
        else:
            self._spawn_status_task(
                self.display.update_status,
                "UNKNOWN SAT",
                f"{sid} sent STATUS."
            )

    async def _handle_power_command(self, sid, val):
        """
        Handle POWER command from satellite,
        which may indicate power state changes or alerts.
        """
        v_data = parse_values(val)
        self.sat_telemetry[sid] = {
            "in": get_float(v_data, 0),
            "bus": get_float(v_data, 1),
            "log": get_float(v_data, 2),
        }

    async def _handle_hello_command(self, sid, val):
        """
        Handle HELLO command from satellite,
        which indicates a new satellite has come online and is announcing itself.
        """
        if sid in self.satellites:
            self.satellites[sid].update_heartbeat()
        else:
            # Identify type from the first 2 characters of the SID (e.g., "0100" -> "01" type)
            sat_type_id = sid[:2]
            if sat_type_id == "01":
                from satellites.sat_01_driver import IndustrialSatelliteDriver
                self.satellites[sid] = IndustrialSatelliteDriver(
                    sid, self.transport
                )
            self._spawn_status_task(
                self.display.update_status, "NEW SAT", f"{sid} sent HELLO {val}."
            )

    async def _handle_new_sat_command(self, sid, val):
        """
        Handle NEW_SAT command from satellite,
        which may indicate a new satellite has been detected by an existing satellite.
        This is useful for multi-hop satellite networks where not all satellites are directly visible to the core manager.
        """
        self._spawn_status_task(
            self.display.update_status, f"SAT {sid} CONNECTED", f"TYPE {val} FOUND"
        )
        self.discover_satellites(val)

    async def _handle_error_command(self, sid, val):
        """
        Handle ERROR command from satellite,
        which may indicate malfunctions or critical issues.
        """
        self._spawn_status_task(
            self.display.update_status,
            "SAT ERROR",
            f"ID: {sid} ERR: {val}"
        )
        self._spawn_audio_task(
            self.audio.play,
            "alarm_klaxon.wav",
            channel=self.audio.CH_SFX
        )

    async def _handle_log_command(self, sid, val):
        """
        Handle LOG command from satellite,
        which may contain debug or informational messages from the satellite firmware.
        """
        print(f"LOG from {sid}: {val}")
        # TODO: More robust logging system, potentially with log levels and storage

    async def monitor_messages(self, heartbeat_callback=None):
        """
        Background task to process incoming messages.

        This method should be run as an asyncio task. It handles:
        - Monitoring the transport rx queue for inbound messages
        - Processing the message based on command and destination
        """
        # Event Driven message check
        while True:
            if heartbeat_callback:
                heartbeat_callback()

            try:
                message = await asyncio.wait_for(self.transport.receive(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            # Store message representation for debugging
            if self._debug_mode:
                # TODO: Fix this, message is not a string anymore
                self.last_message_debug = str(message)

            # Process the message based on its command and destination
            try:
                sid = message.destination
                cmd = message.command
                payload = message.payload

                await self._process_inbound_cmd(sid, cmd, payload)
            except (ValueError, IndexError) as e:
                print(f"Error handling message: {e}")

    async def monitor_satellites(self, heartbeat_callback=None):
        """
        Background task to monitor satellite health.

        This method should be run as an asyncio task. It handles:
        - Link watchdog to detect disconnected satellites
        """
        while True:
            # Invoke heartbeat callback if provided (e.g., to feed a watchdog timer in the core manager)
            if heartbeat_callback:
                heartbeat_callback()

            # Link Watchdog
            now = ticks_ms()
            for sid, sat in self.satellites.items():
                # If sat is active
                if sat.is_active:
                    if sat.was_offline:
                        # Satellite is online now but was detected as offline
                        self._spawn_status_task(
                            self.display.update_status,
                            "LINK RESTORED",
                            f"ID: {sid}"
                        )
                        self._spawn_audio_task(
                            self.audio.play,
                            "link_restored.wav",
                            channel=self.audio.CH_SFX
                        )
                        sat.was_offline = False

                    if ticks_diff(now, sat.last_seen) > 5000:
                        # Satellite has not been seen for over 5 seconds, mark as offline
                        sat.is_active = False
                        sat.was_offline = True
                        self._spawn_status_task(
                            self.display.update_status,
                            "LINK LOST",
                            f"ID: {sid}"
                        )
                        self._spawn_audio_task(
                            self.audio.play,
                            "link_lost.wav",
                            channel=self.audio.CH_SFX
                        )

            await asyncio.sleep(0.5)
