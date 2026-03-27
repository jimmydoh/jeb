# `.janim` Animation Format Specification (V2)

The `.janim` (JEB Animation) file is a lightweight, custom binary format designed for the JEB Pixel Art Studio. It stores multi-frame, 16x16 pixel art animations with variable frame durations for playback on the hardware LED matrix.

**Endianness:** All multi-byte integers (16-bit) are stored in **Little-Endian** format.
**Encoding:** Raw Binary (No text encoding)

---

## 1. Global Header (5 Bytes)

Every `.janim` file begins with a 5-byte global header that defines the animation parameters.

| Byte Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `0x00` - `0x03` | `char[]` | 4 bytes | **Magic Bytes:** `JANM` (`0x4A`, `0x41`, `0x4E`, `0x4D`) |
| `0x04`      | `uint8` | 1 byte  | **Frame Count:** Total number of frames in the animation (`1-255`) |

---

## 2. Frame Data Blocks

Immediately following the global header are the frame data blocks. There will be exactly `Frame Count` blocks appended consecutively. Each block is exactly **258 bytes** long and dictates the frame's duration and pixel state.

| Block Offset | Type    | Size    | Description |
| :--- | :--- | :--- | :--- |
| `+0x00` - `+0x01` | `uint16` | 2 bytes | **Duration:** Frame hold time in milliseconds (`ms`). |
| `+0x02` - `+0x101` | `uint8[]` | 256 bytes | **Pixel Data:** 16x16 grid of palette indices, stored row-major (top-left to bottom-right). |

*(Note: The total file size can always be calculated as `5 + (Frame Count * 258)` bytes).*

---

## 3. Data Value Mappings

### 3.1 Pixel Data (Palette Indices)
The 256-byte pixel array dictates the color of each LED on the 16x16 matrix. Each `uint8` value maps to the standard JEB hardware palette:
* `0` = `OFF` (Black / Unlit)
* `1` - `4` = Grayscale (`1`=Charcoal, `2`=Gray, `3`=Silver, `4`=White)
* `11`, `21`, `31` = Warm (`11`=Red, `21`=Orange, `31`=Yellow)
* `41`, `51`, `61` = Cool (`41`=Green, `51`=Cyan, `61`=Blue)
* `71` = `MAGENTA`

*(See `Palette.LIBRARY` in the core utilities for the complete 40-color index mapping).*
