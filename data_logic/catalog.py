import os
import random
import pandas as pd
from pathlib import Path
from config import CSV_PATH, IMAGE_DIR

def build_catalog(image_dir: str = IMAGE_DIR):
    """
    Scan image directory and build catalog from filenames.
    Images are named as: {poem_title}_{type}.jpg or {poem_title}_{type}.png where type is gpt, mj, nano, or seedream.
    
    Returns: { image_path: {"poem_title": str, "image_type": str} }
    """
    image_dir_path = Path(image_dir)
    if not image_dir_path.exists():
        raise FileNotFoundError(f"Image directory not found: {image_dir}")
    
    catalog = {}
    valid_types = {"gpt", "mj", "nano", "seedream"}
    
    # Scan all image files (both JPG and PNG) in directory
    for image_file in list(image_dir_path.glob("*.jpg")) + list(image_dir_path.glob("*.png")):
        filename = image_file.name
        # Remove extension (.jpg or .png - both are 3 characters)
        name_without_ext = filename[:-4]
        
        # Parse filename: {poem_title}_{type}
        # Find the last underscore to split title and type
        last_underscore_idx = name_without_ext.rfind("_")
        if last_underscore_idx == -1:
            # No underscore found, skip this file
            continue
        
        poem_title = name_without_ext[:last_underscore_idx]
        image_type = name_without_ext[last_underscore_idx + 1:]
        
        # Validate type
        if image_type not in valid_types:
            continue
        
        # Store with full path
        image_path = str(image_file.resolve())
        catalog[image_path] = {
            "poem_title": poem_title,
            "image_type": image_type
        }
    
    if not catalog:
        raise RuntimeError(f"No valid images found in {image_dir}. Expected format: {{poem_title}}_{{type}}.jpg or {{poem_title}}_{{type}}.png")
    
    print(f"Built catalog with {len(catalog)} images from {image_dir}")
    return catalog

def load_poem_info(csv_path: str = CSV_PATH):
    """
    Load poem information from CSV file.
    
    Returns:
      { title: { "author": ..., "content": ..., "similar_titles": [A, B, C] } }
    """
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
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
    Get pre-defined similar distractors from Excel/CSV columns A, B, C for Phase 1 evaluation.
    Returns list of poem titles (excluding target).
    
    Note: catalog is now {image_path: {poem_title, image_type}}, so we need to extract unique poem titles.
    """
    # Get all unique poem titles from catalog
    catalog_poem_titles = set()
    for image_data in catalog.values():
        catalog_poem_titles.add(image_data["poem_title"])
    
    # Get pre-defined similar titles from the Excel/CSV
    target_info = poem_info.get(target_title, {})
    similar_titles = target_info.get("similar_titles", [])
    
    # Filter to only include titles that exist in catalog and are not the target
    available_distractors = [
        t for t in similar_titles 
        if t in catalog_poem_titles and t != target_title
    ]
    
    # If we don't have enough pre-defined distractors, fall back to random selection
    if len(available_distractors) < num_distractors:
        available_titles = [t for t in catalog_poem_titles if t != target_title]
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
