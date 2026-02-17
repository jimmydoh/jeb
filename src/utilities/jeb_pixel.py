# File: src/core/utilities/jeb_pixel.py
"""A wrapper to treat a segment of a NeoPixel strip as an independent object."""

class JEBPixel:
    """A wrapper to treat a segment of a NeoPixel strip as an independent object."""
    def __init__(self, parent, start_idx, num_pixels):
        self.parent = parent    # The real, physical strip (68 pixels)
        self.start = start_idx  # Start index (e.g., 64)
        self.n = num_pixels          # Length (e.g., 4)

    def __setitem__(self, index, val):
        """Sets a specific pixel in the segment."""
        # Maps slice index [0] to parent index [start + 0]
        if index < 0 or index >= self.n:
            return
        self.parent[self.start + index] = val

    def __getitem__(self, index):
        """Gets a specific pixel from the segment."""
        if index < 0 or index >= self.n:
            return (0,0,0)
        return self.parent[self.start + index]

    def __len__(self):
        """Returns the number of pixels in this segment."""
        return self.n

    def fill(self, color):
        """Fills the entire segment with a single color."""
        for i in range(self.start, self.start + self.n):
            self.parent[i] = color

    def show(self):
        """Updates the segment's buffer memory only.

        Note: Hardware write is now centralized in CoreManager.render_loop().
        This method is kept for API compatibility but no longer triggers hardware writes.
        """
        # Memory buffer is already updated via __setitem__ and fill()
        # No hardware write needed - render loop handles that
        pass
