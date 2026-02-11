""""""

import asyncio
import time

from adafruit_ticks import ticks_ms
import busio

from managers import PowerManager, WatchdogManager
from transport import Message, UARTTransport, CMD_ID_ASSIGN, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS
from utilities import Pins

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
        self.last_tx = 0
        self.last_seen = 0
        self.is_active = True
        # Frame sync state for coordinated animations with Core
        self.frame_counter = 0
        self.last_sync_frame = 0
        self.time_offset = 0.0  # Estimated time difference from Core (in seconds)

        # Common Hardware
        # Init power manager first for voltage readings
        self.power = PowerManager(
            Pins.SENSE_PINS,
            ["input", "satbus", "main"],
            Pins.MOSFET_CONTROL,
            Pins.SATBUS_DETECT
        )

        # UART for satellite communication
        uart_up_hw = busio.UART(
            Pins.UART_TX,
            Pins.UART_RX,
            baudrate=115200,
            receiver_buffer_size=512,
            timeout=0.01
        )
        uart_down_hw = busio.UART(
            Pins.UART_DOWN_TX,
            Pins.UART_DOWN_RX,
            baudrate=115200,
            timeout=0.01
        )

        # Wrap with transport layer (always uses queued mode now)
        self.transport_up = UARTTransport(uart_up_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)
        self.transport_down = UARTTransport(uart_down_hw, COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE, PAYLOAD_SCHEMAS)

        self._system_handlers = {
            CMD_ID_ASSIGN: self._handle_id_assign
        }

        self.watchdog = WatchdogManager(
            task_names=["power", "connection", "relay"],
            timeout=5.0
        )

    async def _handle_id_assign(self, val):
        if isinstance(val, bytes):
            val = val.decode('utf-8')
        type_prefix = val[:2]
        current_index = int(val[2:])

        if type_prefix == self.sat_type_id:
            new_index = current_index + 1
            self.id = f"{type_prefix}{new_index:02d}"

            # Forward new index downstream
            msg_out = Message("ALL", CMD_ID_ASSIGN, self.id)
            self.transport_down.send(msg_out)
        else:
            # Pass original downstream
            msg_out = Message("ALL", CMD_ID_ASSIGN, val)
            self.transport_down.send(msg_out)

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
                msg_out = Message(self.id, "LOG", "LINK_DETECTED:INIT_PWR")
                self.transport_up.send(msg_out)
                # Perform soft-start to protect the bus
                success, error = await self.power.soft_start_satellites()
                if success:
                    msg_out = Message(self.id, "LOG", "LINK_ACTIVE")
                    self.transport_up.send(msg_out)
                else:
                    msg_out = Message(self.id, "ERROR", f"PWR_FAILED:{error}")
                    self.transport_up.send(msg_out)

            # Scenario: Physical link lost while power is ON
            elif not self.power.satbus_connected and self.power.sat_pwr.value:
                self.power.emergency_kill() # Immediate hardware cut-off
                msg_out = Message(self.id, "ERROR", "LINK_LOST")
                self.transport_up.send(msg_out)

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
            if self.power.sat_pwr.value and v["bus"] < 17.0:
                self.power.emergency_kill() # Instant cut-off

            # Suppress power monitoring messages during initial
            # discovery phase when ID is not yet assigned
            if not self.id:
                await asyncio.sleep(0.5)
                continue

            # Send periodic voltage reports upstream every 5 seconds
            if now - last_broadcast > 5.0:
                self.transport_up.send(
                    Message(
                        self.id,
                        "POWER",
                        [v['in'], v['bus'], v['log']]
                    )
                )
                last_broadcast = now

            # Send Error Message for Logic rail sagging
            if v["log"] < 4.7:
                self.transport_up.send(
                    Message(
                        self.id,
                        "ERROR",
                        f"LOGIC_BROWNOUT:{v['log']}V"
                    )
                )

            # Send Error Message for Downstream Bus Failure
            if self.power.sat_pwr.value and v["bus"] < 17.0:
                self.transport_up.send(
                    Message(
                        self.id,
                        "ERROR",
                        "BUS_SHUTDOWN:LOW_V"
                    )
                )

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
            return

    async def custom_start(self):
        """Custom startup sequence for the satellite. Override in subclasses."""
        raise NotImplementedError("custom_start() must be implemented by satellite subclasses.")

    async def start(self):
        """
        Main async loop for handling communication and tasks.
        """
        # Start the trasnport tasks
        self.transport_up.start()
        self.transport_down.start()
        self.transport_up.enable_relay_from(
            self.transport_down,
            heartbeat_callback=lambda: self.watchdog.check_in("relay")
        )

        # Start monitoring tasks
        asyncio.create_task(self.monitor_power())
        asyncio.create_task(self.monitor_connection())

        # Sat specific tasks
        await self.custom_start()

        asyncio.create_task(self.monitor_watchdog_feed())

        # Primary satellite loop
        while True:
            # Local status tasks
            # Set LEDs based on power status
            # Add visuals for local errors / status

            # TX TO UPSTREAM
            if not self.id: # Initial Discovery Phase
                if time.monotonic() - self.last_tx > 3.0:
                    msg_out = Message("SAT", "NEW_SAT", self.sat_type_id)
                    self.transport_up.send(msg_out)
                    self.last_tx = time.monotonic()
            else: # Normal Operation
                if time.monotonic() - self.last_tx > 0.1:
                    # Use get_status_bytes() to avoid string allocation overhead
                    # Message class supports both str and bytes payloads
                    msg_out = Message(self.id, "STATUS", self._get_status_bytes())
                    self.transport_up.send(msg_out)
                    self.last_tx = time.monotonic()

            # RX FROM UPSTREAM -> CMD PROCESSING & TX TO DOWNSTREAM
            try:
                # Receive message via transport (non-blocking)
                message = self.transport_up.receive()
                if message:
                    # Process if addressed to us or broadcast
                    if message.destination == self.id or message.destination == "ALL":
                        await self._process_local_cmd(message.command, message.payload)
                    # Forward message downstream
                    self.transport_down.send(message)
            except ValueError as e:
                # Buffer overflow or other error
                print(f"Transport Error: {e}")
            except Exception as e:
                print(f"Transport Unexpected Error: {e}")

            await asyncio.sleep(0.01)
