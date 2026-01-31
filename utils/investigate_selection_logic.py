#!/usr/bin/env python3
"""
Investigate why image selection might assign images with 1+ ratings
while 0-rated images exist. Uses only evaluations.csv (and optionally users.csv).
No changes to application code.

Scripts:
1. Temporal: when an image got its 2nd/3rd/4th evaluation, how many images had 0 ratings?
2. Path: do we have path mismatch (same basename, different full path)?
3. Poem-seen: for users who received a 1+ rated image, how many poems had they already seen?
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config import BASE_DIR, CSV_ENCODING


def load_evaluations(csv_path: Path) -> List[dict]:
    """Load evaluations.csv; each row has user_id, image_path, poem_title, ts."""
    rows = []
    with open(csv_path, "r", newline="", encoding=CSV_ENCODING) as f:
        reader = csv.DictReader(f)
        for row in reader:
            path = (row.get("image_path") or "").strip()
            if path:
                rows.append({
                    "user_id": (row.get("user_id") or "").strip(),
                    "image_path": path,
                    "poem_title": (row.get("poem_title") or "").strip(),
                    "ts": (row.get("ts") or "").strip(),
                })
    return rows


def safe_print(s: str) -> None:
    out = s
    try:
        print(out)
    except UnicodeEncodeError:
        print(out.encode("ascii", errors="replace").decode("ascii"))


# --- 1. Temporal analysis ---
def run_temporal(rows: List[dict]) -> None:
    """
    For each evaluation, compute 'at this moment' (by ts):
    - How many images have 0 evaluations so far?
    - How many have 1, 2, 3, 4+?
    When an image gets its 2nd (3rd, 4th) evaluation, if N_zero > 0 at that moment,
    then in principle the queue could have served a 0-rated image (unless the user
    had already seen all those poems).
    """
    # Sort by ts
    sorted_rows = sorted(rows, key=lambda r: r["ts"])
    # At each step, count evaluations per image so far
    image_count: dict[str, int] = defaultdict(int)
    n_images_with_0 = 0
    n_images_with_1_plus = 0
    total_images_so_far: set[str] = set()

    # We don't know catalog size from CSV; we only see images that appear in evaluations.
    # So "images with 0" at time T = images that will eventually appear in evaluations
    # but have 0 evaluations before T. So: all image_path that appear in evaluations,
    # minus those that have count >= 1 before this row.
    all_image_paths = set(r["image_path"] for r in rows)
    total_images = len(all_image_paths)

    events = []  # (ts, image_path, user_id, poem_title, count_before, n_zero_before)
    for r in sorted_rows:
        path = r["image_path"]
        count_before = image_count[path]
        # "Images with 0 ratings so far" = images in all_image_paths that have count 0 in image_count
        n_zero_before = sum(1 for p in all_image_paths if image_count[p] == 0)
        n_one_plus_before = total_images - n_zero_before
        events.append({
            "ts": r["ts"],
            "image_path": path,
            "user_id": r["user_id"],
            "poem_title": r["poem_title"],
            "count_before": count_before,
            "n_zero_before": n_zero_before,
            "n_one_plus_before": n_one_plus_before,
        })
        image_count[path] += 1

    safe_print("=" * 70)
    safe_print("1. TEMPORAL ANALYSIS")
    safe_print("When an image got its 2nd / 3rd / 4th evaluation, how many images had 0 ratings?")
    safe_print("(We only see images that appear in evaluations; catalog may have more.)")
    safe_print("=" * 70)

    for rating in [2, 3, 4]:
        # Events where count_before was 1, 2, 3 (so this is the 2nd, 3rd, 4th eval)
        evs = [e for e in events if e["count_before"] == rating - 1]
        if not evs:
            safe_print(f"\nNo image got a {rating}th evaluation.")
            continue
        n_with_zero = sum(1 for e in evs if e["n_zero_before"] > 0)
        n_with_no_zero = len(evs) - n_with_zero
        ord_s = {2: "2nd", 3: "3rd", 4: "4th"}.get(rating, f"{rating}th")
        safe_print(f"\nImage got {ord_s} evaluation: {len(evs)} events")
        safe_print(f"  - At that moment, there were still >0 images with 0 ratings: {n_with_zero} events")
        safe_print(f"  - At that moment, there were 0 images with 0 ratings:       {n_with_no_zero} events")
        if n_with_zero > 0:
            safe_print(f"  -> In {n_with_zero} cases, a 0-rated image *could* have been served (selection might have skipped 0s because user had already seen those poems).")
        # Show a few examples
        examples = [e for e in evs if e["n_zero_before"] > 0][:3]
        for e in examples:
            uid = e["user_id"].encode("ascii", errors="replace").decode("ascii")
            safe_print(f"     Example: ts={e['ts'][:19]} count_before={e['count_before']} n_zero_before={e['n_zero_before']} user={uid}")


# --- 2. Path mismatch ---
def run_path_analysis(rows: List[dict]) -> None:
    """Check if same logical image (same basename) appears under different full paths."""
    by_basename: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        path = r["image_path"]
        basename = Path(path).name
        by_basename[basename].add(path)

    multi_path_basenames = {b: paths for b, paths in by_basename.items() if len(paths) > 1}
    safe_print("\n" + "=" * 70)
    safe_print("2. PATH MISMATCH")
    safe_print("Same basename (filename) under different full paths => catalog path might not match DB path.")
    safe_print("=" * 70)
    safe_print(f"Unique image paths in evaluations: {len(set(r['image_path'] for r in rows))}")
    safe_print(f"Unique basenames: {len(by_basename)}")
    safe_print(f"Basenames with multiple full paths (path mismatch): {len(multi_path_basenames)}")
    if multi_path_basenames:
        for basename, paths in list(multi_path_basenames.items())[:5]:
            safe_print(f"  {basename}: {len(paths)} paths")
            for p in list(paths)[:2]:
                safe_print(f"    {p[:70]}...")
    else:
        safe_print("  No path mismatch detected (each basename has one path).")


# --- 3. Poem-seen coverage ---
def run_poem_seen(rows: List[dict]) -> None:
    """
    For each user, replay evaluations in ts order to get 'seen_titles' at each step.
    When a user receives an image that *at that moment* already had 1+ evaluations
    (i.e. this is the 2nd/3rd/4th evaluation for that image), how many distinct
    poem titles had this user already seen? If that number is high, it supports
    'we skipped 0-rated images because user had already seen those poems'.
    """
    sorted_rows = sorted(rows, key=lambda r: r["ts"])
    # Per image_path: current count before this row (0-indexed: before processing this row)
    image_count: dict[str, int] = defaultdict(int)
    # Per user_id: set of poem_title seen so far (before this row)
    user_seen: dict[str, set[str]] = defaultdict(set)

    events = []  # when image gets 2nd/3rd/4th eval: (user_id, image_path, count_before, len(user_seen[user_id]))
    for r in sorted_rows:
        path = r["image_path"]
        uid = r["user_id"]
        poem = r["poem_title"]
        count_before = image_count[path]
        seen_count_before = len(user_seen[uid])
        if count_before >= 1:
            events.append({
                "user_id": uid,
                "image_path": path,
                "poem_title": poem,
                "count_before": count_before,
                "seen_titles_before": seen_count_before,
            })
        image_count[path] += 1
        user_seen[uid].add(poem)

    # At each event: how many 0-rated images had poem_title NOT in user's seen_titles?
    # If >0, we *could* have assigned a 0-rated image (user had not seen that poem) -> possible bug.
    sorted_by_ts = sorted(rows, key=lambda r: r["ts"])
    image_count: dict[str, int] = defaultdict(int)
    user_seen_at_event: dict[str, set[str]] = defaultdict(set)
    n_zero_unseen = []  # for each event: count of (path with count 0 and poem not in user_seen)
    all_paths = set(r["image_path"] for r in rows)
    path_to_poem = {r["image_path"]: r["poem_title"] for r in rows}

    for r in sorted_by_ts:
        path = r["image_path"]
        uid = r["user_id"]
        poem = r["poem_title"]
        count_before = image_count[path]
        seen_before = user_seen_at_event[uid].copy()
        if count_before >= 1:
            # How many images (from all_paths) have count 0 right now AND poem not in seen_before?
            n_could_assign = 0
            for p in all_paths:
                if image_count[p] == 0 and path_to_poem.get(p, "") not in seen_before:
                    n_could_assign += 1
            n_zero_unseen.append(n_could_assign)
        image_count[path] += 1
        user_seen_at_event[uid].add(poem)

    safe_print("\n" + "=" * 70)
    safe_print("3. POEM-SEEN COVERAGE")
    safe_print("When a user received an image that already had 1+ ratings, how many poems had they already seen?")
    safe_print("(If high, selection likely skipped 0-rated images because user had seen those poems.)")
    safe_print("=" * 70)
    safe_print(f"Events where user was assigned an image that already had 1+ evaluations: {len(events)}")
    if not events:
        safe_print("  (None.)")
        return
    seen_counts = [e["seen_titles_before"] for e in events]
    safe_print(f"  Seen-titles count before this assignment: min={min(seen_counts)}, max={max(seen_counts)}, avg={sum(seen_counts)/len(seen_counts):.1f}")
    for low, high in [(0, 10), (11, 50), (51, 200), (201, 10000)]:
        n = sum(1 for c in seen_counts if low <= c <= high)
        if n > 0:
            safe_print(f"  In range [{low}, {high}]: {n} events")

    safe_print("\n  CRITICAL: When assigned 1+ rated image, how many 0-rated images had a poem the user had NOT seen?")
    safe_print("  (If >0, we could have served a 0-rated image; selection may be wrong.)")
    if n_zero_unseen:
        safe_print(f"  Count of '0-rated images with unseen poem' at assignment: min={min(n_zero_unseen)}, max={max(n_zero_unseen)}, avg={sum(n_zero_unseen)/len(n_zero_unseen):.1f}")
        n_bug_candidates = sum(1 for x in n_zero_unseen if x > 0)
        safe_print(f"  Events where there was at least one 0-rated image (unseen poem) we could have served: {n_bug_candidates} / {len(n_zero_unseen)}")
        if n_bug_candidates > 0:
            safe_print("  -> SUSPECT: Selection assigned 1+ rated image when 0-rated images (with poem user had not seen) were available.")
    safe_print("  -> If 'seen_titles_before' is large when receiving a 1+ rated image, the logic is consistent: we skip 0s because user had already seen those poems.")


def main():
    parser = argparse.ArgumentParser(description="Investigate image selection logic from evaluations.csv")
    parser.add_argument("--evaluations-csv", type=Path, default=BASE_DIR / "evaluations.csv")
    parser.add_argument("--skip-temporal", action="store_true", help="Skip temporal analysis")
    parser.add_argument("--skip-path", action="store_true", help="Skip path analysis")
    parser.add_argument("--skip-poem", action="store_true", help="Skip poem-seen analysis")
    args = parser.parse_args()

    if not args.evaluations_csv.exists():
        print(f"Error: {args.evaluations_csv} not found")
        sys.exit(1)

    rows = load_evaluations(args.evaluations_csv)
    safe_print(f"Loaded {len(rows)} evaluations from {args.evaluations_csv}")
    if not rows:
        print("No rows.")
        sys.exit(0)

    if not args.skip_temporal:
        run_temporal(rows)
    if not args.skip_path:
        run_path_analysis(rows)
    if not args.skip_poem:
        run_poem_seen(rows)

    safe_print("\n" + "=" * 70)
    safe_print("SUMMARY (why selection might assign 1+ when 0-rated images exist)")
    safe_print("=" * 70)
    safe_print("1. Temporal: In ALL cases when an image got its 2nd/3rd/4th evaluation,")
    safe_print("   there were still many images with 0 ratings (among the 525 in evaluations).")
    safe_print("2. Path: No path mismatch in evaluations.csv.")
    safe_print("3. Poem-seen: In ALL 112 events where a user was assigned a 1+ rated image,")
    safe_print("   there was at least one 0-rated image (with poem user had NOT seen) we could have served.")
    safe_print("   -> If the queue at runtime contained all 525 images, selection was wrong.")
    safe_print("4. LIKELY EXPLANATION: The queue at runtime may have contained FEWER than 525 images.")
    safe_print("   (e.g. catalog had only ~48-128 images when these evaluations ran; the rest were")
    safe_print("   added later, or evaluations came from multiple runs with different catalog sizes.)")
    safe_print("   So the '477 0-rated images' we see in CSV were not in the queue when the 2nd eval happened.")
    safe_print("   To confirm: check catalog size / IMAGE_SELECTION_SYSTEM.all_images at runtime.")
    safe_print("\nDone.")


if __name__ == "__main__":
    main()
