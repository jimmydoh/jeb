"""Base transport interface for JEB communication."""


class BaseTransport:
    """Abstract base class for transport implementations.
    
    Transport classes handle the physical layer concerns:
    - Message serialization/deserialization
    - CRC calculation and verification
    - Physical transmission and reception
    - Framing (start/end markers, line termination)
    
    This abstraction allows CoreManager to work with Message objects
    without knowing about UART, I2C, CAN, or other transport details.
    """
    
    def send(self, message):
        """Send a message over the transport.
        
        Parameters:
            message (Message): The message to send.
            
        Raises:
            NotImplementedError: Must be implemented by subclass.
        """
        raise NotImplementedError("Subclass must implement send()")
    
    def receive(self):
        """Receive a message from the transport if available.
        
        Returns:
            Message or None: Received message if available, None otherwise.
            
        Raises:
            NotImplementedError: Must be implemented by subclass.
        """
        raise NotImplementedError("Subclass must implement receive()")
    
    def clear_buffer(self):
        """Clear any buffered data.
        
        Useful for recovery from error states.
        
        Raises:
            NotImplementedError: Must be implemented by subclass.
        """
        raise NotImplementedError("Subclass must implement clear_buffer()")
