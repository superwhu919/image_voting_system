#!/usr/bin/env python3
"""
Investigate duplicate (user, image) / (user, poem) and rating distribution.

Uses evaluations.db only (and catalog for total image count). No changes to app code.

Findings:
1. Duplicate images/poems: list (user, image_path or poem) with count and timestamps;
   compute time delta between first and second evaluation to detect concurrent requests.
2. Rating distribution: for each image with 2+ evaluations, break down by
   unique users vs same-user multiple (duplicate submissions inflate count).
3. Catalog coverage: total images in catalog vs images with at least one evaluation.
"""

import argparse
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import EVALUATIONS_DB_PATH, USERS_DB_PATH


def _parse_ts(s: str):
    """Parse ISO-like ts to datetime; truncate to 6 fractional seconds for strptime."""
    s = (s or "").replace("Z", "").strip()
    if not s:
        return None
    if "." in s:
        base, frac = s.split(".", 1)
        frac = (frac + "000000")[:6]  # strptime %f expects max 6 digits
        s = base + "." + frac
    else:
        s = s + ".0"
    try:
        return datetime.strptime(s[:26], "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        return None


def _format_time_delta(first_ts: str, last_ts: str) -> str:
    """Return a short note like '[TIME DELTA: 11s — likely concurrent request]' or '[TIME DELTA: 16.1 min]'."""
    if not first_ts or not last_ts or first_ts == last_ts:
        return ""
    t1, t2 = _parse_ts(first_ts), _parse_ts(last_ts)
    if t1 is None or t2 is None:
        return f"  [first_ts={first_ts}, last_ts={last_ts}]"
    delta_sec = abs((t2 - t1).total_seconds())
    if delta_sec < 120:
        return "  [TIME DELTA: %.0fs — likely concurrent request]" % delta_sec
    return "  [TIME DELTA: %.1f min]" % (delta_sec / 60.0)


def safe_print(s: str) -> None:
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("ascii", errors="replace").decode("ascii"))


def load_evals_with_ts(conn: sqlite3.Connection):
    """Return list of (user_id, image_path, poem_title, ts) ordered by ts."""
    rows = conn.execute(
        """
        SELECT user_id, image_path, poem_title, ts
        FROM evaluations
        WHERE image_path IS NOT NULL AND image_path != ''
        ORDER BY ts ASC
        """
    ).fetchall()
    return [{"user_id": r[0], "image_path": r[1], "poem_title": r[2] or "", "ts": r[3] or ""} for r in rows]


def run_duplicate_analysis(conn: sqlite3.Connection) -> None:
    """Analyze duplicate (user, image_path) and (user, poem_title) with timestamps and deltas."""
    safe_print("\n" + "=" * 60)
    safe_print("1. DUPLICATE (USER, IMAGE) AND (USER, POEM)")
    safe_print("=" * 60)

    # Duplicate images per user
    dup_images = conn.execute(
        """
        SELECT user_id, image_path, COUNT(*) as cnt,
               MIN(ts) as first_ts, MAX(ts) as last_ts
        FROM evaluations
        WHERE image_path IS NOT NULL AND image_path != ''
        GROUP BY user_id, image_path
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, user_id
        """
    ).fetchall()

    if not dup_images:
        safe_print("[OK] No duplicate (user, image_path) found.")
    else:
        safe_print(f"[WARNING] Found {len(dup_images)} (user, image_path) with count > 1:\n")
        for user_id, image_path, cnt, first_ts, last_ts in dup_images:
            delta_note = _format_time_delta(first_ts or "", last_ts or "")
            short_path = image_path.split("/")[-1] if "/" in image_path else image_path
            safe_print(f"   User: {user_id}, Image: {short_path}, Count: {cnt}{delta_note}")

    # Duplicate poems per user
    dup_poems = conn.execute(
        """
        SELECT user_id, poem_title, COUNT(*) as cnt,
               MIN(ts) as first_ts, MAX(ts) as last_ts
        FROM evaluations
        WHERE poem_title IS NOT NULL AND poem_title != ''
        GROUP BY user_id, poem_title
        HAVING COUNT(*) > 1
        ORDER BY cnt DESC, user_id
        """
    ).fetchall()

    if not dup_poems:
        safe_print("\n[OK] No duplicate (user, poem_title) found.")
    else:
        safe_print(f"\n[WARNING] Found {len(dup_poems)} (user, poem_title) with count > 1:\n")
        for user_id, poem_title, cnt, first_ts, last_ts in dup_poems:
            delta_note = _format_time_delta(first_ts or "", last_ts or "")
            safe_print(f"   User: {user_id}, Poem: {poem_title}, Count: {cnt}{delta_note}")


