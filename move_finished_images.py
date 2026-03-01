#!/usr/bin/env python3
"""
Move images from finished_rating_images back to all_images, using to_move.csv.

to_move.csv (in cwd) must have an "image_filename" column.

--local:  Use .png and local paths (script_dir/finished_rating_images, script_dir/all_images).
No --local: Use .jpg and remote paths (/home/ubuntu/.../finished_rating_images, .../all_images).
"""
import argparse
import shutil
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
CSV_PATH = Path.cwd() / "to_move.csv"
REMOTE_BASE = Path("/home/ubuntu/workspace/image_voting_system")


def _to_png(name: str) -> str:
    if name.lower().endswith(".jpg"):
        return name[:-4] + ".png"
    return name


def _to_jpg(name: str) -> str:
    if name.lower().endswith(".png"):
        return name[:-4] + ".jpg"
    return name


def main():
    parser = argparse.ArgumentParser(
        description="Move images from finished_rating_images to all_images per to_move.csv.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use .png and local paths (Mac). Omit for .jpg and remote paths (Ubuntu).",
    )
    args = parser.parse_args()

    if not CSV_PATH.exists():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig")
    if "image_filename" not in df.columns:
        raise SystemExit(f"{CSV_PATH}: no column 'image_filename'")

    names = df["image_filename"].dropna().astype(str).str.strip().unique()

    if args.local:
        finished_dir = SCRIPT_DIR / "finished_rating_images"
        all_images = SCRIPT_DIR / "all_images"
        def src_dest(name):
            f = _to_png(name)
            return finished_dir / f, all_images / f
    else:
        finished_dir = REMOTE_BASE / "finished_rating_images"
        all_images = REMOTE_BASE / "all_images"
        def src_dest(name):
            f = _to_jpg(name)
            return finished_dir / f, all_images / f

    all_images.mkdir(parents=True, exist_ok=True)
    moved = 0
    skipped = 0
    for name in names:
        if not name or name == "image_filename":
            continue
        src, dest = src_dest(name)
        if not src.exists():
            skipped += 1
            continue
        shutil.move(str(src), str(dest))
        moved += 1

    print(f"Moved {moved} from {finished_dir.name} to {all_images.name}")
    if skipped:
        print(f"Skipped {skipped} (file not found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
