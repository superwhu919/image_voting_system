# dump_db.py
import os
import csv
import sqlite3
from openpyxl import Workbook

from config import DB_PATH, EVALUATIONS_CSV, CSV_ENCODING

EXPORT_COLUMNS = [
    "id", "ts", "user_id", "poem_title", "image_path",
    "phase1_choice", "phase1_response_ms",
    "q2_main_subject", "q3_quantity", "q4_attributes",
    "q5_action_state", "q6_environment", "q7_seasonal_temporal",
    "q8_atmospheric_tone", "q9_historical_violations",
    "q10_irrelevant_intrusion", "q11_pseudo_text",
    "phase2_response_ms", "total_response_ms"
]

def _fetch_all_rows():
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        """SELECT id, ts, user_id, poem_title, image_path,
           phase1_choice, phase1_response_ms,
           q2_main_subject, q3_quantity, q4_attributes,
           q5_action_state, q6_environment, q7_seasonal_temporal,
           q8_atmospheric_tone, q9_historical_violations,
           q10_irrelevant_intrusion, q11_pseudo_text,
           phase2_response_ms, total_response_ms
           FROM evaluations ORDER BY id ASC"""
    ).fetchall()
    conn.close()
    return rows

def export_evaluations_csv(out_path: str = EVALUATIONS_CSV) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows = _fetch_all_rows()
    with open(out_path, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(EXPORT_COLUMNS)
        w.writerows(rows)
    return out_path

def export_evaluations_xlsx(out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows = _fetch_all_rows()
    wb = Workbook()
    ws = wb.active
    ws.title = "evaluations"
    ws.append(EXPORT_COLUMNS)
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
