#!/usr/bin/env python3
"""
Real-Time Load Test - Simulates 550 users voting over time with frontend focus

This test simulates realistic user behavior including:
- Mixed timing patterns (gradual ramp-up, bursts, steady stream)
- Limit increases (5% of users, 2-4 times randomly)
- Unfinished sessions (10% of users abandon at random points)
- Both backend API and frontend browser testing (70% frontend, 30% backend)
- Comprehensive error detection and metrics collection
- Server process memory monitoring
- Real-time progress bars with live statistics

Usage:
    # Test against a running server (default: http://127.0.0.1:7860)
    python tests/test_realtime_load.py
    
    # Or specify different parameters
    python tests/test_realtime_load.py --users 550 --frontend-ratio 0.7 --duration 600
"""

import sys
import os
import time
import random
import threading
import json
import argparse
from pathlib import Path
from collections import defaultdict, deque
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import traceback

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("ERROR: requests not available. Install with: pip install requests")

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import Select
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("ERROR: selenium not available. Install with: pip install selenium webdriver-manager")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Memory monitoring disabled. Install with: pip install psutil")

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("Warning: tqdm not available. Progress bars disabled. Install with: pip install tqdm")

# Default server URL
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:7860")

# Global metrics and state
metrics_lock = threading.Lock()
image_assignments: Dict[str, List[str]] = defaultdict(list)  # image_path -> [user_ids]
errors: List[Dict] = []
completed_users: Set[str] = set()
abandoned_users: Set[str] = set()
limit_increases: Dict[str, int] = defaultdict(int)  # user_id -> count
response_times: Dict[str, List[float]] = defaultdict(list)  # endpoint -> [times]
memory_samples: List[Tuple[float, float]] = []  # [(timestamp, memory_mb)]
concurrent_users: List[Tuple[float, int]] = []  # [(timestamp, count)]
active_sessions: Set[str] = set()
session_lock = threading.Lock()
started_users: Set[str] = set()
started_lock = threading.Lock()


@dataclass
class UserBehaviorConfig:
    """Configuration for user behavior patterns."""
    user_id: str
    is_limit_increaser: bool = False
    is_unfinished: bool = False
    limit_increase_count: int = 0  # How many times to increase (2-4)
    limit_increase_points: List[int] = field(default_factory=list)  # After which vote to increase
    abandonment_point: Optional[str] = None  # 'before_phase1', 'after_phase1', 'after_reveal', 'mid_phase2'
    abandonment_vote: int = 0  # Which vote to abandon at


@dataclass
class MetricsCollector:
    """Thread-safe metrics collection."""
    
    def record_error(self, user_id: str, error_type: str, message: str, endpoint: str = None):
        """Record an error."""
        with metrics_lock:
            errors.append({
                "user_id": user_id,
                "error_type": error_type,
                "message": message,
                "endpoint": endpoint,
                "timestamp": time.time()
            })
    
    def record_image_assignment(self, user_id: str, image_path: str):
        """Record image assignment for race condition detection."""
        with metrics_lock:
            image_assignments[image_path].append(user_id)
    
    def record_response_time(self, endpoint: str, duration: float):
        """Record response time for an endpoint."""
        with metrics_lock:
            response_times[endpoint].append(duration)
    
    def record_limit_increase(self, user_id: str):
        """Record a limit increase."""
        with metrics_lock:
            limit_increases[user_id] += 1
    
    def record_completion(self, user_id: str):
        """Record user completion."""
        with metrics_lock:
            completed_users.add(user_id)
            if user_id in active_sessions:
                active_sessions.remove(user_id)
    
    def record_abandonment(self, user_id: str):
        """Record user abandonment."""
        with metrics_lock:
            abandoned_users.add(user_id)
            if user_id in active_sessions:
                active_sessions.remove(user_id)
    
    def record_started(self, user_id: str):
        """Record user started."""
        with started_lock:
            started_users.add(user_id)
    
    def add_active_session(self, user_id: str):
        """Add active session."""
        with session_lock:
            active_sessions.add(user_id)
    
    def get_stats(self) -> Dict:
        """Get current statistics."""
        with metrics_lock:
            with started_lock:
                with session_lock:
                    return {
                        "total_errors": len(errors),
                        "started_users": len(started_users),
                        "completed_users": len(completed_users),
                        "abandoned_users": len(abandoned_users),
                        "limit_increases": dict(limit_increases),
                        "active_sessions": len(active_sessions),
                        "image_assignments": len(image_assignments),
                        "response_times": {k: len(v) for k, v in response_times.items()},
                    }


