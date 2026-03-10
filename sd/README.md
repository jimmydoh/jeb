# SD Card Assets

This directory contains static assets that are loaded from the SD card at runtime.

## Required Files

### `font5x8.bin`

Required for matrix text scrolling (`MatrixManager.display_text()`).

This is the standard Adafruit 5×8 pixel bitmap font used by `adafruit_pixel_framebuf`.

**To obtain:** Copy `font5x8.bin` from the
[Adafruit CircuitPython framebuf](https://github.com/adafruit/Adafruit_CircuitPython_framebuf)
repository (it ships alongside the library) to this directory and to the root
of your `CIRCUITPY` drive.
