#!/usr/bin/env python3
"""
Move images listed in high_quality_data.xlsx from all_images to finished_rating_images.

high_quality_data.xlsx is read from the current working directory by default
(so run from project root: python move_finished_images.py).
It must have an "image_path" column (e.g. /home/ubuntu/.../all_images/foo.jpg).

--local:   Excel paths are from remote (.jpg). Local images are .png only.
           Move from <script_dir>/all_images/<name>.png to <script_dir>/finished_rating_images/
No --local: Running on remote Ubuntu; paths in Excel are real (.jpg). Move to finished_rating_images.
"""
import argparse
import shutil
from pathlib import Path

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
# Default Excel: current working directory (run from project root)
DEFAULT_EXCEL = Path.cwd() / "high_quality_data.xlsx"
DEFAULT_ALL_IMAGES = SCRIPT_DIR / "all_images"
DEFAULT_FINISHED_DIR = SCRIPT_DIR / "finished_rating_images"


def _move_local(excel_path: Path, all_images: Path, finished_dir: Path) -> tuple[int, int]:
    """Excel has remote paths (.jpg); local files are .png. Use basename with .png only."""
    finished_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(excel_path)
    if "image_path" not in df.columns:
        raise SystemExit(f"{excel_path}: no column 'image_path'")
    paths = df["image_path"].dropna().astype(str).str.strip().unique()
    moved = 0
    skipped = 0
    for path_str in paths:
        if not path_str or path_str == "image_path":
            continue
        name = Path(path_str).name
        # Remote is .jpg; local is .png only
        name_png = name[:-4] + ".png" if name.lower().endswith(".jpg") else name
        src = all_images / name_png
        if not src.exists():
            skipped += 1
            continue
        dest = finished_dir / name_png
        shutil.move(str(src), str(dest))
        moved += 1
    return moved, skipped


def _move_remote(excel_path: Path, finished_dir: Path) -> tuple[int, int]:
    """Excel paths are real filesystem paths; move to finished_dir."""
    finished_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(excel_path)
    if "image_path" not in df.columns:
        raise SystemExit(f"{excel_path}: no column 'image_path'")
    paths = df["image_path"].dropna().astype(str).str.strip().unique()
    moved = 0
    skipped = 0
    for path_str in paths:
        if not path_str or path_str == "image_path":
            continue
        src = Path(path_str)
        if not src.exists():
            skipped += 1
            continue
        dest = finished_dir / src.name
        shutil.move(str(src), str(dest))
        moved += 1
    return moved, skipped


def main():
    parser = argparse.ArgumentParser(
        description="Move images from high_quality_data.xlsx into finished_rating_images.",
        epilog="Use --local on Mac (local paths, .png). Omit on Ubuntu (paths in Excel are real).",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Excel paths are from remote (.jpg); local all_images are .png only",
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=DEFAULT_EXCEL,
        help="Path to high_quality_data.xlsx (default: <cwd>/high_quality_data.xlsx)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_FINISHED_DIR,
        dest="finished_dir",
        help="Destination directory (default: finished_rating_images)",
    )
    parser.add_argument(
        "--all-images",
        type=Path,
        default=DEFAULT_ALL_IMAGES,
        help="Source directory (only with --local)",
    )
    args = parser.parse_args()

    excel_path = args.excel.resolve()
    if not excel_path.exists():
        raise SystemExit(f"Excel not found: {excel_path}")

    if args.local:
        moved, skipped = _move_local(excel_path, args.all_images, args.finished_dir)
        print(f"Moved {moved} to {args.finished_dir} (local all_images, .png only)")
    else:
        moved, skipped = _move_remote(excel_path, args.finished_dir)
        print(f"Moved {moved} to {args.finished_dir} (paths from Excel)")
    if skipped:
        print(f"Skipped {skipped} (file not found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
