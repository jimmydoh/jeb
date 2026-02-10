"""Ring buffer implementation for efficient UART data handling.

This provides O(1) deletion from the front of the buffer, eliminating the
O(N) memory copy overhead of bytearray deletion on microcontrollers.
"""


class RingBuffer:
    """A ring buffer with O(1) deletion from front.
    
    Designed for UART receive buffers where data is continuously received
    and extracted from the front (e.g., read_until pattern).
    """
    
    def __init__(self, capacity):
        """Initialize ring buffer with given capacity.
        
        Parameters:
            capacity (int): Maximum number of bytes the buffer can hold.
        """
        self.capacity = capacity
        self._buffer = bytearray(capacity)
        self._head = 0  # Read position
        self._tail = 0  # Write position
        self._size = 0  # Number of bytes in buffer
    
    def __len__(self):
        """Return number of bytes in buffer."""
        return self._size
    
    def extend(self, data):
        """Add data to the end of the buffer.
        
        Parameters:
            data (bytes): Data to append.
            
        Raises:
            ValueError: If adding data would exceed capacity.
        """
        if len(data) + self._size > self.capacity:
            raise ValueError(
                f"Buffer overflow: trying to add {len(data)} bytes to buffer "
                f"with {self._size}/{self.capacity} bytes used"
            )
        
        for byte in data:
            self._buffer[self._tail] = byte
            self._tail = (self._tail + 1) % self.capacity
            self._size += 1
    
    def __getitem__(self, key):
        """Get item(s) from buffer using slice notation.
        
        Parameters:
            key (slice): Slice specification.
            
        Returns:
            bytes: Data at the specified slice.
        """
        if isinstance(key, slice):
            start, stop, step = key.indices(self._size)
            if step != 1:
                raise ValueError("Ring buffer only supports step=1 slices")
            
            result = bytearray()
            for i in range(start, stop):
                pos = (self._head + i) % self.capacity
                result.append(self._buffer[pos])
            return bytes(result)
        else:
            # Single index
            if key < 0 or key >= self._size:
                raise IndexError("Ring buffer index out of range")
            pos = (self._head + key) % self.capacity
            return self._buffer[pos]
    
    def __delitem__(self, key):
        """Delete item(s) from buffer using slice notation.
        
        Only supports deletion from the front (slice starting at 0).
        This is O(1) operation - just moves the head pointer.
        
        Parameters:
            key (slice): Slice specification (must start at 0).
            
        Raises:
            ValueError: If slice doesn't start at 0.
        """
        if isinstance(key, slice):
            start, stop, step = key.indices(self._size)
            if step != 1:
                raise ValueError("Ring buffer only supports step=1 slices")
            if start != 0:
                raise ValueError("Ring buffer only supports deletion from front (slice must start at 0)")
            
            # O(1) operation: just move the head pointer
            count = stop - start
            self._head = (self._head + count) % self.capacity
            self._size -= count
        else:
            raise ValueError("Ring buffer only supports slice deletion")
    
    def find(self, pattern):
        """Find pattern in buffer.
        
        Parameters:
            pattern (bytes): Pattern to search for.
            
        Returns:
            int: Index of first occurrence, or -1 if not found.
        """
        if not pattern or len(pattern) > self._size:
            return -1
        
        # Search for pattern
        for i in range(self._size - len(pattern) + 1):
            match = True
            for j, byte in enumerate(pattern):
                pos = (self._head + i + j) % self.capacity
                if self._buffer[pos] != byte:
                    match = False
                    break
            if match:
                return i
        
        return -1
    
    def clear(self):
        """Clear all data from buffer."""
        self._head = 0
        self._tail = 0
        self._size = 0
