#!/usr/bin/env python3
"""q1-2 distribution: overall and (optionally) nano when q1-1 incorrect."""
import csv
import json
import sys
from pathlib import Path
from collections import Counter

script_dir = Path(__file__).resolve().parent

def run_overall():
    counts = Counter()
    n = 0
    with open(script_dir / "evaluations.csv", "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                answers = json.loads(row["answers_json"])
            except (json.JSONDecodeError, TypeError, KeyError):
                answers = {}
            q1_2 = (answers.get("q1-2") or "").strip().lower() or "(missing)"
            n += 1
            counts[q1_2] += 1
    print("Overall q1-2: n =", n)
    print("\nq1-2 distribution (count):")
    for opt in sorted(counts.keys()):
        print(f"  {opt}: {counts[opt]}")
    print("\nq1-2 distribution (%):")
    for opt in sorted(counts.keys()):
        print(f"  {opt}: {100*counts[opt]/n:.1f}%")

def run_nano_incorrect():
    counts = Counter()
    n = 0
    with open(script_dir / "evaluations.csv", "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get("image_type") != "nano":
                continue
            try:
                answers = json.loads(row["answers_json"])
            except (json.JSONDecodeError, TypeError, KeyError):
                answers = {}
            right = (row.get("q1_1_right_answer") or "").strip().upper()
            q1_1 = (answers.get("q1-1") or "").strip().upper()
            q1_2 = (answers.get("q1-2") or "").strip().lower() or "(missing)"
            if q1_1 != right:
                n += 1
                counts[q1_2] += 1
    print("nano, q1-1 incorrect: n =", n)
    print("\nq1-2 distribution (count):")
    for opt in sorted(counts.keys()):
        print(f"  {opt}: {counts[opt]}")
    print("\nq1-2 distribution (%):")
    for opt in sorted(counts.keys()):
        print(f"  {opt}: {100*counts[opt]/n:.1f}%")

def run_q1_2_e():
    rows = []
    with open(script_dir / "evaluations.csv", "r", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                answers = json.loads(row["answers_json"])
            except (json.JSONDecodeError, TypeError, KeyError):
                answers = {}
            q1_2 = (answers.get("q1-2") or "").strip().lower()
            if q1_2 == "e":
                rows.append({
                    "id": row.get("id"),
                    "image_type": row.get("image_type"),
                })
    print("q1-2 = e: n =", len(rows))
    for r in rows:
        print(f"  id={r['id']}  image_type={r['image_type']}")
    by_type = Counter(r["image_type"] for r in rows)
    print("By image_type:", dict(by_type))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "nano-incorrect":
        run_nano_incorrect()
    elif len(sys.argv) > 1 and sys.argv[1] == "e":
        run_q1_2_e()
    else:
        run_overall()
