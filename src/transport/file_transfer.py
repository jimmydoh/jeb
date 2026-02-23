"""UART-based file transfer for JEB devices.

Implements chunked file streaming between devices (e.g. Core → Satellite)
using the existing COBS-framed transport layer.  The transfer is designed
to be RAM-friendly: the file is never loaded into memory in its entirety.

Protocol sequence
-----------------
Sender                                Receiver
  |                                      |
  |-- FILE_START (filename, size) -----> |  open staging file
  |<-- ACK ----------------------------- |
  |                                      |
  |-- FILE_CHUNK (offset + data) ------> |  seek to offset, write data
  |<-- ACK / NACK -------------------- - |  NACK triggers retransmit
  |   (repeat for every chunk)           |
  |                                      |
  |-- FILE_END (SHA-256 hex) ----------> |  hash-verify staging file
  |<-- ACK / NACK ---------------------- |

FILE_CHUNK wire format
----------------------
Each FILE_CHUNK payload is::

    [offset: 4 bytes little-endian uint32] [chunk data: N bytes]

Prepending the byte offset of the chunk within the file makes
retransmissions idempotent: if the receiver already wrote a chunk but
its ACK was lost on the UART line, the sender will re-send the same
chunk with the same offset.  The receiver will seek to that offset and
overwrite the data it already wrote rather than appending it a second
time.  Without this guard a single lost ACK corrupts the file.

The sender/receiver roles are deliberately agnostic: either side can
initiate a transfer so that future Sat → Core log uploads work without
any protocol changes.
"""

import asyncio
import hashlib
import os
import struct

from .message import Message
from .protocol import CMD_ACK, CMD_NACK, CMD_FILE_START, CMD_FILE_CHUNK, CMD_FILE_END

# Transfer defaults
DEFAULT_CHUNK_SIZE = 128
DEFAULT_STAGING_PATH = "/temp/pending.tmp"
DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_TRANSFER_TIMEOUT_MS = 10000  # 10 seconds without a chunk → abort

# Number of bytes used to encode the chunk offset in a FILE_CHUNK payload
_OFFSET_SIZE = 4  # uint32 little-endian


def _makedirs(path):
    """Recursively create *path* and all missing parent directories.

    Equivalent to ``os.makedirs(path, exist_ok=True)`` but uses only the
    ``os.mkdir`` call available in CircuitPython, so it works on deeply
    nested paths like ``/sd/updates/temp``.
    """
    if not path:
        return

    # Normalize Windows paths for PC testing
    path = path.replace("\\", "/")

    # Build the list of ancestor paths to create, innermost last.
    parts = []
    current = path
    while True:
        parent = "/".join(current.split("/")[:-1])
        if not parent or parent == current:
            break
        parts.append(current)
        current = parent
    # Create from outermost to innermost.
    for directory in reversed(parts):
        try:
            os.mkdir(directory)
        except OSError:
            pass  # Already exists or not creatable — ignore


def calculate_sha256(filepath):
    """Calculate the SHA-256 hash of a file using streaming reads.

    The file is read in 4 KB blocks so that arbitrarily large files can be
    hashed without exhausting the limited RAM on the Pico.

    Parameters:
        filepath (str): Path to the file to hash.

    Returns:
        str: Lowercase hex-encoded SHA-256 digest, or None if the file
        cannot be opened.
    """
    try:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            while True:
                block = f.read(4096)
                if not block:
                    break
                sha256_hash.update(block)
        return sha256_hash.hexdigest()
    except OSError:
        return None


