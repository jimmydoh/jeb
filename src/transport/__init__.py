"""Transport layer for JEB communication system.

This module provides an abstraction layer that decouples the transport
(UART, I2C, CAN) from the protocol logic. The CoreManager works with
Message objects, while Transport implementations handle the actual
serialization, CRC, and physical transmission.

For backward compatibility and convenience, the protocol definitions are
also exported from this module so existing code can import them easily.
"""

from .message import Message
from .uart_transport import UARTTransport
from .protocol import (
    CMD_PING,
    CMD_ACK,
    CMD_NACK,
    CMD_ID_ASSIGN,
    CMD_NEW_SAT,
    CMD_STATUS,
    CMD_ERROR,
    CMD_LOG,
    CMD_SYNC_FRAME,
    CMD_POWER,
    CMD_SETENC,
    COMMAND_MAP,
    DEST_MAP,
    LED_COMMANDS,
    DSP_COMMANDS,
    SYSTEM_COMMANDS,
    MAX_INDEX_VALUE,
    ENCODING_RAW_TEXT,
    ENCODING_NUMERIC_BYTES,
    ENCODING_NUMERIC_WORDS,
    ENCODING_FLOATS,
    PAYLOAD_SCHEMAS,
)

__all__ = [
    'Message',
    'UARTTransport',
    'CMD_PING',
    'CMD_ACK',
    'CMD_NACK',
    'CMD_ID_ASSIGN',
    'CMD_NEW_SAT',
    'CMD_STATUS',
    'CMD_ERROR',
    'CMD_LOG',
    'CMD_SYNC_FRAME',
    'CMD_POWER',
    'CMD_SETENC',
    'COMMAND_MAP',
    'DEST_MAP',
    'LED_COMMANDS',
    'DSP_COMMANDS',
    'SYSTEM_COMMANDS',
    'MAX_INDEX_VALUE',
    'ENCODING_RAW_TEXT',
    'ENCODING_NUMERIC_BYTES',
    'ENCODING_NUMERIC_WORDS',
    'ENCODING_FLOATS',
    'PAYLOAD_SCHEMAS',
]
