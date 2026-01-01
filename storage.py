# storage.py
import sqlite3
import threading
from datetime import datetime
from config import DB_PATH

WRITE_LOCK = threading.Lock()

def db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("""CREATE TABLE IF NOT EXISTS votes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT, user_id TEXT, poem TEXT,
        left_path TEXT, right_path TEXT,
        choice TEXT, preferred_path TEXT,
        response_ms INTEGER
    )""")
    conn.commit()
    return conn

DB = db_connect()

def user_count(uid: str) -> int:
    with WRITE_LOCK:
        (n,) = DB.execute("SELECT COUNT(*) FROM votes WHERE user_id=?", (uid,)).fetchone()
    return int(n or 0)

def write_vote(uid, poem_title, left, right, choice, preferred, response_ms):
    ts = datetime.utcnow().isoformat()
    with WRITE_LOCK:
        DB.execute(
            "INSERT INTO votes(ts,user_id,poem,left_path,right_path,choice,preferred_path,response_ms) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (ts, uid, poem_title, left, right, choice, preferred, response_ms),
        )
        DB.commit()
    return ts
