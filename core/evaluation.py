# Core evaluation logic: poem selection and formatting
import heapq
import random
from pathlib import Path
from data_logic.catalog import CATALOG, POEM_INFO, get_distractors
from data_logic.storage import get_all_image_rating_counts
from core.image_selection import ImageSelectionSystem


def _extract_image_type(image_path: str) -> str:
    """Extract image type from image path (filename format: {poem_title}_{type}.png)."""
    path_obj = Path(image_path)
    filename = path_obj.stem  # filename without extension
    # Find the last underscore to split title and type
    last_underscore_idx = filename.rfind("_")
    if last_underscore_idx == -1:
        return ""
    image_type = filename[last_underscore_idx + 1:]
    return image_type if image_type in {"gpt", "mj", "nano", "seedream"} else ""


def _init_image_selection_system() -> ImageSelectionSystem:
    """Initialize ImageSelectionSystem from catalog and sync existing ratings."""
    # Validate catalog
    if not CATALOG:
        raise RuntimeError("CATALOG is empty (no valid images found).")
    
    # Initialize system from catalog
    system = ImageSelectionSystem.from_catalog(CATALOG)
    
    # Sync existing ratings from database
    rating_counts = get_all_image_rating_counts()
    
    # Clear the initial heap (all entries have rating 0)
    system.priority_queue = []
    
    # Shuffle images before rebuilding heap to randomize order when priorities are equal
    random.shuffle(system.all_images)
    
    # Rebuild heap with correct ratings from database
    # Use (rating_count, random_tie_breaker, image_record) to preserve shuffle order
    for image in system.all_images:
        count = rating_counts.get(image.path, 0)
        system.current_ratings[image.path] = count
        tie_breaker = random.random()  # Random value to preserve shuffle order
        heapq.heappush(system.priority_queue, (count, tie_breaker, image))
    
    return system


# Initialize global image selection system
IMAGE_SELECTION_SYSTEM = _init_image_selection_system()


def get_evaluation_item(user_id: str):
    """
    Get an image using the priority queue-based selection system.
    
    Args:
        user_id: User ID to use as identifier
    
    Returns: (poem_title, image_path, image_type, distractors_list, poem_options_dict, target_letter) or None
    poem_options_dict: {"A": poem_title, "B": distractor1, "C": distractor2, "D": distractor3}
    Returns None if user has seen all images.
    """
    # Check for timeouts before selecting
    IMAGE_SELECTION_SYSTEM.check_timeouts(timeout_minutes=10)
    
    # Get next image from selection system
    result = IMAGE_SELECTION_SYSTEM.get_next_image(user_id)
    if result is None:
        raise RuntimeError("No images available for evaluation. All queues exhausted.")
    
    image_record, queue_num = result
    image_path = image_record.path
    target_title = image_record.poem_title
    
    # Extract image_type from path
    image_type = _extract_image_type(image_path)
    if not image_type:
        # Fallback: try to get from catalog
        image_data = CATALOG.get(image_path, {})
        image_type = image_data.get("image_type", "")
    
    # Get 3 pre-defined similar distractors
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
    
    return target_title, image_path, image_type, distractor_titles, options_dict, target_letter


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
