"""Transport layer for JEB communication system.

This module provides an abstraction layer that decouples the transport
(UART, I2C, CAN) from the protocol logic. The CoreManager works with
Message objects, while Transport implementations handle the actual
serialization, CRC, and physical transmission.
"""

from .message import Message
from .base_transport import BaseTransport
from .uart_transport import UARTTransport

__all__ = ['Message', 'BaseTransport', 'UARTTransport']
