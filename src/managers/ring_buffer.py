"""Ring Buffer (Circular Buffer) for efficient UART data handling.

This implementation provides O(1) read and write operations, eliminating
the O(N) buffer shifting overhead present with standard bytearray operations.
"""


class RingBuffer:
    """A circular buffer implementation optimized for UART data handling.
    
    Provides O(1) append and consume operations without data copying,
    critical for high-speed UART throughput on microcontrollers.
    """
    
    def __init__(self, capacity=1024):
        """Initialize the ring buffer.
        
        Parameters:
            capacity: Maximum buffer capacity in bytes (default: 1024).
        """
        self._buffer = bytearray(capacity)
        self._capacity = capacity
        self._head = 0  # Write position
        self._tail = 0  # Read position
        self._size = 0  # Current number of bytes in buffer
    
    def extend(self, data):
        """Add data to the buffer.
        
        Parameters:
            data: Bytes or bytearray to add to the buffer.
            
        Raises:
            ValueError: If data would exceed buffer capacity.
        """
        data_len = len(data)
        if self._size + data_len > self._capacity:
            raise ValueError(f"Buffer overflow: cannot add {data_len} bytes to buffer with {self._capacity - self._size} bytes free")
        
        for byte in data:
            self._buffer[self._head] = byte
            self._head = (self._head + 1) % self._capacity
            self._size += 1
    
    def find(self, pattern):
        """Find the first occurrence of pattern in the buffer.
        
        Parameters:
            pattern: Bytes pattern to search for.
            
        Returns:
            int: Index of first occurrence, or -1 if not found.
        """
        if self._size == 0 or len(pattern) == 0:
            return -1
        
        # Search through the logical buffer
        for i in range(self._size - len(pattern) + 1):
            match = True
            for j, byte in enumerate(pattern):
                if self._get_byte_at(i + j) != byte:
                    match = False
                    break
            if match:
                return i
        return -1
    
    def _get_byte_at(self, index):
        """Get byte at logical index (internal helper).
        
        Parameters:
            index: Logical index in the buffer.
            
        Returns:
            int: Byte value at that position.
        """
        physical_index = (self._tail + index) % self._capacity
        return self._buffer[physical_index]
    
    def __getitem__(self, key):
        """Support slice notation for reading data.
        
        Parameters:
            key: Slice object or integer index.
            
        Returns:
            bytearray: Data at the specified slice/index.
        """
        if isinstance(key, slice):
            start, stop, step = key.indices(self._size)
            if step != 1:
                raise NotImplementedError("Step values other than 1 are not supported")
            
            result = bytearray()
            for i in range(start, stop):
                result.append(self._get_byte_at(i))
            return result
        elif isinstance(key, int):
            if key < 0:
                key = self._size + key
            if key < 0 or key >= self._size:
                raise IndexError("Index out of range")
            return self._get_byte_at(key)
        else:
            raise TypeError("Indices must be integers or slices")
    
    def __delitem__(self, key):
        """Support deletion via slice notation.
        
        This provides O(1) deletion from the front of the buffer,
        which is the primary use case for UART line reading.
        
        Parameters:
            key: Slice object specifying what to delete.
        """
        if not isinstance(key, slice):
            raise TypeError("Only slice deletion is supported")
        
        start, stop, step = key.indices(self._size)
        if step != 1:
            raise NotImplementedError("Step values other than 1 are not supported")
        
        # Only support deleting from the front (start == 0)
        # This is O(1) and is the primary use case for UART
        if start != 0:
            raise NotImplementedError("Only deletion from the front of buffer is supported")
        
        # Delete 'stop' bytes from the front
        bytes_to_delete = stop
        if bytes_to_delete > self._size:
            bytes_to_delete = self._size
        
        self._tail = (self._tail + bytes_to_delete) % self._capacity
        self._size -= bytes_to_delete
    
    def clear(self):
        """Clear all data from the buffer."""
        self._head = 0
        self._tail = 0
        self._size = 0
    
    def __len__(self):
        """Return the current number of bytes in the buffer."""
        return self._size
    
    @property
    def capacity(self):
        """Get the maximum capacity of the buffer."""
        return self._capacity
