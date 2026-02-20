#!/usr/bin/env python3
"""Tests for UART-based file transfer (FileTransferSender / FileTransferReceiver).

These tests run entirely on the development machine using temporary files and
a mock bidirectional transport, with no real UART hardware required.
"""

import asyncio
import hashlib
import os
import struct
import sys
import tempfile

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from transport.file_transfer import (
    FileTransferReceiver,
    FileTransferSender,
    calculate_sha256,
)
from transport.message import Message
from transport.protocol import (
    CMD_ACK,
    CMD_FILE_CHUNK,
    CMD_FILE_END,
    CMD_FILE_START,
    CMD_NACK,
    FILE_COMMANDS,
)


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

class PipeTransport:
    """Bidirectional in-memory transport for testing.

    Messages sent via ``send()`` are placed into the *peer* transport's
    receive queue so that two PipeTransport instances form a lossless pipe.
    """

    def __init__(self):
        self._queue = asyncio.Queue()
        self.peer = None
        self.sent_messages = []

    def send(self, msg):
        self.sent_messages.append(msg)
        if self.peer is not None:
            self.peer._queue.put_nowait(msg)

    async def receive(self):
        return await self._queue.get()

    def receive_nowait(self):
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


def make_pipe():
    """Return a connected (sender_transport, receiver_transport) pair."""
    a = PipeTransport()
    b = PipeTransport()
    a.peer = b
    b.peer = a
    return a, b


def make_temp_file(content: bytes) -> str:
    """Write *content* to a temporary file and return its path."""
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


