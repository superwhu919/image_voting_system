#!/usr/bin/env python3
"""
Export image paths that have >= 5 ratings to a CSV file.

Reads from evaluations.db (or optional evaluations CSV). Output CSV has columns:
  image_path, rating_count
"""
import csv
import sqlite3
import sys
from pathlib import Path
from typing import Optional

# Project root = parent of check-tb
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
EVALUATIONS_DB = PROJECT_ROOT / "evaluations.db"
DEFAULT_OUTPUT = SCRIPT_DIR / "images_with_5_plus_ratings.csv"
DEFAULT_LOCAL_IMAGES = PROJECT_ROOT / "all_images"


def _path_for_output(image_path: str, replace_with_dir: Optional[Path]) -> str:
    """Return image_path unchanged or replaced with local dir + basename."""
    if replace_with_dir is None:
        return image_path
    return str(replace_with_dir / Path(image_path).name)


def from_db(
    db_path: Path,
    output_path: Path,
    min_ratings: int = 5,
    replace_with_dir: Optional[Path] = None,
) -> int:
    """Query evaluations.db and write image_paths with count >= min_ratings."""
    if not db_path.exists():
        print(f"Error: DB not found: {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        """
        SELECT image_path, COUNT(*) AS rating_count
        FROM evaluations
        WHERE image_path IS NOT NULL AND image_path != ''
        GROUP BY image_path
        HAVING rating_count >= ?
        ORDER BY rating_count DESC, image_path
        """,
        (min_ratings,),
    ).fetchall()
    conn.close()
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_path", "rating_count"])
        for path, count in rows:
            w.writerow([_path_for_output(path, replace_with_dir), count])
    return len(rows)


def from_csv(
    csv_path: Path,
    output_path: Path,
    min_ratings: int = 5,
    replace_with_dir: Optional[Path] = None,
) -> int:
    """Aggregate evaluations CSV and write image_paths with count >= min_ratings."""
    import pandas as pd
    if not csv_path.exists():
        print(f"Error: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)
    df = pd.read_csv(csv_path)
    if "image_path" not in df.columns:
        print("Error: CSV must have column 'image_path'", file=sys.stderr)
        sys.exit(1)
    counts = df.groupby("image_path").size().reset_index(name="rating_count")
    ge = counts[counts["rating_count"] >= min_ratings].sort_values(
        ["rating_count", "image_path"], ascending=[False, True]
    )
    if replace_with_dir is not None:
        ge = ge.copy()
        ge["image_path"] = ge["image_path"].map(
            lambda p: _path_for_output(str(p), replace_with_dir)
        )
    ge.to_csv(output_path, index=False, encoding="utf-8")
    return len(ge)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Export image paths with >= 5 ratings to CSV")
    parser.add_argument("--db", type=Path, default=EVALUATIONS_DB, help="Path to evaluations.db")
    parser.add_argument("--csv", type=Path, default=None, help="Use evaluations CSV instead of DB")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path")
    parser.add_argument("--min", type=int, default=5, help="Minimum rating count (default: 5)")
    parser.add_argument(
        "--replace-path",
        action="store_true",
        help="Replace image_path with local path (basename under --local-dir)",
    )
    parser.add_argument(
        "--local-dir",
        type=Path,
        default=DEFAULT_LOCAL_IMAGES,
        help="Directory used when --replace-path (default: project all_images)",
    )
    args = parser.parse_args()
    replace_with = args.local_dir if args.replace_path else None
    if args.csv is not None:
        n = from_csv(args.csv, args.output, args.min, replace_with_dir=replace_with)
        print(f"From CSV: wrote {n} image paths to {args.output}")
    else:
        n = from_db(args.db, args.output, args.min, replace_with_dir=replace_with)
        print(f"From DB: wrote {n} image paths to {args.output}")


if __name__ == "__main__":
    main()
