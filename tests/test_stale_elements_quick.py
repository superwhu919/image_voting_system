#!/usr/bin/env python3
"""
Quick test for stale element fixes - tests just a few users to verify fixes work.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the realtime load test function
from tests.test_realtime_load import run_realtime_load_test

if __name__ == "__main__":
    print("Running quick stale element test...")
    print("=" * 60)
    
    # Run with minimal users and short duration
    success = run_realtime_load_test(
        num_users=3,
        frontend_ratio=1.0,  # All frontend to test stale element fixes
        duration_seconds=30,  # Very short duration
        enable_memory_monitoring=False,  # Skip memory monitoring for speed
        headless=True
    )
    
    print("\n" + "=" * 60)
    if success:
        print("✓ Quick test completed")
    else:
        print("⚠️  Quick test had issues - check output above")
    
    sys.exit(0 if success else 1)
