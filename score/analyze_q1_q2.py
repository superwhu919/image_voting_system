#!/usr/bin/env python3
"""
Analyze q1-1 correctness and q2 option distribution by q1-1 correct/incorrect.
Usage: python analyze_q1_q2.py [--input FILE]
Default input: evaluations.csv. Use --input evaluations_deduped.csv for deduped.
"""

import argparse
import json
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser(description="Analyze q1-1 and q2 distributions.")
    parser.add_argument(
        "--input",
        default="evaluations.csv",
        help="Input CSV (default: evaluations.csv; use evaluations_deduped.csv for deduped)",
    )
    args = parser.parse_args()
    script_dir = Path(__file__).resolve().parent
    eval_path = script_dir / args.input if not Path(args.input).is_absolute() else Path(args.input)
    if not eval_path.exists():
        raise SystemExit(f"Input file not found: {eval_path}")
    df = pd.read_csv(eval_path)

    print(f"Input: {eval_path.name}")
    print()

    # Parse answers and q1-1 correctness
    q1_correct = []
    answers_list = []
    for _, row in df.iterrows():
        try:
            answers = json.loads(row["answers_json"])
        except (json.JSONDecodeError, TypeError):
            answers = {}
        right = str(row.get("q1_1_right_answer", "")).strip().upper()
        q1_1_ans = (answers.get("q1-1") or "").strip().upper()
        correct = q1_1_ans == right
        q1_correct.append(correct)
        answers_list.append(answers)

    df = df.copy()
    df["q1_1_correct"] = q1_correct
    df["_answers"] = answers_list

    n_total = len(df)
    n_correct = df["q1_1_correct"].sum()
    n_incorrect = n_total - n_correct

    # Unique images: one row per (image_path) evaluation; count unique images with at least one correct
    n_unique_images = df["image_path"].nunique()
    correct_per_image = df.groupby("image_path")["q1_1_correct"].max()
    n_images_with_correct = correct_per_image.sum()

    print("=" * 60)
    print("Q1-1 CORRECTNESS")
    print("=" * 60)
    print(f"Evaluations (rows) with q1-1 correct: {int(n_correct)} / {n_total} ({100 * n_correct / n_total:.1f}%)")
    print(f"Evaluations with q1-1 incorrect:      {int(n_incorrect)} / {n_total} ({100 * n_incorrect / n_total:.1f}%)")
    print(f"Unique images (image_path):         {n_unique_images}")
    print(f"Images with at least one q1-1 correct evaluation: {int(n_images_with_correct)} / {n_unique_images}")

    # Q2 option distribution by q1-1 correct / incorrect
    q2_keys = [f"q2-{i}" for i in range(1, 11)]
    correct_df = df[df["q1_1_correct"]]
    incorrect_df = df[~df["q1_1_correct"]]

    print("\n" + "=" * 60)
    print("Q2 OPTION DISTRIBUTION BY Q1-1 CORRECT vs INCORRECT")
    print("=" * 60)

    for q in q2_keys:
        correct_answers = correct_df["_answers"].apply(lambda a: (a.get(q) or "").strip().lower())
        incorrect_answers = incorrect_df["_answers"].apply(lambda a: (a.get(q) or "").strip().lower())
        c_counts = correct_answers.value_counts().sort_index()
        i_counts = incorrect_answers.value_counts().sort_index()
        all_options = sorted(set(c_counts.index) | set(i_counts.index)) or ["(none)"]
        print(f"\n--- {q} ---")
        print(f"  {'option':<8}  {'when q1-1 correct':>18}  {'when q1-1 incorrect':>20}")
        print(f"  {'':8}  {'count':>8}  {'%':>8}  {'count':>8}  {'%':>10}")
        for opt in all_options:
            if opt == "(none)":
                continue
            c_n = int(c_counts.get(opt, 0))
            i_n = int(i_counts.get(opt, 0))
            c_pct = 100 * c_n / n_correct if n_correct else 0
            i_pct = 100 * i_n / n_incorrect if n_incorrect else 0
            print(f"  {opt:<8}  {c_n:>8}  {c_pct:>7.1f}%  {i_n:>8}  {i_pct:>9.1f}%")
        # Missing/other
        c_miss = n_correct - c_counts.sum()
        i_miss = n_incorrect - i_counts.sum()
        if c_miss or i_miss:
            print(f"  (missing)  {int(c_miss):>8}  {100*c_miss/n_correct if n_correct else 0:>7.1f}%  {int(i_miss):>8}  {100*i_miss/n_incorrect if n_incorrect else 0:>9.1f}%")


if __name__ == "__main__":
    main()
