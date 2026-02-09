#!/usr/bin/env python3
"""
Move images listed in images_with_5_plus_ratings.csv from all_images to finished_rating_images.

--replace: CSV has paths from another env (e.g. Ubuntu, .jpg); use basename and look in local
  all_images (tries both .jpg and .png — local is often .png). Use on Mac when CSV was exported on Ubuntu.
No --replace: CSV paths are real filesystem paths (.jpg on Ubuntu); move from that path to
  finished_rating_images. Use on Ubuntu where paths in CSV match the server.
"""
import argparse
import csv
import shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = SCRIPT_DIR / "images_with_5_plus_ratings.csv"
DEFAULT_ALL_IMAGES = SCRIPT_DIR / "all_images"
DEFAULT_FINISHED_DIR = SCRIPT_DIR / "finished_rating_images"


def _move_replace_mode(csv_path: Path, all_images: Path, finished_dir: Path) -> tuple[int, int]:
    """Use CSV path as basename only; find file in all_images (try .jpg and .png), move to finished_dir.
    CSV is from Ubuntu (.jpg); local files are often .png — we try both and keep the extension we find."""
    finished_dir.mkdir(exist_ok=True)
    moved = 0
    skipped = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            path_str = row["image_path"].strip()
            if not path_str or path_str == "image_path":
                continue
            name = Path(path_str).name
            src_jpg = all_images / name
            name_png = name[:-4] + ".png" if name.lower().endswith(".jpg") else name
            src_png = all_images / name_png
            src = None
            dest_name = name
            if src_jpg.exists():
                src = src_jpg
            elif src_png.exists():
                src = src_png
                dest_name = name_png
            if src is None:
                skipped += 1
                continue
            dest = finished_dir / dest_name
            shutil.move(str(src), str(dest))
            moved += 1
    return moved, skipped


def _move_direct_mode(csv_path: Path, finished_dir: Path) -> tuple[int, int]:
    """CSV path is the real file path; move to finished_dir (same basename)."""
    finished_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    skipped = 0
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            path_str = row["image_path"].strip()
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
        description="Move images from CSV list into finished_rating_images.",
        epilog="Use --replace on local Mac when CSV has Ubuntu paths. Omit --replace on Ubuntu.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="CSV paths are from another env; use basename and local all_images/finished_rating_images",
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to images CSV")
    parser.add_argument(
        "--all-images",
        type=Path,
        default=DEFAULT_ALL_IMAGES,
        help="Source directory (only with --replace)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_FINISHED_DIR,
        dest="finished_dir",
        help="Destination directory (finished_rating_images)",
    )
    args = parser.parse_args()

    if args.replace:
        moved, skipped = _move_replace_mode(args.csv, args.all_images, args.finished_dir)
        print(f"Moved {moved} images to {args.finished_dir} (local all_images)")
    else:
        moved, skipped = _move_direct_mode(args.csv, args.finished_dir)
        print(f"Moved {moved} images to {args.finished_dir} (paths from CSV)")
    if skipped:
        print(f"Skipped {skipped} (file not found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
