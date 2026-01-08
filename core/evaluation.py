# Core evaluation logic: poem selection and formatting
import random
from data.catalog import CATALOG, POEM_INFO, get_distractors


def get_evaluation_item():
    """
    Get a random poem with its image and 3 distractors for Phase 1.
    Returns: (poem_title, image_path, distractors_list, poem_options_dict, target_letter)
    poem_options_dict: {"A": poem_title, "B": distractor1, "C": distractor2, "D": distractor3}
    """
    keys = list(CATALOG.keys())
    if not keys:
        raise RuntimeError("CATALOG is empty (no valid images found).")

    target_title = random.choice(keys)
    image_path = CATALOG[target_title]
    
    # Get 3 pre-defined similar distractors from CSV
    distractor_titles = get_distractors(target_title, CATALOG, POEM_INFO, num_distractors=3)
    
    # Create options: A = target, B/C/D = distractors (shuffled)
    all_options = [target_title] + distractor_titles
    random.shuffle(all_options)
    
    # Find which letter is the target
    target_letter = None
    options_dict = {}
    for i, title in enumerate(all_options):
        letter = chr(65 + i)  # A, B, C, D
        options_dict[letter] = title
        if title == target_title:
            target_letter = letter
    
    return target_title, image_path, distractor_titles, options_dict, target_letter


def format_poem_data(title: str, letter: str) -> dict:
    """Format poem data for template rendering."""
    info = POEM_INFO.get(title, {})
    author = info.get("author", "")
    content = info.get("content", "")
    
    # Clean up content: strip leading/trailing whitespace from each line
    if content:
        lines = content.split('\n')
        # Strip leading whitespace (spaces and tabs) from ALL lines
        lines = [line.lstrip().rstrip() for line in lines]
        # Remove leading empty lines
        while lines and not lines[0]:
            lines.pop(0)
        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()
        content = '\n'.join(lines)
    
    # Show preview only for poems with 7 or more lines
    # For shorter poems, show full content without unfold button
    lines = content.split('\n') if content else []
    if len(lines) >= 7:
        # Show first 3 lines as preview for long poems
        preview_lines = lines[:3]
        preview = '\n'.join(preview_lines)
        has_more_content = True
    else:
        # For poems with 6 or fewer lines, show full content
        preview = content
        has_more_content = False
    
    return {
        "title": title,
        "author": author,
        "content": content,
        "preview": preview,
        "has_more_content": has_more_content,
        "letter": letter,
    }


def format_poem_full(title: str) -> dict:
    """Format full poem data for Phase 2 display."""
    info = POEM_INFO.get(title, {})
    author = info.get("author", "")
    content = info.get("content", "")
    
    # Clean up content: strip leading/trailing whitespace from each line
    if content:
        lines = content.split('\n')
        # Strip leading whitespace (spaces and tabs) from ALL lines
        lines = [line.lstrip().rstrip() for line in lines]
        # Remove leading empty lines
        while lines and not lines[0]:
            lines.pop(0)
        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()
        content = '\n'.join(lines)
    
    return {
        "title": title,
        "author": author,
        "content": content,
    }