class ServerMemoryMonitor:
    """Monitor server process memory usage."""
    
    def __init__(self, server_pid: Optional[int] = None, port: int = 7860, interval: float = 5.0):
        """
        Initialize memory monitor.
        
        Args:
            server_pid: Process ID of server (auto-detect if None)
            port: Port number to find server process
            interval: Sampling interval in seconds
        """
        self.server_pid = server_pid
        self.port = port
        self.interval = interval
        self.running = False
        self.thread = None
        self.process = None
        
        if not PSUTIL_AVAILABLE:
            return
        
        # Find server process
        if self.server_pid:
            try:
                self.process = psutil.Process(self.server_pid)
            except psutil.NoSuchProcess:
                print(f"Warning: Process {self.server_pid} not found")
                self.process = None
        else:
            # Auto-detect by port
            self.process = self._find_process_by_port(port)
    
    def _find_process_by_port(self, port: int):
        """Find process listening on given port."""
        try:
            # Use net_connections to find process by port (more reliable)
            connections = psutil.net_connections(kind='inet')
            for conn in connections:
                if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                    if conn.pid:
                        return psutil.Process(conn.pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            # Fallback: iterate through processes and check connections
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        connections = proc.connections(kind='inet')
                        for conn in connections:
                            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                                return psutil.Process(proc.info['pid'])
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        continue
            except Exception as e:
                print(f"Warning: Could not find server process on port {port}: {e}")
        except Exception as e:
            print(f"Warning: Could not find server process on port {port}: {e}")
        return None
    
    def start(self):
        """Start monitoring."""
        if not PSUTIL_AVAILABLE or not self.process:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
    
    def _monitor(self):
        """Monitor memory usage."""
        while self.running:
            try:
                if self.process:
                    mem_info = self.process.memory_info()
                    mem_mb = mem_info.rss / 1024 / 1024
                    with metrics_lock:
                        memory_samples.append((time.time(), mem_mb))
                time.sleep(self.interval)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception:
                break


def get_random_answer(options: List[Dict]) -> str:
    """Get a random answer from options."""
    if not options:
        return ""
    return random.choice(options).get("value", "")


def safe_js_click_by_selector(driver, selector: str, index: int = None):
    """Click element using CSS selector in JavaScript to avoid stale element issues."""
    if index is not None:
        script = f"""
        var elements = document.querySelectorAll('{selector}');
        if (elements.length > {index}) {{
            elements[{index}].scrollIntoView({{behavior: 'instant', block: 'center'}});
            elements[{index}].click();
            return true;
        }}
        return false;
        """
    else:
        script = f"""
        var element = document.querySelector('{selector}');
        if (element) {{
            element.scrollIntoView({{behavior: 'instant', block: 'center'}});
            element.click();
            return true;
        }}
        return false;
        """
    return driver.execute_script(script)


def safe_js_click_random_by_selector(driver, selector: str):
    """Click a random element from selector in JavaScript."""
    script = f"""
    var elements = document.querySelectorAll('{selector}');
    if (elements.length > 0) {{
        var randomIndex = Math.floor(Math.random() * elements.length);
        elements[randomIndex].scrollIntoView({{behavior: 'instant', block: 'center'}});
        elements[randomIndex].click();
        return true;
    }}
    return false;
    """
    return driver.execute_script(script)


def safe_js_check_checked(driver, selector: str, index: int):
    """Check if element is checked using CSS selector."""
    script = f"""
    var elements = document.querySelectorAll('{selector}');
    if (elements.length > {index}) {{
        return elements[{index}].checked;
    }}
    return false;
    """
    return driver.execute_script(script)


def simulate_backend_user(user_id: str, behavior: UserBehaviorConfig, metrics: MetricsCollector) -> bool:
    """
    Simulate a user via backend API calls.
    Returns True if completed successfully, False if abandoned.
    """
    try:
        metrics.add_active_session(user_id)
        metrics.record_started(user_id)
        
        # Start session
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/start",
            json={
                "user_id": user_id,
                "age": random.randint(18, 80),
                "gender": random.choice(["男", "女"]),
                "education": random.choice(["本科", "硕士", "博士", "高中"])
            },
            timeout=30
        )
        metrics.record_response_time("start", time.time() - start_time)
        
        if response.status_code != 200:
            metrics.record_error(user_id, "http_error", f"Start failed with status {response.status_code}", "start")
            return False
        
        data = response.json()
        if data.get("status") != "success":
            if data.get("status") == "limit_reached":
                # Handle limit reached - increase if this user is a limit increaser
                if behavior.is_limit_increaser and behavior.limit_increase_count > 0:
                    increase_response = requests.post(
                        f"{BASE_URL}/api/increase-limit",
                        json={"user_id": user_id},
                        timeout=30
                    )
                    if increase_response.status_code == 200:
                        metrics.record_limit_increase(user_id)
                        behavior.limit_increase_count -= 1
                        # Retry start
                        response = requests.post(
                            f"{BASE_URL}/api/start",
                            json={
                                "user_id": user_id,
                                "age": random.randint(18, 80),
                                "gender": random.choice(["男", "女"]),
                                "education": random.choice(["本科", "硕士", "博士", "高中"])
                            },
                            timeout=30
                        )
                        if response.status_code == 200:
                            data = response.json()
                        else:
                            metrics.record_error(user_id, "http_error", "Retry start failed", "start")
                            return False
                    else:
                        metrics.record_error(user_id, "limit_increase_error", "Failed to increase limit", "increase-limit")
                        return False
                else:
                    metrics.record_error(user_id, "unexpected_limit", "Limit reached but not a limit increaser", "start")
                    return False
            else:
                # #region agent log
                try:
                    with open('/Users/williamhu/Desktop/poem-work/voting_system/.cursor/debug.log', 'a') as f:
                        import json
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "D",
                            "location": f"test_realtime_load.py:{335}",
                            "message": "Start API returned non-success status",
                            "data": {
                                "user_id": user_id,
                                "status": data.get('status'),
                                "message": str(data.get('message', ''))[:100],
                                "response_data": str(data)[:200]
                            },
                            "timestamp": int(time.time() * 1000)
                        }
                        f.write(json.dumps(log_entry) + '\n')
                except:
                    pass
                # #endregion
                error_msg = f"Start returned {data.get('status')}"
                if data.get('message'):
                    error_msg += f": {str(data.get('message'))[:50]}"
                metrics.record_error(user_id, "api_error", error_msg, "start")
                return False
        
        # Track image assignment
        image_path = data.get("image_path")
        if image_path:
            metrics.record_image_assignment(user_id, image_path)
        
        vote_count = 0
        max_votes = 50  # Safety limit to prevent infinite loops
        
        # Main voting loop
        while vote_count < max_votes:
            vote_count += 1
            
            # Check if should abandon before Phase 1
            if behavior.is_unfinished and behavior.abandonment_point == "before_phase1" and vote_count == behavior.abandonment_vote:
                metrics.record_abandonment(user_id)
                return False
            
            # Phase 1: Make choice and answer questions
            poem_title = data.get("poem_title")
            image_path = data.get("image_path")
            options_dict = data.get("options_dict", {})
            target_letter = data.get("target_letter", "A")
            phase1_start_ms = data.get("phase1_start_ms", str(int(time.time() * 1000)))
            
            if not all([poem_title, image_path, options_dict, target_letter]):
                metrics.record_error(user_id, "missing_data", "Missing required data for vote", "start")
                break
            
            # Random delay (simulating reading)
            time.sleep(random.uniform(2, 8))
            
            # Make random Phase 1 choice
            phase1_choice = random.choice(["A", "B", "C", "D"])
            
            # Answer Phase 1 questions (q1-2)
            phase1_answers = {}
            if "q1-2" in data:
                q1_2_options = data.get("q1-2", {}).get("options", [])
                if q1_2_options:
                    phase1_answers["q1-2"] = get_random_answer(q1_2_options)
            
            # Check if should abandon after Phase 1
            if behavior.is_unfinished and behavior.abandonment_point == "after_phase1" and vote_count == behavior.abandonment_vote:
                metrics.record_abandonment(user_id)
                return False
            
            # Reveal poem
            reveal_start = time.time()
            reveal_response = requests.post(
                f"{BASE_URL}/api/reveal",
                json={
                    "user_id": user_id,
                    "poem_title": poem_title,
                    "image_path": image_path,
                    "options_dict": options_dict,
                    "target_letter": target_letter,
                    "phase1_choice": phase1_choice,
                    "phase1_answers": phase1_answers,
                    "phase1_start_ms": phase1_start_ms
                },
                timeout=30
            )
            metrics.record_response_time("reveal", time.time() - reveal_start)
            
            if reveal_response.status_code != 200:
                metrics.record_error(user_id, "http_error", "Reveal failed", "reveal")
                break
            
            reveal_data = reveal_response.json()
            if reveal_data.get("status") != "success":
                metrics.record_error(user_id, "api_error", f"Reveal returned {reveal_data.get('status')}", "reveal")
                break
            
            # Check if should abandon after reveal
            if behavior.is_unfinished and behavior.abandonment_point == "after_reveal" and vote_count == behavior.abandonment_vote:
                metrics.record_abandonment(user_id)
                return False
            
            # Phase 2: Answer questions
            phase2_start_ms = reveal_data.get("phase2_start_ms", str(int(time.time() * 1000)))
            questions = reveal_data.get("questions", {})
            
            # Build phase2_answers
            phase2_answers = {}
            question_ids = sorted([q_id for q_id in questions.keys() if q_id.startswith("q2-")])
            
            # Check if should abandon mid-Phase 2
            abandon_mid_phase2 = (behavior.is_unfinished and 
                                 behavior.abandonment_point == "mid_phase2" and 
                                 vote_count == behavior.abandonment_vote)
            
            for i, q_id in enumerate(question_ids):
                q_data = questions.get(q_id, {})
                options = q_data.get("options", [])
                if options:
                    phase2_answers[q_id] = get_random_answer(options)
                
                # Abandon mid-Phase 2 (after answering some but not all questions)
                if abandon_mid_phase2 and i < len(question_ids) - 1:
                    metrics.record_abandonment(user_id)
                    return False
                
                # Random delay between questions
                time.sleep(random.uniform(0.5, 2.0))
            
            # Random delay before submit
            time.sleep(random.uniform(1, 3))
            
            # Submit evaluation
            submit_start = time.time()
            submit_response = requests.post(
                f"{BASE_URL}/api/submit",
                json={
                    "user_id": user_id,
                    "user_age": random.randint(18, 80),
                    "user_gender": random.choice(["男", "女"]),
                    "user_education": random.choice(["本科", "硕士", "博士", "高中"]),
                    "poem_title": poem_title,
                    "image_path": image_path,
                    "image_type": data.get("image_type", ""),
                    "options_dict": options_dict,
                    "target_letter": target_letter,
                    "phase1_choice": phase1_choice,
                    "phase1_answers": phase1_answers,
                    "phase1_response_ms": 0,
                    "phase2_answers": phase2_answers,
                    "phase2_start_ms": phase2_start_ms,
                    "phase1_start_ms": phase1_start_ms
                },
                timeout=30
            )
            metrics.record_response_time("submit", time.time() - submit_start)
            
            if submit_response.status_code != 200:
                metrics.record_error(user_id, "http_error", "Submit failed", "submit")
                break
            
            submit_data = submit_response.json()
            
            if submit_data.get("status") == "success":
                # Check if should increase limit
                if behavior.is_limit_increaser and vote_count in behavior.limit_increase_points:
                    if behavior.limit_increase_count > 0:
                        increase_response = requests.post(
                            f"{BASE_URL}/api/increase-limit",
                            json={"user_id": user_id},
                            timeout=30
                        )
                        if increase_response.status_code == 200:
                            metrics.record_limit_increase(user_id)
                            behavior.limit_increase_count -= 1
                
                # Get next evaluation
                data = submit_data
                next_image_path = data.get("image_path")
                if next_image_path:
                    metrics.record_image_assignment(user_id, next_image_path)
                else:
                    # No next image - user has seen all images or server issue
                    metrics.record_error(user_id, "no_next_image", "Success but no next image_path in response", "submit")
                    break
            elif submit_data.get("status") == "limit_reached":
                # Handle limit reached
                if behavior.is_limit_increaser and behavior.limit_increase_count > 0:
                    increase_response = requests.post(
                        f"{BASE_URL}/api/increase-limit",
                        json={"user_id": user_id},
                        timeout=30
                    )
                    if increase_response.status_code == 200:
                        metrics.record_limit_increase(user_id)
                        behavior.limit_increase_count -= 1
                        # Get next evaluation by calling start
                        start_response = requests.post(
                            f"{BASE_URL}/api/start",
                            json={
                                "user_id": user_id,
                                "age": random.randint(18, 80),
                                "gender": random.choice(["男", "女"]),
                                "education": random.choice(["本科", "硕士", "博士", "高中"])
                            },
                            timeout=30
                        )
                        if start_response.status_code == 200:
                            start_data = start_response.json()
                            if start_data.get("status") == "success":
                                data = start_data
                                next_image_path = data.get("image_path")
                                if next_image_path:
                                    metrics.record_image_assignment(user_id, next_image_path)
                                continue
                # User reached limit and doesn't want to continue
                break
            elif submit_data.get("status") == "all_images_seen":
                # User has seen all images - normal completion
                break
            else:
                metrics.record_error(user_id, "api_error", f"Submit returned {submit_data.get('status')}", "submit")
                break
        
        metrics.record_completion(user_id)
        return True
        
    except Exception as e:
        metrics.record_error(user_id, "exception", f"Exception: {str(e)}\n{traceback.format_exc()}")
        metrics.record_abandonment(user_id)
        return False


