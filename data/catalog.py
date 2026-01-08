import os
import random
import pandas as pd
from config import CSV_PATH, IMAGE_DIR, IMAGE_SUFFIX

def build_catalog(csv_path: str = CSV_PATH,
                  image_dir: str = IMAGE_DIR):
    """
    Returns: { title: image_path }
    Only includes poems that have Nano images.
    """
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    catalog = {}

    for _, row in df.iterrows():
        title = str(row.get("Title", "")).strip()
        if not title:
            continue

        image_path = os.path.join(image_dir, f"{title}{IMAGE_SUFFIX}")

        if os.path.isfile(image_path):
            catalog[title] = image_path

    return catalog

def load_poem_info(csv_path: str = CSV_PATH):
    """
    Returns:
      { title: { "author": ..., "content": ..., "similar_titles": [A, B, C] } }
    """
    df = pd.read_csv(csv_path)
    poem_info = {}
    for _, row in df.iterrows():
        title = str(row.get("Title", "")).strip()
        author = str(row.get("Author", "")).strip()
        content = str(row.get("Content", "")).strip()
        # Get similar titles from columns A, B, C
        similar_a = str(row.get("A", "")).strip()
        similar_b = str(row.get("B", "")).strip()
        similar_c = str(row.get("C", "")).strip()
        similar_titles = [t for t in [similar_a, similar_b, similar_c] if t]
        
        if title:
            poem_info[title] = {
                "author": author,
                "content": content,
                "similar_titles": similar_titles,
            }
    return poem_info

def get_distractors(target_title: str, catalog: dict, poem_info: dict, num_distractors: int = 3):
    """
    Get pre-defined similar distractors from CSV columns A, B, C for Phase 1 evaluation.
    Returns list of poem titles (excluding target).
    """
    # Get pre-defined similar titles from the CSV
    target_info = poem_info.get(target_title, {})
    similar_titles = target_info.get("similar_titles", [])
    
    # Filter to only include titles that exist in catalog and are not the target
    available_distractors = [
        t for t in similar_titles 
        if t in catalog and t != target_title
    ]
    
    # If we don't have enough pre-defined distractors, fall back to random selection
    if len(available_distractors) < num_distractors:
        available_titles = [t for t in catalog.keys() if t != target_title]
        # Combine pre-defined with random ones if needed
        if len(available_titles) < num_distractors:
            raise ValueError(f"Not enough poems for distractors. Need {num_distractors}, have {len(available_titles)}")
        
        # Use pre-defined ones first, then fill with random
        remaining_needed = num_distractors - len(available_distractors)
        remaining_titles = [t for t in available_titles if t not in available_distractors]
        additional = random.sample(remaining_titles, min(remaining_needed, len(remaining_titles)))
        available_distractors.extend(additional)
    
    # Return exactly num_distractors (take first num_distractors from available)
    return available_distractors[:num_distractors]

# Eagerly built globals used by logic.py
CATALOG   = build_catalog()
POEM_INFO = load_poem_info()
