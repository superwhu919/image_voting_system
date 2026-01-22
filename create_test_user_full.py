#!/usr/bin/env python3
"""
Create a test user "full" who has seen 1279 images (out of 1280).
This allows testing the "all_images_seen" case from the frontend.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from data_logic.catalog import CATALOG
from data_logic.storage import USERS_DB, WRITE_LOCK, save_user_state
import json
from datetime import datetime

def create_test_user_full():
    """Create user 'full' who has seen 1279 images."""
    
    # Get all unique poem titles from catalog
    all_poem_titles = set()
    for image_data in CATALOG.values():
        poem_title = image_data.get("poem_title", "")
        if poem_title:
            all_poem_titles.add(poem_title)
    
    total_titles = len(all_poem_titles)
    print(f"Total unique poem titles in catalog: {total_titles}")
    
    # Take all but 1 title (leave 1 unseen for testing)
    seen_titles = list(all_poem_titles)[:total_titles - 1]
    remaining_titles = list(all_poem_titles)[total_titles - 1:]
    
    print(f"Marking {len(seen_titles)} poem titles as seen")
    print(f"Leaving {len(remaining_titles)} poem title(s) unseen")
    
    # Create user in database
    user_id = "full"
    with WRITE_LOCK:
        # Check if user already exists
        existing = USERS_DB.execute(
            "SELECT user_id FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
        
        if existing:
            print(f"User '{user_id}' already exists. Updating...")
            # Update existing user
            USERS_DB.execute(
                """UPDATE users 
                   SET user_age = ?, user_gender = ?, user_education = ?, 
                       user_limit = ?, created_at = ?
                   WHERE user_id = ?""",
                (25, "男", "本科", 20, datetime.now().isoformat(), user_id)
            )
        else:
            print(f"Creating new user '{user_id}'...")
            # Insert new user
            USERS_DB.execute(
                """INSERT INTO users (user_id, user_age, user_gender, user_education, user_limit, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, 25, "男", "本科", 20, datetime.now().isoformat())
            )
        
        USERS_DB.commit()
    
    # Save seen titles
    seen_titles_set = set(seen_titles)
    save_user_state(user_id, seen_titles_set, set())
    
    print(f"\n[OK] User '{user_id}' created successfully!")
    print(f"  - Seen {len(seen_titles_set)} poem titles")
    print(f"  - Can still see {len(remaining_titles)} more poem title(s)")
    print(f"\nYou can now test from the frontend with user name: {user_id}")
    print(f"After seeing the remaining image(s), you should see the 'all_images_seen' status.")

if __name__ == "__main__":
    create_test_user_full()
