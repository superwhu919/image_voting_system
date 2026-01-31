#!/usr/bin/env python3
"""
Verify whether images with 2+, 3+, 4+ ratings in evaluations.csv are due to
duplicate submissions (same user submitting the same image multiple times).

Usage:
  python utils/verify_duplicate_submissions.py
  python utils/verify_duplicate_submissions.py --evaluations-csv path/to/evaluations.csv
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import BASE_DIR, CSV_ENCODING


def main():
    parser = argparse.ArgumentParser(description="Verify duplicate submissions from evaluations.csv")
    parser.add_argument(
        "--evaluations-csv",
        type=Path,
        default=BASE_DIR / "evaluations.csv",
        help="Path to evaluations.csv",
    )
    args = parser.parse_args()
    csv_path = args.evaluations_csv

    if not csv_path.exists():
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    # image_path -> list of user_id
    by_image: dict[str, list[str]] = defaultdict(list)
    with open(csv_path, "r", newline="", encoding=CSV_ENCODING) as f:
        reader = csv.DictReader(f)
        for row in reader:
            path = (row.get("image_path") or "").strip()
            uid = (row.get("user_id") or "").strip()
            if path:
                by_image[path].append(uid)

    # Rating = number of evaluations for this image
    # Duplicate = same user_id appears more than once for this image
    rating_stats: dict[int, list[tuple[str, int, int]]] = defaultdict(list)  # rating -> [(path, n_evals, n_unique_users), ...]
    for path, user_ids in by_image.items():
        n_evals = len(user_ids)
        n_unique = len(set(user_ids))
        rating_stats[n_evals].append((path, n_evals, n_unique))

    print("=" * 60)
    print("DUPLICATE SUBMISSION VERIFICATION (evaluations.csv)")
    print("=" * 60)
    print()

    for rating in sorted(rating_stats.keys(), reverse=True):
        entries = rating_stats[rating]
        # Has duplicate = at least one image where n_evals > n_unique_users
        with_duplicates = [(p, n_ev, n_u) for p, n_ev, n_u in entries if n_ev > n_u]
        all_from_duplicates = [(p, n_ev, n_u) for p, n_ev, n_u in entries if n_ev > n_u and n_u == 1]
        all_from_different_users = [(p, n_ev, n_u) for p, n_ev, n_u in entries if n_ev == n_u]

        print(f"Images with {rating} rating(s) (total evaluations = {rating}): {len(entries)} images")
        print(f"  - All evaluations from different users (no duplicate): {len(all_from_different_users)}")
        print(f"  - Has at least one duplicate (same user submitted >1):   {len(with_duplicates)}")
        print(f"  - All {rating} evaluations from same user (pure duplicate): {len(all_from_duplicates)}")
        if with_duplicates:
            print(f"  Examples (image_path, n_evals, n_unique_users):")
            for p, n_ev, n_u in with_duplicates[:5]:
                safe_p = p.encode("utf-8", errors="replace").decode("utf-8")
                print(f"    evals={n_ev}  unique_users={n_u}  path={safe_p[:80]}...")
        if all_from_different_users and rating >= 2:
            print(f"  Examples of images with {rating} different users (no duplicate):")
            for p, n_ev, n_u in all_from_different_users[:3]:
                safe_p = p.encode("utf-8", errors="replace").decode("utf-8")
                print(f"    evals={n_ev}  unique_users={n_u}  path={safe_p[:80]}...")
        print()

    # Summary: are ALL images with 2+, 3+, 4+ ratings from duplicate submissions?
    for r in [2, 3, 4]:
        if r not in rating_stats:
            continue
        entries = rating_stats[r]
        all_duplicate = all(n_ev > n_u for _, n_ev, n_u in entries)
        any_duplicate = any(n_ev > n_u for _, n_ev, n_u in entries)
        all_different = all(n_ev == n_u for _, n_ev, n_u in entries)
        print(f"Rating {r}: All from duplicate submissions? {all_duplicate}. All from different users? {all_different}. Any duplicate? {any_duplicate}.")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
