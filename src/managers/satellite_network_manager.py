"""Manages satellite network discovery, health monitoring, and communication."""

import asyncio
from adafruit_ticks import ticks_ms, ticks_diff

from transport import Message

from transport.protocol import (
    CMD_ACK,
    CMD_MODE,
    CMD_SET_OFFSET,
    CMD_VERSION_CHECK,
    CMD_UPDATE_START,
    CMD_UPDATE_WAIT,
)

from utilities.logger import JEBLogger
from utilities.payload_parser import parse_values

class SatelliteNetworkManager:
    """Manages satellite discovery, health monitoring, and message handling.

    Responsibilities:
    - Satellite discovery via ID assignment
    - Health monitoring and link watchdog
    - Message routing and handling
    - Satellite registry management
    """

    def __init__(self, transport, display, audio, abort_event, config=None):
        """Initialize the satellite network manager.

        Args:
            transport: UARTTransport instance for communication
            display: DisplayManager instance for status updates
            audio: AudioManager instance for audio feedback
            abort_event: Event to signal abort conditions
            config: Optional configuration dict. May contain a
                ``"satellite_offsets"`` key mapping satellite IDs to
                ``{"offset_x": int, "offset_y": int}`` dicts used to
                transmit the ``SETOFF`` command upon satellite connection.
        """
        self.transport = transport
        self.display = display
        self.audio = audio
        self.abort_event = abort_event

        # Satellite spatial offsets for the global animation canvas.
        # Keys are satellite IDs (e.g. "0101"), values are {"offset_x", "offset_y"}.
        # Config key "satellites" is canonical; "satellite_offsets" is accepted for
        # backwards compatibility with existing config files.
        _cfg = config or {}
        self._satellite_offsets = _cfg.get("satellites", _cfg.get("satellite_offsets", {}))

        # Satellite Registry
        self.satellites = {}
        self.sat_telemetry = {}

        # Firmware update state: only one satellite is updated at a time
        self._update_in_progress = None

        # Debug state
        self.last_message_debug = ""
        self._debug_mode = False

        # Task throttling: Single slot for status updates to prevent unbounded task spawning
        self._current_status_task = None
        self._current_audio_task = None

        # Callback invoked when a satellite sends CMD_MODE ACTIVE (remote wake)
        self._wake_callback = None

        # System command handlers (can be extended for common commands across satellites)
        self._system_handlers = {
            "STATUS": self._handle_status_command,
            "POWER": self._handle_power_command,
            "ERROR": self._handle_error_command,
            "HELLO": self._handle_hello_command,
            "NEW_SAT": self._handle_new_sat_command,
            "LOG": self._handle_log_command,
            "PING": self._handle_ping_command,
            CMD_MODE: self._handle_mode_command,
            CMD_VERSION_CHECK: self._handle_version_check_command,
        }

    def set_debug_mode(self, debug_mode):
        """Enable or disable debug mode for message logging."""
        self._debug_mode = debug_mode

    @property
    def satellite_offsets(self):
        """Return the current satellite offset mapping.

        Returns:
            dict: Mapping of satellite ID -> {"offset_x": int, "offset_y": int}.
        """
        return self._satellite_offsets

    def set_satellite_offset(self, sid, offset_x, offset_y):
        """Update the in-memory spatial offset for a satellite.

        This does **not** persist the change to ``config.json``; call
        :func:`~modes.layout_configurator.save_satellite_offsets` from the
        Layout Configurator mode to persist.  Immediately sends a ``SETOFF``
        command to the satellite so it can reposition itself on the global
        canvas in real-time.

        Args:
            sid (str): Satellite ID (e.g. ``"0101"``).
            offset_x (int): New X offset on the global animation canvas.
            offset_y (int): New Y offset on the global animation canvas.
        """
        self._satellite_offsets[sid] = {"offset_x": offset_x, "offset_y": offset_y}
        if sid in self.satellites:
            self.transport.send(
                Message("CORE", sid, CMD_SET_OFFSET, [offset_x, offset_y])
            )
            JEBLogger.info(
                "NETM",
                f"Live SETOFF ({offset_x},{offset_y}) to {sid}."
            )

    def set_wake_callback(self, callback):
        """Register a coroutine callback to invoke when a satellite triggers a remote wake.

        Args:
            callback: An async callable (coroutine function) to call on remote wake.
        """
        self._wake_callback = callback

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
        message = Message("CORE", "ALL", "ID_ASSIGN", f"{sat_type_id}00")
        JEBLogger.debug("NETM", f"Triggering Sat Discovery with {sat_type_id}00")
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
            self.get_sat(sid).send(cmd, val)

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
            self.display.update_status("UNKNOWN COMMAND", f"{sid} sent {cmd}")
            JEBLogger.warning("NETM", f"Unknown command '{cmd}' | DATA:{val}", src=sid)

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
                    self.satellites[sid].send("DSPMATRIX", "2")
            self.satellites[sid].update_from_packet(val)
        else:
            self.display.update_status("UNKNOWN SAT", f"{sid} sent STATUS.")
            JEBLogger.warning("NETM", f"STATUS from unknown sat {sid} | DATA: {val}")

    async def _handle_power_command(self, sid, val):
        """
        Handle POWER command from satellite,
        which may indicate power state changes or alerts.
        """
        data = parse_values(val)
        # TODO: Do something with this
        i = 0
        formatted_data = ", ".join(f"{v:5.2f}" for v in data)
        #JEBLogger.debug("NETM", f"POWER update | DATA: {formatted_data}", src=sid)

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
                self.satellites[sid].update_heartbeat(increment=2000)

            self.display.update_status("NEW SAT", f"{sid} sent HELLO {val}.")
            JEBLogger.info("NETM", f"New sat {sid} TYPE-{val} via HELLO.")

            # Send spatial offset if configured so the satellite can register
            # its LEDs on the correct position of the global animation canvas.
            offset = self._satellite_offsets.get(sid)
            if offset is not None:
                offset_x = int(offset.get("offset_x", 0))
                offset_y = int(offset.get("offset_y", 0))
                self.transport.send(
                    Message("CORE", sid, CMD_SET_OFFSET, [offset_x, offset_y])
                )
                JEBLogger.info(
                    "NETM",
                    f"Sent SETOFF ({offset_x},{offset_y}) to {sid}."
                )

    async def _handle_new_sat_command(self, sid, val):
        """
        Handle NEW_SAT command from satellite,
        which may indicate a new satellite has been detected by an existing satellite.
        This is useful for multi-hop satellite networks where not all satellites are directly visible to the core manager.
        """
        self.display.update_status(f"SAT {sid} CONNECTED", f"TYPE {val} FOUND")
        JEBLogger.info("NETM", f"New sat {sid} TYPE-{val} via NEW_SAT.")
        await self.discover_satellites(val)

    async def _handle_error_command(self, sid, val):
        """
        Handle ERROR command from satellite,
        which may indicate malfunctions or critical issues.
        """
        self.display.update_status(f"SAT ERROR", f"ID: {sid} ERR: {val}")
        JEBLogger.error("NETM", f"Sat Error | DATA: {val}", src=sid)
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
        JEBLogger.info("NETM", f"LOG from {sid}: {val}", src=sid)
        # TODO: More robust logging system, potentially with log levels and storage

    async def _handle_ping_command(self, sid, val):
        """
        Handle PING command from satellite,
        which may be used as a keepalive signal.
        """
        if sid in self.satellites:
            self.satellites[sid].update_heartbeat()
            #JEBLogger.info("NETM", f"PING", src=sid)
        else:
            JEBLogger.warning("NETM", f"PING from unknown sat", src=sid)

    async def _handle_mode_command(self, sid, val):
        """Handle CMD_MODE from a satellite.

        When a satellite sends ACTIVE (remote wake trigger), wake the Core
        and echo the ACTIVE broadcast to all other satellites.
        """
        mode_str = val.strip() if isinstance(val, str) else str(val).strip()
        JEBLogger.info("NETM", f"MODE '{mode_str}' from sat", src=sid)
        if mode_str == "ACTIVE" and self._wake_callback:
            await self._wake_callback()
            # Echo ACTIVE to all satellites so they also wake up
            self.send_all(CMD_MODE, "ACTIVE")

    async def _handle_version_check_command(self, sid, val):
        """Handle VERSION_CHECK from a satellite.

        Compares the satellite's reported firmware version against the version
        in the satellite manifest stored on the Core's SD card.  Sends an
        ACK if the versions match (or no manifest is available), or sends
        UPDATE_START followed by all firmware files when an update is needed.

        Only one satellite is updated at a time.  If an update is already in
        progress for a different satellite, UPDATE_WAIT is sent so the
        requesting satellite can retry later.

        Parameters:
            sid (str): Satellite ID (e.g. ``"0101"``).
            val: VERSION_CHECK payload — the satellite's firmware version string.
        """
        if isinstance(val, bytes):
            sat_version = val.decode('utf-8').strip()
        elif isinstance(val, str):
            sat_version = val.strip()
        else:
            sat_version = "0.0.0"

        sat_type_id = sid[:2]
        JEBLogger.info("NETM", f"VERSION_CHECK: sat={sat_version}", src=sid)

        # Only one satellite update at a time
        if self._update_in_progress and self._update_in_progress != sid:
            JEBLogger.info(
                "NETM",
                f"Update in progress for {self._update_in_progress}, sending UPDATE_WAIT to {sid}"
            )
            self.transport.send(Message("CORE", sid, CMD_UPDATE_WAIT, ""))
            return

        expected_version = self._get_satellite_expected_version(sat_type_id)

        if expected_version is None or sat_version == expected_version:
            # No manifest available or versions already match — proceed normally
            JEBLogger.info("NETM", f"Version OK ({sat_version}), allowing {sid} to proceed")
            self.transport.send(Message("CORE", sid, CMD_ACK, ""))
        else:
            # Version mismatch — initiate update
            JEBLogger.info(
                "NETM",
                f"Version mismatch: sat={sat_version}, expected={expected_version}. "
                f"Starting update for {sid}"
            )
            self._update_in_progress = sid
            asyncio.create_task(self._initiate_satellite_update(sid, sat_type_id))

    def _get_satellite_expected_version(self, sat_type_id):
        """Return the expected firmware version for a satellite type.

        Reads ``/sd/satellites/<type_id>/manifest.json`` from the Core's SD
        card.  Returns ``None`` when the manifest is absent or unreadable,
        which causes the Core to accept the satellite's current version.

        Parameters:
            sat_type_id (str): Two-character type identifier (e.g. ``"01"``).

        Returns:
            str | None: Version string from the manifest, or ``None``.
        """
        manifest_path = f"/sd/satellites/{sat_type_id}/manifest.json"
        try:
            import json
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            return manifest.get('version')
        except (OSError, ValueError):
            return None

    async def _initiate_satellite_update(self, sid, sat_type_id):
        """Stream firmware files to a satellite that needs an update.

        Sends UPDATE_START with the file count and total byte size, then
        transfers the satellite manifest (``manifest.json``) followed by every
        file listed in that manifest using the existing chunked file-transfer
        protocol.

        Files are sourced from ``/sd/satellites/<type_id>/``.  The target path
        on the satellite (taken from the manifest ``"path"`` field) is used as
        the ``remote_filename`` in each FILE_START message so the satellite can
        stage files under the correct sub-directory inside ``/update/``.

        Parameters:
            sid (str): Satellite ID to update.
            sat_type_id (str): Two-character type identifier (e.g. ``"01"``).
        """
        base_path = f"/sd/satellites/{sat_type_id}"
        manifest_path = f"{base_path}/manifest.json"

        try:
            try:
                import json
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
            except (OSError, ValueError):
                JEBLogger.warning("NETM", f"No satellite manifest at {manifest_path}, skipping update for {sid}")
                self.transport.send(Message("CORE", sid, CMD_ACK, ""))
                return

            files = manifest.get("files", [])
            # +1 for manifest.json itself
            file_count = len(files) + 1
            total_bytes = sum(f.get("size", 0) for f in files)

            self.transport.send(Message("CORE", sid, CMD_UPDATE_START, f"{file_count},{total_bytes}"))

            from transport.file_transfer import FileTransferSender
            sender = FileTransferSender(self.transport, "CORE")

            # Send manifest.json first so the satellite can parse it when applying
            success = await sender.send_file(sid, manifest_path, remote_filename="manifest.json")
            if not success:
                JEBLogger.error("NETM", f"Failed to send manifest to {sid}")
                return

            # Send each firmware file with its full target path as the remote filename
            for file_entry in files:
                filepath = f"{base_path}/{file_entry['path']}"
                remote_filename = file_entry['path']
                success = await sender.send_file(sid, filepath, remote_filename=remote_filename)
                if not success:
                    JEBLogger.error("NETM", f"Failed to send {filepath} to {sid}")
                    return

            JEBLogger.info("NETM", f"Firmware update files sent to {sid}")
        finally:
            self._update_in_progress = None

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
                src = message.source
                sid = message.destination
                cmd = message.command
                payload = message.payload

                if src == "CORE":
                    continue

                await self._process_inbound_cmd(src, cmd, payload)
            except (ValueError, IndexError) as e:
                JEBLogger.error("NETM", f"Error handling message: {e}")

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
                        JEBLogger.info("NETM", f"Link restored with {sid}. Marking as active.")
                        self.display.update_status(f"LINK RESTORED", f"ID: {sid}")

                        self._spawn_audio_task(
                            self.audio.play,
                            "link_restored.wav",
                            channel=self.audio.CH_SFX
                        )
                        sat.was_offline = False

                    if ticks_diff(now, sat.last_seen) > 5000:
                        # Satellite has not been seen for over 5 seconds, mark as offline
                        JEBLogger.warning("NETM", f"Link lost with {sid}. Marking as offline.")
                        sat.is_active = False
                        sat.was_offline = True
                        self.display.update_status(f"LINK LOST", f"ID: {sid}")

                        self._spawn_audio_task(
                            self.audio.play,
                            "link_lost.wav",
                            channel=self.audio.CH_SFX
                        )

            await asyncio.sleep(0.5)
