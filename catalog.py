import os
import pandas as pd
from config import XLSX_PATH, ROOT_DIR_A, ROOT_DIR_B, A_SUFFIX, B_SUFFIX

def build_catalog(xlsx_path: str = XLSX_PATH,
                  root_a: str = ROOT_DIR_A,
                  root_b: str = ROOT_DIR_B):
    """
    Returns: { title: {"a": pathA, "b": pathB} }
    """
    if not os.path.isfile(xlsx_path):
        raise FileNotFoundError(f"Excel not found: {xlsx_path}")

    df = pd.read_excel(xlsx_path)
    catalog = {}

    for _, row in df.iterrows():
        title = str(row.get("Title", "")).strip()
        if not title:
            continue

        a_path = os.path.join(root_a, f"{title}{A_SUFFIX}")
        b_path = os.path.join(root_b, f"{title}{B_SUFFIX}")

        if os.path.isfile(a_path) and os.path.isfile(b_path):
            catalog[title] = {"a": a_path, "b": b_path}

    return catalog

def load_poem_info(xlsx_path: str = XLSX_PATH):
    """
    Returns:
      { title: { "author": ..., "content": ... } }
    """
    df = pd.read_excel(xlsx_path)
    poem_info = {}
    for _, row in df.iterrows():
        title = str(row.get("Title", "")).strip()
        author = str(row.get("Author", "")).strip()
        content = str(row.get("Content", "")).strip()
        if title:
            poem_info[title] = {
                "author": author,
                "content": content,
            }
    return poem_info

# Eagerly built globals used by logic.py
CATALOG   = build_catalog()
POEM_INFO = load_poem_info()
