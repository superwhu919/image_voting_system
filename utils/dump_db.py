# dump_db.py
import os
import sys
import csv
import sqlite3
import json
from pathlib import Path
from openpyxl import Workbook

# Add parent directory to path so we can import config when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH, EVALUATIONS_CSV, CSV_ENCODING

def _fetch_all_rows():
    """Fetch all evaluation rows, handling both old and new schema."""
    conn = sqlite3.connect(str(DB_PATH))
    
    # Check if answers_json column exists
    cursor = conn.execute("PRAGMA table_info(evaluations)")
    columns = [row[1] for row in cursor.fetchall()]
    has_json_column = 'answers_json' in columns
    
    if has_json_column:
        # New schema: read from JSON column
        # Check if phase1_choice column exists (for backward compatibility)
        cursor = conn.execute("PRAGMA table_info(evaluations)")
        columns = [row[1] for row in cursor.fetchall()]
        has_phase1_choice = 'phase1_choice' in columns
        
        # Check if q1_1_right_answer column exists
        cursor = conn.execute("PRAGMA table_info(evaluations)")
        columns = [row[1] for row in cursor.fetchall()]
        has_q1_1_right_answer = 'q1_1_right_answer' in columns
        
        if has_phase1_choice:
            # Old new schema (with phase1_choice)
            if has_q1_1_right_answer:
                rows = conn.execute(
                    """SELECT id, ts, user_id, user_age, user_gender, user_education,
                       poem_title, image_path, image_type, q1_1_right_answer,
                       phase1_choice, phase1_response_ms,
                       answers_json,
                       phase2_response_ms, total_response_ms
                       FROM evaluations ORDER BY id ASC"""
                ).fetchall()
                answers_json_index = 12  # after phase1_response_ms
            else:
                rows = conn.execute(
                    """SELECT id, ts, user_id, user_age, user_gender, user_education,
                       poem_title, image_path, image_type,
                       phase1_choice, phase1_response_ms,
                       answers_json,
                       phase2_response_ms, total_response_ms
                       FROM evaluations ORDER BY id ASC"""
                ).fetchall()
                answers_json_index = 11  # after phase1_response_ms
        else:
            # New clean schema (without phase1_choice)
            if has_q1_1_right_answer:
                rows = conn.execute(
                    """SELECT id, ts, user_id, user_age, user_gender, user_education,
                       poem_title, image_path, image_type, q1_1_right_answer,
                       phase1_response_ms,
                       answers_json,
                       phase2_response_ms, total_response_ms
                       FROM evaluations ORDER BY id ASC"""
                ).fetchall()
                answers_json_index = 11  # after phase1_response_ms
            else:
                rows = conn.execute(
                    """SELECT id, ts, user_id, user_age, user_gender, user_education,
                       poem_title, image_path, image_type,
                       phase1_response_ms,
                       answers_json,
                       phase2_response_ms, total_response_ms
                       FROM evaluations ORDER BY id ASC"""
                ).fetchall()
                answers_json_index = 10  # after phase1_response_ms
        
        # First, collect all unique question IDs from all rows
        all_question_ids = set()
        for row in rows:
            answers_json_str = row[answers_json_index]
            if answers_json_str:
                try:
                    answers = json.loads(answers_json_str)
                    all_question_ids.update(answers.keys())
                except (json.JSONDecodeError, TypeError):
                    pass
        question_columns = sorted(all_question_ids)
        
        # Parse JSON and expand answers into columns
        expanded_rows = []
        for row in rows:
            row_list = list(row)
            # answers_json index depends on schema
            answers_json_str = row_list[answers_json_index]
            answers = {}
            if answers_json_str:
                try:
                    answers = json.loads(answers_json_str)
                except (json.JSONDecodeError, TypeError):
                    answers = {}
            
            # Replace answers_json with expanded columns (all question IDs, even if empty)
            # This ensures all rows have the same number of columns
            expanded_answers = [answers.get(qid, "") for qid in question_columns]
            row_list = row_list[:answers_json_index] + expanded_answers + row_list[answers_json_index+1:]
            expanded_rows.append(tuple(row_list))
        
        conn.close()
        return expanded_rows, question_columns, has_phase1_choice
    else:
        # Old schema: read from individual columns (backward compatibility)
        # Check if q1_1_right_answer column exists
        cursor = conn.execute("PRAGMA table_info(evaluations)")
        columns = [row[1] for row in cursor.fetchall()]
        has_q1_1_right_answer = 'q1_1_right_answer' in columns
        has_phase1_choice = 'phase1_choice' in columns
        
        if has_q1_1_right_answer:
            rows = conn.execute(
                """SELECT id, ts, user_id, user_age, user_gender, user_education,
                   poem_title, image_path, image_type, q1_1_right_answer,
                   phase1_choice, phase1_response_ms,
                   q0_answer, q1_answer, q2_answer, q3_answer, q4_answer, q5_answer,
                   q6_answer, q7_answer, q8_answer, q9_answer, q10_answer,
                   q11_answer, q12_answer,
                   phase2_response_ms, total_response_ms
                   FROM evaluations ORDER BY id ASC"""
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, ts, user_id, user_age, user_gender, user_education,
                   poem_title, image_path, image_type,
                   phase1_choice, phase1_response_ms,
                   q0_answer, q1_answer, q2_answer, q3_answer, q4_answer, q5_answer,
                   q6_answer, q7_answer, q8_answer, q9_answer, q10_answer,
                   q11_answer, q12_answer,
                   phase2_response_ms, total_response_ms
                   FROM evaluations ORDER BY id ASC"""
            ).fetchall()
        # Old column names for backward compatibility
        question_columns = ["q0_answer", "q1_answer", "q2_answer", "q3_answer", "q4_answer", 
                          "q5_answer", "q6_answer", "q7_answer", "q8_answer", "q9_answer", 
                          "q10_answer", "q11_answer", "q12_answer"]
        conn.close()
        return rows, question_columns, has_phase1_choice

def export_evaluations_csv(out_path: str = EVALUATIONS_CSV) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows, question_columns, has_phase1_choice = _fetch_all_rows()
    
    # Check if q1_1_right_answer column exists
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("PRAGMA table_info(evaluations)")
    columns = [row[1] for row in cursor.fetchall()]
    has_q1_1_right_answer = 'q1_1_right_answer' in columns
    conn.close()
    
    # Build column headers
    base_columns = [
        "id", "ts", "user_id", "user_age", "user_gender", "user_education",
        "poem_title", "image_path", "image_type"
    ]
    # Add q1_1_right_answer right after image_type if it exists
    if has_q1_1_right_answer:
        base_columns.append("q1_1_right_answer")
    # Add phase1_choice only if it exists in the schema
    if has_phase1_choice:
        base_columns.append("phase1_choice")
    base_columns.append("phase1_response_ms")
    
    export_columns = base_columns + question_columns + [
        "phase2_response_ms", "total_response_ms"
    ]
    
    with open(out_path, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(export_columns)
        w.writerows(rows)
    return out_path

def export_evaluations_xlsx(out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows, question_columns, has_phase1_choice = _fetch_all_rows()
    
    # Check if q1_1_right_answer column exists
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.execute("PRAGMA table_info(evaluations)")
    columns = [row[1] for row in cursor.fetchall()]
    has_q1_1_right_answer = 'q1_1_right_answer' in columns
    conn.close()
    
    # Build column headers
    base_columns = [
        "id", "ts", "user_id", "user_age", "user_gender", "user_education",
        "poem_title", "image_path", "image_type"
    ]
    # Add q1_1_right_answer right after image_type if it exists
    if has_q1_1_right_answer:
        base_columns.append("q1_1_right_answer")
    # Add phase1_choice only if it exists in the schema
    if has_phase1_choice:
        base_columns.append("phase1_choice")
    base_columns.append("phase1_response_ms")
    
    export_columns = base_columns + question_columns + [
        "phase2_response_ms", "total_response_ms"
    ]
    
    wb = Workbook()
    ws = wb.active
    ws.title = "evaluations"
    ws.append(export_columns)
    for r in rows:
        ws.append(list(r))
    wb.save(out_path)
    return out_path

if __name__ == "__main__":
    """
    Usage:
      python dump_db.py csv
      python dump_db.py csv /path/to/evaluations.csv
      python dump_db.py xlsx /path/to/evaluations.xlsx
    """
    import sys

    mode = (sys.argv[1] if len(sys.argv) > 1 else "csv").lower()

    if mode == "csv":
        out = sys.argv[2] if len(sys.argv) > 2 else EVALUATIONS_CSV
        print(f"Exported CSV to: {export_evaluations_csv(out)}")

    elif mode == "xlsx":
        out = (
            sys.argv[2]
            if len(sys.argv) > 2
            else os.path.splitext(str(EVALUATIONS_CSV))[0] + ".xlsx"
        )
        print(f"Exported XLSX to: {export_evaluations_xlsx(out)}")

    else:
        raise SystemExit(
            "Usage: python dump_db.py [csv|xlsx] [output_path]"
        )
