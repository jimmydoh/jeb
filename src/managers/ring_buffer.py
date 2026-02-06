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
        
        # Optimize by copying in chunks when possible
        if data_len == 0:
            return
        
        # Calculate how much we can write before wrapping
        space_before_wrap = self._capacity - self._head
        
        if data_len <= space_before_wrap:
            # No wrap - single copy
            self._buffer[self._head:self._head + data_len] = data
            self._head = (self._head + data_len) % self._capacity
        else:
            # Wrap required - two copies
            self._buffer[self._head:self._head + space_before_wrap] = data[:space_before_wrap]
            remaining = data_len - space_before_wrap
            self._buffer[0:remaining] = data[space_before_wrap:]
            self._head = remaining
        
        self._size += data_len
    
    def find(self, pattern):
        """Find pattern using native C-speed optimizations.
        
        Parameters:
            pattern: Bytes pattern to search for.
            
        Returns:
            int: Index of first occurrence, or -1 if not found.
        """
        if self._size == 0 or len(pattern) == 0:
            return -1
        
        if len(pattern) > self._size:
            return -1
        
        # Search the first physical chunk (from tail to end of buffer or head)
        first_chunk_end = min(self._capacity, self._tail + self._size)
        res = self._buffer.find(pattern, self._tail, first_chunk_end)
        if res != -1:
            return res - self._tail
        
        # If wrapped, search the second chunk (from index 0 to head)
        if self._tail + self._size > self._capacity:
            second_chunk_end = (self._tail + self._size) % self._capacity
            res = self._buffer.find(pattern, 0, second_chunk_end)
            if res != -1:
                return (self._capacity - self._tail) + res
        
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
            
            # Map logical start to physical start
            phys_start = (self._tail + start) % self._capacity
            length = stop - start
            
            # Check if this slice wraps around
            if phys_start + length <= self._capacity:
                # Contiguous: fast copy using slice
                return self._buffer[phys_start:phys_start + length]
            else:
                # Wrapped: Two copies joined
                part1 = self._buffer[phys_start:self._capacity]
                part2 = self._buffer[0:length - len(part1)]
                return part1 + part2
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
