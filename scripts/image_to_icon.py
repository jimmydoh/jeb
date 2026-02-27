"""
Script to convert an image into a 16x16 icon using the JEB Palette.
Outputs either Python code or a .bin file.

Usage:
    python emoji_to_icon.py shield.png SHIELD --autocrop --pad
    python emoji_to_icon.py assets/emojis/shield.png SHIELD --autocrop --pad --bin
"""

import argparse
import math
import os
from PIL import Image

# The JEB Palette Library
JEB_PALETTE = {
    0: (0, 0, 0), 1: (30, 30, 30), 2: (100, 100, 100), 3: (180, 180, 180), 4: (255, 255, 255),
    10: (100, 0, 0), 11: (255, 0, 0), 12: (255, 80, 80), 13: (255, 180, 180), 14: (255, 50, 50),
    20: (90, 45, 0), 21: (255, 120, 0), 22: (255, 200, 0), 23: (255, 220, 180), 24: (255, 180, 50),
    30: (100, 100, 0), 31: (255, 255, 0), 32: (255, 255, 150), 33: (255, 240, 200), 34: (255, 255, 200),
    40: (0, 80, 0), 41: (0, 200, 0), 42: (100, 255, 50), 43: (180, 255, 180), 44: (150, 255, 100),
    50: (0, 100, 100), 51: (0, 200, 200), 52: (100, 255, 255), 53: (200, 255, 255), 54: (180, 255, 255),
    60: (0, 0, 80), 61: (0, 0, 255), 62: (60, 100, 255), 63: (180, 180, 255), 64: (100, 150, 255),
    70: (60, 0, 100), 71: (200, 0, 200), 72: (200, 100, 255), 73: (230, 180, 255), 74: (255, 100, 255)
}

def color_distance(c1, c2):
    """Calculates Euclidean distance between two RGB colors."""
    return math.sqrt((c1[0] - c2[0])**2 + (c1[1] - c2[1])**2 + (c1[2] - c2[2])**2)

def find_closest_palette_color(rgb):
    """Finds the ID of the closest matching color in the JEB palette."""
    closest_id = 1  # Default to Charcoal if nothing matches
    min_dist = float('inf')

    for pal_id, pal_rgb in JEB_PALETTE.items():
        if pal_id == 0:
            continue

        dist = color_distance(rgb, pal_rgb)
        if dist < min_dist:
            min_dist = dist
            closest_id = pal_id

    return closest_id

def generate_icon(image_path, icon_name="NEW_EMOJI", pad=False, pad_color=0, autocrop=False, export_bin=False):
    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"Error opening image: {e}")
        return

    if autocrop:
        alpha_channel = img.split()[-1]
        bbox = alpha_channel.getbbox()
        if bbox:
            img = img.crop(bbox)

    img_size = 14 if pad else 16
    img = img.resize((img_size, img_size), Image.Resampling.LANCZOS)
    pixels = img.load()

    # Collect flat data regardless of export method
    flat_data = []

    for y in range(16):
        for x in range(16):
            if pad and (x == 0 or x == 15 or y == 0 or y == 15):
                flat_data.append(pad_color)
            else:
                sample_x = x - 1 if pad else x
                sample_y = y - 1 if pad else y

                r, g, b, a = pixels[sample_x, sample_y]

                if a < 128:
                    flat_data.append(0)
                else:
                    flat_data.append(find_closest_palette_color((r, g, b)))

    # Output routing
    if export_bin:
        out_dir = os.path.dirname(os.path.abspath(image_path))
        out_file = os.path.join(out_dir, f"{icon_name.lower()}.bin")

        with open(out_file, "wb") as f:
            f.write(bytes(flat_data))
        print(f"✅ Generated binary asset: {out_file} ({len(flat_data)} bytes)")
    else:
        print(f"    {icon_name} = bytes([")
        for i in range(16):
            # Slice the flat array into rows of 16 for readable formatting
            row = flat_data[i*16 : (i+1)*16]
            formatted_row = ", ".join(f"{val:>2}" for val in row) + ","
            print(f"        {formatted_row}")
        print("    ])")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert an image to a 16x16 JEB Palette Icon.")
    parser.add_argument("image_path", help="Path to the source image file.")
    parser.add_argument("icon_name", nargs="?", default="NEW_EMOJI", help="Name of the exported asset.")
    parser.add_argument("--pad", action="store_true", help="Squish the image to 14x14 and add a 1-pixel border.")
    parser.add_argument("--pad-color", type=int, default=0, help="The Palette ID to use for the border (default: 0/OFF).")
    parser.add_argument("--autocrop", action="store_true", help="Automatically crop out transparent margins before scaling.")
    parser.add_argument("--bin", action="store_true", help="Export to a .bin file next to the source image instead of printing Python code.")

    args = parser.parse_args()

    generate_icon(
        args.image_path,
        args.icon_name,
        args.pad,
        args.pad_color,
        args.autocrop,
        args.bin
    )
