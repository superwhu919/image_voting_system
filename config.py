import os

# -----------------------------------
# Base directory (project root)
# -----------------------------------
# Example:
# project/
#   final_3/
#   tangshi_sub1.xlsx
#   voting_system/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -----------------------------------
# Dataset paths
# -----------------------------------
ROOT_DIR = os.path.join(BASE_DIR, "final_3")
ROOT_ABS = ROOT_DIR

XLSX_PATH = os.path.join(BASE_DIR, "tangshi_sub1.xlsx")

# -----------------------------------
# Output / persistence paths
# -----------------------------------
VOTES_CSV = os.path.join(BASE_DIR, "votes.csv")
DB_PATH = os.path.join(BASE_DIR, "votes.db")

# -----------------------------------
# Settings
# -----------------------------------
MAX_PER_USER = 10
CSV_ENCODING = "utf-8-sig"
