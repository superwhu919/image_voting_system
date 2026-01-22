#!/usr/bin/env python3
"""
Test file for database validation:
1. Dumps evaluations.db and users.db to CSV files
2. Checks if any user has seen an image twice
3. Checks if any user has seen a poem twice
4. Prints statistics about image ratings (number of evaluations per image)

Run with: python test_db_validation.py
"""

import sys
import csv
import sqlite3
import json
import io
import os
from pathlib import Path
from collections import defaultdict, Counter

# Set UTF-8 encoding for output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import USERS_DB_PATH, EVALUATIONS_DB_PATH


def dump_evaluations_to_csv(output_path: str = "evaluations.csv"):
    """Dump evaluations.db to CSV file."""
    conn = sqlite3.connect(str(EVALUATIONS_DB_PATH))
    cursor = conn.cursor()
    
    # Get all rows
    cursor.execute("SELECT * FROM evaluations ORDER BY id ASC")
    rows = cursor.fetchall()
    
    # Get column names
    cursor.execute("PRAGMA table_info(evaluations)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Write to CSV
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    conn.close()
    print(f"[OK] Dumped evaluations.db to {output_path} ({len(rows)} rows)")
    return output_path


def dump_users_to_csv(output_path: str = "users.csv"):
    """Dump users.db to CSV file."""
    conn = sqlite3.connect(str(USERS_DB_PATH))
    cursor = conn.cursor()
    
    # Get all rows
    cursor.execute("SELECT * FROM users ORDER BY user_id ASC")
    rows = cursor.fetchall()
    
    # Get column names
    cursor.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Write to CSV
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)
    
    conn.close()
    print(f"[OK] Dumped users.db to {output_path} ({len(rows)} rows)")
    return output_path


def check_duplicate_images():
    """Check if any user has seen an image twice."""
    conn = sqlite3.connect(str(EVALUATIONS_DB_PATH))
    cursor = conn.cursor()
    
    # Get all evaluations with user_id and image_path
    cursor.execute("""
        SELECT user_id, image_path, COUNT(*) as count
        FROM evaluations
        WHERE image_path IS NOT NULL AND image_path != ''
        GROUP BY user_id, image_path
        HAVING COUNT(*) > 1
        ORDER BY count DESC, user_id
    """)
    
    duplicates = cursor.fetchall()
    conn.close()
    
    if duplicates:
        print("\n[WARNING] Found users who have seen the same image multiple times:")
        for user_id, image_path, count in duplicates:
            print(f"   User: {user_id}, Image: {image_path}, Count: {count}")
        return False
    else:
        print("\n[OK] No duplicate images found for any user")
        return True


def check_duplicate_poems():
    """Check if any user has seen a poem twice."""
    conn = sqlite3.connect(str(EVALUATIONS_DB_PATH))
    cursor = conn.cursor()
    
    # Get all evaluations with user_id and poem_title
    cursor.execute("""
        SELECT user_id, poem_title, COUNT(*) as count
        FROM evaluations
        WHERE poem_title IS NOT NULL AND poem_title != ''
        GROUP BY user_id, poem_title
        HAVING COUNT(*) > 1
        ORDER BY count DESC, user_id
    """)
    
    duplicates = cursor.fetchall()
    conn.close()
    
    if duplicates:
        print("\n[WARNING] Found users who have seen the same poem multiple times:")
        for user_id, poem_title, count in duplicates:
            print(f"   User: {user_id}, Poem: {poem_title}, Count: {count}")
        return False
    else:
        print("\n[OK] No duplicate poems found for any user")
        return True


def print_rating_statistics():
    """Print statistics about image ratings (number of evaluations per image)."""
    conn = sqlite3.connect(str(EVALUATIONS_DB_PATH))
    cursor = conn.cursor()
    
    # Count evaluations per image
    cursor.execute("""
        SELECT image_path, COUNT(*) as count
        FROM evaluations
        WHERE image_path IS NOT NULL AND image_path != ''
        GROUP BY image_path
    """)
    
    rating_counts = cursor.fetchall()
    conn.close()
    
    # Count images by rating count
    rating_distribution = Counter(count for _, count in rating_counts)
    
    # Calculate statistics
    # images_gt_5: number of images with more than 5 evaluations
    images_gt_5 = sum(num_images for count, num_images in rating_distribution.items() if count > 5)
    images_eq_5 = rating_distribution.get(5, 0)
    images_eq_4 = rating_distribution.get(4, 0)
    images_eq_3 = rating_distribution.get(3, 0)
    images_eq_2 = rating_distribution.get(2, 0)
    images_eq_1 = rating_distribution.get(1, 0)
    images_eq_0 = rating_distribution.get(0, 0)
    
    print("\n" + "="*60)
    print("IMAGE RATING STATISTICS")
    print("="*60)
    print(f"Number of images with rating > 5:  {images_gt_5}")
    print(f"Number of images with rating = 5:  {images_eq_5}")
    print(f"Number of images with rating = 4:  {images_eq_4}")
    print(f"Number of images with rating = 3:  {images_eq_3}")
    print(f"Number of images with rating = 2:  {images_eq_2}")
    print(f"Number of images with rating = 1:  {images_eq_1}")
    print(f"Number of images with rating = 0:  {images_eq_0}")
    print("-"*60)
    print(f"Total unique images evaluated:     {len(rating_counts)}")
    # Total evaluations = sum of (rating_count * number_of_images_with_that_rating)
    total_evaluations = sum(count * num_images for count, num_images in rating_distribution.items())
    print(f"Total evaluations:                 {total_evaluations}")
    
    # Show distribution details
    if rating_distribution:
        print("\nRating distribution (count -> number of images):")
        for count in sorted(rating_distribution.keys(), reverse=True):
            num_images = rating_distribution[count]
            print(f"  {count} evaluations: {num_images} images")
    
    print("="*60)


def main():
    """Main function to run all checks."""
    print("="*60)
    print("DATABASE VALIDATION TEST")
    print("="*60)
    
    # Check if databases exist
    if not EVALUATIONS_DB_PATH.exists():
        print(f"[ERROR] {EVALUATIONS_DB_PATH} does not exist")
        return 1
    
    if not USERS_DB_PATH.exists():
        print(f"[ERROR] {USERS_DB_PATH} does not exist")
        return 1
    
    # Dump databases to CSV
    print("\n1. Dumping databases to CSV files...")
    try:
        dump_evaluations_to_csv("evaluations.csv")
        dump_users_to_csv("users.csv")
    except Exception as e:
        print(f"[ERROR] Error dumping databases: {e}")
        return 1
    
    # Check for duplicate images
    print("\n2. Checking for duplicate images per user...")
    try:
        no_duplicate_images = check_duplicate_images()
    except Exception as e:
        print(f"[ERROR] Error checking duplicate images: {e}")
        return 1
    
    # Check for duplicate poems
    print("\n3. Checking for duplicate poems per user...")
    try:
        no_duplicate_poems = check_duplicate_poems()
    except Exception as e:
        print(f"[ERROR] Error checking duplicate poems: {e}")
        return 1
    
    # Print rating statistics
    print("\n4. Printing image rating statistics...")
    try:
        print_rating_statistics()
    except Exception as e:
        print(f"[ERROR] Error printing rating statistics: {e}")
        return 1
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    if no_duplicate_images and no_duplicate_poems:
        print("[OK] All checks passed!")
    else:
        print("[WARNING] Some issues found (see warnings above)")
    print("="*60)
    
    return 0 if (no_duplicate_images and no_duplicate_poems) else 1


if __name__ == "__main__":
    sys.exit(main())
