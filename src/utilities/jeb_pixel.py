# File: src/core/utilities/jeb_pixel.py
"""A wrapper to treat a segment of a NeoPixel strip as an independent object."""

class JEBPixel:
    """A wrapper to treat a segment of a NeoPixel strip as an independent object."""
    def __init__(self, parent, start_idx, num_pixels, pixel_order="GRB"):
        self.parent = parent    # The real, physical strip (68 pixels)
        self.start = start_idx  # Start index (e.g., 64)
        self.n = num_pixels          # Length (e.g., 4)
        self.pixel_order = pixel_order
        if self.pixel_order == "RGB":
            self.custom_order = True
            self.color_order = (1, 0, 2)
        else:
            self.custom_order = False

    def _reorder_color(self, color):
        """Reorders the color tuple based on the pixel order."""
        if self.custom_order:
            return tuple(color[i] for i in self.color_order)
        return color

    def __setitem__(self, index, color):
        """Sets a specific pixel in the segment."""
        # Maps slice index [0] to parent index [start + 0]
        if index < 0 or index >= self.n:
            return
        if self.custom_order:
            self.parent[self.start + index] = self._reorder_color(color)
        else:
            self.parent[self.start + index] = color


    def __getitem__(self, index):
        """Gets a specific pixel from the segment."""
        if index < 0 or index >= self.n:
            return (0,0,0)
        if self.custom_order:
            return self._reorder_color(self.parent[self.start + index])
        return self.parent[self.start + index]

    def __len__(self):
        """Returns the number of pixels in this segment."""
        return self.n

    def fill(self, color):
        """Fills the entire segment with a single color."""
        for i in range(self.start, self.start + self.n):
            if self.custom_order:
                self.parent[i] = self._reorder_color(color)
            else:
                self.parent[i] = color

    def show(self):
        """Updates the segment's buffer memory only.

        Note: Hardware write is now centralized in CoreManager.render_loop().
        This method is kept for API compatibility but no longer triggers hardware writes.
        """
        # Memory buffer is already updated via __setitem__ and fill()
        # No hardware write needed - render loop handles that
        pass
