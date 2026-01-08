# storage.py
import sqlite3
import threading
from datetime import datetime
from config import DB_PATH
from utils.flush import maybe_flush

WRITE_LOCK = threading.Lock()

def db_connect():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)

    # ✅ Option A: single-file DB snapshot (best for HF upload)
    conn.execute("PRAGMA journal_mode=DELETE;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")

    # Drop old votes table if it exists (migration)
    conn.execute("DROP TABLE IF EXISTS votes")
    
    # Create users table to store demographics when users start
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users(
        user_id TEXT PRIMARY KEY,
        user_age INTEGER,
        user_gender TEXT,
        user_education TEXT,
        created_at TEXT
        )""")
    
    # Check if evaluations table exists and has old schema
    try:
        cursor = conn.execute("PRAGMA table_info(evaluations)")
        columns = [row[1] for row in cursor.fetchall()]
        # If table exists but missing new columns, drop and recreate
        if columns and ('user_age' not in columns or 'q1_answer' not in columns):
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

DB = db_connect()

def user_count(uid: str) -> int:
    with WRITE_LOCK:
        (n,) = DB.execute("SELECT COUNT(*) FROM evaluations WHERE user_id=?", (uid,)).fetchone()
    return int(n or 0)

def get_user_demographics(uid: str) -> dict:
    """Get user demographics (age, gender, education) from users table, or from first evaluation record."""
    with WRITE_LOCK:
        # First try to get from users table (stored when user starts)
        row = DB.execute(
            "SELECT user_age, user_gender, user_education FROM users WHERE user_id=?",
            (uid,)
        ).fetchone()
        if row:
            return {
                "age": row[0],
                "gender": row[1] or "",
                "education": row[2] or "",
            }
        # Fall back to evaluations table (for backward compatibility)
        row = DB.execute(
            "SELECT user_age, user_gender, user_education FROM evaluations WHERE user_id=? LIMIT 1",
            (uid,)
        ).fetchone()
        if row:
            return {
                "age": row[0],
                "gender": row[1] or "",
                "education": row[2] or "",
            }
    return None

def store_user_demographics(uid: str, user_age: int = None, user_gender: str = "", user_education: str = ""):
    """Store user demographics when user starts a session."""
    ts = datetime.utcnow().isoformat()
    with WRITE_LOCK:
        # Use INSERT OR REPLACE to update if user already exists
        DB.execute(
            """INSERT OR REPLACE INTO users(user_id, user_age, user_gender, user_education, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (uid, user_age, user_gender, user_education, ts)
        )
        DB.commit()

def write_evaluation(
    uid,
    user_age,
    user_gender,
    user_education,
    poem_title,
    image_path,
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
        DB.execute(
            """INSERT INTO evaluations(
                ts, user_id, user_age, user_gender, user_education,
                poem_title, image_path,
                phase1_choice, phase1_response_ms,
                q0_answer, q1_answer, q2_answer, q3_answer, q4_answer, q5_answer,
                q6_answer, q7_answer, q8_answer, q9_answer, q10_answer,
                q11_answer, q12_answer,
                phase2_response_ms, total_response_ms
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts, uid, user_age, user_gender, user_education,
                poem_title, image_path,
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
        DB.commit()
        maybe_flush()
    return ts