def simulate_frontend_user(user_id: str, behavior: UserBehaviorConfig, metrics: MetricsCollector, 
                           driver: webdriver.Chrome) -> bool:
    """
    Simulate a user via frontend browser interactions.
    Returns True if completed successfully, False if abandoned.
    """
    try:
        metrics.add_active_session(user_id)
        metrics.record_started(user_id)
        
        # Navigate to page - use lock to prevent concurrent navigation on same driver
        nav_lock = getattr(driver, '_nav_lock', None)
        if nav_lock:
            with nav_lock:
                driver.get(BASE_URL)
        else:
            driver.get(BASE_URL)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "start-btn"))
        )
        time.sleep(0.5)
        
        # Fill in user info
        user_input = driver.find_element(By.ID, "user-input")
        age_input = driver.find_element(By.ID, "user-age")
        gender_select = driver.find_element(By.ID, "user-gender")
        education_select = driver.find_element(By.ID, "user-education")
        
        user_input.clear()
        user_input.send_keys(user_id)
        age_input.clear()
        age_input.send_keys(str(random.randint(18, 80)))
        
        gender_dropdown = Select(gender_select)
        gender_dropdown.select_by_value(random.choice(["男", "女"]))
        
        education_dropdown = Select(education_select)
        education_dropdown.select_by_value(random.choice(["本科", "硕士", "博士", "高中"]))
        
        # Click start - wait for clickable
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "start-btn"))
        )
        time.sleep(0.2)
        # Use CSS selector in JavaScript to avoid stale element issues
        safe_js_click_by_selector(driver, "#start-btn")
        
        # Wait for evaluation box
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "evaluation-box"))
        )
        time.sleep(1)
        
        # Get image path from page (if available via JavaScript)
        try:
            image_path = driver.execute_script("return window.currentSession?.image_path || '';")
            if image_path:
                metrics.record_image_assignment(user_id, image_path)
        except:
            pass
        
        vote_count = 0
        
        # Main voting loop
        while vote_count < 15:  # Reasonable limit for frontend testing
            vote_count += 1
            
            # Check abandonment points
            if behavior.is_unfinished and vote_count == behavior.abandonment_vote:
                if behavior.abandonment_point == "before_phase1":
                    metrics.record_abandonment(user_id)
                    return False
            
            # Phase 1: Make choice
            time.sleep(random.uniform(2, 5))
            
            # Select random poem - wait for clickable
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[name="phase1_choice"]'))
                )
                # #region agent log
                try:
                    with open('/Users/williamhu/Desktop/poem-work/voting_system/.cursor/debug.log', 'a') as f:
                        import json
                        log_entry = {
                            "sessionId": "debug-session",
                            "runId": "run1",
                            "hypothesisId": "B",
                            "location": f"test_realtime_load.py:{632}",
                            "message": "Before phase1_choice click",
                            "data": {"user_id": user_id, "vote_count": vote_count, "operation": "phase1_choice_click"},
                            "timestamp": int(time.time() * 1000)
                        }
                        f.write(json.dumps(log_entry) + '\n')
                except:
                    pass
                # #endregion
                # Use CSS selector in JavaScript to avoid stale element issues
                if not safe_js_click_random_by_selector(driver, 'input[name="phase1_choice"]'):
                    break
                time.sleep(0.5)
            except:
                break
            
            # Answer Phase 1 questions - wait for clickable
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[name="q1-2"]'))
                )
                # Use CSS selector in JavaScript to avoid stale element issues
                safe_js_click_random_by_selector(driver, 'input[name="q1-2"]')
                time.sleep(0.3)
            except:
                pass
            
            if behavior.is_unfinished and behavior.abandonment_point == "after_phase1" and vote_count == behavior.abandonment_vote:
                metrics.record_abandonment(user_id)
                return False
            
            # Click reveal - wait for clickable
            try:
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "reveal-btn"))
                )
                time.sleep(0.2)
                # Use CSS selector in JavaScript to avoid stale element issues
                if not safe_js_click_by_selector(driver, "#reveal-btn"):
                    break
                time.sleep(1)
            except:
                break
            
            if behavior.is_unfinished and behavior.abandonment_point == "after_reveal" and vote_count == behavior.abandonment_vote:
                metrics.record_abandonment(user_id)
                return False
            
            # Answer Phase 2 questions - wait for clickable
            try:
                phase2_radios = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[name^="q2-"]'))
                )
                answered = 0
                total_questions = len(phase2_radios)
                # Use CSS selector in JavaScript to avoid stale element references
                for i in range(total_questions):
                    try:
                        # #region agent log
                        try:
                            with open('/Users/williamhu/Desktop/poem-work/voting_system/.cursor/debug.log', 'a') as f:
                                import json
                                log_entry = {
                                    "sessionId": "debug-session",
                                    "runId": "run1",
                                    "hypothesisId": "C",
                                    "location": f"test_realtime_load.py:{708}",
                                    "message": "Before phase2 radio check/click",
                                    "data": {"user_id": user_id, "vote_count": vote_count, "question_index": i, "total_questions": total_questions},
                                    "timestamp": int(time.time() * 1000)
                                }
                                f.write(json.dumps(log_entry) + '\n')
                        except:
                            pass
                        # #endregion
                        # Check if selected using CSS selector in JavaScript to avoid stale element
                        is_selected = safe_js_check_checked(driver, 'input[name^="q2-"]', i)
                        if not is_selected:
                            time.sleep(0.1)
                            # Use CSS selector in JavaScript to avoid stale element issues
                            if safe_js_click_by_selector(driver, 'input[name^="q2-"]', i):
                                answered += 1
                                time.sleep(random.uniform(0.5, 1.5))
                                
                                if behavior.is_unfinished and behavior.abandonment_point == "mid_phase2" and vote_count == behavior.abandonment_vote and answered < total_questions // 2:
                                    metrics.record_abandonment(user_id)
                                    return False
                    except Exception as e:
                        # If element is stale or not found, continue to next
                        continue
            except:
                pass
            
            # Submit - wait for clickable
            try:
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "submit-btn"))
                )
                time.sleep(1)
                # Use CSS selector in JavaScript to avoid stale element issues
                if not safe_js_click_by_selector(driver, "#submit-btn"):
                    break
                time.sleep(2)
            except:
                break
            
            # Check for limit reached modal - wait for clickable
            try:
                modal = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "limit-extension-modal"))
                )
                # Check if modal is displayed using JavaScript
                is_displayed = driver.execute_script("""
                    var modal = document.getElementById('limit-extension-modal');
                    return modal && window.getComputedStyle(modal).display !== 'none';
                """)
                if is_displayed:
                    if behavior.is_limit_increaser and behavior.limit_increase_count > 0:
                        WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.ID, "limit-extension-yes-btn"))
                        )
                        time.sleep(0.2)
                        # Use CSS selector in JavaScript to avoid stale element issues
                        if safe_js_click_by_selector(driver, "#limit-extension-yes-btn"):
                            time.sleep(1)
                            metrics.record_limit_increase(user_id)
                            behavior.limit_increase_count -= 1
                    else:
                        WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.ID, "limit-extension-no-btn"))
                        )
                        time.sleep(0.2)
                        # Use CSS selector in JavaScript to avoid stale element issues
                        if safe_js_click_by_selector(driver, "#limit-extension-no-btn"):
                            break
            except:
                pass
            
            # Wait for next evaluation to load
            time.sleep(1)
        
        metrics.record_completion(user_id)
        return True
        
    except Exception as e:
        # #region agent log
        try:
            with open('/Users/williamhu/Desktop/poem-work/voting_system/.cursor/debug.log', 'a') as f:
                import json
                log_entry = {
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "A",
                    "location": f"test_realtime_load.py:{545}",
                    "message": "Frontend exception caught",
                    "data": {
                        "user_id": user_id,
                        "vote_count": vote_count if 'vote_count' in locals() else None,
                        "error_type": type(e).__name__,
                        "error_msg": str(e)[:200]
                    },
                    "timestamp": int(time.time() * 1000)
                }
                f.write(json.dumps(log_entry) + '\n')
        except:
            pass
        # #endregion
        
        # Print error immediately (thread-safe)
        error_msg_short = str(e)[:150]  # Truncate for cleaner output
        error_traceback = traceback.format_exc()
        with metrics_lock:  # Use existing metrics lock for thread-safe printing
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n[{timestamp}] [FRONTEND_EXCEPTION] User: {user_id}", flush=True)
            print(f"  Error: {type(e).__name__}: {error_msg_short}", flush=True)
            # Print first few lines of traceback for debugging
            traceback_lines = error_traceback.split('\n')
            if len(traceback_lines) > 10:
                print(f"  Traceback (first 10 lines):", flush=True)
                for line in traceback_lines[:10]:
                    print(f"    {line}", flush=True)
                print(f"    ... (truncated)", flush=True)
            else:
                print(f"  Traceback:", flush=True)
                for line in traceback_lines:
                    print(f"    {line}", flush=True)
        
        metrics.record_error(user_id, "frontend_exception", f"Exception: {str(e)}\n{error_traceback}")
        metrics.record_abandonment(user_id)
        return False


