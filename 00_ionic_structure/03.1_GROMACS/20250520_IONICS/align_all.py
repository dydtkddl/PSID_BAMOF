import os
import sys
import subprocess
from pathlib import Path

def run_align_in_subdirs(base_dir):
    base_path = Path(base_dir).resolve()
    if not base_path.is_dir():
        print(f"[ERR] Provided path is not a directory: {base_dir}")
        return

    for sub in sorted(base_path.iterdir())[:50]:
        if sub.is_dir():
            try:
                print(f"\n[▶] Entering {sub}")
                subprocess.run(["python", "../../align_coords.py"], cwd=sub, check=True)
                print(f"[✓] Completed {sub.name}")
            except subprocess.CalledProcessError:
                print(f"[✗] Error in {sub.name} — skipping...")
            except Exception as e:
                print(f"[✗] Unexpected error in {sub.name}: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_align_all.py <base_directory>")
        sys.exit(1)

    run_align_in_subdirs(sys.argv[1])