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

__all__ = [
    'Message',
    'UARTTransport'
]
