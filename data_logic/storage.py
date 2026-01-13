# storage.py
import sqlite3
import threading
from datetime import datetime
from config import USERS_DB_PATH, EVALUATIONS_DB_PATH
from utils.flush import maybe_flush

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
            # If missing other critical columns, drop and recreate
            required_columns = ['user_age', 'q1_answer', 'image_path']
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
        phase1_choice TEXT,
        phase1_response_ms INTEGER,
        q0_answer TEXT,
        q1_answer TEXT,
        q2_answer TEXT,
        q3_answer TEXT,
        q4_answer TEXT,
        q5_answer TEXT,
        q6_answer TEXT,
        q7_answer TEXT,
        q8_answer TEXT,
        q9_answer TEXT,
        q10_answer TEXT,
        q11_answer TEXT,
        q12_answer TEXT,
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
    phase1_response_ms,
    phase2_answers,  # dict with keys q1, q2, ..., q12
    phase2_response_ms,
    total_response_ms
):
    """
    Write a complete evaluation to the database.
    phase2_answers should be a dict like:
    {
        "q1": "A",
        "q2": "Present",
        ...
        "q12": "Refined and expressive"
    }
    """
    ts = datetime.utcnow().isoformat()
    with WRITE_LOCK:
        EVALUATIONS_DB.execute(
            """INSERT INTO evaluations(
                ts, user_id, user_age, user_gender, user_education,
                poem_title, image_path, image_type,
                phase1_choice, phase1_response_ms,
                q0_answer, q1_answer, q2_answer, q3_answer, q4_answer, q5_answer,
                q6_answer, q7_answer, q8_answer, q9_answer, q10_answer,
                q11_answer, q12_answer,
                phase2_response_ms, total_response_ms
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts, uid, user_age, user_gender, user_education,
                poem_title, image_path, image_type,
                phase1_choice, phase1_response_ms,
                phase1_choice,  # q0_answer is the same as phase1_choice (A/B/C/D)
                phase2_answers.get("q1", ""),
                phase2_answers.get("q2", ""),
                phase2_answers.get("q3", ""),
                phase2_answers.get("q4", ""),
                phase2_answers.get("q5", ""),
                phase2_answers.get("q6", ""),
                phase2_answers.get("q7", ""),
                phase2_answers.get("q8", ""),
                phase2_answers.get("q9", ""),
                phase2_answers.get("q10", ""),
                phase2_answers.get("q11", ""),
                phase2_answers.get("q12", ""),
                phase2_response_ms, total_response_ms
            ),
        )
        EVALUATIONS_DB.commit()
        maybe_flush()
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

def get_coverage_metrics(total_images: int) -> dict:
    """Calculate coverage metrics.
    Args:
        total_images: Total number of images in catalog
    Returns:
        {
            "total_images": int,
            "images_with_5_ratings": int,
            "images_with_at_least_1_rating": int,
            "coverage_5_ratings": float,  # percentage
            "coverage_at_least_1": float,  # percentage
            "current_round": int,  # 1-5
            "round_progress": dict  # {"round": int, "completed": int, "total": int}
        }
    """
    rating_counts = get_all_image_rating_counts()
    
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
