"""Transport layer for JEB communication system.

This module provides an abstraction layer that decouples the transport
(UART, I2C, CAN) from the protocol logic. The CoreManager works with
Message objects, while Transport implementations handle the actual
serialization, CRC, and physical transmission.

For backward compatibility and convenience, the protocol definitions are
also exported from this module so existing code can import them easily.
"""

from .message import Message
from .base_transport import BaseTransport
from .uart_transport import UARTTransport

# Import protocol definitions for convenience
# Users can import from here: from transport import COMMAND_MAP, DEST_MAP
# Or from protocol module directly: from protocol import COMMAND_MAP, DEST_MAP
try:
    # Try to import from parent package (protocol.py at src level)
    from ..protocol import COMMAND_MAP, DEST_MAP, MAX_INDEX_VALUE
except (ImportError, ValueError):
    # If relative import fails (e.g., running as script), provide empty defaults
    COMMAND_MAP = {}
    DEST_MAP = {}
    MAX_INDEX_VALUE = 100

__all__ = ['Message', 'BaseTransport', 'UARTTransport', 'COMMAND_MAP', 'DEST_MAP', 'MAX_INDEX_VALUE']