def make_staging_path(suffix=".tmp") -> str:
    """Return the path to a unique, empty temporary file suitable as a staging path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    return path


# ---------------------------------------------------------------------------
# calculate_sha256 tests
# ---------------------------------------------------------------------------

def test_calculate_sha256_known_value():
    """SHA-256 of a known byte string must match the expected digest."""

    content = b"Hello, JEB!"
    path = make_temp_file(content)
    try:
        result = calculate_sha256(path)
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected, f"Expected {expected!r}, got {result!r}"
    finally:
        os.unlink(path)

    print("✓ calculate_sha256 known value test passed")


def test_calculate_sha256_missing_file():
    """calculate_sha256 returns None for a non-existent path."""
    result = calculate_sha256("/nonexistent/path/to/file.bin")
    assert result is None
    print("✓ calculate_sha256 missing file returns None")


def test_calculate_sha256_empty_file():
    """calculate_sha256 handles an empty file without error."""

    path = make_temp_file(b"")
    try:
        result = calculate_sha256(path)
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected
    finally:
        os.unlink(path)

    print("✓ calculate_sha256 empty file test passed")


# ---------------------------------------------------------------------------
# Protocol constant tests
# ---------------------------------------------------------------------------

def test_file_commands_in_protocol():
    """FILE_START, FILE_CHUNK, FILE_END must be defined in the protocol."""
    from transport import protocol

    for cmd in (CMD_FILE_START, CMD_FILE_CHUNK, CMD_FILE_END):
        assert cmd in protocol.COMMAND_MAP, f"{cmd} missing from COMMAND_MAP"
        assert cmd in protocol.PAYLOAD_SCHEMAS, f"{cmd} missing from PAYLOAD_SCHEMAS"
        assert cmd in protocol.COMMAND_REVERSE_MAP.values(), \
            f"{cmd} missing from COMMAND_REVERSE_MAP"

    print("✓ File transfer commands present in protocol")


def test_file_commands_byte_range():
    """FILE_* commands must occupy the 0x40–0x4F range."""
    from transport import protocol

    for cmd in (CMD_FILE_START, CMD_FILE_CHUNK, CMD_FILE_END):
        code = protocol.COMMAND_MAP[cmd]
        assert 0x40 <= code <= 0x4F, \
            f"{cmd} byte code 0x{code:02X} not in expected range 0x40–0x4F"

    print("✓ File transfer command byte codes are in 0x40–0x4F range")


def test_file_commands_set():
    """FILE_COMMANDS set must contain exactly the three file-transfer commands."""
    assert FILE_COMMANDS == {CMD_FILE_START, CMD_FILE_CHUNK, CMD_FILE_END}
    print("✓ FILE_COMMANDS set is correct")


def test_no_duplicate_command_codes():
    """Adding FILE_* commands must not create duplicate byte codes."""
    from transport import protocol

    values = list(protocol.COMMAND_MAP.values())
    assert len(values) == len(set(values)), "Duplicate byte codes detected in COMMAND_MAP"
    print("✓ No duplicate command codes after adding FILE_* commands")


def test_encoding_raw_bytes_constant():
    """ENCODING_RAW_BYTES must be defined in protocol."""
    from transport import protocol

    assert hasattr(protocol, "ENCODING_RAW_BYTES"), \
        "ENCODING_RAW_BYTES constant missing from protocol"
    assert protocol.ENCODING_RAW_BYTES == "raw_bytes"
    print("✓ ENCODING_RAW_BYTES constant is defined")


def test_file_chunk_schema_uses_raw_bytes():
    """FILE_CHUNK payload schema must use ENCODING_RAW_BYTES."""
    from transport import protocol

    schema = protocol.PAYLOAD_SCHEMAS[CMD_FILE_CHUNK]
    assert schema["type"] == protocol.ENCODING_RAW_BYTES, \
        f"Expected ENCODING_RAW_BYTES, got {schema['type']!r}"
    print("✓ FILE_CHUNK schema uses ENCODING_RAW_BYTES")


# ---------------------------------------------------------------------------
# FileTransferSender unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sender_sends_file_start():
    """Sender must emit FILE_START before any chunk."""
    sender_t, receiver_t = make_pipe()

    content = b"test data"
    path = make_temp_file(content)
    try:
        sender = FileTransferSender(sender_t, source_id="CORE", timeout=0.5)

        # Inject ACK responses for FILE_START and FILE_END
        async def ack_loop():
            while True:
                msg = await receiver_t.receive()
                receiver_t.send(Message("0101", "CORE", CMD_ACK, ""))
                if msg.command == CMD_FILE_END:
                    break

        task = asyncio.create_task(ack_loop())
        result = await sender.send_file("0101", path)
        await task

        assert result is True
        # First sent message must be FILE_START
        assert sender_t.sent_messages[0].command == CMD_FILE_START
        assert sender_t.sent_messages[0].destination == "0101"
    finally:
        os.unlink(path)

    print("✓ Sender emits FILE_START as first message")


@pytest.mark.asyncio
async def test_sender_file_start_payload_format():
    """FILE_START payload must be 'filename,size'."""
    sender_t, receiver_t = make_pipe()

    content = b"x" * 50
    path = make_temp_file(content)
    try:
        filename = os.path.basename(path)
        sender = FileTransferSender(sender_t, source_id="CORE", timeout=0.5)

        async def ack_loop():
            while True:
                msg = await receiver_t.receive()
                receiver_t.send(Message("0101", "CORE", CMD_ACK, ""))
                if msg.command == CMD_FILE_END:
                    break

        task = asyncio.create_task(ack_loop())
        await sender.send_file("0101", path)
        await task

        start_msg = sender_t.sent_messages[0]
        assert start_msg.command == CMD_FILE_START
        parts = start_msg.payload.split(",", 1)
        assert parts[0] == filename, "Filename in FILE_START payload is wrong"
        assert int(parts[1]) == 50, "Size in FILE_START payload is wrong"
    finally:
        os.unlink(path)

    print("✓ FILE_START payload contains correct filename and size")


@pytest.mark.asyncio
async def test_sender_remote_filename_overrides_local_basename():
    """remote_filename parameter must override the local basename in FILE_START."""
    sender_t, receiver_t = make_pipe()

    content = b"x" * 50
    path = make_temp_file(content)
    try:
        sender = FileTransferSender(sender_t, source_id="CORE", timeout=0.5)
        remote = "managers/led_manager.mpy"

        async def ack_loop():
            while True:
                msg = await receiver_t.receive()
                receiver_t.send(Message("0101", "CORE", CMD_ACK, ""))
                if msg.command == CMD_FILE_END:
                    break

        task = asyncio.create_task(ack_loop())
        await sender.send_file("0101", path, remote_filename=remote)
        await task

        start_msg = sender_t.sent_messages[0]
        assert start_msg.command == CMD_FILE_START
        parts = start_msg.payload.split(",", 1)
        assert parts[0] == remote, f"Expected remote_filename '{remote}', got '{parts[0]}'"
    finally:
        os.unlink(path)

    print("✓ remote_filename correctly overrides local basename in FILE_START payload")


@pytest.mark.asyncio
async def test_sender_sends_chunks():
    """Sender must emit FILE_CHUNK messages for each portion of the file."""
    sender_t, receiver_t = make_pipe()

    content = bytes(range(256))  # 256 bytes
    path = make_temp_file(content)
    try:
        sender = FileTransferSender(
            sender_t, source_id="CORE", chunk_size=64, timeout=0.5
        )

        async def ack_loop():
            while True:
                msg = await receiver_t.receive()
                receiver_t.send(Message("0101", "CORE", CMD_ACK, ""))
                if msg.command == CMD_FILE_END:
                    break

        task = asyncio.create_task(ack_loop())
        result = await sender.send_file("0101", path)
        await task

        assert result is True
        chunk_msgs = [m for m in sender_t.sent_messages if m.command == CMD_FILE_CHUNK]
        # 256 bytes / 64 bytes per chunk = 4 chunks
        assert len(chunk_msgs) == 4, f"Expected 4 chunks, got {len(chunk_msgs)}"
        # Reassemble: each chunk payload is [4-byte offset][chunk data]
        reassembled = b"".join(m.payload[4:] for m in chunk_msgs)
        assert reassembled == content
    finally:
        os.unlink(path)

    print("✓ Sender emits correct FILE_CHUNK messages")


@pytest.mark.asyncio
async def test_sender_sends_file_end_with_sha256():
    """Sender must emit FILE_END containing the correct SHA-256 hex digest."""

    sender_t, receiver_t = make_pipe()

    content = b"JEB file transfer test"
    path = make_temp_file(content)
    try:
        sender = FileTransferSender(sender_t, source_id="CORE", timeout=0.5)

        async def ack_loop():
            while True:
                msg = await receiver_t.receive()
                receiver_t.send(Message("0101", "CORE", CMD_ACK, ""))
                if msg.command == CMD_FILE_END:
                    break

        task = asyncio.create_task(ack_loop())
        await sender.send_file("0101", path)
        await task

        end_msgs = [m for m in sender_t.sent_messages if m.command == CMD_FILE_END]
        assert len(end_msgs) == 1
        expected_hash = hashlib.sha256(content).hexdigest()
        assert end_msgs[0].payload == expected_hash, \
            f"Expected {expected_hash!r}, got {end_msgs[0].payload!r}"
    finally:
        os.unlink(path)

    print("✓ FILE_END payload contains correct SHA-256 hash")


@pytest.mark.asyncio
async def test_sender_retransmits_on_nack():
    """Sender must retransmit a chunk when it receives NACK."""
    sender_t, receiver_t = make_pipe()

    content = b"retry test"
    path = make_temp_file(content)
    try:
        sender = FileTransferSender(
            sender_t, source_id="CORE", timeout=0.5, max_retries=3
        )

        nack_count = {"n": 0}

        async def ack_loop():
            while True:
                msg = await receiver_t.receive()
                if msg.command == CMD_FILE_CHUNK and nack_count["n"] < 2:
                    # Send NACK for first two chunk attempts
                    nack_count["n"] += 1
                    receiver_t.send(Message("0101", "CORE", CMD_NACK, ""))
                else:
                    receiver_t.send(Message("0101", "CORE", CMD_ACK, ""))
                if msg.command == CMD_FILE_END:
                    break

        task = asyncio.create_task(ack_loop())
        result = await sender.send_file("0101", path)
        await task

        assert result is True
        chunk_msgs = [m for m in sender_t.sent_messages if m.command == CMD_FILE_CHUNK]
        # 2 NACKed + 1 successful = 3 total chunk transmissions for the one chunk
        assert len(chunk_msgs) == 3, \
            f"Expected 3 chunk transmissions (2 retries), got {len(chunk_msgs)}"
    finally:
        os.unlink(path)

    print("✓ Sender retransmits chunk after NACK")


@pytest.mark.asyncio
async def test_sender_fails_after_max_retries():
    """Sender must return False when retries are exhausted."""
    sender_t, receiver_t = make_pipe()

    content = b"give up"
    path = make_temp_file(content)
    try:
        sender = FileTransferSender(
            sender_t, source_id="CORE", timeout=0.5, max_retries=3
        )

        async def always_nack():
            while True:
                msg = await receiver_t.receive()
                receiver_t.send(Message("0101", "CORE", CMD_NACK, ""))
                if msg.command == CMD_FILE_START:
                    # After FILE_START NACK the sender aborts
                    break

        task = asyncio.create_task(always_nack())
        result = await sender.send_file("0101", path)
        await asyncio.wait_for(task, timeout=2.0)

        assert result is False
    finally:
        os.unlink(path)

    print("✓ Sender returns False after max retries exhausted")


@pytest.mark.asyncio
async def test_sender_timeout():
    """Sender returns False when no ACK arrives within the timeout window."""
    sender_t, _receiver_t = make_pipe()  # peer connected but nobody consumes

    content = b"timeout test"
    path = make_temp_file(content)
    try:
        sender = FileTransferSender(
            sender_t, source_id="CORE", timeout=0.1
        )
        result = await sender.send_file("0101", path)
        assert result is False
    finally:
        os.unlink(path)

    print("✓ Sender returns False on ACK timeout")


# ---------------------------------------------------------------------------
# FileTransferReceiver unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_receiver_acks_file_start():
    """Receiver must send ACK in response to a valid FILE_START."""
    _sender_t, receiver_t = make_pipe()
    staging = make_staging_path()
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging)

    msg = Message("CORE", "0101", CMD_FILE_START, "test.bin,10")
    await receiver.handle_message(msg)

    # ACK should be in sender_t queue (receiver_t.peer = sender_t)
    ack = _sender_t.receive_nowait()
    assert ack is not None and ack.command == CMD_ACK

    # Clean up
    receiver._close_staging_file()
    if os.path.exists(staging):
        os.unlink(staging)

    print("✓ Receiver ACKs FILE_START")


@pytest.mark.asyncio
async def test_receiver_nacks_malformed_file_start():
    """Receiver must send NACK when FILE_START payload is malformed."""
    sender_t, receiver_t = make_pipe()
    receiver = FileTransferReceiver(receiver_t, source_id="0101")

    msg = Message("CORE", "0101", CMD_FILE_START, "MALFORMED_NO_SIZE")
    await receiver.handle_message(msg)

    response = sender_t.receive_nowait()
    assert response is not None and response.command == CMD_NACK

    print("✓ Receiver NACKs malformed FILE_START")


@pytest.mark.asyncio
async def test_receiver_writes_chunks():
    """Receiver must write each FILE_CHUNK to the staging file."""
    sender_t, receiver_t = make_pipe()
    staging = make_staging_path()
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging)

    content = bytes(range(64))

    # FILE_START
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_START, f"data.bin,{len(content)}")
    )
    sender_t.receive_nowait()  # consume ACK

    # FILE_CHUNK — payload must include the 4-byte little-endian offset prefix
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_CHUNK, struct.pack("<I", 0) + content)
    )
    ack = sender_t.receive_nowait()
    assert ack is not None and ack.command == CMD_ACK

    # Verify staged bytes (only the raw chunk data, not the offset prefix)
    receiver._close_staging_file()
    with open(staging, "rb") as f:
        written = f.read()
    assert written == content, "Staged content does not match sent chunk"
    os.unlink(staging)

    print("✓ Receiver writes FILE_CHUNK data to staging file")


@pytest.mark.asyncio
async def test_receiver_nacks_chunk_when_idle():
    """Receiver in IDLE state must NACK a stray FILE_CHUNK."""
    sender_t, receiver_t = make_pipe()
    receiver = FileTransferReceiver(receiver_t, source_id="0101")

    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_CHUNK, b"orphan chunk")
    )
    response = sender_t.receive_nowait()
    assert response is not None and response.command == CMD_NACK

    print("✓ Receiver NACKs FILE_CHUNK when in IDLE state")


@pytest.mark.asyncio
async def test_receiver_validates_sha256_on_file_end():
    """Receiver must ACK FILE_END only when the SHA-256 hash matches."""

    sender_t, receiver_t = make_pipe()
    staging = make_staging_path()
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging)

    content = b"valid file content for hashing"
    expected_hash = hashlib.sha256(content).hexdigest()

    # FILE_START
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_START, f"file.bin,{len(content)}")
    )
    sender_t.receive_nowait()  # ACK

    # FILE_CHUNK — include 4-byte offset prefix
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_CHUNK, struct.pack("<I", 0) + content)
    )
    sender_t.receive_nowait()  # ACK
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_END, expected_hash)
    )
    ack = sender_t.receive_nowait()
    assert ack is not None and ack.command == CMD_ACK, \
        f"Expected ACK for correct hash, got {ack}"

    if os.path.exists(staging):
        os.unlink(staging)

    print("✓ Receiver ACKs FILE_END with correct SHA-256")


@pytest.mark.asyncio
async def test_receiver_nacks_wrong_sha256():
    """Receiver must NACK FILE_END when the SHA-256 hash is wrong."""
    sender_t, receiver_t = make_pipe()
    staging = make_staging_path()
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging)

    content = b"some bytes"

    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_START, f"file.bin,{len(content)}")
    )
    sender_t.receive_nowait()

    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_CHUNK, struct.pack("<I", 0) + content)
    )
    sender_t.receive_nowait()

    wrong_hash = "a" * 64  # 64 hex chars but wrong value
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_END, wrong_hash)
    )
    nack = sender_t.receive_nowait()
    assert nack is not None and nack.command == CMD_NACK, \
        f"Expected NACK for wrong hash, got {nack}"

    if os.path.exists(staging):
        os.unlink(staging)

    print("✓ Receiver NACKs FILE_END with wrong SHA-256")


@pytest.mark.asyncio
async def test_receiver_ignores_non_file_commands():
    """handle_message must return False for non-file-transfer commands."""
    sender_t, receiver_t = make_pipe()
    receiver = FileTransferReceiver(receiver_t, source_id="0101")

    result = await receiver.handle_message(
        Message("CORE", "0101", CMD_ACK, "")
    )
    assert result is False
    assert sender_t.receive_nowait() is None  # No response sent

    print("✓ Receiver ignores non-file-transfer commands")


# ---------------------------------------------------------------------------
# Full end-to-end transfer test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_transfer_small_file():
    """Full transfer of a small file: content and hash must survive round-trip."""

    content = b"Small file content for integration test."
    source_path = make_temp_file(content)
    staging_path = make_staging_path()

    sender_t, receiver_t = make_pipe()
    sender = FileTransferSender(sender_t, source_id="CORE", chunk_size=16, timeout=1.0)
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging_path)

    async def receiver_loop():
        while True:
            msg = await receiver_t.receive()
            await receiver.handle_message(msg)
            if msg.command == CMD_FILE_END:
                break

    try:
        recv_task = asyncio.create_task(receiver_loop())
        result = await sender.send_file("0101", source_path)
        await recv_task

        assert result is True, "send_file should return True on success"

        with open(staging_path, "rb") as f:
            received_content = f.read()

        assert received_content == content, "Received content does not match original"
        assert hashlib.sha256(received_content).hexdigest() == hashlib.sha256(content).hexdigest()
    finally:
        os.unlink(source_path)
        if os.path.exists(staging_path):
            os.unlink(staging_path)

    print("✓ Full small-file transfer end-to-end test passed")


@pytest.mark.asyncio
async def test_full_transfer_binary_file():
    """Transfer of a binary file with null bytes and arbitrary values."""
    content = bytes(range(256)) * 4  # 1024 bytes with all byte values including 0x00
    source_path = make_temp_file(content)
    staging_path = make_staging_path()

    sender_t, receiver_t = make_pipe()
    sender = FileTransferSender(sender_t, source_id="CORE", chunk_size=128, timeout=1.0)
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging_path)

    async def receiver_loop():
        while True:
            msg = await receiver_t.receive()
            await receiver.handle_message(msg)
            if msg.command == CMD_FILE_END:
                break

    try:
        recv_task = asyncio.create_task(receiver_loop())
        result = await sender.send_file("0101", source_path)
        await recv_task

        assert result is True

        with open(staging_path, "rb") as f:
            received = f.read()

        assert received == content, \
            f"Binary content mismatch: {len(received)} bytes received vs {len(content)} expected"
    finally:
        os.unlink(source_path)
        if os.path.exists(staging_path):
            os.unlink(staging_path)

    print("✓ Full binary-file transfer end-to-end test passed")


@pytest.mark.asyncio
async def test_receiver_resets_state_after_successful_transfer():
    """Receiver must return to IDLE after a successful FILE_END."""

    sender_t, receiver_t = make_pipe()
    staging_path = make_staging_path()
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging_path)

    content = b"state reset test"

    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_START, f"f.bin,{len(content)}")
    )
    sender_t.receive_nowait()
    await receiver.handle_message(Message("CORE", "0101", CMD_FILE_CHUNK, struct.pack("<I", 0) + content))
    sender_t.receive_nowait()
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_END, hashlib.sha256(content).hexdigest())
    )
    sender_t.receive_nowait()

    assert receiver._state == FileTransferReceiver.IDLE
    assert receiver._staging_file is None

    if os.path.exists(staging_path):
        os.unlink(staging_path)

    print("✓ Receiver returns to IDLE after successful transfer")


@pytest.mark.asyncio
async def test_lost_ack_does_not_corrupt_file():
    """A lost ACK must not cause the file to be written twice.

    Scenario:
      1. Sender sends Chunk A.
      2. Receiver writes Chunk A, sends ACK.
      3. The ACK is dropped (never reaches the sender).
      4. Sender times out and retransmits Chunk A with the same offset.
      5. Receiver seeks to the same offset and overwrites — no duplication.
      6. FILE_END SHA-256 check must still pass.
    """

    content = b"idempotent chunk write test"
    source_path = make_temp_file(content)
    staging_path = make_staging_path()

    sender_t, receiver_t = make_pipe()
    sender = FileTransferSender(
        sender_t, source_id="CORE", chunk_size=128, timeout=0.3, max_retries=3
    )
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging_path)

    ack_dropped = {"dropped": False}

    async def receiver_loop():
        while True:
            msg = await receiver_t.receive()
            await receiver.handle_message(msg)
            if msg.command == CMD_FILE_CHUNK and not ack_dropped["dropped"]:
                # Silently discard the first ACK so the sender retransmits
                sender_t._queue.get_nowait()  # pop the ACK off the sender's queue
                ack_dropped["dropped"] = True
            if msg.command == CMD_FILE_END:
                break

    try:
        recv_task = asyncio.create_task(receiver_loop())
        result = await sender.send_file("0101", source_path)
        await recv_task

        assert result is True, "Transfer must succeed despite lost ACK"

        with open(staging_path, "rb") as f:
            received = f.read()

        expected_hash = hashlib.sha256(content).hexdigest()
        assert received == content, (
            f"File corrupted after lost ACK: got {len(received)} bytes, "
            f"expected {len(content)} bytes"
        )
        assert hashlib.sha256(received).hexdigest() == expected_hash, \
            "SHA-256 mismatch after lost-ACK retransmission"
    finally:
        os.unlink(source_path)
        if os.path.exists(staging_path):
            os.unlink(staging_path)

    print("✓ Lost ACK does not corrupt file (idempotent chunk write)")


@pytest.mark.asyncio
async def test_receiver_nacks_chunk_without_offset():
    """Receiver must NACK a FILE_CHUNK payload that is too short to contain an offset."""
    sender_t, receiver_t = make_pipe()
    staging = make_staging_path()
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging)

    # Open a transfer so receiver is in RECEIVING state
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_START, "f.bin,4")
    )
    sender_t.receive_nowait()  # consume ACK

    # Send a chunk with only 3 bytes — too short to hold a 4-byte offset
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_CHUNK, b"\x01\x02\x03")
    )
    response = sender_t.receive_nowait()
    assert response is not None and response.command == CMD_NACK, \
        "Expected NACK for payload shorter than offset header"

    receiver._close_staging_file()
    if os.path.exists(staging):
        os.unlink(staging)

    print("✓ Receiver NACKs FILE_CHUNK payload too short to contain offset")


# ---------------------------------------------------------------------------
# New robustness tests (items 1-3 from review)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_receiver_nacks_chunk_beyond_declared_size():
    """Receiver must NACK a FILE_CHUNK that would write past the declared file size."""
    sender_t, receiver_t = make_pipe()
    staging = make_staging_path()
    # Declare a 10-byte file
    receiver = FileTransferReceiver(receiver_t, source_id="0101", staging_path=staging)

    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_START, "f.bin,10")
    )
    sender_t.receive_nowait()  # consume ACK

    # Send a chunk whose offset+length exceeds 10 bytes
    # offset=8, data=4 bytes → would write bytes 8..12, but file is only 10
    oversized_payload = struct.pack("<I", 8) + b"\x01\x02\x03\x04"
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_CHUNK, oversized_payload)
    )
    response = sender_t.receive_nowait()
    assert response is not None and response.command == CMD_NACK, \
        "Expected NACK when chunk writes past declared file size"

    receiver._close_staging_file()
    if os.path.exists(staging):
        os.unlink(staging)

    print("✓ Receiver NACKs FILE_CHUNK beyond declared file size")


@pytest.mark.asyncio
async def test_receiver_tick_expires_stale_transfer():
    """tick() must close the staging file and reset to IDLE on timeout."""
    sender_t, receiver_t = make_pipe()
    staging = make_staging_path()
    receiver = FileTransferReceiver(
        receiver_t, source_id="0101", staging_path=staging,
        transfer_timeout_ms=1000,
    )

    content = b"partial data"

    # Start a transfer and send one chunk
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_START, f"f.bin,{len(content)}")
    )
    sender_t.receive_nowait()
    await receiver.handle_message(
        Message("CORE", "0101", CMD_FILE_CHUNK, struct.pack("<I", 0) + content)
    )
    sender_t.receive_nowait()

    assert receiver._state == FileTransferReceiver.RECEIVING

    # Simulate 500 ms passing — not yet timed out
    last_time = receiver._last_chunk_time
    receiver.tick(last_time + 500)
    assert receiver._state == FileTransferReceiver.RECEIVING, \
        "Should still be RECEIVING after 500 ms"

    # Simulate 2000 ms passing — timeout exceeded
    receiver.tick(last_time + 2000)
    assert receiver._state == FileTransferReceiver.IDLE, \
        "Should have reset to IDLE after timeout"
    assert receiver._staging_file is None, \
        "Staging file should be closed after timeout"

    if os.path.exists(staging):
        os.unlink(staging)

    print("✓ tick() expires stale transfer and resets to IDLE")


@pytest.mark.asyncio
async def test_receiver_tick_no_effect_when_idle():
    """tick() must be a no-op when the receiver is already IDLE."""
    _sender_t, receiver_t = make_pipe()
    receiver = FileTransferReceiver(receiver_t, source_id="0101")

    assert receiver._state == FileTransferReceiver.IDLE
    receiver.tick(99999999)  # should not raise or change state
    assert receiver._state == FileTransferReceiver.IDLE

    print("✓ tick() is a no-op when receiver is IDLE")


def test_makedirs_single_level():
    """_makedirs must create a single-level directory."""
    from transport.file_transfer import _makedirs
    import tempfile

    base = tempfile.mkdtemp()
    target = os.path.join(base, "newdir")
    try:
        _makedirs(target)
        assert os.path.isdir(target), "Directory was not created"
    finally:
        if os.path.isdir(target):
            os.rmdir(target)
        os.rmdir(base)

    print("✓ _makedirs creates a single-level directory")


def test_makedirs_nested():
    """_makedirs must recursively create nested directories."""
    from transport.file_transfer import _makedirs
    import tempfile

    base = tempfile.mkdtemp()
    target = os.path.join(base, "a", "b", "c")
    try:
        _makedirs(target)
        assert os.path.isdir(target), "Nested directory was not created"
    finally:
        # Clean up recursively
        for sub in [target,
                    os.path.join(base, "a", "b"),
                    os.path.join(base, "a"),
                    base]:
            if os.path.isdir(sub):
                os.rmdir(sub)

    print("✓ _makedirs recursively creates nested directories")


def test_makedirs_existing_path():
    """_makedirs must not raise when the path already exists."""
    from transport.file_transfer import _makedirs
    import tempfile

    base = tempfile.mkdtemp()
    try:
        _makedirs(base)  # already exists — must not raise
        assert os.path.isdir(base)
    finally:
        os.rmdir(base)

    print("✓ _makedirs does not raise when path already exists")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_sync_tests():
    tests = [
        test_calculate_sha256_known_value,
        test_calculate_sha256_missing_file,
        test_calculate_sha256_empty_file,
        test_file_commands_in_protocol,
        test_file_commands_byte_range,
        test_file_commands_set,
        test_no_duplicate_command_codes,
        test_encoding_raw_bytes_constant,
        test_file_chunk_schema_uses_raw_bytes,
        test_makedirs_single_level,
        test_makedirs_nested,
        test_makedirs_existing_path,
    ]
    for t in tests:
        t()


async def run_async_tests():
    await test_sender_sends_file_start()
    await test_sender_file_start_payload_format()
    await test_sender_remote_filename_overrides_local_basename()
    await test_sender_sends_chunks()
    await test_sender_sends_file_end_with_sha256()
    await test_sender_retransmits_on_nack()
    await test_sender_fails_after_max_retries()
    await test_sender_timeout()
    await test_receiver_acks_file_start()
    await test_receiver_nacks_malformed_file_start()
    await test_receiver_writes_chunks()
    await test_receiver_nacks_chunk_when_idle()
    await test_receiver_validates_sha256_on_file_end()
    await test_receiver_nacks_wrong_sha256()
    await test_receiver_ignores_non_file_commands()
    await test_full_transfer_small_file()
    await test_full_transfer_binary_file()
    await test_receiver_resets_state_after_successful_transfer()
    await test_lost_ack_does_not_corrupt_file()
    await test_receiver_nacks_chunk_without_offset()
    await test_receiver_nacks_chunk_beyond_declared_size()
    await test_receiver_tick_expires_stale_transfer()
    await test_receiver_tick_no_effect_when_idle()


if __name__ == "__main__":
    print("=" * 70)
    print("File Transfer Test Suite")
    print("=" * 70)

    try:
        run_sync_tests()
        asyncio.run(run_async_tests())

        print("\n" + "=" * 70)
        print("ALL FILE TRANSFER TESTS PASSED ✓")
        print("=" * 70)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
