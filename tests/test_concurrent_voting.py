#!/usr/bin/env python3
"""
Concurrent Voting Test - Simulates multiple users voting simultaneously

This test simulates multiple users making concurrent requests to test for race conditions
in the image selection system.

Usage:
    # Test against a running server (default: http://127.0.0.1:7860)
    python tests/test_concurrent_voting.py
    
    # Or specify a different server
    BASE_URL=http://localhost:8000 python tests/test_concurrent_voting.py
"""

import sys
import os
import time
import threading
import requests
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Default server URL
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:7860")

# Thread-safe tracking
image_assignments: Dict[str, List[str]] = defaultdict(list)  # image_path -> [user_ids]
assignment_lock = threading.Lock()
errors: List[str] = []
errors_lock = threading.Lock()
completed_users: Set[str] = set()
completed_lock = threading.Lock()


def simulate_user(user_id: str, num_votes: int = 3):
    """Simulate a single user completing multiple votes."""
    try:
        # Start session
        response = requests.post(
            f"{BASE_URL}/api/start",
            json={
                "user_id": user_id,
                "age": 25,
                "gender": "male",
                "education": "bachelor"
            },
            timeout=10
        )
        
        if response.status_code != 200:
            with errors_lock:
                errors.append(f"User {user_id}: Start failed with status {response.status_code}")
            return
        
        data = response.json()
        if data.get("status") != "success":
            with errors_lock:
                errors.append(f"User {user_id}: Start returned {data.get('status')}: {data.get('message')}")
            return
        
        # Track image assignment
        image_path = data.get("image_path")
        if image_path:
            with assignment_lock:
                image_assignments[image_path].append(user_id)
        
        # Complete num_votes voting cycles
        for vote_num in range(num_votes):
            # Get session data
            poem_title = data.get("poem_title")
            image_path = data.get("image_path")
            options_dict = data.get("options_dict", {})
            target_letter = data.get("target_letter", "A")
            phase1_start_ms = data.get("phase1_start_ms", str(int(time.time() * 1000)))
            
            if not all([poem_title, image_path, options_dict, target_letter]):
                with errors_lock:
                    errors.append(f"User {user_id} vote {vote_num}: Missing required data")
                break
            
            # Phase 1: Make a choice (random for testing)
            phase1_choice = target_letter  # Choose correct answer for simplicity
            phase1_answers = {
                "q1-2": "Somewhat confident",
                "q1-3": "Holistic_best_match"
            }
            
            # Reveal poem (Phase 2)
            time.sleep(0.1)  # Simulate thinking time
            reveal_response = requests.post(
                f"{BASE_URL}/api/reveal",
                json={
                    "user_id": user_id,
                    "poem_title": poem_title,
                    "image_path": image_path,
                    "options_dict": options_dict,
                    "target_letter": target_letter,
                    "phase1_choice": phase1_choice,
                    "phase1_answers": phase1_answers,
                    "phase1_start_ms": phase1_start_ms
                },
                timeout=10
            )
            
            if reveal_response.status_code != 200:
                with errors_lock:
                    errors.append(f"User {user_id} vote {vote_num}: Reveal failed")
                break
            
            reveal_data = reveal_response.json()
            if reveal_data.get("status") != "success":
                with errors_lock:
                    errors.append(f"User {user_id} vote {vote_num}: Reveal returned {reveal_data.get('status')}")
                break
            
            # Phase 2: Answer questions
            phase2_start_ms = reveal_data.get("phase2_start_ms", str(int(time.time() * 1000)))
            questions = reveal_data.get("questions", {})
            
            # Build phase2_answers (simplified - just fill with defaults)
            phase2_answers = {}
            for q_id in sorted(questions.keys()):
                if q_id.startswith("q2-"):
                    # Get first option as answer (simplified)
                    q_data = questions.get(q_id, {})
                    options = q_data.get("options", [])
                    if options:
                        phase2_answers[q_id] = options[0].get("value", "")
                    else:
                        phase2_answers[q_id] = "answer"
            
            # Submit evaluation
            time.sleep(0.1)  # Simulate thinking time
            submit_response = requests.post(
                f"{BASE_URL}/api/submit",
                json={
                    "user_id": user_id,
                    "user_age": 25,
                    "user_gender": "male",
                    "user_education": "bachelor",
                    "poem_title": poem_title,
                    "image_path": image_path,
                    "image_type": data.get("image_type", ""),
                    "options_dict": options_dict,
                    "target_letter": target_letter,
                    "phase1_choice": phase1_choice,
                    "phase1_answers": phase1_answers,
                    "phase1_response_ms": 2000,
                    "phase2_answers": phase2_answers,
                    "phase2_start_ms": phase2_start_ms,
                    "phase1_start_ms": phase1_start_ms
                },
                timeout=10
            )
            
            if submit_response.status_code != 200:
                with errors_lock:
                    errors.append(f"User {user_id} vote {vote_num}: Submit failed")
                break
            
            submit_data = submit_response.json()
            if submit_data.get("status") == "success":
                # Get next evaluation
                data = submit_data
                next_image_path = data.get("image_path")
                if next_image_path:
                    with assignment_lock:
                        image_assignments[next_image_path].append(user_id)
            elif submit_data.get("status") == "limit_reached":
                # User reached limit, that's okay
                break
            else:
                with errors_lock:
                    errors.append(f"User {user_id} vote {vote_num}: Submit returned {submit_data.get('status')}")
                break
        
        with completed_lock:
            completed_users.add(user_id)
            
    except Exception as e:
        with errors_lock:
            errors.append(f"User {user_id}: Exception - {str(e)}")


