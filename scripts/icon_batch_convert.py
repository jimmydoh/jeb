import os
import glob
import subprocess
import sys

# Configuration
SOURCE_DIR = "source_emojis"
OUTPUT_FILE = "generated_icons.py"

def main():
    # 1. Ensure the source directory exists
    if not os.path.exists(SOURCE_DIR):
        os.makedirs(SOURCE_DIR)
        print(f"📁 Created folder '{SOURCE_DIR}'.")
        print("Please drop your transparent emoji PNGs into this folder and run the script again!")
        sys.exit(0)

    # 2. Find all PNGs
    png_files = glob.glob(os.path.join(SOURCE_DIR, "*.png"))

    if not png_files:
        print(f"⚠️ No PNG files found in '{SOURCE_DIR}'.")
        sys.exit(0)

    print(f"🚀 Found {len(png_files)} images. Starting batch conversion...\n")

    # 3. Process and write to output file
    with open(OUTPUT_FILE, "w") as f:
        # Add a helpful header and a class wrapper so it's ready to paste into icons.py
        f.write('"""Auto-generated JEB Icons."""\n\n')
        f.write("class GeneratedIcons:\n")

        for filepath in png_files:
            # Extract just the filename (e.g., "skull.png" -> "SKULL")
            basename = os.path.basename(filepath)
            icon_name = os.path.splitext(basename)[0].upper()

            # Clean up names with spaces or dashes so they are valid Python variables
            icon_name = icon_name.replace(" ", "_").replace("-", "_")

            print(f"   Converting {basename} -> {icon_name}...")

            # Call the converter script using subprocess
            result = subprocess.run(
                [sys.executable, ".\\image_to_icon.py", filepath, icon_name, "--autocrop", "--pad"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                f.write(result.stdout)
                f.write("\n")
            else:
                print(f"❌ Error converting {basename}:\n{result.stderr}")

    print(f"\n✅ Done! All icons have been compiled into '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    main()