class FileTransferSender:
    """Sends a file to a remote device in chunks over a transport.

    Usage::

        sender = FileTransferSender(transport, source_id="CORE")
        success = await sender.send_file("0101", "/sd/firmware.bin")

    Each FILE_CHUNK is acknowledged before the next is sent.  A NACK
    or timeout causes up to *max_retries* retransmissions before the
    entire transfer is aborted.
    """

    def __init__(
        self,
        transport,
        source_id,
        chunk_size=DEFAULT_CHUNK_SIZE,
        timeout=DEFAULT_TIMEOUT,
        max_retries=DEFAULT_MAX_RETRIES,
    ):
        """Initialise the sender.

        Parameters:
            transport: Transport instance with ``send()`` and ``receive()``
                methods.
            source_id (str): Source device ID used in outgoing messages.
            chunk_size (int): Number of bytes per FILE_CHUNK payload.
            timeout (float): Seconds to wait for an ACK before timing out.
            max_retries (int): Maximum retransmission attempts per chunk.
        """
        self.transport = transport
        self.source_id = source_id
        self.chunk_size = chunk_size
        self.timeout = timeout
        self.max_retries = max_retries

    async def send_file(self, destination, filepath, remote_filename=None):
        """Transfer *filepath* to *destination*.

        Parameters:
            destination (str): Target device ID (e.g. ``"0101"`` or ``"SAT"``).
            filepath (str): Absolute path to the local file to send.
            remote_filename (str | None): Override the filename sent in the
                FILE_START payload.  When ``None`` (default) the basename of
                *filepath* is used.  Pass a relative path (e.g.
                ``"managers/led_manager.mpy"``) to preserve directory structure
                on the receiver side.

        Returns:
            bool: ``True`` if the file was transferred and the receiver
            confirmed a matching SHA-256 hash; ``False`` otherwise.

        Raises:
            OSError: If *filepath* cannot be opened or read.
        """
        file_stat = os.stat(filepath)
        file_size = file_stat[6]
        filename = remote_filename if remote_filename is not None else filepath.replace("\\", "/").split("/")[-1]

        # --- FILE_START ---
        start_payload = f"{filename},{file_size}"
        self.transport.send(Message(self.source_id, destination, CMD_FILE_START, start_payload))
        if not await self._wait_for_ack():
            return False

        # --- FILE_CHUNK stream ---
        with open(filepath, "rb") as f:
            offset = 0
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                # Prepend 4-byte little-endian offset so the receiver can
                # seek to the correct position and retransmissions are safe.
                chunk_payload = struct.pack("<I", offset) + bytes(chunk)
                success = False
                for _ in range(self.max_retries):
                    self.transport.send(
                        Message(self.source_id, destination, CMD_FILE_CHUNK, chunk_payload)
                    )
                    if await self._wait_for_ack():
                        success = True
                        break
                if not success:
                    return False
                offset += len(chunk)

        # --- FILE_END with SHA-256 ---
        sha256 = calculate_sha256(filepath)
        if sha256 is None:
            return False
        self.transport.send(Message(self.source_id, destination, CMD_FILE_END, sha256))
        return await self._wait_for_ack()

    async def _wait_for_ack(self):
        """Wait for an ACK message within *self.timeout* seconds.

        Returns:
            bool: ``True`` if ACK received, ``False`` on NACK or timeout.
        """
        try:
            msg = await asyncio.wait_for(self.transport.receive(), timeout=self.timeout)
            return msg is not None and msg.command == CMD_ACK
        except asyncio.TimeoutError:
            return False


