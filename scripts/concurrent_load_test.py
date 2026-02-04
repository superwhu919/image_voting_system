#!/usr/bin/env python3
"""
Concurrent load test for the voting system. Sends up to N concurrent "users"
through the full flow: start -> reveal -> submit (with random user info and answers).
Run the app with PROFILING_ENABLED=1 and then run this script to see bottleneck logs.

Usage:
  # Terminal 1: start app with profiling
  PROFILING_ENABLED=1 python app.py

  # Terminal 2: run load test (default 30 workers, 2 evaluations per user)
  python scripts/concurrent_load_test.py
  python scripts/concurrent_load_test.py --workers 30 --evals-per-user 2 --base-url http://127.0.0.1:7860
"""
import argparse
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)

# Project root
BASE_DIR = Path(__file__).resolve().parent.parent
QUESTIONS_JSON_PATH = BASE_DIR / "questions.json"

# Load Phase 2 question IDs and option values for random answers
with open(QUESTIONS_JSON_PATH, "r", encoding="utf-8") as f:
    QUESTIONS = json.load(f)

PHASE2_IDS = sorted(
    [q for q in QUESTIONS if q.startswith("q2-")],
    key=lambda q: int(q.split("-")[1]) if q.startswith("q2-") else 999,
)


def get_random_phase2_answers():
    """Build phase2_answers with one random option per q2-* question."""
    out = {}
    for qid in PHASE2_IDS:
        q = QUESTIONS.get(qid, {})
        opts = q.get("options", [])
        if opts:
            out[qid] = random.choice(opts).get("value", "a")
        else:
            out[qid] = "a"
    return out


def get_random_phase1_answers(target_letter: str):
    """phase1_choice is one of A,B,C,D; q1-2 random from a..e."""
    choice = random.choice(["A", "B", "C", "D"])
    return {
        "q1-1": choice,
        "q1-2": random.choice(["a", "b", "c", "d", "e"]),
    }


def run_one_user(base_url: str, user_id: str, evals_per_user: int, timeout: float):
    """Run one virtual user: start, then evals_per_user times (reveal -> submit). Returns (success_count, error_msg)."""
    session = requests.Session()
    age = random.randint(18, 60)
    gender = random.choice(["男", "女", "其他"])
    education = random.choice(["高中", "本科", "硕士", "博士", "其他"])

    # Start
    try:
        r = session.post(
            f"{base_url}/api/start",
            json={
                "user_id": user_id,
                "age": age,
                "gender": gender,
                "education": education,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return 0, f"start: {e}"

    if data.get("status") not in ("success", "limit_reached", "all_images_seen"):
        return 0, f"start status={data.get('status')}"

    success_count = 0
    for _ in range(evals_per_user):
        # If we didn't get an image (limit_reached or all_images_seen), stop
        if data.get("status") != "success":
            break
        poem_title = data.get("poem_title")
        image_path = data.get("image_path")
        options_dict = data.get("options_dict", {})
        target_letter = data.get("target_letter", "A")
        phase1_start_ms = data.get("phase1_start_ms", str(int(time.time() * 1000)))

        phase1_answers = get_random_phase1_answers(target_letter)
        phase1_choice = phase1_answers["q1-1"]
        phase1_response_ms = random.randint(500, 3000)
        phase2_start_ms = str(int(time.time() * 1000) - phase1_response_ms)
        phase2_answers = get_random_phase2_answers()

        # Reveal
        try:
            r = session.post(
                f"{base_url}/api/reveal",
                json={
                    "user_id": user_id,
                    "poem_title": poem_title,
                    "image_path": image_path,
                    "options_dict": options_dict,
                    "target_letter": target_letter,
                    "phase1_choice": phase1_choice,
                    "phase1_answers": phase1_answers,
                    "phase1_start_ms": phase1_start_ms,
                },
                timeout=timeout,
            )
            r.raise_for_status()
        except Exception as e:
            return success_count, f"reveal: {e}"

        # Submit
        try:
            r = session.post(
                f"{base_url}/api/submit",
                json={
                    "user_id": user_id,
                    "user_age": age,
                    "user_gender": gender,
                    "user_education": education,
                    "poem_title": poem_title,
                    "image_path": image_path,
                    "image_type": data.get("image_type", ""),
                    "options_dict": options_dict,
                    "target_letter": target_letter,
                    "phase1_choice": phase1_choice,
                    "phase1_answers": phase1_answers,
                    "phase1_response_ms": phase1_response_ms,
                    "phase2_answers": phase2_answers,
                    "phase2_start_ms": phase2_start_ms,
                    "phase1_start_ms": phase1_start_ms,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            success_count += 1
        except Exception as e:
            return success_count, f"submit: {e}"

    return success_count, None


def main():
    ap = argparse.ArgumentParser(description="Concurrent load test for voting system")
    ap.add_argument("--workers", type=int, default=30, help="Max concurrent users (default 30)")
    ap.add_argument("--evals-per-user", type=int, default=2, help="Evaluations per user (default 2)")
    ap.add_argument("--base-url", default="http://127.0.0.1:7860", help="App base URL")
    ap.add_argument("--timeout", type=float, default=60.0, help="Request timeout seconds")
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/")
    print(f"Concurrent load test: {args.workers} workers, {args.evals_per_user} evals/user")
    print(f"Base URL: {base_url}")
    print("Ensure the app is running with PROFILING_ENABLED=1 to see bottleneck logs.")
    print()

    t0 = time.perf_counter()
    completed = 0
    errors = []

    def run_worker(i):
        uid = f"loadtest-user-{i}-{random.randint(1000, 9999)}"
        return run_one_user(base_url, uid, args.evals_per_user, args.timeout)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(run_worker, i): i for i in range(args.workers)}
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                count, err = fut.result()
                completed += count
                if err:
                    errors.append((i, err))
            except Exception as e:
                errors.append((i, str(e)))

    elapsed = time.perf_counter() - t0
    print(f"Done in {elapsed:.1f}s. Total evaluations completed: {completed}")
    if errors:
        print(f"Errors ({len(errors)}):")
        for i, err in errors[:10]:
            print(f"  worker {i}: {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    print("\nCheck the app terminal for profile logs (lock_wait.*, storage.*, request) to find bottlenecks.")


if __name__ == "__main__":
    main()