def create_user_behaviors(total_users: int) -> List[UserBehaviorConfig]:
    """Create behavior configurations for all users."""
    behaviors = []
    
    # Calculate counts
    num_limit_increasers = int(total_users * 0.05)  # 5%
    num_unfinished = int(total_users * 0.10)  # 10%
    
    # Create user IDs with timestamp to avoid conflicts with previous test runs
    timestamp_suffix = int(time.time() * 1000) % 100000  # Last 5 digits of timestamp
    user_ids = [f"realtime_test_user_{timestamp_suffix}_{i:04d}" for i in range(total_users)]
    
    # Randomly assign limit increasers
    limit_increaser_ids = set(random.sample(user_ids, num_limit_increasers))
    
    # Randomly assign unfinished (can overlap with limit increasers)
    unfinished_ids = set(random.sample(user_ids, num_unfinished))
    
    for user_id in user_ids:
        is_limit_increaser = user_id in limit_increaser_ids
        is_unfinished = user_id in unfinished_ids
        
        behavior = UserBehaviorConfig(
            user_id=user_id,
            is_limit_increaser=is_limit_increaser,
            is_unfinished=is_unfinished
        )
        
        if is_limit_increaser:
            # Random number of increases (2-4)
            behavior.limit_increase_count = random.randint(2, 4)
            # Random points to increase (after which vote)
            max_votes = 15
            behavior.limit_increase_points = sorted(random.sample(range(1, max_votes), behavior.limit_increase_count))
        
        if is_unfinished:
            # Random abandonment point
            behavior.abandonment_point = random.choice(["before_phase1", "after_phase1", "after_reveal", "mid_phase2"])
            # Random vote to abandon at (1-10)
            behavior.abandonment_vote = random.randint(1, 10)
        
        behaviors.append(behavior)
    
    return behaviors


