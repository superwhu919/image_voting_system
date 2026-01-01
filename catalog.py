import os
import pandas as pd
from config import ROOT_DIR, XLSX_PATH

def build_catalog(xlsx_path: str = XLSX_PATH, root_dir: str = ROOT_DIR):
    """
    Returns: { title : [list_of_image_paths] }
    """
    if not os.path.isfile(xlsx_path):
        raise FileNotFoundError(f"Excel not found: {xlsx_path}")

    df = pd.read_excel(xlsx_path)
    catalog = {}
    for _, row in df.iterrows():
        title = str(row.get("Title", "")).strip()
        if not title:
            continue

        poem_dir = os.path.join(root_dir, title)
        if not os.path.isdir(poem_dir):
            continue

        imgs = [
            os.path.join(poem_dir, f)
            for f in os.listdir(poem_dir)
            if f.lower().endswith(".png")
        ]
        if len(imgs) >= 2:
            catalog[title] = sorted(imgs)

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
