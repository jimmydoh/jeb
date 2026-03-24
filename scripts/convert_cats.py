import os
import sys

# Ensure we can import the Icons class from the source tree
from utilities.icons import Icons

def create_janim_v2(filepath, frames_data, timings):
    """Packages frames and variable timings into a .janim V2 file."""
    frame_count = len(frames_data)

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'wb') as f:
        # Write the 5-byte V2 header (JANM + frame_count)
        f.write(b'JANM')
        f.write(bytes([frame_count]))

        # Write interleaved duration and frame data
        for i in range(frame_count):
            duration_ms = timings[i]

            # Write 2-byte duration (16-bit unsigned little-endian)
            f.write(duration_ms.to_bytes(2, byteorder='little', signed=False))

            # Write the 256 bytes of pixel data
            f.write(frames_data[i])

    print(f"Saved: {filepath} | Frames: {frame_count} | Timings (ms): {timings}")

if __name__ == "__main__":
    print("Extracting animations to .janim V2 format...")

    # ========================================================
    # 1. Convert CAT_WALK
    # ========================================================
    walk_data = Icons.CAT_WALK
    walk_frames = [
        walk_data[0:256],
        walk_data[256:512]
    ]
    walk_timings = Icons.CAT_WALK_TIMING  # (300, 300)

    create_janim_v2("sd/icons/cat_walk.janim", walk_frames, walk_timings)

    # ========================================================
    # 2. Convert CAT_IDLE
    # ========================================================
    idle_data = Icons.CAT_IDLE_ANIMATED
    idle_frames = [
        idle_data[0:256],
        idle_data[256:512],
        idle_data[512:768],
        idle_data[768:1024]
    ]
    idle_timings = Icons.CAT_IDLE_TIMING  # (2000, 150, 150, 150)

    create_janim_v2("sd/icons/cat_idle.janim", idle_frames, idle_timings)

    print("\nDone! V2 files generated.")
