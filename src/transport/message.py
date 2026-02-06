"""Message class for protocol-level communication."""


class Message:
    """Represents a protocol-level message independent of transport.
    
    A Message contains the logical components of communication:
    - destination: Target ID (e.g., "ALL", "0101")
    - command: Command type (e.g., "STATUS", "LED", "ID_ASSIGN")
    - payload: Command-specific data (e.g., "0100", "0000,C,N,0,0")
    
    The Message class is transport-agnostic and doesn't know about
    CRC, framing, or physical layer details.
    """
    
    def __init__(self, destination, command, payload):
        """Initialize a Message.
        
        Parameters:
            destination (str): Target ID or "ALL" for broadcast.
            command (str): Command type.
            payload (str|bytes|bytearray): Command payload data. Can be string or bytes.
        """
        self.destination = destination
        self.command = command
        self.payload = payload
    
    def __repr__(self):
        """String representation for debugging."""
        return f"Message(dest={self.destination}, cmd={self.command}, payload={self.payload})"
    
    def __eq__(self, other):
        """Check equality based on message contents.
        
        Note: Payloads are normalized for comparison - bytes are decoded to UTF-8 strings.
        If byte payloads contain invalid UTF-8, the comparison will return False.
        """
        if not isinstance(other, Message):
            return False
        
        # Normalize payloads for comparison (bytes to str if needed)
        self_payload = self.payload
        other_payload = other.payload
        
        try:
            if isinstance(self_payload, (bytes, bytearray)):
                self_payload = self_payload.decode('utf-8')
            if isinstance(other_payload, (bytes, bytearray)):
                other_payload = other_payload.decode('utf-8')
        except UnicodeDecodeError:
            # If decoding fails, payloads are not equal
            return False
        
        return (self.destination == other.destination and
                self.command == other.command and
                self_payload == other_payload)
