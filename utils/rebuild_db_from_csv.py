#!/usr/bin/env python3
"""
Rebuild evaluations.db and users.db from evaluations.csv and users.csv.

CSV files should be in the project root (same directory as config.py).
Use the CSVs produced by tests/test_db_validation.py (dump_evaluations_to_csv,
dump_users_to_csv) or equivalent.

Usage:
  python utils/rebuild_db_from_csv.py
  # One run: rewrites image_path (remote prefix -> local IMAGE_DIR) and .jpg -> .png.
  python utils/rebuild_db_from_csv.py --evaluations-csv path/to/evaluations.csv --users-csv path/to/users.csv
  # Use --no-image-path-rewrite to disable path and .png normalization.
"""

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import (
    BASE_DIR,
    USERS_DB_PATH,
    EVALUATIONS_DB_PATH,
    CSV_ENCODING,
    IMAGE_DIR,
)

# Default old prefix to replace when migrating from common remote paths (e.g. Ubuntu server).
# Enables path + .png normalization in one run without passing --image-path-old-prefix.
DEFAULT_IMAGE_PATH_OLD_PREFIX = "/home/ubuntu/workspace/image_voting_system/all_images"

# Schema: columns we write into the rebuilt DB (must match storage.py)
EVALUATIONS_TABLE_SCHEMA = """
CREATE TABLE evaluations(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    user_id TEXT,
    user_age INTEGER,
    user_gender TEXT,
    user_education TEXT,
    poem_title TEXT,
    image_path TEXT,
    image_type TEXT,
    q1_1_right_answer TEXT,
    phase1_response_ms INTEGER,
    answers_json TEXT,
    phase2_response_ms INTEGER,
    total_response_ms INTEGER
)
"""

EVALUATIONS_COLUMNS = [
    "id", "ts", "user_id", "user_age", "user_gender", "user_education",
    "poem_title", "image_path", "image_type", "q1_1_right_answer",
    "phase1_response_ms", "answers_json", "phase2_response_ms", "total_response_ms",
]

INTEGER_EVAL_COLUMNS = {"id", "user_age", "phase1_response_ms", "phase2_response_ms", "total_response_ms"}

USERS_TABLE_SCHEMA = """
CREATE TABLE users(
    user_id TEXT PRIMARY KEY,
    user_age INTEGER,
    user_gender TEXT,
    user_education TEXT,
    user_limit INTEGER,
    created_at TEXT,
    seen_titles TEXT,
    seen_paths TEXT
)
"""

USERS_COLUMNS = [
    "user_id", "user_age", "user_gender", "user_education",
    "user_limit", "created_at", "seen_titles", "seen_paths",
]

INTEGER_USER_COLUMNS = {"user_age", "user_limit"}


def _coerce_value(value: str, col: str, integer_columns: set):
    """Convert CSV string to DB value; empty string -> None, int columns -> int or None."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return None
    if col in integer_columns:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None
    return value


def _rewrite_image_path(path: str, old_prefix: str, new_prefix: str) -> str:
    """If path starts with old_prefix, replace with new_prefix; otherwise return path unchanged."""
    if not path or not old_prefix or not new_prefix:
        return path
    path = path.strip()
    old = old_prefix.rstrip("/")
    if path.startswith(old + "/") or path == old:
        suffix = path[len(old) :].lstrip("/")
        return str(Path(new_prefix.rstrip("/")) / suffix) if suffix else str(Path(new_prefix))
    return path


def _jpg_to_png(path: str) -> str:
    """Replace .jpg extension with .png so paths match local catalog (e.g. converted images)."""
    if not path or not path.strip():
        return path
    path = path.strip()
    if path.lower().endswith(".jpg"):
        return path[:-4] + ".png"
    return path


def rebuild_evaluations(
    csv_path: Path,
    db_path: Path,
    image_path_old_prefix: str = "",
    image_path_new_prefix: str = "",
) -> int:
    """Drop evaluations table, recreate it, and load rows from CSV. Returns row count.
    If image_path_old_prefix and image_path_new_prefix are set, rewrite image_path
    so paths from another machine use the local prefix.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS evaluations")
    conn.execute(EVALUATIONS_TABLE_SCHEMA.strip())
    conn.commit()

    if not csv_path.exists():
        print(f"[SKIP] {csv_path} not found; evaluations table created empty.")
        conn.close()
        return 0

    with open(csv_path, "r", newline="", encoding=CSV_ENCODING) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"[OK] evaluations: 0 rows (empty CSV)")
        conn.close()
        return 0

    placeholders = ",".join("?" * len(EVALUATIONS_COLUMNS))
    insert_sql = f"INSERT INTO evaluations ({','.join(EVALUATIONS_COLUMNS)}) VALUES ({placeholders})"
    count = 0
    for row in rows:
        values = [
            _coerce_value(row.get(col), col, INTEGER_EVAL_COLUMNS)
            for col in EVALUATIONS_COLUMNS
        ]
        # Rewrite image_path: optional prefix replacement, then .jpg -> .png
        if "image_path" in EVALUATIONS_COLUMNS:
            idx = EVALUATIONS_COLUMNS.index("image_path")
            raw = row.get("image_path") or ""
            if image_path_old_prefix and image_path_new_prefix:
                raw = _rewrite_image_path(
                    raw, image_path_old_prefix, image_path_new_prefix
                )
            raw = _jpg_to_png(raw)
            values[idx] = _coerce_value(raw, "image_path", set())
        conn.execute(insert_sql, values)
        count += 1

    conn.commit()
    conn.close()
    print(f"[OK] evaluations: loaded {count} rows from {csv_path} -> {db_path}")
    return count


