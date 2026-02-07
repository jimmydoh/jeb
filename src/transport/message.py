"""Message class for protocol-level communication."""


class Message:
    """Represents a protocol-level message independent of transport.
    
    A Message contains the logical components of communication:
    - destination: Target ID (e.g., "ALL", "0101")
    - command: Command type (e.g., "STATUS", "LED", "ID_ASSIGN")
    - payload: Command-specific data (str, bytes, tuple, or list)
    
    The Message class is transport-agnostic and doesn't know about
    CRC, framing, or physical layer details.
    
    The payload can be:
    - str: Text data or text-encoded values (e.g., "0100", "HELLO")
    - bytes: Binary packed data (e.g., struct-packed values for performance)
    - tuple/list: Numeric values (optimization to reduce string allocations)
    """
    
    def __init__(self, destination, command, payload):
        """Initialize a Message.
        
        Parameters:
            destination (str): Target ID or "ALL" for broadcast.
            command (str): Command type.
            payload (str, bytes, tuple, or list): Command payload data.
        """
        self.destination = destination
        self.command = command
        self.payload = payload
    
    def __repr__(self):
        """String representation for debugging."""
        if isinstance(self.payload, str):
            payload_repr = self.payload
        elif isinstance(self.payload, (tuple, list)):
            payload_repr = str(self.payload)
        else:
            payload_repr = f"<bytes:{len(self.payload)}>"
        return f"Message(dest={self.destination}, cmd={self.command}, payload={payload_repr})"
    
    def __eq__(self, other):
        """Check equality based on message contents."""
        if not isinstance(other, Message):
            return False
        return (self.destination == other.destination and
                self.command == other.command and
                self.payload == other.payload)
