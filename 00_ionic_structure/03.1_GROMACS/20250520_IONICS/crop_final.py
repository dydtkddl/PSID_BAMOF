import os
import sys
import shutil
from pathlib import Path

def copy_and_rename_final_xyz(src_base_dir, dst_dir):
    src_base = Path(src_base_dir).resolve()
    dst = Path(dst_dir).resolve()

    if not src_base.is_dir():
        print(f"[ERROR] Source base directory not found: {src_base}")
        return

    if not dst.exists():
        print(f"[INFO] Destination directory not found, creating: {dst}")
        dst.mkdir(parents=True)

    for subdir in src_base.iterdir():
        if not subdir.is_dir():
            continue

        src_file = subdir / "final_coord4.xyz"
        if src_file.exists():
            new_name = f"{subdir.name}_final_coord.xyz"
            dst_file = dst / new_name
            try:
                shutil.copy2(src_file, dst_file)
                print(f"[COPY] {src_file} -> {dst_file}")
            except Exception as e:
                print(f"[ERROR] Failed to copy {src_file}: {e}")
        else:
            print(f"[SKIP] final_coord3.xyz not found in {subdir}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python copy_final_xyz.py <source_base_dir> <destination_dir>")
        sys.exit(1)

    source_dir = sys.argv[1]
    destination_dir = sys.argv[2]

    copy_and_rename_final_xyz(source_dir, destination_dir)