def run_concurrent_test(num_users: int = 10, votes_per_user: int = 3):
    """Run concurrent test with multiple users."""
    print("=" * 70)
    print("Concurrent Voting Test")
    print("=" * 70)
    print(f"Server URL: {BASE_URL}")
    print(f"Number of users: {num_users}")
    print(f"Votes per user: {votes_per_user}")
    print(f"Total expected votes: {num_users * votes_per_user}")
    print()
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code != 200:
            print(f"ERROR: Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Cannot connect to server at {BASE_URL}")
        print(f"Make sure your server is running: python app.py")
        return False
    
    print("✓ Server is reachable")
    print()
    
    # Clear tracking
    global image_assignments, errors, completed_users
    image_assignments.clear()
    errors.clear()
    completed_users.clear()
    
    # Create threads for concurrent users
    threads = []
    start_time = time.time()
    
    print(f"Starting {num_users} concurrent users...")
    for i in range(num_users):
        user_id = f"concurrent_user_{i:03d}"
        thread = threading.Thread(target=simulate_user, args=(user_id, votes_per_user))
        thread.start()
        threads.append(thread)
        # Small delay to stagger starts slightly
        time.sleep(0.01)
    
    print("All threads started. Waiting for completion...")
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join(timeout=60)  # 60 second timeout per thread
    
    elapsed_time = time.time() - start_time
    
    # Analyze results
    print()
    print("=" * 70)
    print("Test Results")
    print("=" * 70)
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    print(f"Users completed: {len(completed_users)}/{num_users}")
    print(f"Total errors: {len(errors)}")
    print()
    
    # Check for duplicate image assignments (race condition indicator)
    duplicates_found = False
    print("Image Assignment Analysis:")
    print("-" * 70)
    for image_path, user_list in image_assignments.items():
        if len(user_list) > 1:
            duplicates_found = True
            print(f"⚠️  DUPLICATE: Image '{image_path}' assigned to {len(user_list)} users:")
            for user_id in user_list:
                print(f"   - {user_id}")
    
    if not duplicates_found:
        print("✓ No duplicate image assignments detected")
    
    print()
    print(f"Total unique images assigned: {len(image_assignments)}")
    print(f"Total assignments: {sum(len(users) for users in image_assignments.values())}")
    print()
    
    # Show errors if any
    if errors:
        print("Errors encountered:")
        print("-" * 70)
        for error in errors[:20]:  # Show first 20 errors
            print(f"  - {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")
        print()
    
    # Summary
    print("=" * 70)
    if duplicates_found:
        print("⚠️  RACE CONDITION DETECTED!")
        print("   Multiple users were assigned the same image simultaneously.")
        print("   This indicates the image selection system is not thread-safe.")
    elif len(errors) > 0:
        print("⚠️  ERRORS ENCOUNTERED")
        print("   Some requests failed, but no duplicate assignments detected.")
    else:
        print("✓ TEST PASSED")
        print("   No duplicate assignments or errors detected.")
    print("=" * 70)
    
    return not duplicates_found and len(errors) == 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test concurrent voting for race conditions")
    parser.add_argument("--users", type=int, default=10, help="Number of concurrent users (default: 10)")
    parser.add_argument("--votes", type=int, default=3, help="Votes per user (default: 3)")
    parser.add_argument("--url", type=str, default=None, help="Server URL (default: http://127.0.0.1:7860)")
    
    args = parser.parse_args()
    
    if args.url:
        BASE_URL = args.url
    
    success = run_concurrent_test(num_users=args.users, votes_per_user=args.votes)
    sys.exit(0 if success else 1)