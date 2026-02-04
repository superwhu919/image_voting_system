#!/usr/bin/env python3
"""
Parse profiling log lines (profile {...}) from stdin or a file and print a summary.
Use after running concurrent_load_test.py with PROFILING_ENABLED=1 and saving app stderr.

  PROFILING_ENABLED=1 python app.py 2> profile.log
  # in another terminal: python scripts/concurrent_load_test.py
  python scripts/analyze_profile_log.py < profile.log
"""
import ast
import sys
from collections import defaultdict


def main():
    segments = defaultdict(list)
    path = sys.argv[1] if len(sys.argv) > 1 else None
    stream = open(path) if path else sys.stdin
    try:
        for line in stream:
            if "profile {" not in line and "profile '" not in line:
                continue
            try:
                start = line.find("{")
                if start == -1:
                    continue
                d = ast.literal_eval(line[start:].strip())
                seg = d.get("segment", "")
                ms = d.get("ms", 0)
                segments[seg].append(ms)
            except Exception:
                pass
    finally:
        if path:
            stream.close()

    print("=== Segment summary (count, avg ms, max ms) ===\n")
    for seg in sorted(segments.keys()):
        vals = segments[seg]
        n, avg, mx = len(vals), sum(vals) / len(vals), max(vals)
        print(f"  {seg}: n={n}, avg={avg:.1f}ms, max={mx:.1f}ms")

    if "request" in segments:
        vals = segments["request"]
        print("\n=== Request times ===")
        print(f"  n={len(vals)}, avg={sum(vals)/len(vals):.0f}ms, max={max(vals):.0f}ms, min={min(vals):.0f}ms")

    print("\n=== Lock wait (contention) ===")
    for k in ["lock_wait.WRITE_LOCK", "lock_wait.image_selection._lock"]:
        if k in segments:
            vals = segments[k]
            over_10 = sum(1 for v in vals if v >= 10)
            print(f"  {k}: max={max(vals):.1f}ms, count>=10ms={over_10}/{len(vals)}")

    print("\n=== Bottleneck interpretation ===")
    if "lock_hold.WRITE_LOCK" in segments:
        mx = max(segments["lock_hold.WRITE_LOCK"])
        if mx > 20:
            print(f"  WRITE_LOCK is held up to {mx:.0f}ms -> DB (SQLite) serializes all writes.")
    if "lock_hold.image_selection._lock" in segments:
        mx = max(segments["lock_hold.image_selection._lock"])
        if mx > 20:
            print(f"  image_selection._lock held up to {mx:.0f}ms -> selection + DB under one lock.")
    if "storage.save_user_state" in segments:
        mx = max(segments["storage.save_user_state"])
        if mx > 50:
            print(f"  storage.save_user_state max {mx:.0f}ms -> slow under concurrency (WRITE_LOCK).")
    print("  High lock_wait.* = threads waiting for lock. High lock_hold.* = work done while holding lock.")


if __name__ == "__main__":
    main()