def run_rating_breakdown(conn: sqlite3.Connection) -> None:
    """
    For each image with 2+ evaluations, break down:
    - How many evaluations from distinct users?
    - How many from same user (duplicate) — inflates rating count.
    """
    safe_print("\n" + "=" * 60)
    safe_print("2. RATING DISTRIBUTION: UNIQUE USERS vs SAME-USER DUPLICATES")
    safe_print("=" * 60)

    # Per image: list of (user_id, count of evaluations by that user)
    image_user_counts = defaultdict(lambda: defaultdict(int))
    rows = conn.execute(
        """
        SELECT image_path, user_id
        FROM evaluations
        WHERE image_path IS NOT NULL AND image_path != ''
        """
    ).fetchall()
    for image_path, user_id in rows:
        image_user_counts[image_path][user_id] += 1

    # Summarize
    total_evals = 0
    total_unique_images = 0
    images_with_duplicate_submissions = 0
    evals_that_are_duplicates = 0  # extra evals beyond first per (image, user)
    by_unique_users = defaultdict(int)  # k = number of unique users -> number of images

    for image_path, user_counts in image_user_counts.items():
        total_unique_images += 1
        n_evals = sum(user_counts.values())
        total_evals += n_evals
        n_unique_users = len(user_counts)
        by_unique_users[n_unique_users] += 1
        # Duplicate = any user has more than 1 evaluation for this image
        dup_users = [u for u, c in user_counts.items() if c > 1]
        if dup_users:
            images_with_duplicate_submissions += 1
            for u, c in user_counts.items():
                if c > 1:
                    evals_that_are_duplicates += (c - 1)

    safe_print(f"Total unique images in evaluations: {total_unique_images}")
    safe_print(f"Total evaluations: {total_evals}")
    safe_print(f"Images that have at least one same-user duplicate: {images_with_duplicate_submissions}")
    safe_print(f"Evaluations that are 'extra' (same user, same image): {evals_that_are_duplicates}")
    safe_print("\nDistribution of images by number of unique evaluators:")
    for k in sorted(by_unique_users.keys()):
        safe_print(f"  {k} unique user(s): {by_unique_users[k]} images")

    # Rating count distribution (like test_db_validation): 1 eval, 2 evals, ...
    rating_dist = defaultdict(int)
    for image_path, user_counts in image_user_counts.items():
        n_evals = sum(user_counts.values())
        rating_dist[n_evals] += 1
    safe_print("\nRating count distribution (evaluations per image, including duplicates):")
    for cnt in sorted(rating_dist.keys(), reverse=True):
        safe_print(f"  {cnt} evaluations: {rating_dist[cnt]} images")


def run_catalog_coverage(conn: sqlite3.Connection) -> None:
    """Compare catalog size vs images that have at least one evaluation."""
    safe_print("\n" + "=" * 60)
    safe_print("3. CATALOG COVERAGE (images with 0 vs 1+ evaluations)")
    safe_print("=" * 60)

    try:
        from data_logic.catalog import CATALOG
        total_catalog = len(CATALOG)
    except Exception as e:
        safe_print(f"[SKIP] Could not load catalog: {e}")
        return

    evaluated_paths = set(
        row[0] for row in conn.execute(
            "SELECT DISTINCT image_path FROM evaluations WHERE image_path IS NOT NULL AND image_path != ''"
        ).fetchall()
    )
    # Catalog keys might be full path; evaluations might store same or different path (e.g. .jpg vs .png)
    # Normalize to basename for comparison if needed
    total_evaluated = len(evaluated_paths)
    not_in_evals = total_catalog - total_evaluated
    if not_in_evals < 0:
        # Evaluations might have paths not in current catalog (e.g. different machine path)
        not_in_evals = 0
    safe_print(f"Total images in catalog: {total_catalog}")
    safe_print(f"Unique images in evaluations: {total_evaluated}")
    safe_print(f"Catalog images with 0 evaluations (never shown): {total_catalog - total_evaluated}")


def main():
    parser = argparse.ArgumentParser(description="Investigate duplicates and rating distribution")
    parser.add_argument("--db", type=Path, default=EVALUATIONS_DB_PATH, help="Path to evaluations.db")
    parser.add_argument("--no-catalog", action="store_true", help="Skip catalog coverage (no catalog load)")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"[ERROR] DB not found: {args.db}")
        return 1

    conn = sqlite3.connect(str(args.db))
    try:
        run_duplicate_analysis(conn)
        run_rating_breakdown(conn)
        if not args.no_catalog:
            run_catalog_coverage(conn)
    finally:
        conn.close()

    safe_print("\n" + "=" * 60)
    safe_print("ROOT CAUSE HYPOTHESIS (see design doc or code comments)")
    safe_print("=" * 60)
    safe_print("""
- Duplicate (user, image) / (user, poem): seen_titles is only persisted on SUBMIT.
  If the same user triggers get_next_image twice before either submit (e.g. two tabs,
  or two workers), both see empty/stale seen_titles and can get the same poem/image.
- Rating skew (many 1-rated, some 2–4): (1) Duplicate submissions inflate counts
  for some images. (2) Priority queue prefers low-rated images, but concurrent
  assignments and timeouts can return the same image to the queue and get it
  assigned again before other 0-rated images are shown.
""" )
    return 0


if __name__ == "__main__":
    sys.exit(main())
