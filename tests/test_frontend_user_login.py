#!/usr/bin/env python3
"""
Frontend integration tests for user login using Selenium.

These tests actually test the frontend JavaScript and HTML behavior in a real browser.
This will catch bugs where the frontend doesn't read input values correctly.

Requirements:
    pip install selenium webdriver-manager

Run with: python tests/test_frontend_user_login.py
"""

import unittest
import sys
import time
import tempfile
import shutil
from pathlib import Path
import importlib
import threading
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: Selenium not available. Install with: pip install selenium webdriver-manager")

try:
    import uvicorn
    UVICORN_AVAILABLE = True
except ImportError:
    UVICORN_AVAILABLE = False
    print("Warning: uvicorn not available. Install with: pip install uvicorn")


class FrontendUserLoginTest(unittest.TestCase):
    """Frontend tests using Selenium to test actual browser behavior."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test server and browser."""
        if not SELENIUM_AVAILABLE:
            raise unittest.SkipTest("Selenium not available")
        if not UVICORN_AVAILABLE:
            raise unittest.SkipTest("uvicorn not available")
        
        # Set up temporary databases
        cls.temp_dir = tempfile.mkdtemp()
        cls.users_db = Path(cls.temp_dir) / "test_users.db"
        cls.evaluations_db = Path(cls.temp_dir) / "test_evaluations.db"
        
        # Set environment variables for test databases
        import os
        import config
        
        # Store original paths
        cls._original_users_db = config.USERS_DB_PATH
        cls._original_eval_db = config.EVALUATIONS_DB_PATH
        
        # Set new paths
        config.USERS_DB_PATH = cls.users_db
        config.EVALUATIONS_DB_PATH = cls.evaluations_db
        
        # Force reload of storage module
        import data_logic.storage
        importlib.reload(data_logic.storage)
        
        # Start test server in background thread
        cls.server_port = 8765
        cls.server_url = f"http://127.0.0.1:{cls.server_port}"
        
        # Change to project root directory for server to find files
        cls.original_cwd = os.getcwd()
        project_root = Path(__file__).parent.parent.resolve()
        
        def run_server():
            # Change to project root in the server thread
            os.chdir(project_root)
            import uvicorn
            # Import app after changing directory
            from app import app
            uvicorn.run(app, host="127.0.0.1", port=cls.server_port, log_level="error")
        
        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()
        
        # Wait for server to start
        try:
            import requests
        except ImportError:
            requests = None
        
        max_retries = 10
        for i in range(max_retries):
            try:
                if requests:
                    response = requests.get(f"{cls.server_url}/", timeout=1)
                    if response.status_code == 200:
                        break
                else:
                    # Fallback: just wait
                    time.sleep(1)
                    break
            except:
                time.sleep(0.5)
        else:
            if requests:
                raise RuntimeError("Test server failed to start")
        
        # Set up Chrome driver
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")  # Set window size
        
        try:
            cls.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            cls.driver.implicitly_wait(5)  # Wait up to 5 seconds for elements
            cls.driver.set_window_size(1920, 1080)  # Ensure window is large enough
        except Exception as e:
            raise unittest.SkipTest(f"Could not start Chrome driver: {e}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up browser and server."""
        if hasattr(cls, 'driver'):
            try:
                cls.driver.quit()
            except:
                pass
        
        # Restore original working directory
        if hasattr(cls, 'original_cwd'):
            try:
                os.chdir(cls.original_cwd)
            except:
                pass
        
        # Clean up databases
        try:
            import data_logic.storage
            if hasattr(data_logic.storage, 'USERS_DB'):
                data_logic.storage.USERS_DB.close()
            if hasattr(data_logic.storage, 'EVALUATIONS_DB'):
                data_logic.storage.EVALUATIONS_DB.close()
        except:
            pass
        
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    def setUp(self):
        """Navigate to test page before each test."""
        if not hasattr(self.__class__, 'driver'):
            self.skipTest("Browser not available")
        
        self.driver.get(self.__class__.server_url)
        # Wait for page to fully load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "start-btn"))
        )
        time.sleep(0.5)  # Additional wait for JavaScript to initialize
    
    def _click_button(self, button_element):
        """Helper method to click a button, handling interception issues."""
        try:
            # Try scrolling into view first
            self.driver.execute_script("arguments[0].scrollIntoView(true);", button_element)
            time.sleep(0.2)
            
            # Wait for element to be clickable
            WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(button_element)
            )
            
            # Try regular click first
            button_element.click()
        except Exception:
            # Fallback to JavaScript click if regular click fails
            self.driver.execute_script("arguments[0].click();", button_element)
    
    def test_enter_username_only_shows_age_error_not_username_error(self):
        """Test: Enter "whu" in username, leave other fields empty, should error about age.
        
        This test catches the frontend bug where JavaScript doesn't read the username
        input value correctly, causing it to send empty username to backend.
        
        EXPECTED: Error about missing age/gender/education
        ACTUAL BUG: Error about missing username
        """
        # Find input elements
        username_input = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "user-input"))
        )
        start_button = self.driver.find_element(By.ID, "start-btn")
        
        # Enter username "whu"
        username_input.clear()
        username_input.send_keys("whu")
        
        # Verify the input value is set (this checks if frontend can read it)
        actual_value = username_input.get_attribute("value")
        self.assertEqual(actual_value, "whu", 
                        f"Input value should be 'whu', but got: '{actual_value}'")
        
        # Click start button (without filling other fields)
        self._click_button(start_button)
        
        # Wait for error message to appear
        time.sleep(1)
        
        # Check what error message is shown
        status_message = self.driver.find_element(By.ID, "status-message")
        error_text = status_message.text
        
        # Should error about age/gender/education, NOT about username
        # This will FAIL if the frontend bug exists (sends empty username)
        self.assertNotIn("昵称", error_text,
                        f"BUG DETECTED: Frontend shows username error even though 'whu' was entered. "
                        f"Error message: '{error_text}'. "
                        f"This means frontend JavaScript is not reading the input value correctly.")
        
        # Should error about missing fields (age, gender, or education)
        self.assertTrue(
            "年龄" in error_text or "性别" in error_text or "教育" in error_text,
            f"Should error about missing age/gender/education, but got: '{error_text}'"
        )
    
    def test_enter_empty_username_shows_username_error(self):
        """Test: Leave username empty, should show username error."""
        start_button = self.driver.find_element(By.ID, "start-btn")
        
        # Don't enter anything in username field
        self._click_button(start_button)
        
        time.sleep(1)
        
        status_message = self.driver.find_element(By.ID, "status-message")
        error_text = status_message.text
        
        # Should error about username
        self.assertIn("昵称", error_text,
                     f"Should error about username when it's empty, but got: '{error_text}'")
    
    def test_enter_all_fields_starts_successfully(self):
        """Test: Enter all fields correctly, should start successfully."""
        username_input = self.driver.find_element(By.ID, "user-input")
        age_input = self.driver.find_element(By.ID, "user-age")
        gender_select = self.driver.find_element(By.ID, "user-gender")
        education_select = self.driver.find_element(By.ID, "user-education")
        start_button = self.driver.find_element(By.ID, "start-btn")
        
        # Enter all fields
        username_input.clear()
        username_input.send_keys("testuser123")
        age_input.clear()
        age_input.send_keys("25")
        
        # Select gender
        from selenium.webdriver.support.ui import Select
        gender_dropdown = Select(gender_select)
        gender_dropdown.select_by_value("男")
        
        # Select education
        education_dropdown = Select(education_select)
        education_dropdown.select_by_value("本科")
        
        # Click start
        self._click_button(start_button)
        
        # Wait for response
        time.sleep(2)
        
        # Check if evaluation box appears (indicates success)
        try:
            evaluation_box = self.driver.find_element(By.ID, "evaluation-box")
            self.assertFalse("hidden" in evaluation_box.get_attribute("class") or 
                           evaluation_box.is_displayed() == False,
                           "Evaluation box should be visible after successful start")
        except:
            # Check status message instead
            status_message = self.driver.find_element(By.ID, "status-message")
            status_text = status_message.text
            self.assertIn("成功", status_text or "欢迎" in status_text,
                         f"Should show success message, but got: '{status_text}'")
    
    def test_enter_whitespace_username_shows_username_error(self):
        """Test: Enter only whitespace in username, should show username error."""
        username_input = self.driver.find_element(By.ID, "user-input")
        start_button = self.driver.find_element(By.ID, "start-btn")
        
        # Enter only spaces
        username_input.clear()
        username_input.send_keys("   ")
        
        self._click_button(start_button)
        
        time.sleep(1)
        
        status_message = self.driver.find_element(By.ID, "status-message")
        error_text = status_message.text
        
        # Whitespace gets trimmed, so should error about username
        self.assertIn("昵称", error_text,
                     f"Should error about username when only whitespace entered, but got: '{error_text}'")
    
    def test_frontend_reads_input_value_correctly(self):
        """Test: Verify frontend JavaScript can read input values correctly.
        
        This test directly checks if the frontend can read the input value,
        which is the root cause of the bug.
        """
        username_input = self.driver.find_element(By.ID, "user-input")
        
        # Set value via JavaScript (simulating user typing)
        self.driver.execute_script("arguments[0].value = 'whu';", username_input)
        
        # Trigger input event to ensure JavaScript handlers are notified
        self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", username_input)
        
        # Check if value is readable
        value_via_js = self.driver.execute_script("return arguments[0].value;", username_input)
        value_via_attribute = username_input.get_attribute("value")
        
        self.assertEqual(value_via_js, "whu",
                        f"JavaScript should be able to read value 'whu', but got: '{value_via_js}'")
        self.assertEqual(value_via_attribute, "whu",
                        f"getAttribute should return 'whu', but got: '{value_via_attribute}'")
        
        # Now test if handleStart function can read it
        # We'll trigger the start button and see what gets sent
        start_button = self.driver.find_element(By.ID, "start-btn")
        self._click_button(start_button)
        
        time.sleep(1)
        
        # Check console logs (if available) or error message
        status_message = self.driver.find_element(By.ID, "status-message")
        error_text = status_message.text
        
        # If frontend reads correctly, should NOT error about username
        if "昵称" in error_text:
            self.fail(
                f"FRONTEND BUG: JavaScript cannot read input value correctly. "
                f"Value was set to 'whu' but frontend shows username error: '{error_text}'. "
                f"This indicates handleStart() function is not reading userInput.value correctly."
            )


if __name__ == "__main__":
    print("=" * 70)
    print("Frontend User Login Test Suite")
    print("=" * 70)
    print()
    print("This test suite uses Selenium to test the actual browser behavior.")
    print("It will catch bugs where frontend JavaScript doesn't read input values correctly.")
    print()
    
    if not SELENIUM_AVAILABLE:
        print("ERROR: Selenium not available.")
        print("Install with: pip install selenium webdriver-manager")
        sys.exit(1)
    
    if not UVICORN_AVAILABLE:
        print("ERROR: uvicorn not available.")
        print("Install with: pip install uvicorn")
        sys.exit(1)
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(FrontendUserLoginTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    sys.exit(0 if result.wasSuccessful() else 1)