class FileTransferReceiver:
    """Receives a file sent by a :class:`FileTransferSender`.

    Maintains a simple state machine (IDLE → RECEIVING → IDLE) and
    responds with ACK/NACK after each message.

    Usage::

        receiver = FileTransferReceiver(transport, source_id="0101")

        # In the application dispatch loop:
        msg = await transport.receive()
        if msg.command in FILE_COMMANDS:
            await receiver.handle_message(msg)

        # Also call tick() regularly so stale transfers time out:
        receiver.tick(current_time_ms)

    After a successful transfer the staged file is available at
    ``receiver.staging_path``.  The caller is responsible for moving it
    to its final destination.
    """

    IDLE = "IDLE"
    RECEIVING = "RECEIVING"

    def __init__(
        self,
        transport,
        source_id,
        staging_path=DEFAULT_STAGING_PATH,
        transfer_timeout_ms=DEFAULT_TRANSFER_TIMEOUT_MS,
    ):
        """Initialise the receiver.

        Parameters:
            transport: Transport instance with a ``send()`` method.
            source_id (str): Source device ID used in outgoing ACK/NACK messages.
            staging_path (str): Path where incoming data is written.  The
                parent directory tree is created automatically if absent.
            transfer_timeout_ms (int): Milliseconds of inactivity after which
                an in-progress transfer is considered stale and aborted.
                Pass 0 to disable the timeout.
        """
        self.transport = transport
        self.source_id = source_id
        self.staging_path = staging_path
        self.transfer_timeout_ms = transfer_timeout_ms

        self._state = self.IDLE
        self._expected_filename = None
        self._expected_size = None
        self._bytes_received = 0
        self._staging_file = None
        self._last_chunk_time = None
        self.last_transfer_ok = False  # True after a successful FILE_END hash verification

    async def handle_message(self, msg):
        """Process an incoming file-transfer protocol message.

        Call :meth:`tick` regularly (e.g. from the main application loop)
        to expire stale in-progress transfers when the sender goes silent.

        Parameters:
            msg (Message): A message whose command is FILE_START, FILE_CHUNK,
                or FILE_END.

        Returns:
            bool: ``True`` if the message was handled (regardless of outcome),
            ``False`` if the command is not a file-transfer command.
        """
        if msg.command == CMD_FILE_START:
            return await self._handle_start(msg)
        if msg.command == CMD_FILE_CHUNK:
            return await self._handle_chunk(msg)
        if msg.command == CMD_FILE_END:
            return await self._handle_end(msg)
        return False

    def tick(self, current_time_ms):
        """Expire a stale in-progress transfer.

        Should be called regularly from the application main loop.  If the
        receiver is in the ``RECEIVING`` state and no chunk has arrived for
        longer than ``transfer_timeout_ms`` milliseconds, the staging file is
        closed and the state machine resets to ``IDLE``.

        Has no effect when the receiver is ``IDLE`` or when
        ``transfer_timeout_ms`` is 0.

        Parameters:
            current_time_ms (int): Current monotonic time in milliseconds
                (e.g. ``supervisor.ticks_ms()`` on CircuitPython or
                ``int(time.monotonic() * 1000)`` in CPython tests).
        """
        if (
            self.transfer_timeout_ms > 0
            and self._state == self.RECEIVING
            and self._last_chunk_time is not None
            and current_time_ms - self._last_chunk_time > self.transfer_timeout_ms
        ):
            self._close_staging_file()
            self._state = self.IDLE

    # ------------------------------------------------------------------
    # Internal handlers
    # ------------------------------------------------------------------

    async def _handle_start(self, msg):
        self._close_staging_file()
        self.last_transfer_ok = False  # Reset for the new transfer

        try:
            parts = msg.payload.split(",", 1)
            self._expected_filename = parts[0]
            self._expected_size = int(parts[1])
        except (ValueError, IndexError, AttributeError):
            self._send_nack(msg.source)
            return True

        # Ensure the full staging directory tree exists
        staging_dir = "/".join(self.staging_path.split("/")[:-1])
        _makedirs(staging_dir)

        try:
            # "w+b" creates or truncates the file and opens it for both
            # reading and writing, so retransmitted chunks can seek to
            # the correct offset and overwrite rather than appending.
            self._staging_file = open(self.staging_path, "w+b")
            self._bytes_received = 0
            self._last_chunk_time = None
            self._state = self.RECEIVING
            self._send_ack(msg.source)
        except OSError:
            self._state = self.IDLE
            self._send_nack(msg.source)

        return True

    async def _handle_chunk(self, msg):
        if self._state != self.RECEIVING or self._staging_file is None:
            self._send_nack(msg.source)
            return True

        chunk_data = msg.payload
        if isinstance(chunk_data, (bytes, bytearray)):
            pass
        elif isinstance(chunk_data, (tuple, list)):
            chunk_data = bytes(chunk_data)
        elif isinstance(chunk_data, str):
            chunk_data = chunk_data.encode("latin-1")

        # Extract the 4-byte little-endian offset prepended by the sender.
        if len(chunk_data) < _OFFSET_SIZE:
            self._send_nack(msg.source)
            return True

        offset = struct.unpack("<I", chunk_data[:_OFFSET_SIZE])[0]
        data = chunk_data[_OFFSET_SIZE:]

        # Reject writes that would extend the file beyond the declared size.
        if self._expected_size is not None and offset + len(data) > self._expected_size:
            self._send_nack(msg.source)
            return True

        try:
            self._staging_file.seek(offset)
            self._staging_file.write(data)
            self._bytes_received = max(self._bytes_received, offset + len(data))
            self._last_chunk_time = self._monotonic_ms()
            self._send_ack(msg.source)
        except OSError:
            self._send_nack(msg.source)

        return True

    async def _handle_end(self, msg):
        if self._state != self.RECEIVING:
            self._send_nack(msg.source)
            return True

        self._close_staging_file()

        expected_hash = msg.payload
        if isinstance(expected_hash, (bytes, bytearray)):
            expected_hash = expected_hash.decode("utf-8")

        actual_hash = calculate_sha256(self.staging_path)
        self._state = self.IDLE

        if actual_hash is not None and actual_hash == expected_hash:
            self.last_transfer_ok = True
            self._send_ack(msg.source)
        else:
            self.last_transfer_ok = False
            self._send_nack(msg.source)

        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _monotonic_ms():
        """Return a monotonic timestamp in milliseconds.

        Uses ``time.monotonic_ns()`` on CPython (available in Python 3.3+)
        and falls back to ``time.monotonic() * 1000`` for CircuitPython
        environments that lack nanosecond resolution.
        """
        try:
            import time
            return time.monotonic_ns() // 1_000_000
        except AttributeError:
            import time
            return int(time.monotonic() * 1000)

    def _send_ack(self, destination):
        self.transport.send(Message(self.source_id, destination, CMD_ACK, ""))

    def _send_nack(self, destination):
        self.transport.send(Message(self.source_id, destination, CMD_NACK, ""))

    def _close_staging_file(self):
        if self._staging_file is not None:
            try:
                self._staging_file.close()
            except OSError:
                pass
            self._staging_file = None
