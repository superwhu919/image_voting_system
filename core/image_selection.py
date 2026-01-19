"""
Multi-Model Image Evaluation System - Image Selection Logic

Implements a priority queue-based image selection system with 6 queues
and session-based conflict resolution.
"""

import csv
import random
import tempfile
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional, Tuple, Set, Dict
from datetime import datetime, timedelta
from pathlib import Path


@dataclass
class ImageRecord:
    """Represents a single image record."""
    path: str
    poem_title: str
    
    def __repr__(self):
        return f"ImageRecord(path='{self.path}', title='{self.poem_title}')"


class SessionState:
    """Tracks session state for a single user session."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.seen_titles: Set[str] = set()
        self.seen_paths: Set[str] = set()
        self.pending_images: Dict[str, Tuple[ImageRecord, int, datetime]] = {}  # path -> (record, queue_num, assigned_time)
    
    def add_seen(self, image: ImageRecord):
        """Mark an image as seen and rated."""
        self.seen_titles.add(image.poem_title)
        self.seen_paths.add(image.path)
        # Remove from pending if it was there
        if image.path in self.pending_images:
            del self.pending_images[image.path]
    
    def mark_checked(self, image: ImageRecord):
        """Mark an image path as checked (for Scenario B)."""
        self.seen_paths.add(image.path)
    
    def add_pending(self, image: ImageRecord, queue_num: int):
        """Add an image to pending list (assigned but not yet rated)."""
        self.pending_images[image.path] = (image, queue_num, datetime.now())


class ImageSelectionSystem:
    """
    Main image selection system with 6 priority queues.
    
    Each queue contains all images found in the catalog/CSV, independently shuffled.
    The number of images is determined dynamically by scanning the input folder.
    Selection follows priority: Q1 -> Q2 -> ... -> Q6
    """
    
    def __init__(self, csv_path: str = None, catalog: Dict = None):
        """
        Initialize the system by loading images from CSV or catalog.
        
        Args:
            csv_path: Path to the CSV file containing image records (optional if catalog provided)
            catalog: Dict of {image_path: {"poem_title": str, "image_type": str}} (optional if csv_path provided)
        """
        self.queues: Dict[int, deque] = {}
        self.sessions: Dict[str, SessionState] = {}
        self.ratings: Dict[str, int] = {}  # image_path -> count
        self.all_images: list[ImageRecord] = []
        # Thread-safe reentrant lock for all operations on shared state
        # Using RLock to allow nested lock acquisitions (e.g., check_timeouts -> get_session_state)
        self._lock = threading.RLock()
        
        # Load images from CSV or catalog
        if catalog is not None:
            self._load_images_from_catalog(catalog)
        elif csv_path is not None:
            self._load_images_from_csv(csv_path)
        else:
            raise ValueError("Either csv_path or catalog must be provided")
        
        # Initialize 6 queues, each with a shuffled copy of all images
        for queue_num in range(1, 7):
            queue = deque(self.all_images.copy())
            random.shuffle(queue)
            self.queues[queue_num] = queue
        
        print(f"Initialized system with {len(self.all_images)} images in 6 queues")
    
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
                self.ratings[image.path] = 0
    
    def _load_images_from_csv(self, csv_path: str):
        """Load image records from CSV file."""
        with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
            reader = csv.DictReader(f)
            for row in reader:
                # Handle potential BOM in column names
                path_key = 'absolute_path'
                if '\ufeffabsolute_path' in row:
                    path_key = '\ufeffabsolute_path'
                
                image = ImageRecord(
                    path=row[path_key],
                    poem_title=row['poem_title']
                )
                self.all_images.append(image)
                self.ratings[image.path] = 0
    
    @classmethod
    def from_catalog(cls, catalog: Dict):
        """Create ImageSelectionSystem from catalog dict."""
        return cls(catalog=catalog)
    
    def get_session_state(self, session_id: str) -> SessionState:
        """Get or create session state for a session."""
        with self._lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = SessionState(session_id)
            return self.sessions[session_id]
    
    def get_next_image(self, session_id: str) -> Optional[Tuple[ImageRecord, int]]:
        """
        Get the next image for a session following the 3-scenario logic.
        
        Returns:
            Tuple of (ImageRecord, queue_number) if successful, None if all queues exhausted
        """
        with self._lock:
            session = self.get_session_state(session_id)
            
            # Start with Q1, try each queue in order
            for queue_num in range(1, 7):
                queue = self.queues[queue_num]
                
                # Skip if queue is empty
                if len(queue) == 0:
                    continue
                
                # Try to find a valid image in this queue
                attempts = 0
                max_attempts = len(queue)  # Prevent infinite loops
                
                while attempts < max_attempts:
                    if len(queue) == 0:
                        break
                    
                    # Pop the top image
                    image = queue.popleft()
                    attempts += 1
                    
                    # SCENARIO A: SUCCESS (New Content)
                    if image.poem_title not in session.seen_titles:
                        # Mark as pending (will be confirmed when rating is submitted)
                        session.add_pending(image, queue_num)
                        return (image, queue_num)
                    
                    # SCENARIO B: SOFT CONFLICT (Duplicate Title, but new path)
                    elif image.path not in session.seen_paths:
                        # Mark path as checked
                        session.mark_checked(image)
                        # Recycle to bottom of current queue
                        queue.append(image)
                        # Continue to next image in same queue
                        continue
                    
                    # SCENARIO C: HARD CONFLICT (Both title and path seen)
                    else:
                        # This means we've cycled through the entire queue
                        # Skip this queue and move to next
                        # But first, put the image back (we just popped it)
                        queue.appendleft(image)
                        break
                
                # If we exhausted this queue, continue to next queue
                # (The break above will take us to the next queue_num)
            
            # All queues exhausted or all have conflicts
            return None
    
    def submit_rating(self, session_id: str, image_path: str, poem_title: str):
        """
        Submit a rating for an image.
        
        This confirms the image was rated and updates session state.
        """
        with self._lock:
            session = self.get_session_state(session_id)
            
            # Find the image record
            image = ImageRecord(path=image_path, poem_title=poem_title)
            
            # Update session state
            session.add_seen(image)
            
            # Update global rating count
            if image_path in self.ratings:
                self.ratings[image_path] += 1
            else:
                self.ratings[image_path] = 1
    
    def handle_timeout(self, session_id: str, image_path: str, poem_title: str, original_queue: int):
        """
        Handle timeout: return image to the head of its original queue.
        
        Args:
            session_id: Session that timed out
            image_path: Path of the image that timed out
            poem_title: Title of the poem
            original_queue: Queue number (1-6) where image came from
        """
        with self._lock:
            session = self.get_session_state(session_id)
            
            # Remove from pending
            if image_path in session.pending_images:
                del session.pending_images[image_path]
            
            # Remove from seen_paths if it was there (so it can be served again)
            session.seen_paths.discard(image_path)
            
            # Create image record and return to head of original queue
            image = ImageRecord(path=image_path, poem_title=poem_title)
            self.queues[original_queue].appendleft(image)
    
    def check_timeouts(self, timeout_minutes: int = 10):
        """
        Check for pending images that have timed out and return them to queues.
        
        Args:
            timeout_minutes: Minutes before an image is considered timed out
        """
        with self._lock:
            timeout_delta = timedelta(minutes=timeout_minutes)
            now = datetime.now()
            
            for session in self.sessions.values():
                timed_out = []
                for image_path, (image, queue_num, assigned_time) in list(session.pending_images.items()):
                    if now - assigned_time > timeout_delta:
                        timed_out.append((image_path, image.poem_title, queue_num))
                
                for image_path, poem_title, queue_num in timed_out:
                    # Inline timeout handling here since we're already holding the lock
                    # (could call handle_timeout, but inline is more efficient)
                    # Remove from pending
                    if image_path in session.pending_images:
                        del session.pending_images[image_path]
                    
                    # Remove from seen_paths if it was there (so it can be served again)
                    session.seen_paths.discard(image_path)
                    
                    # Create image record and return to head of original queue
                    image = ImageRecord(path=image_path, poem_title=poem_title)
                    self.queues[queue_num].appendleft(image)
    
    def get_statistics(self) -> Dict:
        """Get statistics about the system state."""
        with self._lock:
            total_ratings = sum(self.ratings.values())
            images_with_5_plus = sum(1 for count in self.ratings.values() if count >= 5)
            images_with_0_4 = sum(1 for count in self.ratings.values() if 0 <= count < 5)
            
            rating_counts = list(self.ratings.values())
            if rating_counts:
                min_ratings = min(rating_counts)
                max_ratings = max(rating_counts)
                mean_ratings = sum(rating_counts) / len(rating_counts)
                sorted_counts = sorted(rating_counts)
                median_ratings = sorted_counts[len(sorted_counts) // 2]
            else:
                min_ratings = max_ratings = mean_ratings = median_ratings = 0
            
            queue_sizes = {f"Q{i}": len(self.queues[i]) for i in range(1, 7)}
            
            return {
                'total_images': len(self.all_images),
                'total_ratings': total_ratings,
                'images_with_5_plus_ratings': images_with_5_plus,
                'images_with_0_4_ratings': images_with_0_4,
                'min_ratings_per_image': min_ratings,
                'max_ratings_per_image': max_ratings,
                'mean_ratings_per_image': mean_ratings,
                'median_ratings_per_image': median_ratings,
                'queue_sizes': queue_sizes,
                'active_sessions': len(self.sessions),
            }
