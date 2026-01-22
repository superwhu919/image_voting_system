"""
Multi-Model Image Evaluation System - Image Selection Logic

Implements a priority queue-based image selection system that prioritizes
images with fewer ratings and prevents race conditions.
"""

import csv
import heapq
import threading
from dataclasses import dataclass
from typing import Optional, Tuple, Set, Dict
from datetime import datetime, timedelta
from pathlib import Path
from data_logic.storage import load_user_state, save_user_state, save_user_seen_titles


@dataclass
class ImageRecord:
    """Represents a single image record."""
    path: str
    poem_title: str
    
    def __repr__(self):
        return f"ImageRecord(path='{self.path}', title='{self.poem_title}')"
    
    def __lt__(self, other):
        """Enable comparison for heapq when priorities are equal."""
        if not isinstance(other, ImageRecord):
            return NotImplemented
        return self.path < other.path


class UserState:
    """Tracks state for a single user."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.seen_titles: Set[str] = set()
        self.pending_images: Dict[str, Tuple[ImageRecord, datetime]] = {}  # path -> (record, assigned_time)
    
    def add_seen(self, image: ImageRecord):
        """Mark an image as seen and rated."""
        self.seen_titles.add(image.poem_title)
        # Remove from pending if it was there
        if image.path in self.pending_images:
            del self.pending_images[image.path]
    
    def add_pending(self, image: ImageRecord):
        """Add an image to pending list (assigned but not yet rated)."""
        self.pending_images[image.path] = (image, datetime.now())


class ImageSelectionSystem:
    """
    Main image selection system using a priority queue (min-heap).
    
    Images are prioritized by rating count (lowest first). The system prevents
    race conditions by tracking currently assigned images globally.
    """
    
    def __init__(self, csv_path: str = None, catalog: Dict = None):
        """
        Initialize the system by loading images from CSV or catalog.
        
        Args:
            csv_path: Path to the CSV file containing image records (optional if catalog provided)
            catalog: Dict of {image_path: {"poem_title": str, "image_type": str}} (optional if csv_path provided)
        """
        self.priority_queue = []  # Min-heap: [(rating_count, image_record), ...]
        self.users: Dict[str, UserState] = {}
        self.current_ratings: Dict[str, int] = {}  # image_path -> actual current rating count
        self.all_images: list[ImageRecord] = []
        # Thread-safe reentrant lock for all operations on shared state
        self._lock = threading.RLock()
        
        # Load images from CSV or catalog
        if catalog is not None:
            self._load_images_from_catalog(catalog)
        elif csv_path is not None:
            self._load_images_from_csv(csv_path)
        else:
            raise ValueError("Either csv_path or catalog must be provided")
        
        # Initialize priority queue with all images (rating 0)
        for image in self.all_images:
            heapq.heappush(self.priority_queue, (0, image))
            self.current_ratings[image.path] = 0
        
        print(f"Initialized system with {len(self.all_images)} images in priority queue")
    
    def _load_images_from_catalog(self, catalog: Dict):
        """Load image records from catalog dict."""
        for image_path, image_data in catalog.items():
            poem_title = image_data.get("poem_title", "")
            if poem_title:
                image = ImageRecord(
                    path=image_path,
                    poem_title=poem_title
                )
                self.all_images.append(image)
    
    def _load_images_from_csv(self, csv_path: str):
        """Load image records from CSV file."""
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                path_key = 'absolute_path'
                if '\ufeffabsolute_path' in row:
                    path_key = '\ufeffabsolute_path'
                
                image = ImageRecord(
                    path=row[path_key],
                    poem_title=row['poem_title']
                )
                self.all_images.append(image)
    
    @classmethod
    def from_catalog(cls, catalog: Dict):
        """Create ImageSelectionSystem from catalog dict."""
        return cls(catalog=catalog)
    
    def get_user_state(self, user_id: str) -> UserState:
        """Get or create user state for a user. Loads from database if user exists."""
        with self._lock:
            if user_id not in self.users:
                user_state = UserState(user_id)
                
                # Try to load existing state from database
                db_state = load_user_state(user_id)
                if db_state:
                    user_state.seen_titles = db_state['seen_titles']
                    # Note: seen_paths is ignored in simplified version
                
                self.users[user_id] = user_state
            
            return self.users[user_id]
    
    def get_next_image(self, user_id: str) -> Optional[Tuple[ImageRecord, int]]:
        """
        Get the next image for a user from the priority queue.
        
        Returns:
            Tuple of (ImageRecord, 0) if successful, None if queue exhausted
        """
        with self._lock:
            user_state = self.get_user_state(user_id)
            
            attempts = 0
            max_attempts = len(self.priority_queue) * 2  # Prevent infinite loops
            checked_this_request = set()  # Track images we've already checked
            images_to_add_back = []  # Track images to add back after loop
            
            while attempts < max_attempts:
                if len(self.priority_queue) == 0:
                    break
                
                # Pop from heap (lowest rating first)
                rating_count, image_record = heapq.heappop(self.priority_queue)
                attempts += 1
                
                # Check if entry is stale (rating was updated since this entry was added)
                if rating_count != self.current_ratings.get(image_record.path, 0):
                    continue  # Skip stale entry, don't add back
                
                # Check if already checked in this request (prevent infinite loop)
                if image_record.path in checked_this_request:
                    continue  # Skip, don't add back
                
                # Check if user has seen this poem
                if image_record.poem_title not in user_state.seen_titles:
                    # SUCCESS - assign the image
                    user_state.add_pending(image_record)
                    
                    # Add back all checked images before returning
                    for (rating, img) in images_to_add_back:
                        heapq.heappush(self.priority_queue, (rating, img))
                    
                    return (image_record, 0)  # Return 0 as queue_num for compatibility
                else:
                    # CONFLICT - user already saw this poem
                    checked_this_request.add(image_record.path)
                    images_to_add_back.append((rating_count, image_record))  # Track for later
                    continue  # Don't add back yet
            
            # Loop exhausted - add back all checked images
            for (rating, img) in images_to_add_back:
                heapq.heappush(self.priority_queue, (rating, img))
            
            # All images seen or exhausted
            return None
    
    def submit_rating(self, user_id: str, image_path: str, poem_title: str):
        """
        Submit a rating for an image.
        
        This confirms the image was rated and updates user state and priority queue.
        """
        with self._lock:
            user_state = self.get_user_state(user_id)
            
            # Find the image record
            image = ImageRecord(path=image_path, poem_title=poem_title)
            
            # Update user state
            user_state.add_seen(image)
            
            # Persist user state to database (pass empty set for seen_paths for compatibility)
            save_user_state(user_id, user_state.seen_titles, set())
            
            # Update rating count
            new_rating = self.current_ratings.get(image_path, 0) + 1
            self.current_ratings[image_path] = new_rating
            
            # Add back to heap with new rating (incremented)
            heapq.heappush(self.priority_queue, (new_rating, image))
    
    def handle_timeout(self, user_id: str, image_path: str, poem_title: str, original_queue: int):
        """
        Handle timeout: return image to priority queue.
        
        Args:
            user_id: User that timed out
            image_path: Path of the image that timed out
            poem_title: Title of the poem
            original_queue: Ignored (kept for compatibility)
        """
        with self._lock:
            user_state = self.get_user_state(user_id)
            
            # Remove from pending
            if image_path in user_state.pending_images:
                del user_state.pending_images[image_path]
            
            # Add back to heap with current rating (not incremented)
            current_rating = self.current_ratings.get(image_path, 0)
            image = ImageRecord(path=image_path, poem_title=poem_title)
            heapq.heappush(self.priority_queue, (current_rating, image))
    
    def check_timeouts(self, timeout_minutes: int = 10):
        """
        Check for pending images that have timed out and return them to queue.
        
        Args:
            timeout_minutes: Minutes before an image is considered timed out
        """
        with self._lock:
            timeout_delta = timedelta(minutes=timeout_minutes)
            now = datetime.now()
            
            for user_state in self.users.values():
                timed_out = []
                for image_path, (image, assigned_time) in list(user_state.pending_images.items()):
                    if now - assigned_time > timeout_delta:
                        timed_out.append((image_path, image.poem_title))
                
                for image_path, poem_title in timed_out:
                    # Remove from pending
                    if image_path in user_state.pending_images:
                        del user_state.pending_images[image_path]
                    
                    # Add back to heap with current rating (not incremented)
                    current_rating = self.current_ratings.get(image_path, 0)
                    image = ImageRecord(path=image_path, poem_title=poem_title)
                    heapq.heappush(self.priority_queue, (current_rating, image))
    
    def get_statistics(self) -> Dict:
        """Get statistics about the system state."""
        with self._lock:
            total_ratings = sum(self.current_ratings.values())
            images_with_5_plus = sum(1 for count in self.current_ratings.values() if count >= 5)
            images_with_0_4 = sum(1 for count in self.current_ratings.values() if 0 <= count < 5)
            
            rating_counts = list(self.current_ratings.values())
            if rating_counts:
                min_ratings = min(rating_counts)
                max_ratings = max(rating_counts)
                mean_ratings = sum(rating_counts) / len(rating_counts)
                sorted_counts = sorted(rating_counts)
                median_ratings = sorted_counts[len(sorted_counts) // 2]
            else:
                min_ratings = max_ratings = mean_ratings = median_ratings = 0
            
            return {
                'total_images': len(self.all_images),
                'total_ratings': total_ratings,
                'images_with_5_plus_ratings': images_with_5_plus,
                'images_with_0_4_ratings': images_with_0_4,
                'min_ratings_per_image': min_ratings,
                'max_ratings_per_image': max_ratings,
                'mean_ratings_per_image': mean_ratings,
                'median_ratings_per_image': median_ratings,
                'queue_size': len(self.priority_queue),
                'active_users': len(self.users),
            }
