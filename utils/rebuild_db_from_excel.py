#!/usr/bin/env python3
"""
Rebuild evaluations.db from high_quality_data.xlsx and users.db from high_quality_users.xlsx.

Evaluations Excel must have columns matching the evaluations table.
Users Excel must have columns matching the users table (user_id, user_age, ...).

--local:   Excel paths are from remote Ubuntu (.jpg). Rewrite image_path to local
           IMAGE_DIR and .png. Use when running on Mac.
No --local: Running on remote Ubuntu; paths in Excel are real. No rewrite.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import EVALUATIONS_DB_PATH, IMAGE_DIR, USERS_DB_PATH

DEFAULT_EVALUATIONS_EXCEL = PROJECT_ROOT / "high_quality_data.xlsx"
DEFAULT_USERS_EXCEL = PROJECT_ROOT / "high_quality_users.xlsx"
DEFAULT_IMAGE_PATH_OLD_PREFIX = "/home/ubuntu/workspace/image_voting_system/all_images"

# Evaluations
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

# Users (match storage.py + seen_titles, seen_paths)
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


def _coerce_value(value, col: str, integer_columns: set):
    """Convert to DB value; empty -> None, int columns -> int or None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip() if value is not None else ""
    if s == "":
        return None
    if col in integer_columns:
        try:
            return int(float(s))
        except (ValueError, TypeError):
            return None
    return s


def _rewrite_image_path(path: str, old_prefix: str, new_prefix: str) -> str:
    """If path starts with old_prefix, replace with new_prefix."""
    if not path or not old_prefix or not new_prefix:
        return path
    path = path.strip()
    old = old_prefix.rstrip("/")
    if path.startswith(old + "/") or path == old:
        suffix = path[len(old) :].lstrip("/")
        return str(Path(new_prefix.rstrip("/")) / suffix) if suffix else str(Path(new_prefix))
    return path


def _jpg_to_png(path: str) -> str:
    """Replace .jpg with .png (local catalog is .png)."""
    if not path or not str(path).strip():
        return path
    path = str(path).strip()
    if path.lower().endswith(".jpg"):
        return path[:-4] + ".png"
    return path


def rebuild_evaluations(
    excel_path: Path,
    db_path: Path,
    local: bool,
) -> int:
    """Drop evaluations table, recreate it, load rows from Excel. Returns row count."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS evaluations")
    conn.execute(EVALUATIONS_TABLE_SCHEMA.strip())
    conn.commit()

    if not excel_path.exists():
        print(f"[SKIP] {excel_path} not found; evaluations table created empty.")
        conn.close()
        return 0

    df = pd.read_excel(excel_path)
    missing = [c for c in EVALUATIONS_COLUMNS if c not in df.columns]
    if missing:
        conn.close()
        raise SystemExit(f"Evaluations Excel missing columns: {missing}")

    old_prefix = DEFAULT_IMAGE_PATH_OLD_PREFIX if local else ""
    new_prefix = str(IMAGE_DIR) if local else ""

    placeholders = ",".join("?" * len(EVALUATIONS_COLUMNS))
    insert_sql = f"INSERT INTO evaluations ({','.join(EVALUATIONS_COLUMNS)}) VALUES ({placeholders})"
    count = 0
    for _, row in df.iterrows():
        values = []
        for col in EVALUATIONS_COLUMNS:
            val = row.get(col)
            if col == "image_path" and local and val is not None:
                raw = str(val).strip()
                raw = _rewrite_image_path(raw, old_prefix, new_prefix)
                raw = _jpg_to_png(raw)
                val = _coerce_value(raw, "image_path", set())
            else:
                val = _coerce_value(val, col, INTEGER_EVAL_COLUMNS)
            values.append(val)
        conn.execute(insert_sql, values)
        count += 1

    conn.commit()
    conn.close()
    print(f"[OK] evaluations: loaded {count} rows from {excel_path.name} -> {db_path}")
    return count


def rebuild_users(excel_path: Path, db_path: Path) -> int:
    """Drop users table, recreate it, load rows from Excel. Returns row count."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("DROP TABLE IF EXISTS users")
    conn.execute(USERS_TABLE_SCHEMA.strip())
    conn.commit()

    if not excel_path.exists():
        print(f"[SKIP] {excel_path} not found; users table created empty.")
        conn.close()
        return 0

    df = pd.read_excel(excel_path)
    missing = [c for c in USERS_COLUMNS if c not in df.columns]
    if missing:
        conn.close()
        raise SystemExit(f"Users Excel missing columns: {missing}")

    placeholders = ",".join("?" * len(USERS_COLUMNS))
    insert_sql = f"INSERT OR REPLACE INTO users ({','.join(USERS_COLUMNS)}) VALUES ({placeholders})"
    count = 0
    for _, row in df.iterrows():
        values = [
            _coerce_value(row.get(col), col, INTEGER_USER_COLUMNS)
            for col in USERS_COLUMNS
        ]
        conn.execute(insert_sql, values)
        count += 1

    conn.commit()
    conn.close()
    print(f"[OK] users: loaded {count} rows from {excel_path.name} -> {db_path}")
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild evaluations.db and users.db from high_quality_data.xlsx and high_quality_users.xlsx.",
        epilog="Use --local on Mac (rewrite paths to local IMAGE_DIR, .png). Omit on Ubuntu.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Excel paths are from remote; rewrite to local IMAGE_DIR and .png",
    )
    parser.add_argument(
        "--evaluations-excel",
        type=Path,
        default=DEFAULT_EVALUATIONS_EXCEL,
        help=f"Path to high_quality_data.xlsx (default: {DEFAULT_EVALUATIONS_EXCEL})",
    )
    parser.add_argument(
        "--users-excel",
        type=Path,
        default=DEFAULT_USERS_EXCEL,
        help=f"Path to high_quality_users.xlsx (default: {DEFAULT_USERS_EXCEL})",
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
    args = parser.parse_args()

    n_eval = rebuild_evaluations(
        args.evaluations_excel.resolve(),
        args.evaluations_db,
        local=args.local,
    )
    n_users = rebuild_users(args.users_excel.resolve(), args.users_db)
    print(f"Done. Evaluations: {n_eval}, Users: {n_users}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
