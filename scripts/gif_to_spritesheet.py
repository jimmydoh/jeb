import os
import argparse
from PIL import Image, ImageSequence

def convert_gif_to_spritesheet(input_path, output_path=None, target_width=128, target_height=64):
    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' not found.")
        return

    if output_path is None:
        # Default to the same folder, same name, .bmp extension
        base_name = os.path.splitext(input_path)[0]
        output_path = f"{base_name}_spritesheet.bmp"

    try:
        with Image.open(input_path) as img:
            frames = []

            print(f"Processing '{input_path}'...")

            # Iterate through each frame in the GIF
            for i, frame in enumerate(ImageSequence.Iterator(img)):
                # 1. Convert to RGBA to handle any transparency properly
                frame_rgba = frame.convert("RGBA")

                # 2. Resize to force the 128x64 OLED dimensions (uses nearest neighbor for sharp pixels)
                frame_resized = frame_rgba.resize((target_width, target_height), Image.Resampling.NEAREST)

                # 3. Create a solid black background (pixels 'off' on OLED)
                bg = Image.new("RGBA", (target_width, target_height), (0, 0, 0, 255))

                # 4. Composite the frame over the black background
                bg.paste(frame_resized, (0, 0), frame_resized)

                # 5. Convert to 1-bit black and white (dithered)
                final_frame = bg.convert("1")
                frames.append(final_frame)

            frame_count = len(frames)
            if frame_count == 0:
                print("No frames found in the GIF.")
                return

            sheet_height = target_height * frame_count
            print(f"Extracted {frame_count} frames. Creating a {target_width}x{sheet_height} sprite sheet...")

            # Create the final vertical canvas (1-bit mode)
            spritesheet = Image.new("1", (target_width, sheet_height))

            # Paste each frame vertically
            for index, f in enumerate(frames):
                y_offset = index * target_height
                spritesheet.paste(f, (0, y_offset))

            # Save as BMP
            spritesheet.save(output_path, format="BMP")
            print(f"Success! Saved to: {output_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert a GIF to a 1-bit vertical BMP sprite sheet for OLEDs.")
    parser.add_argument("input_gif", help="Path to the input .gif file")
    parser.add_argument("-o", "--output", help="Path to save the output .bmp file (optional)", default=None)
    parser.add_argument("-w", "--width", type=int, help="Target width per frame (default: 128)", default=128)
    parser.add_argument("-t", "--height", type=int, help="Target height per frame (default: 64)", default=64)

    args = parser.parse_args()

    convert_gif_to_spritesheet(args.input_gif, args.output, args.width, args.height)
