# export.py
import os
import csv
import sqlite3
from openpyxl import Workbook

from config import DB_PATH, VOTES_CSV, CSV_ENCODING

EXPORT_COLUMNS = [
    "timestamp_iso","user_id","poem","left_path","right_path",
    "choice","preferred_path","response_ms"
]

def _fetch_all_rows():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT ts,user_id,poem,left_path,right_path,choice,preferred_path,response_ms "
        "FROM votes ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return rows

def export_votes_csv(out_path: str = VOTES_CSV) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows = _fetch_all_rows()
    with open(out_path, "w", newline="", encoding=CSV_ENCODING) as f:
        w = csv.writer(f)
        w.writerow(EXPORT_COLUMNS)
        w.writerows(rows)
    return out_path

def export_votes_xlsx(out_path: str) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rows = _fetch_all_rows()
    wb = Workbook()
    ws = wb.active
    ws.title = "votes"
    ws.append(EXPORT_COLUMNS)
    for r in rows:
        ws.append(list(r))
    wb.save(out_path)
    return out_path

if __name__ == "__main__":
    """
    Usage:
      python export.py csv
      python export.py csv /path/to/votes.csv
      python export.py xlsx /path/to/votes.xlsx
    """
    import sys

    mode = (sys.argv[1] if len(sys.argv) > 1 else "csv").lower()

    if mode == "csv":
        out = sys.argv[2] if len(sys.argv) > 2 else VOTES_CSV
        print(f"Exported CSV to: {export_votes_csv(out)}")

    elif mode == "xlsx":
        out = (
            sys.argv[2]
            if len(sys.argv) > 2
            else os.path.splitext(VOTES_CSV)[0] + ".xlsx"
        )
        print(f"Exported XLSX to: {export_votes_xlsx(out)}")

    else:
        raise SystemExit(
            "Usage: python export.py [csv|xlsx] [output_path]"
        )