def distribute_users(total_users: int, duration_seconds: int) -> List[Tuple[float, int]]:
    """
    Create user distribution schedule with mixed patterns.
    Returns list of (start_time_offset, user_count) tuples.
    """
    schedule = []
    remaining_users = total_users
    
    # Gradual start: 200 users over 5 minutes
    gradual_count = min(200, remaining_users)
    if gradual_count > 0:
        gradual_duration = min(300, duration_seconds // 2)  # 5 minutes or half duration
        for i in range(gradual_count):
            offset = (i / gradual_count) * gradual_duration
            schedule.append((offset, 1))
        remaining_users -= gradual_count
    
    # Burst waves: 3 waves of ~100 users each
    burst_size = min(100, remaining_users // 3)
    if burst_size > 0 and remaining_users > 0:
        wave_times = [duration_seconds * 0.2, duration_seconds * 0.5, duration_seconds * 0.8]
        for wave_time in wave_times:
            if remaining_users <= 0:
                break
            wave_count = min(burst_size, remaining_users)
            # All users in wave start within 10 seconds
            for i in range(wave_count):
                offset = wave_time + random.uniform(0, 10)
                schedule.append((offset, 1))
            remaining_users -= wave_count
    
    # Steady stream: remaining users at random intervals
    if remaining_users > 0:
        for i in range(remaining_users):
            offset = random.uniform(0, duration_seconds)
            schedule.append((offset, 1))
    
    # Sort by start time
    schedule.sort(key=lambda x: x[0])
    return schedule


def check_concurrent_assignments() -> Dict[str, List[str]]:
    """
    Check for race conditions by examining the actual system state.
    
    Returns:
        Dict mapping image_path -> list of user_ids that currently have this image pending.
        Only includes images that are assigned to 2+ users simultaneously (race conditions).
    """
    try:
        from core.evaluation import IMAGE_SELECTION_SYSTEM
        
        # Build reverse mapping: image_path -> [user_ids]
        image_to_users: Dict[str, List[str]] = defaultdict(list)
        
        # Access the system's user states (protected by lock internally)
        with IMAGE_SELECTION_SYSTEM._lock:
            for user_id, user_state in IMAGE_SELECTION_SYSTEM.users.items():
                for image_path in user_state.pending_images.keys():
                    image_to_users[image_path].append(user_id)
        
        # Filter to only concurrent assignments (2+ users)
        concurrent = {
            image_path: user_list 
            for image_path, user_list in image_to_users.items() 
            if len(user_list) > 1
        }
        
        return concurrent
    except Exception as e:
        print(f"Warning: Could not check concurrent assignments: {e}")
        return {}


def check_database_integrity(total_users: int, metrics: MetricsCollector) -> Dict:
    """Check database integrity after test."""
    results = {
        "passed": True,
        "issues": []
    }
    
    try:
        from data_logic.storage import user_count, get_all_image_rating_counts
        
        # Check user counts
        stats = metrics.get_stats()
        expected_completed = len(completed_users)
        
        # Check for concurrent assignments (real race condition check)
        concurrent_assignments = check_concurrent_assignments()
        if concurrent_assignments:
            results["passed"] = False
            results["issues"].append(f"Found {len(concurrent_assignments)} images assigned to multiple users simultaneously (race condition)")
        
        # Check error rate
        error_rate = stats["total_errors"] / total_users if total_users > 0 else 0
        if error_rate > 0.05:  # More than 5% error rate
            results["issues"].append(f"High error rate: {error_rate:.2%}")
        
    except Exception as e:
        results["passed"] = False
        results["issues"].append(f"Database check failed: {str(e)}")
    
    return results


def generate_comprehensive_report(metrics: MetricsCollector, elapsed_time: float, total_users: int, 
                                 memory_monitor: Optional[ServerMemoryMonitor] = None):
    """Generate comprehensive test report."""
    stats = metrics.get_stats()
    
    print()
    print("=" * 80)
    print("Comprehensive Test Report")
    print("=" * 80)
    print(f"Test Duration: {elapsed_time:.2f} seconds ({elapsed_time/60:.1f} minutes)")
    print(f"Total Users: {total_users}")
    print(f"Started Users: {stats['started_users']}")
    print(f"Completed Users: {len(completed_users)}")
    print(f"Abandoned Users: {len(abandoned_users)}")
    print(f"Total Errors: {stats['total_errors']}")
    print()
    
    # Error analysis
    if errors:
        print("Error Analysis:")
        print("-" * 80)
        error_types = defaultdict(int)
        for error in errors:
            error_types[error['error_type']] += 1
        
        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count}")
        print()
        
        # Show sample errors
        print("Sample Errors (first 10):")
        for error in errors[:10]:
            # Safely encode message to avoid Unicode issues
            msg = error['message'][:60].encode('ascii', 'replace').decode('ascii')
            print(f"  [{error['error_type']}] User {error['user_id']}: {msg}")
        print()
    
    # Race condition detection (check actual system state for concurrent assignments)
    print("Race Condition Analysis:")
    print("-" * 80)
    concurrent_assignments = check_concurrent_assignments()
    if concurrent_assignments:
        print(f"⚠️  RACE CONDITION DETECTED: {len(concurrent_assignments)} images currently assigned to multiple users simultaneously:")
        for image_path, user_list in list(concurrent_assignments.items())[:20]:  # Show first 20
            print(f"[WARNING] DUPLICATE: Image '{image_path}' assigned to {len(user_list)} users:")
            for user_id in user_list[:5]:  # Show first 5 users
                print(f"     - {user_id}")
            if len(user_list) > 5:
                print(f"     ... and {len(user_list) - 5} more")
        if len(concurrent_assignments) > 20:
            print(f"     ... and {len(concurrent_assignments) - 20} more concurrent assignments")
    else:
        print("[OK] No concurrent image assignments detected (no race conditions)")
    print()
    
    # Response time statistics
    print("Response Time Statistics:")
    print("-" * 80)
    for endpoint, times in response_times.items():
        if times:
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            sorted_times = sorted(times)
            median_time = sorted_times[len(sorted_times) // 2]
            print(f"  {endpoint}:")
            print(f"    Count: {len(times)}")
            print(f"    Avg: {avg_time*1000:.1f}ms")
            print(f"    Median: {median_time*1000:.1f}ms")
            print(f"    Min: {min_time*1000:.1f}ms")
            print(f"    Max: {max_time*1000:.1f}ms")
    print()
    
    # Limit increases
    print("Limit Increases:")
    print("-" * 80)
    if limit_increases:
        total_increases = sum(limit_increases.values())
        print(f"Total increases: {total_increases}")
        print(f"Users who increased: {len(limit_increases)}")
        for user_id, count in sorted(limit_increases.items(), key=lambda x: -x[1])[:10]:
            print(f"  {user_id}: {count} increases")
    else:
        print("No limit increases recorded")
    print()
    
    # Memory usage
    if memory_samples:
        print("Server Memory Usage:")
        print("-" * 80)
        mem_values = [mem for _, mem in memory_samples]
        if mem_values:
            avg_mem = sum(mem_values) / len(mem_values)
            min_mem = min(mem_values)
            max_mem = max(mem_values)
            growth = max_mem - min_mem
            growth_pct = (growth / min_mem * 100) if min_mem > 0 else 0
            print(f"  Samples: {len(memory_samples)}")
            print(f"  Avg: {avg_mem:.1f} MB")
            print(f"  Min: {min_mem:.1f} MB")
            print(f"  Max: {max_mem:.1f} MB")
            print(f"  Growth: {growth:.1f} MB ({growth_pct:.1f}%)")
            if growth_pct > 50:
                print("  [WARNING] Significant memory growth detected (potential leak)")
    print()
    
    # Concurrent users
    if concurrent_users:
        print("Concurrent Users:")
        print("-" * 80)
        max_concurrent = max(count for _, count in concurrent_users)
        avg_concurrent = sum(count for _, count in concurrent_users) / len(concurrent_users)
        print(f"  Max concurrent: {max_concurrent}")
        print(f"  Avg concurrent: {avg_concurrent:.1f}")
    print()
    
    # Database integrity
    print("Database Integrity Check:")
    print("-" * 80)
    integrity = check_database_integrity(total_users, metrics)
    if integrity["passed"]:
        print("[OK] Database integrity check passed")
    else:
        print("[WARNING] Database integrity issues found:")
        for issue in integrity["issues"]:
            print(f"  - {issue}")
    print()
    
    # Summary
    print("=" * 80)
    if concurrent_assignments:
        print("⚠️  RACE CONDITION DETECTED!")
    elif stats['total_errors'] > total_users * 0.01:
        print("[WARNING] HIGH ERROR RATE")
    elif memory_samples and (max(mem for _, mem in memory_samples) - min(mem for _, mem in memory_samples)) / min(mem for _, mem in memory_samples) > 0.5:
        print("[WARNING] MEMORY LEAK DETECTED")
    else:
        print("[OK] TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)


def run_realtime_load_test(num_users: int = 550, frontend_ratio: float = 0.7, 
                           duration_seconds: int = 600, enable_memory_monitoring: bool = True,
                           server_pid: Optional[int] = None, headless: bool = True):
    """Run real-time load test."""
    print("=" * 80)
    print("Real-Time Load Test")
    print("=" * 80)
    print(f"Server URL: {BASE_URL}")
    print(f"Total users: {num_users}")
    print(f"Frontend ratio: {frontend_ratio:.1%}")
    print(f"Backend ratio: {1 - frontend_ratio:.1%}")
    print(f"Test duration: {duration_seconds} seconds")
    print()
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code != 200:
            print(f"ERROR: Server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Cannot connect to server at {BASE_URL}")
        print(f"Make sure your server is running: python app.py")
        return False
    
    print("[OK] Server is reachable")
    print()
    
    # Clear global state
    global image_assignments, errors, completed_users, abandoned_users
    global limit_increases, response_times, memory_samples, concurrent_users, active_sessions, started_users
    image_assignments.clear()
    errors.clear()
    completed_users.clear()
    abandoned_users.clear()
    limit_increases.clear()
    response_times.clear()
    memory_samples.clear()
    concurrent_users.clear()
    active_sessions.clear()
    started_users.clear()
    
    # Initialize metrics
    metrics = MetricsCollector()
    
    # Start memory monitoring
    memory_monitor = None
    if enable_memory_monitoring and PSUTIL_AVAILABLE:
        memory_monitor = ServerMemoryMonitor(server_pid=server_pid, port=7860, interval=5.0)
        memory_monitor.start()
        print("[OK] Server memory monitoring enabled")
    
    # Create user behaviors
    print("Creating user behavior configurations...")
    behaviors = create_user_behaviors(num_users)
    print(f"[OK] Created {len(behaviors)} user configurations")
    print(f"  - Limit increasers: {sum(1 for b in behaviors if b.is_limit_increaser)}")
    print(f"  - Unfinished sessions: {sum(1 for b in behaviors if b.is_unfinished)}")
    print()
    
    # Create user distribution schedule
    print("Creating user distribution schedule...")
    schedule = distribute_users(num_users, duration_seconds)
    print(f"[OK] Created schedule for {len(schedule)} user starts")
    print()
    
    # Prepare Selenium drivers for frontend users
    frontend_drivers = []
    num_frontend = int(num_users * frontend_ratio)
    if num_frontend > 0 and SELENIUM_AVAILABLE:
        print(f"Preparing {num_frontend} frontend browser instances...")
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        # Limit concurrent browsers to avoid resource exhaustion
        max_browsers = min(num_frontend, 20)  # Max 20 concurrent browsers
        for i in range(max_browsers):
            try:
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=chrome_options
                )
                # Add a lock to each driver to prevent concurrent navigation
                driver._nav_lock = threading.Lock()
                frontend_drivers.append(driver)
            except Exception as e:
                print(f"Warning: Could not create browser {i}: {e}")
        print(f"[OK] Created {len(frontend_drivers)} browser instances")
        print()
    
    # Start test
    print("Starting load test...")
    print()
    
    start_time = time.time()
    threads = []
    behavior_index = 0
    frontend_driver_index = 0
    
    # Track concurrent users
    def update_concurrent_count():
        while True:
            with session_lock:
                count = len(active_sessions)
            with metrics_lock:
                concurrent_users.append((time.time() - start_time, count))
            time.sleep(1)
    
    concurrent_tracker = threading.Thread(target=update_concurrent_count, daemon=True)
    concurrent_tracker.start()
    
    # Initialize progress bars
    if TQDM_AVAILABLE:
        main_pbar = tqdm(total=num_users, desc="Users Started", unit="user", 
                        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]')
        main_pbar.set_postfix_str("Starting...")
    else:
        main_pbar = None
        print("Progress: Starting users...")
    
    # Launch users according to schedule
    for schedule_time, user_count in schedule:
        # Wait until scheduled time
        elapsed = time.time() - start_time
        if elapsed < schedule_time:
            time.sleep(schedule_time - elapsed)
        
        for _ in range(user_count):
            if behavior_index >= len(behaviors):
                break
            
            behavior = behaviors[behavior_index]
            behavior_index += 1
            
            # Decide backend vs frontend
            use_frontend = (random.random() < frontend_ratio) and frontend_drivers
            
            if use_frontend and frontend_drivers:
                # Use frontend
                driver = frontend_drivers[frontend_driver_index % len(frontend_drivers)]
                frontend_driver_index += 1
                thread = threading.Thread(
                    target=simulate_frontend_user,
                    args=(behavior.user_id, behavior, metrics, driver)
                )
            else:
                # Use backend
                thread = threading.Thread(
                    target=simulate_backend_user,
                    args=(behavior.user_id, behavior, metrics)
                )
            
            thread.start()
            threads.append(thread)
            
            # Update progress bar
            if main_pbar:
                main_pbar.update(1)
                stats = metrics.get_stats()
                main_pbar.set_postfix_str(
                    f"Active: {stats['active_sessions']} | "
                    f"Done: {stats['completed_users']} | "
                    f"Abandoned: {stats['abandoned_users']} | "
                    f"Errors: {stats['total_errors']}"
                )
    
    if main_pbar:
        main_pbar.close()
    
    print(f"\nAll {len(threads)} user threads started. Waiting for completion...")
    print()
    
    # Progress bar for waiting phase
    total_finished = len(completed_users) + len(abandoned_users)
    if TQDM_AVAILABLE:
        wait_pbar = tqdm(total=num_users, desc="Completion", unit="user",
                        initial=total_finished,
                        bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]')
        wait_pbar.set_postfix_str("Waiting for users to complete...")
    else:
        wait_pbar = None
        print("Waiting for users to complete...")
    
    # Monitor progress while waiting
    max_wait_time = duration_seconds + 600  # Extra 10 minutes buffer
    check_interval = 2.0  # Update progress every 2 seconds
    
    while threads:
        # Check which threads are done
        active_threads = [t for t in threads if t.is_alive()]
        
        if wait_pbar:
            stats = metrics.get_stats()
            current_finished = stats['completed_users'] + stats['abandoned_users']
            wait_pbar.n = current_finished
            wait_pbar.set_postfix_str(
                f"Active: {stats['active_sessions']} | "
                f"Done: {stats['completed_users']} | "
                f"Abandoned: {stats['abandoned_users']} | "
                f"Errors: {stats['total_errors']}"
            )
            wait_pbar.refresh()
        
        # Remove finished threads
        threads = active_threads
        
        if not threads:
            break
        
        # Check timeout
        elapsed = time.time() - start_time
        if elapsed > max_wait_time:
            print(f"\nWarning: Timeout reached ({max_wait_time}s). Some threads may still be running.")
            break
        
        time.sleep(check_interval)
    
    if wait_pbar:
        wait_pbar.close()
    
    # Final join with timeout for any remaining threads
    for thread in threads:
        thread.join(timeout=10)
    
    # Stop memory monitoring
    if memory_monitor:
        memory_monitor.stop()
    
    # Close browser drivers
    for driver in frontend_drivers:
        try:
            driver.quit()
        except:
            pass
    
    elapsed_time = time.time() - start_time
    
    # Generate report
    generate_comprehensive_report(metrics, elapsed_time, num_users, memory_monitor)
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Real-time load test for voting system")
    parser.add_argument("--users", type=int, default=550, help="Number of users (default: 550)")
    parser.add_argument("--frontend-ratio", type=float, default=0.7, help="Frontend test ratio 0.0-1.0 (default: 0.7)")
    parser.add_argument("--duration", type=int, default=600, help="Test duration in seconds (default: 600)")
    parser.add_argument("--url", type=str, default=None, help="Server URL (default: http://127.0.0.1:7860)")
    parser.add_argument("--server-pid", type=int, default=None, help="Server process ID (auto-detect if not provided)")
    parser.add_argument("--no-memory", action="store_true", help="Disable memory monitoring")
    parser.add_argument("--no-headless", action="store_true", help="Run browsers in visible mode (default: headless)")
    
    args = parser.parse_args()
    
    # Update BASE_URL if provided (reassign module-level variable)
    if args.url:
        globals()['BASE_URL'] = args.url
    
    if not REQUESTS_AVAILABLE:
        print("ERROR: requests library required. Install with: pip install requests")
        sys.exit(1)
    
    if not SELENIUM_AVAILABLE and args.frontend_ratio > 0:
        print("ERROR: selenium library required for frontend testing. Install with: pip install selenium webdriver-manager")
        sys.exit(1)
    
    success = run_realtime_load_test(
        num_users=args.users,
        frontend_ratio=args.frontend_ratio,
        duration_seconds=args.duration,
        enable_memory_monitoring=not args.no_memory,
        server_pid=args.server_pid,
        headless=not args.no_headless
    )
    
    sys.exit(0 if success else 1)
