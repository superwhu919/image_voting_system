#!/usr/bin/env python3
"""
Calculate scores from evaluations.csv using a score mapping (score_v1.json or score_v2.json).
Usage: python calc_score.py score_v1.json
Output: output.csv with per-question scores per evaluation, plus printed statistics.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


def load_score_mapping(score_path: Path) -> dict:
    with open(score_path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_v2_mapping(mapping: dict) -> bool:
    return "q1_joint" in mapping


def score_row_v1(row: pd.Series, mapping: dict) -> dict:
    """Compute per-question scores for one evaluation using v1 mapping."""
    try:
        answers = json.loads(row["answers_json"])
    except (json.JSONDecodeError, TypeError):
        answers = {}
    right = str(row.get("q1_1_right_answer", "")).strip().upper()
    q1_1_ans = (answers.get("q1-1") or "").strip().upper()
    q1_2_ans = (answers.get("q1-2") or "").strip().lower()

    q1_1 = 1 if (q1_1_ans == right) else 0
    q1_2_map = mapping.get("q1-2") or {}
    q1_2 = q1_2_map.get(q1_2_ans, 0)

    out = {"q1-1": q1_1, "q1-2": q1_2}
    for i in range(1, 11):
        key = f"q2-{i}"
        m = mapping.get(key) or {}
        ans = (answers.get(key) or "").strip().lower()
        out[key] = m.get(ans, 0)
    return out


def score_row_v2(row: pd.Series, mapping: dict) -> dict:
    """Compute per-question scores for one evaluation using v2 mapping (q1 combined)."""
    try:
        answers = json.loads(row["answers_json"])
    except (json.JSONDecodeError, TypeError):
        answers = {}
    right = str(row.get("q1_1_right_answer", "")).strip().upper()
    q1_1_ans = (answers.get("q1-1") or "").strip().upper()
    q1_2_ans = (answers.get("q1-2") or "").strip().lower()

    q1_joint = mapping.get("q1_joint") or {}
    correct_map = q1_joint.get("correct") or {}
    incorrect_map = q1_joint.get("incorrect") or {}
    if q1_1_ans == right:
        q1 = correct_map.get(q1_2_ans, 0)
    else:
        q1 = incorrect_map.get(q1_2_ans, 0)

    out = {"q1": q1}
    for i in range(1, 11):
        key = f"q2-{i}"
        m = mapping.get(key) or {}
        ans = (answers.get(key) or "").strip().lower()
        out[key] = m.get(ans, 0)
    return out


def main():
    parser = argparse.ArgumentParser(description="Calculate scores from evaluations using a score JSON.")
    parser.add_argument("score_json", help="Path to score file, e.g. score_v1.json or score_v2.json")
    parser.add_argument(
        "--evaluations",
        default=None,
        help="Path to evaluations CSV (default: same dir as script/evaluations.csv)",
    )
    parser.add_argument(
        "--output",
        default="output.csv",
        help="Output CSV path (default: output.csv)",
    )
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    score_path = Path(args.score_json)
    if not score_path.is_absolute():
        score_path = (script_dir / score_path).resolve()
    if not score_path.exists():
        print(f"Error: score file not found: {score_path}", file=sys.stderr)
        sys.exit(1)

    eval_path = Path(args.evaluations) if args.evaluations else script_dir / "evaluations.csv"
    if not eval_path.is_absolute():
        eval_path = eval_path.resolve()
    if not eval_path.exists():
        print(f"Error: evaluations file not found: {eval_path}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = (script_dir / out_path).resolve()

    mapping = load_score_mapping(score_path)
    v2 = is_v2_mapping(mapping)
    score_version = "v2" if v2 else "v1"

    df = pd.read_csv(eval_path)
    if df.empty:
        print("No rows in evaluations.csv")
        pd.DataFrame().to_csv(out_path, index=False)
        return

    rows = []
    for _, row in df.iterrows():
        if v2:
            scores = score_row_v2(row, mapping)
            q_cols = ["q1"] + [f"q2-{i}" for i in range(1, 11)]
        else:
            scores = score_row_v1(row, mapping)
            q_cols = ["q1-1", "q1-2"] + [f"q2-{i}" for i in range(1, 11)]

        total = sum(scores[k] for k in q_cols)
        out_row = {
            "id": row.get("id"),
            "image_path": row.get("image_path"),
            "image_type": row.get("image_type"),
            "poem_title": row.get("poem_title"),
            **scores,
            "total": total,
        }
        rows.append(out_row)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(out_path, index=False)
    print(f"Wrote {len(out_df)} rows to {out_path}")

    # ---------- Statistics ----------
    q_cols = list(out_df.columns)
    for drop in ("id", "image_path", "image_type", "poem_title", "total"):
        if drop in q_cols:
            q_cols.remove(drop)
    score_cols = [c for c in q_cols if c.startswith("q1") or c.startswith("q2")]

    print("\n" + "=" * 60)
    print(f"SCORE VERSION: {score_version} ({score_path.name})")
    print("=" * 60)

    print("\n--- Overall score statistics ---")
    print(out_df["total"].describe().to_string())
    print(f"\nTotal score: mean = {out_df['total'].mean():.4f}, std = {out_df['total'].std():.4f}")

    print("\n--- Per-question score distribution ---")
    for col in score_cols:
        s = out_df[col]
        print(f"  {col}: count={s.count()}, mean={s.mean():.4f}, std={s.std():.4f}, min={s.min()}, max={s.max()}")

    print("\n--- Per image_type score statistics ---")
    for itype in ["seedream", "nano", "gpt", "mj"]:
        sub = out_df[out_df["image_type"] == itype]
        if sub.empty:
            print(f"  {itype}: no data")
            continue
        print(f"  {itype}: n={len(sub)}, total mean={sub['total'].mean():.4f}, total std={sub['total'].std():.4f}")

    print("\n--- Per-question distribution by image_type ---")
    for itype in ["seedream", "nano", "gpt", "mj"]:
        sub = out_df[out_df["image_type"] == itype]
        if sub.empty:
            continue
        print(f"\n  [{itype}] n={len(sub)}")
        for col in score_cols:
            s = sub[col]
            print(f"    {col}: mean={s.mean():.4f}, std={s.std():.4f}")


if __name__ == "__main__":
    main()
