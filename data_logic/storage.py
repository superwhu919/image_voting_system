# storage.py
import sqlite3
import threading
import json
from datetime import datetime
from config import USERS_DB_PATH, EVALUATIONS_DB_PATH

WRITE_LOCK = threading.Lock()

def connect_users_db():
    """Connect to users database."""
    conn = sqlite3.connect(str(USERS_DB_PATH), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    
    # Create users table to store demographics when users start
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
        user_id TEXT PRIMARY KEY,
        user_age INTEGER,
        user_gender TEXT,
        user_education TEXT,
        user_limit INTEGER,
        created_at TEXT
        )""")
    
    # Add user_limit column if it doesn't exist (for existing databases)
    try:
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'user_limit' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN user_limit INTEGER")
            conn.commit()
        # Add seen_titles and seen_paths columns if they don't exist
        if 'seen_titles' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN seen_titles TEXT")
            conn.commit()
        if 'seen_paths' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN seen_paths TEXT")
            conn.commit()
    except:
        pass
    
    return conn

def connect_evaluations_db():
    """Connect to evaluations database."""
    conn = sqlite3.connect(str(EVALUATIONS_DB_PATH), check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    
    # Drop old votes table if it exists (migration)
    conn.execute("DROP TABLE IF EXISTS votes")
    
    # Check if evaluations table exists and has old schema
    try:
        cursor = conn.execute("PRAGMA table_info(evaluations)")
        columns = [row[1] for row in cursor.fetchall()]
        # If table exists but missing new columns, add them
        if columns:
            if 'image_type' not in columns:
                conn.execute("ALTER TABLE evaluations ADD COLUMN image_type TEXT")
                conn.commit()
            # Add q1_1_right_answer column if it doesn't exist (right after image_type)
            if 'q1_1_right_answer' not in columns:
                conn.execute("ALTER TABLE evaluations ADD COLUMN q1_1_right_answer TEXT")
                conn.commit()
            # Add answers_json column if it doesn't exist
            if 'answers_json' not in columns:
                conn.execute("ALTER TABLE evaluations ADD COLUMN answers_json TEXT")
                conn.commit()
            # If missing other critical columns, drop and recreate
            required_columns = ['user_age', 'image_path']
            if not all(col in columns for col in required_columns):
                conn.execute("DROP TABLE IF EXISTS evaluations")
                columns = []
    except:
        columns = []
    
    if not columns:  # Table doesn't exist or was dropped
        conn.execute("""
        CREATE TABLE evaluations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        user_id TEXT,
        user_age INTEGER,
        user_gender TEXT,
        user_education TEXT,
        poem_title TEXT,
        image_path TEXT,
        image_type TEXT,
        q1_1_right_answer TEXT,
        phase1_response_ms INTEGER,
        answers_json TEXT,
        phase2_response_ms INTEGER,
        total_response_ms INTEGER
        )""")
        conn.commit()
    
    return conn

# Initialize both database connections
USERS_DB = connect_users_db()
EVALUATIONS_DB = connect_evaluations_db()

def user_count(uid: str) -> int:
    """Count how many evaluations a user has completed."""
    with WRITE_LOCK:
        (n,) = EVALUATIONS_DB.execute("SELECT COUNT(*) FROM evaluations WHERE user_id=?", (uid,)).fetchone()
    return int(n or 0)

def get_user_demographics(uid: str) -> dict:
    """Get user demographics (age, gender, education) from users table, or from first evaluation record."""
    with WRITE_LOCK:
        # First try to get from users table (stored when user starts)
        row = USERS_DB.execute(
            "SELECT user_age, user_gender, user_education, user_limit FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()
        if row:
            return {
                "age": row[0],
                "gender": row[1] or "",
                "education": row[2] or "",
                "user_limit": row[3],  # Can be None
            }
        # Fall back to evaluations table (for backward compatibility)
        row = EVALUATIONS_DB.execute(
            "SELECT user_age, user_gender, user_education FROM evaluations WHERE user_id=? LIMIT 1",
            (uid,)
        ).fetchone()
        if row:
            return {
                "age": row[0],
                "gender": row[1] or "",
                "education": row[2] or "",
                "user_limit": None,
            }
    return None

def get_user_limit(uid: str) -> int:
    """Get user-specific limit, or None if using default."""
    with WRITE_LOCK:
        row = USERS_DB.execute(
            "SELECT user_limit FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()
        if row and row[0] is not None:
            return int(row[0])
    return None

def increase_user_limit(uid: str, increment: int = 5) -> int:
    """Increase user's limit by increment. Returns new limit."""
    with WRITE_LOCK:
        # Get current limit directly (don't call get_user_limit to avoid deadlock)
        row = USERS_DB.execute(
            "SELECT user_limit FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()
        
        if row and row[0] is not None:
            current_limit = int(row[0])
        else:
            # User doesn't have a custom limit yet, get from config
            from config import MAX_PER_USER
            current_limit = MAX_PER_USER
        
        new_limit = current_limit + increment
        
        # Update user limit (user should exist since start_session creates them first)
        # Use UPDATE with WHERE to ensure we only update existing users
        USERS_DB.execute(
            """UPDATE users SET user_limit = ? WHERE user_id = ?""",
            (new_limit, uid)
        )
        # If user doesn't exist, this won't update anything, but that's okay
        # since start_session should have created the user first
        USERS_DB.commit()
    
    return new_limit

def store_user_demographics(uid: str, user_age: int = None, user_gender: str = "", user_education: str = ""):
    """Store user demographics when user starts a session."""
    ts = datetime.utcnow().isoformat()
    with WRITE_LOCK:
        # Use INSERT OR REPLACE to update if user already exists
        USERS_DB.execute(
            """INSERT OR REPLACE INTO users(user_id, user_age, user_gender, user_education, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (uid, user_age, user_gender, user_education, ts)
        )
        USERS_DB.commit()

def write_evaluation(
    uid,
    user_age,
    user_gender,
    user_education,
    poem_title,
    image_path,
    image_type,
    phase1_choice,
    target_letter=None,  # The correct answer for q1-1 (A, B, C, or D)
    phase1_answers=None,  # dict with keys q1-1, q1-2
    phase1_response_ms=0,
    phase2_answers=None,  # dict with keys q2-1, q2-2, ..., q2-N (any number)
    phase2_response_ms=0,
    total_response_ms=0
):
    """
    Write a complete evaluation to the database.
    
    All answers are stored in a JSON column for flexibility.
    
    phase2_answers should be a dict like:
    {
        "q2-1": "A",
        "q2-2": "Clear",
        ...
        "q2-13": "High alignment"
    }
    phase1_answers should be a dict like:
    {
        "q1-1": "A",  # phase1_choice (optional, will use phase1_choice if not provided)
        "q1-2": "Very confident"
    }
    """
    if phase1_answers is None:
        phase1_answers = {}
    if phase2_answers is None:
        phase2_answers = {}
    
    # Build complete answers dict
    # Include phase1_choice as q1-1 if not already in phase1_answers
    if "q1-1" not in phase1_answers:
        phase1_answers["q1-1"] = phase1_choice
    
    # Combine all answers into a single dict
    all_answers = {}
    all_answers.update(phase1_answers)
    all_answers.update(phase2_answers)
    
    # Convert to JSON string
    answers_json = json.dumps(all_answers, ensure_ascii=False)
    
    ts = datetime.utcnow().isoformat()
    with WRITE_LOCK:
        # Check if old columns exist for backward compatibility
        cursor = EVALUATIONS_DB.execute("PRAGMA table_info(evaluations)")
        columns = [row[1] for row in cursor.fetchall()]
        has_old_columns = 'q0_answer' in columns
        has_q1_1_right_answer = 'q1_1_right_answer' in columns
        
        if has_old_columns:
            # Old schema: include old columns for backward compatibility
            if has_q1_1_right_answer:
                EVALUATIONS_DB.execute(
                    """INSERT INTO evaluations(
                        ts, user_id, user_age, user_gender, user_education,
                        poem_title, image_path, image_type, q1_1_right_answer,
                        phase1_choice, phase1_response_ms,
                        q0_answer, q1_answer, q2_answer, q3_answer, q4_answer, q5_answer,
                        q6_answer, q7_answer, q8_answer, q9_answer, q10_answer,
                        q11_answer, q12_answer, answers_json,
                        phase2_response_ms, total_response_ms
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ts, uid, user_age, user_gender, user_education,
                        poem_title, image_path, image_type, target_letter or "",
                        phase1_choice, phase1_response_ms,
                        phase1_choice,  # q0_answer is the same as phase1_choice (A/B/C/D)
                        phase2_answers.get("q2-1", ""),  # q1_answer
                        phase2_answers.get("q2-2", ""),  # q2_answer
                        phase2_answers.get("q2-3", ""),  # q3_answer
                        phase2_answers.get("q2-4", ""),  # q4_answer
                        phase2_answers.get("q2-5", ""),  # q5_answer
                        phase2_answers.get("q2-6", ""),  # q6_answer
                        phase2_answers.get("q2-7", ""),  # q7_answer
                        phase2_answers.get("q2-8", ""),  # q8_answer
                        phase2_answers.get("q2-9", ""),  # q9_answer
                        phase2_answers.get("q2-10", ""),  # q10_answer
                        phase2_answers.get("q2-11", ""),  # q11_answer
                        phase2_answers.get("q2-12", ""),  # q12_answer
                        answers_json,  # New JSON column with all answers
                        phase2_response_ms, total_response_ms
                    ),
                )
            else:
                # Old schema without q1_1_right_answer column
                EVALUATIONS_DB.execute(
                    """INSERT INTO evaluations(
                        ts, user_id, user_age, user_gender, user_education,
                        poem_title, image_path, image_type,
                        phase1_choice, phase1_response_ms,
                        q0_answer, q1_answer, q2_answer, q3_answer, q4_answer, q5_answer,
                        q6_answer, q7_answer, q8_answer, q9_answer, q10_answer,
                        q11_answer, q12_answer, answers_json,
                        phase2_response_ms, total_response_ms
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ts, uid, user_age, user_gender, user_education,
                        poem_title, image_path, image_type,
                        phase1_choice, phase1_response_ms,
                        phase1_choice,  # q0_answer is the same as phase1_choice (A/B/C/D)
                        phase2_answers.get("q2-1", ""),  # q1_answer
                        phase2_answers.get("q2-2", ""),  # q2_answer
                        phase2_answers.get("q2-3", ""),  # q3_answer
                        phase2_answers.get("q2-4", ""),  # q4_answer
                        phase2_answers.get("q2-5", ""),  # q5_answer
                        phase2_answers.get("q2-6", ""),  # q6_answer
                        phase2_answers.get("q2-7", ""),  # q7_answer
                        phase2_answers.get("q2-8", ""),  # q8_answer
                        phase2_answers.get("q2-9", ""),  # q9_answer
                        phase2_answers.get("q2-10", ""),  # q10_answer
                        phase2_answers.get("q2-11", ""),  # q11_answer
                        phase2_answers.get("q2-12", ""),  # q12_answer
                        answers_json,  # New JSON column with all answers
                        phase2_response_ms, total_response_ms
                    ),
                )
        else:
            # New schema: only use JSON column (phase1_choice is in JSON as "q1-1")
            if has_q1_1_right_answer:
                EVALUATIONS_DB.execute(
                    """INSERT INTO evaluations(
                        ts, user_id, user_age, user_gender, user_education,
                        poem_title, image_path, image_type, q1_1_right_answer,
                        phase1_response_ms,
                        answers_json,
                        phase2_response_ms, total_response_ms
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ts, uid, user_age, user_gender, user_education,
                        poem_title, image_path, image_type, target_letter or "",
                        phase1_response_ms,
                        answers_json,
                        phase2_response_ms, total_response_ms
                    ),
                )
            else:
                # New schema without q1_1_right_answer column (backward compatibility)
                EVALUATIONS_DB.execute(
                    """INSERT INTO evaluations(
                        ts, user_id, user_age, user_gender, user_education,
                        poem_title, image_path, image_type,
                        phase1_response_ms,
                        answers_json,
                        phase2_response_ms, total_response_ms
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ts, uid, user_age, user_gender, user_education,
                        poem_title, image_path, image_type,
                        phase1_response_ms,
                        answers_json,
                        phase2_response_ms, total_response_ms
                    ),
                )
        EVALUATIONS_DB.commit()
    return ts

def get_image_rating_count(image_path: str) -> int:
    """Count how many ratings (evaluations) an image has."""
    with WRITE_LOCK:
        (count,) = EVALUATIONS_DB.execute(
            "SELECT COUNT(*) FROM evaluations WHERE image_path = ?",
            (image_path,)
        ).fetchone()
    return int(count or 0)

def get_all_image_rating_counts() -> dict:
    """Get rating counts for all images that have been evaluated.
    Returns: {image_path: rating_count}
    """
    with WRITE_LOCK:
        rows = EVALUATIONS_DB.execute(
            "SELECT image_path, COUNT(*) as count FROM evaluations GROUP BY image_path"
        ).fetchall()
    return {image_path: int(count) for image_path, count in rows}

def load_user_state(user_id: str) -> dict:
    """
    Load user state (seen_titles and seen_paths) from database.
    
    Returns:
        dict with 'seen_titles' and 'seen_paths' as sets, or None if user doesn't exist
    """
    with WRITE_LOCK:
        row = USERS_DB.execute(
            "SELECT seen_titles, seen_paths FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()
        
        if row is None:
            return None
        
        seen_titles_json = row[0]
        seen_paths_json = row[1]
        
        # Parse JSON arrays, default to empty sets if NULL or empty
        seen_titles = set()
        seen_paths = set()
        
        if seen_titles_json:
            try:
                seen_titles = set(json.loads(seen_titles_json))
            except (json.JSONDecodeError, TypeError):
                seen_titles = set()
        
        if seen_paths_json:
            try:
                seen_paths = set(json.loads(seen_paths_json))
            except (json.JSONDecodeError, TypeError):
                seen_paths = set()
        
        return {
            'seen_titles': seen_titles,
            'seen_paths': seen_paths
        }


def save_user_state(user_id: str, seen_titles: set, seen_paths: set):
    """
    Save user state (seen_titles and seen_paths) to database.
    
    Args:
        user_id: User ID
        seen_titles: Set of poem titles the user has seen
        seen_paths: Set of image paths the user has seen
    """
    with WRITE_LOCK:
        # Convert sets to JSON arrays
        seen_titles_json = json.dumps(list(seen_titles), ensure_ascii=False)
        seen_paths_json = json.dumps(list(seen_paths), ensure_ascii=False)
        
        # Update user state (user must exist - this is called after user is created)
        USERS_DB.execute(
            """UPDATE users SET seen_titles = ?, seen_paths = ? WHERE user_id = ?""",
            (seen_titles_json, seen_paths_json, user_id)
        )
        USERS_DB.commit()


def save_user_seen_titles(user_id: str, seen_titles: set):
    """Save only seen_titles to database."""
    with WRITE_LOCK:
        seen_titles_json = json.dumps(list(seen_titles), ensure_ascii=False)
        USERS_DB.execute(
            """UPDATE users SET seen_titles = ? WHERE user_id = ?""",
            (seen_titles_json, user_id)
        )
        USERS_DB.commit()


def save_user_seen_paths(user_id: str, seen_paths: set):
    """Save only seen_paths to database."""
    with WRITE_LOCK:
        seen_paths_json = json.dumps(list(seen_paths), ensure_ascii=False)
        USERS_DB.execute(
            """UPDATE users SET seen_paths = ? WHERE user_id = ?""",
            (seen_paths_json, user_id)
        )
        USERS_DB.commit()


def get_total_ratings_count() -> int:
    """Get total number of ratings collected from database."""
    with WRITE_LOCK:
        (count,) = EVALUATIONS_DB.execute("SELECT COUNT(*) FROM evaluations").fetchone()
        return int(count or 0)


def get_coverage_metrics(total_images: int) -> dict:
    """Calculate coverage metrics.
    Args:
        total_images: Total number of images in catalog
    Returns:
        {
            "total_images": int,
            "total_ratings": int,  # Total ratings collected from database
            "target_ratings": int,  # Target: total_images * 5
            "ratings_progress": float,  # Percentage: (total_ratings / target_ratings) * 100
            "images_with_5_ratings": int,
            "images_with_at_least_1_rating": int,
            "coverage_5_ratings": float,  # percentage
            "coverage_at_least_1": float,  # percentage
            "current_round": int,  # 1-5
            "round_progress": dict  # {"round": int, "completed": int, "total": int}
        }
    """
    rating_counts = get_all_image_rating_counts()
    total_ratings = get_total_ratings_count()
    target_ratings = total_images * 5
    
    images_with_5_ratings = sum(1 for count in rating_counts.values() if count >= 5)
    images_with_at_least_1 = len(rating_counts)
    
    # Calculate current round
    if not rating_counts:
        current_round = 1
        round_completed = 0
    else:
        min_ratings = min(rating_counts.values())
        current_round = min(min_ratings + 1, 5)  # Cap at round 5
        # Count images at target rating for current round
        target_rating = current_round - 1
        round_completed = sum(1 for count in rating_counts.values() if count >= target_rating)
    
    return {
        "total_images": total_images,
        "total_ratings": total_ratings,
        "target_ratings": target_ratings,
        "ratings_progress": (total_ratings / target_ratings * 100) if target_ratings > 0 else 0.0,
        "images_with_5_ratings": images_with_5_ratings,
        "images_with_at_least_1_rating": images_with_at_least_1,
        "coverage_5_ratings": (images_with_5_ratings / total_images * 100) if total_images > 0 else 0.0,
        "coverage_at_least_1": (images_with_at_least_1 / total_images * 100) if total_images > 0 else 0.0,
        "current_round": current_round,
        "round_progress": {
            "round": current_round,
            "completed": round_completed,
            "total": total_images
        }
    }


def get_recent_completed_ratings(limit: int = 100) -> list:
    """
    Get recent completed ratings with user names and image paths.
    
    Args:
        limit: Maximum number of recent ratings to return
    
    Returns:
        List of dicts with keys: user_id, image_path, poem_title, ts (timestamp)
    """
    with WRITE_LOCK:
        rows = EVALUATIONS_DB.execute(
            """SELECT user_id, image_path, poem_title, ts 
               FROM evaluations 
               ORDER BY ts DESC 
               LIMIT ?""",
            (limit,)
        ).fetchall()
    
    return [
        {
            "user_id": row[0],
            "image_path": row[1],
            "poem_title": row[2],
            "ts": row[3]
        }
        for row in rows
    ]
