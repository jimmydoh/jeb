"""
Base firmware class for all satellite box hardware.

A class representing a physical satellite expansion box
including hardware init and functions.
"""

import asyncio
import time

from adafruit_ticks import ticks_ms
import busio

from managers import PowerManager, WatchdogManager

from transport import Message, UARTTransport

from transport.protocol import (
    CMD_HELLO,
    CMD_ID_ASSIGN,
    CMD_REBOOT,
    CMD_MODE,
    COMMAND_MAP,
    DEST_MAP,
    MAX_INDEX_VALUE,
    PAYLOAD_SCHEMAS
)

from utilities.pins import Pins

POW_INPUT = "input_20v"
POW_BUS = "satbus_20v"
POW_MAIN = "main_5v"
POW_LED = "led_5v"

class SatelliteFirmware:
    """
    Base firmware class for all satellite boxes.
    A class representing a satellite expansion box
    including hardware init and functions.
    """
    def __init__(self, sid, sat_type_id, sat_type_name):
        """
        Initialize a Satellite object.

        Parameters:
            sid (str): Satellite ID.
            sat_type_id (str): Satellite type ID.
            sat_type_name (str): Satellite type name.
        """
        self.id = sid
        self.sat_type_id = sat_type_id
        self.sat_type_name = sat_type_name

        Pins.initialize(profile="SAT", type_id=self.sat_type_id)

        # State Variables
        self._status_event = asyncio.Event()  # Event to signal status updates for efficient waiting
        self.last_tx = 0
        self.last_seen = 0
        self.is_active = True
        # Frame sync state for coordinated animations with Core
        self.frame_counter = 0
        self.last_sync_frame = 0
        self.time_offset = 0.0  # Estimated time difference from Core (in seconds)

        self.operating_mode = "IDLE"

        # Common Hardware
        # Init power manager first for voltage readings
        self.power = PowerManager(
            Pins.SENSE_PINS,
            [POW_INPUT, POW_BUS, POW_MAIN],
            Pins.MOSFET_CONTROL,
            Pins.SATBUS_DETECT
        )

        # UART for satellite communication
        uart_up_hw = busio.UART(
            Pins.UART_TX,
            Pins.UART_RX,
            baudrate=115200,
            receiver_buffer_size=1024,
            timeout=0.01
        )
        uart_down_hw = busio.UART(
            Pins.UART_DOWN_TX,
            Pins.UART_DOWN_RX,
            baudrate=115200,
            receiver_buffer_size=1024,
            timeout=0.01
        )

        # Wrap with transport layer (always uses queued mode now)
        self.transport_up = UARTTransport(uart_up_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
        self.transport_down = UARTTransport(uart_down_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

        self._system_handlers = {
            CMD_ID_ASSIGN: self._handle_id_assign,
            CMD_REBOOT: self._handle_reboot_command,
            CMD_MODE: self._handle_mode_command
        }

        self.watchdog = WatchdogManager(
            task_names=[],
            timeout=5.0
        )

    def __init_subclass__(cls, **kwargs):
        """
        Enforce implementation of required methods in subclasses.
        This runs at class definition time (import time), providing early feedback.
        """
        super().__init_subclass__(**kwargs)

        # List of methods that must be overridden by the subclass
        required_methods = [
            "_get_status_bytes",
            "custom_start"
        ]

        for method in required_methods:
            # Check if method exists and if it is different from the base class implementation
            if (not hasattr(cls, method)
                or getattr(cls, method)
                is getattr(SatelliteFirmware, method)
            ):
                raise TypeError(
                    f"Satellite subclass '{cls.__name__}' must implement method '{method}'"
                )

    async def _handle_id_assign(self, val):
        #print(f"{self.sat_type_id}-{self.id}: Handling ID_ASSIGN with value: {val}")
        if isinstance(val, bytes):
            val = val.decode('utf-8')
        type_prefix = val[:2]
        current_index = int(val[2:])

        if type_prefix == self.sat_type_id:
            if self.id:
                # I already have an ID, add 1 to my self.id index and broadcast downstream
                new_index = int(self.id[2:]) + 1
            else:
                # I don't have an ID yet, use the current index
                new_index = current_index + 1
                self.id = f"{type_prefix}{new_index:02d}"
                #print(f"{self.sat_type_id}-{self.id}: Assigned new ID based on NEW_SAT: {self.id}")

            # Send back a HELLO
            #print(f"{self.sat_type_id}-{self.id}: Sending HELLO message upstream for ID assignment with ID: {self.id}")
            if not self.transport_up.send(Message(self.id, "CORE", CMD_HELLO, self.sat_type_name)):
                # Ignore send failure, will retry on next status update or command
                print(f"{self.sat_type_id}-{self.id}: Failed to send HELLO message for ID assignment of {self.id}")

            # Forward downstream
            msg_out = Message("CORE", "ALL", CMD_ID_ASSIGN, self.id)
            if not self.transport_down.send(msg_out):
                # Ignore send failure, will retry on next status update or command
                print(f"{self.sat_type_id}-{self.id}: Failed to forward ID assignment of {self.id} downstream")
        else:
            # Pass original downstream
            msg_out = Message("CORE","ALL", CMD_ID_ASSIGN, val)
            if not self.transport_down.send(msg_out):
                # Ignore send failure, will retry on next status update or command
                print(f"{self.sat_type_id}-{self.id}: Failed to forward ID assignment of {self.id} downstream")

    async def _handle_reboot_command(self, val):
        # Log reboot and reason if provided to console and send LOG upstream before rebooting
        reason = val.decode('utf-8') if isinstance(val, bytes) else str(val)
        if reason:
            print(f"{self.sat_type_id}-{self.id}: Reboot command received with reason: {reason}. Rebooting now...")
            log_msg = f"REBOOT_CMD: {reason}"
        else:
            print(f"{self.sat_type_id}-{self.id}: Reboot command received. Rebooting now...")
            log_msg = "REBOOT_CMD: No reason provided"
        if not self.transport_up.send(Message(self.id, "CORE", "LOG", log_msg)):
            # Ignore send failure, non critical logging message
            print(f"{self.sat_type_id}-{self.id}: Failed to send reboot log message upstream")
        # Use the WatchdogManager to reboot (1 second delay)
        self.watchdog.force_reboot()

    async def _handle_mode_command(self, val):
        """Processes an upstream mode change request."""
        if isinstance(val, bytes):
            val = val.decode('utf-8')
        new_mode = val.strip().upper()
        
        if new_mode in ("IDLE", "ACTIVE"):
            if self.operating_mode != new_mode:
                self.operating_mode = new_mode
                # Notify upstream that the switch was successful
                if not self.transport_up.send(Message(self.id, "CORE", "LOG", f"MODE_CHANGED:{new_mode}")):
                    pass
                # Trigger subclass specific cleanups
                await self.on_mode_change(new_mode)

    async def on_mode_change(self, new_mode):
        """Virtual hook for subclasses to react to mode transitions."""
        pass

    async def monitor_connection(self):
        """Background task to manage the downstream RJ45 power pass-through."""
        while True:
            self.watchdog.check_in("connection")

            # Suppress connection monitoring and downstream power management
            # during initial discovery phase when ID is not yet assigned
            if not self.id:
                await asyncio.sleep(0.5)
                continue

            # Scenario: Physical link detected but power is currently OFF
            if self.power.satbus_connected and not self.power.sat_pwr.value:
                msg_out = Message(self.id, "CORE", "LOG", "LINK_DETECTED:INIT_PWR")
                if not self.transport_up.send(msg_out):
                    # Ignore send failure, non critical logging message
                    pass
                # Perform soft-start to protect the bus
                success, error = await self.power.soft_start_satellites()
                if success:
                    msg_out = Message(self.id, "CORE", "LOG", "LINK_ACTIVE")
                    if not self.transport_up.send(msg_out):
                        # Ignore send failure, non critical logging message
                        pass
                else:
                    msg_out = Message(self.id, "CORE", "ERROR", f"PWR_FAILED:{error}")
                    if not self.transport_up.send(msg_out):
                        # TODO: Implement retry logic for power fail message
                        pass

            # Scenario: Physical link lost while power is ON
            elif not self.power.satbus_connected and self.power.sat_pwr.value:
                self.power.emergency_kill() # Immediate hardware cut-off
                msg_out = Message(self.id, "CORE", "ERROR", "LINK_LOST")
                if not self.transport_up.send(msg_out):
                    # TODO: Implement retry logic for link lost message
                    pass

            await asyncio.sleep(0.5)

    async def monitor_power(self):
        """Background task to watch for local brownouts or downstream faults."""
        last_broadcast = 0
        while True:
            self.watchdog.check_in("power")

            # Update voltages and get current readings
            v = self.power.status
            now = time.monotonic()

            # Safety Check: Downstream Bus Failure cut-off
            if self.power.sat_pwr.value and v[POW_BUS] < 17.0:
                self.power.emergency_kill() # Instant cut-off

            # Suppress power monitoring messages during initial
            # discovery phase when ID is not yet assigned
            if not self.id:
                await asyncio.sleep(0.5)
                continue

            # Send periodic voltage reports upstream every 5 seconds
            if now - last_broadcast > 5.0:
                if not self.transport_up.send(
                    Message(
                        self.id,
                        "CORE",
                        "POWER",
                        [v[POW_INPUT], v[POW_BUS], v[POW_MAIN]]
                    )
                ):
                    # Ignore send failure, will retry on next status update or command
                    pass
                else:
                    last_broadcast = now

            # Send Error Message for Logic rail sagging
            if v[POW_MAIN] < 4.7:
                if not self.transport_up.send(
                    Message(
                        self.id,
                        "CORE",
                        "ERROR",
                        f"LOGIC_BROWNOUT:{v[POW_MAIN]}V"
                    )
                ):
                    # TODO: Implement retry logic for critical error messages like brownouts
                    pass

            # Send Error Message for Downstream Bus Failure
            if self.power.sat_pwr.value and v[POW_BUS] < 17.0:
                if not self.transport_up.send(
                    Message(
                        self.id,
                        "CORE",
                        "ERROR",
                        "BUS_SHUTDOWN:LOW_V"
                    )
                ):
                    # TODO: Implement retry logic for critical error messages like bus shutdown
                    pass

            await asyncio.sleep(0.5)

    async def monitor_watchdog_feed(self):
        """Background task to feed the watchdog if all systems are healthy."""
        while True:
            self.watchdog.safe_feed()
            await asyncio.sleep(1)  # Feed the watchdog every second

    def update_heartbeat(self):
        """Update the last seen timestamp."""
        self.last_seen = ticks_ms()
        self.is_active = True

    def trigger_status_update(self):
        """Trigger an immediate status update to be sent upstream."""
        self._status_event.set()  # Signal that a status update is needed

    def _get_status_bytes(self):
        """Return a compact byte representation of the satellite's status for efficient transmission."""
        raise NotImplementedError("_get_status_bytes() must be implemented by satellite subclasses.")

    async def _process_local_cmd(self, cmd, val):
        """Process a command received from upstream that is addressed to this satellite.

        This method should be overridden by subclasses to handle satellite-specific commands.
        The base implementation can handle common system commands and delegate others to subsystems.

        Parameters:
            cmd (str): Command type.
            val (str or bytes): Command value.
        """
        handler = self._system_handlers.get(cmd)
        if handler:
            await handler(val)
            return True
        return False # Command was not handled

    async def _task_tx_upstream(self):
        """
        Handle periodic status updates and initial discovery transmission logic.
        """
        while True:
            self.watchdog.check_in("tx_upstream")

            # Initial Discovery Phase: Broadcast NEW_SAT message until ID is assigned
            if not self.id:
                if time.monotonic() - self.last_tx > 3.0:
                    msg_out = Message(f"{self.sat_type_id}00", "CORE", "NEW_SAT", self.sat_type_id)
                    if self.transport_up.send(msg_out):
                        self.last_tx = time.monotonic()
                    else:
                        # Back off slightly on send failure
                        await asyncio.sleep(1)

            # Normal Operation: Send STATUS message when triggered or every 3 seconds
            else:
                if self.operating_mode == "IDLE":
                    # IDLE STATE: Suppress constant status updates, send a minimalist heartbeat every 3s
                    if time.monotonic() - self.last_tx > 3.0:
                        msg_out = Message(self.id, "CORE", "PING")
                        if self.transport_up.send(msg_out):
                            self.last_tx = time.monotonic()
                            self._status_event.clear()
                else:
                    # Check if update needed (event trigger or timeout)
                    if self._status_event.is_set() or time.monotonic() - self.last_tx > 3.0:
                        # Use get_status_bytes() to avoid string allocation overhead
                        msg_out = Message(self.id, "CORE", "STATUS", self._get_status_bytes())

                        if self.transport_up.send(msg_out):
                            self.last_tx = time.monotonic()
                            self._status_event.clear()
                        elif self._status_event.is_set():
                            # If triggered by event but failed, retry quickly
                            await asyncio.sleep(0.05)
                            continue

            # Base loop delay to yield to other tasks
            await asyncio.sleep(0.1)

    async def _task_rx_upstream(self):
        """
        Handle incoming upstream messages.

        Performs two key functions:
        1. Checks if message is for this device and processes it.
        2. Application-Level Relay: Forwards *all* messages downstream to maintain the chain.
        """
        while True:
            self.watchdog.check_in("rx_upstream")
            try:
                # Receive message via transport (async wait)
                # This yields efficiently until a complete message is ready
                message = await self.transport_up.receive()

                if message:
                    #print(f"{self.sat_type_id}-{self.id}: Received upstream message: {message}")
                    # 1. Local Processing
                    # Process if addressed to us (ID match) or broadcast (ALL)
                    if message.destination == self.id or message.destination == "ALL":
                        #print(f"{self.sat_type_id}-{self.id}: Processing command '{message.command}' with payload: {message.payload}")
                        await self._process_local_cmd(message.command, message.payload)
                    if not message.destination == self.id:
                        # 2. Forward Downstream (Application-level Relay)
                        # We forward the message object downstream.
                        if not self.transport_down.send(message):
                            # Short delay if downstream buffer full, to avoid tight loop
                            await asyncio.sleep(0.01)
            except ValueError as e:
                # Buffer overflow or CRC error
                print(f"Transport Error: {e}")
            except Exception as e:
                print(f"Transport Unexpected Error: {e}")

    async def custom_start(self):
        """Custom startup sequence for the satellite. Override in subclasses."""
        raise NotImplementedError("custom_start() must be implemented by satellite subclasses.")

    async def start(self):
        """
        Main async loop for handling communication and tasks.
        """
        # Register core watchdog flags for main tasks
        self.watchdog.register_flags(
            [
                "power",
                "connection",
                "relay",
                "tx_upstream",
                "rx_upstream"
            ]
        )

        # Start the transport tasks
        self.transport_up.start()
        self.transport_down.start()

        # Start transparent relay from downstream to upstream with watchdog check-in
        self.transport_up.enable_relay_from(
            self.transport_down,
            heartbeat_callback=lambda: self.watchdog.check_in("relay")
        )

        tasks = [
            self.monitor_power(),
            self.monitor_connection(),
            self._task_tx_upstream(),
            self._task_rx_upstream(),
            self.monitor_watchdog_feed()
        ]

        # Add satellite-specific tasks from custom_start()
        tasks.extend(await self.custom_start())

        # Run all tasks concurrently
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"Unexpected Error in satellite tasks: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(1)  # Prevent tight loop on repeated errors