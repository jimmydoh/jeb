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
try:
    from .protocol import (
        COMMAND_MAP,
        DEST_MAP,
        MAX_INDEX_VALUE,
        PAYLOAD_SCHEMAS,
        ENCODING_RAW_TEXT,
        ENCODING_NUMERIC_BYTES,
        ENCODING_NUMERIC_WORDS,
        ENCODING_FLOATS,
    )
except (ImportError, ValueError):
    COMMAND_MAP = {}
    DEST_MAP = {}
    MAX_INDEX_VALUE = 100
    PAYLOAD_SCHEMAS = {}
    ENCODING_RAW_TEXT = 'text'
    ENCODING_NUMERIC_BYTES = 'bytes'
    ENCODING_NUMERIC_WORDS = 'words'
    ENCODING_FLOATS = 'floats'

__all__ = [
    'Message',
    'UARTTransport',
    'COMMAND_MAP',
    'DEST_MAP',
    'MAX_INDEX_VALUE',
    'PAYLOAD_SCHEMAS',
    'ENCODING_RAW_TEXT',
    'ENCODING_NUMERIC_BYTES',
    'ENCODING_NUMERIC_WORDS',
    'ENCODING_FLOATS',
]
