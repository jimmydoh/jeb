"""Manages satellite network discovery, health monitoring, and communication."""

import asyncio
from adafruit_ticks import ticks_ms, ticks_diff

from satellites import IndustrialSatelliteDriver
from transport import Message


class SatelliteNetworkManager:
    """Manages satellite discovery, health monitoring, and message handling.
    
    Responsibilities:
    - Satellite discovery via ID assignment
    - Health monitoring and link watchdog
    - Message routing and handling
    - Satellite registry management
    """
    
    def __init__(self, transport, display, audio, watchdog_flags=None):
        """Initialize the satellite network manager.
        
        Args:
            transport: UARTTransport instance for communication
            display: DisplayManager instance for status updates
            audio: AudioManager instance for audio feedback
            watchdog_flags: Optional dict to set watchdog flag for this task
        """
        self.transport = transport
        self.display = display
        self.audio = audio
        self.watchdog_flags = watchdog_flags
        
        # Satellite Registry
        self.satellites = {}
        self.sat_telemetry = {}
        
        # Debug state
        self.last_message_debug = ""
        self._debug_mode = False
        
        # Task throttling: Single slot for status updates to prevent unbounded task spawning
        self._current_status_task = None
    
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
        is single-threaded, no locking is needed. Do not call this method from
        multiple threads or outside the main event loop context.
        
        Args:
            coro_func: Coroutine function to execute for status update
            *args: Positional arguments to pass to the coroutine function
            **kwargs: Keyword arguments to pass to the coroutine function
        """
        if self._current_status_task is None or self._current_status_task.done():
            self._current_status_task = asyncio.create_task(coro_func(*args, **kwargs))
    
    async def discover_satellites(self):
        """Triggers the ID assignment chain to discover satellites."""
        await self.display.update_status("SCANNING BUS...", "ASSIGNING IDs")
        # Reset local registry
        self.satellites = {}
        
        # Broadcast to Industrial type (01) starting at index 00
        message = Message("ALL", "ID_ASSIGN", "0100")
        self.transport.send(message)
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
    
    def handle_message(self, message):
        """Processes incoming messages and updates satellite states.
        
        Args:
            message: Message instance from transport layer
        """
        # Store message representation for debugging
        if self._debug_mode:
            self.last_message_debug = str(message)
        
        try:
            sid = message.destination
            cmd = message.command
            payload = message.payload
            
            # Import here to avoid circular dependency
            from utilities import parse_values, get_float
            
            # Command Processing
            if cmd == "STATUS":
                if sid in self.satellites:
                    if not self.satellites[sid].is_active:
                        self.satellites[sid].is_active = True
                        self._spawn_status_task(
                            self.display.update_status, "SAT RECONNECTED", f"ID: {sid}"
                        )
                        if self.satellites[sid].sat_type_name == "INDUSTRIAL":
                            self.satellites[sid].send_cmd("DSPANIMCORRECT", "1.5")
                            asyncio.create_task(
                                self.audio.play(
                                    "link_restored.wav", channel=self.audio.CH_SFX
                                )
                            )
                    self.satellites[sid].update_from_packet(payload)
                else:
                    self._spawn_status_task(
                        self.display.update_status, "UNKNOWN SAT", f"{sid} sent STATUS."
                    )
            elif cmd == "POWER":
                v_data = parse_values(payload)
                self.sat_telemetry[sid] = {
                    "in": get_float(v_data, 0),
                    "bus": get_float(v_data, 1),
                    "log": get_float(v_data, 2),
                }
            elif cmd == "ERROR":
                self._spawn_status_task(
                    self.display.update_status, "SAT ERROR", f"ID: {sid} ERR: {payload}"
                )
                asyncio.create_task(
                    self.audio.play("alarm_klaxon.wav", channel=self.audio.CH_SFX)
                )
            elif cmd == "HELLO":
                if sid in self.satellites:
                    self.satellites[sid].update_heartbeat()
                else:
                    if payload == "INDUSTRIAL":
                        self.satellites[sid] = IndustrialSatelliteDriver(
                            sid, self.transport
                        )
                    self._spawn_status_task(
                        self.display.update_status, "NEW SAT", f"{sid} sent HELLO."
                    )
            elif cmd == "NEW_SAT":
                self._spawn_status_task(
                    self.display.update_status, "SAT CONNECTED", f"TYPE {payload} FOUND"
                )
                msg_out = Message("ALL", "ID_ASSIGN", f"{payload}00")
                self.transport.send(msg_out)
            else:
                self._spawn_status_task(
                    self.display.update_status, "UNKNOWN COMMAND", f"{sid} sent {cmd}"
                )
        except (ValueError, IndexError) as e:
            print(f"Error handling message: {e}")
    
    async def monitor_satellites(self):
        """Background task to monitor inbound messages and satellite health.
        
        This method should be run as an asyncio task. It handles:
        - Receiving and processing messages from satellites
        - Link watchdog to detect disconnected satellites
        """
        while True:
            # Set watchdog flag to indicate this task is alive
            if self.watchdog_flags is not None:
                self.watchdog_flags["sat_network"] = True
            
            # Message Handling via transport layer
            try:
                # Receive message via transport (non-blocking)
                message = self.transport.receive()
                if message:
                    self.handle_message(message)
            except ValueError as e:
                # Buffer overflow or other error
                print(f"Transport Error: {e}")
            
            # Link Watchdog
            now = ticks_ms()
            for sid, sat in self.satellites.items():
                if ticks_diff(now, sat.last_seen) > 5000:
                    if sat.is_active:
                        sat.is_active = False
                        self._spawn_status_task(
                            self.display.update_status, "LINK LOST", f"ID: {sid}"
                        )
                else:
                    if not sat.is_active:
                        sat.is_active = True
                        self._spawn_status_task(
                            self.display.update_status, "LINK RESTORED", f"ID: {sid}"
                        )
            
            await asyncio.sleep(0.01)