def rebuild_users(csv_path: Path, db_path: Path) -> int:
    """Drop users table, recreate it, and load rows from CSV. Returns row count."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS users")
    conn.execute(USERS_TABLE_SCHEMA.strip())
    conn.commit()

    if not csv_path.exists():
        print(f"[SKIP] {csv_path} not found; users table created empty.")
        conn.close()
        return 0

    with open(csv_path, "r", newline="", encoding=CSV_ENCODING) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print(f"[OK] users: 0 rows (empty CSV)")
        conn.close()
        return 0

    placeholders = ",".join("?" * len(USERS_COLUMNS))
    insert_sql = f"INSERT OR REPLACE INTO users ({','.join(USERS_COLUMNS)}) VALUES ({placeholders})"
    count = 0
    for row in rows:
        values = [
            _coerce_value(row.get(col), col, INTEGER_USER_COLUMNS)
            for col in USERS_COLUMNS
        ]
        conn.execute(insert_sql, values)
        count += 1

    conn.commit()
    conn.close()
    print(f"[OK] users: loaded {count} rows from {csv_path} -> {db_path}")
    return count


def main():
    parser = argparse.ArgumentParser(description="Rebuild DB from evaluations.csv and users.csv")
    parser.add_argument(
        "--evaluations-csv",
        type=Path,
        default=BASE_DIR / "evaluations.csv",
        help="Path to evaluations.csv",
    )
    parser.add_argument(
        "--users-csv",
        type=Path,
        default=BASE_DIR / "users.csv",
        help="Path to users.csv",
    )
    parser.add_argument(
        "--evaluations-db",
        type=Path,
        default=EVALUATIONS_DB_PATH,
        help="Path to evaluations.db",
    )
    parser.add_argument(
        "--users-db",
        type=Path,
        default=USERS_DB_PATH,
        help="Path to users.db",
    )
    parser.add_argument(
        "--image-path-old-prefix",
        type=str,
        default="",
        help="Prefix of image_path in CSV to replace (default: common Ubuntu path if unset)",
    )
    parser.add_argument(
        "--image-path-new-prefix",
        type=str,
        default="",
        help="Local prefix to use for image_path (default: local IMAGE_DIR from config)",
    )
    parser.add_argument(
        "--no-image-path-rewrite",
        action="store_true",
        help="Disable automatic path and .jpg->.png rewrite for image_path",
    )
    args = parser.parse_args()

    # Apply path + png in one go: use provided old prefix or default, new prefix = local IMAGE_DIR
    if args.no_image_path_rewrite:
        old_prefix = ""
        new_prefix = ""
    else:
        old_prefix = args.image_path_old_prefix or DEFAULT_IMAGE_PATH_OLD_PREFIX
        new_prefix = args.image_path_new_prefix or str(IMAGE_DIR)
    n_eval = rebuild_evaluations(
        args.evaluations_csv,
        args.evaluations_db,
        image_path_old_prefix=old_prefix,
        image_path_new_prefix=new_prefix,
    )
    n_users = rebuild_users(args.users_csv, args.users_db)
    print(f"Done. Evaluations: {n_eval}, Users: {n_users}")


if __name__ == "__main__":
    main()
