#!/usr/bin/env python3
"""
Multi-worker selection skew: real production-style test.

Root cause: Each Gunicorn worker has its own in-memory priority queue and
current_ratings, never synced after startup. Workers that rarely handle
submits keep a stale view and over-serve the same "lowest-count" images.

How we know the problem is fixed (three tests):

1. test_get_evaluation_item_calls_sync_from_db
   Asserts that get_evaluation_item() calls sync_from_db() before get_next_image.
   If someone removes the sync call from core/evaluation.py, this test FAILS.
   So: fix is in the production code path.

2. test_multi_worker_shows_skew_without_sync
   Runs 4 workers with no sync and no shared-DB mock. Asserts spread > 1 (we see skew).
   Documents the bug; passes because without sync we do see skew.

3. test_multi_worker_distribution_is_fair
   Same 4 workers, but we call sync_from_db() before each get_next_image and mock
   get_all_image_rating_counts to return shared counts (updated on every submit).
   Asserts spread <= 1 (fair distribution). Proves that sync + shared truth => fair.
"""

import random
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.image_selection import ImageSelectionSystem, ImageRecord
from core import evaluation as evaluation_module
from data_logic.catalog import CATALOG


def make_mini_catalog(num_images: int):
    """Build a small catalog for testing (no filesystem)."""
    catalog = {}
    for i in range(num_images):
        path = f"/fake/path/poem_{i}_gpt.png"
        catalog[path] = {"poem_title": f"poem_{i}", "image_type": "gpt"}
    return catalog


def create_worker(catalog: dict, seed: int) -> ImageSelectionSystem:
    """Create one worker with a fixed seed so heap order is deterministic."""
    random.seed(seed)
    return ImageSelectionSystem(catalog=catalog)


# Maximum allowed spread (max - min assigns per image). Fair distribution
# gives spread 0 (all images equal) or at most 1. With multi-worker skew we see 2+.
MAX_SPREAD = 1


class TestMultiWorkerSelectionSkew(unittest.TestCase):
    """
    Production-like test: multiple workers, realistic traffic, no hacks.
    We expect NO skew (fair distribution). Test fails with current code, passes after fix.
    """

    def setUp(self):
        self.load_patcher = patch(
            "core.image_selection.load_user_state",
            return_value=None,
        )
        self.save_state_patcher = patch("core.image_selection.save_user_state", MagicMock())
        self.save_pending_patcher = patch("core.image_selection.save_user_pending", MagicMock())
        self.load_patcher.start()
        self.save_state_patcher.start()
        self.save_pending_patcher.start()

    def tearDown(self):
        self.load_patcher.stop()
        self.save_state_patcher.stop()
        self.save_pending_patcher.stop()

    def test_get_evaluation_item_calls_sync_from_db(self):
        """
        Production code path must call sync_from_db() before get_next_image.
        If someone removes that call, this test fails — so we know the fix is in place.
        """
        if not CATALOG:
            self.skipTest("CATALOG is empty")
        path = next(iter(CATALOG))
        poem_title = CATALOG[path].get("poem_title", "")
        fake_result = (ImageRecord(path=path, poem_title=poem_title), 0)

        with patch.object(
            evaluation_module.IMAGE_SELECTION_SYSTEM,
            "sync_from_db",
            MagicMock(),
        ) as mock_sync:
            with patch.object(
                evaluation_module.IMAGE_SELECTION_SYSTEM,
                "get_next_image",
                return_value=fake_result,
            ):
                evaluation_module.get_evaluation_item("test_user_sync_check")
        mock_sync.assert_called_once()

    def test_multi_worker_shows_skew_without_sync(self):
        """
        Without syncing from DB, we see skew (spread > 1).
        Documents the bug; ensures the distribution test is not trivially passing.
        """
        num_images = 100
        catalog = make_mini_catalog(num_images)
        seed = 42
        num_workers = 4
        num_users = 200
        assign_worker_probs = [0.7, 0.1, 0.1, 0.1]
        submit_worker_idx = 0

        workers = [create_worker(catalog, seed) for _ in range(num_workers)]
        global_assigns = defaultdict(int)

        for user_idx in range(num_users):
            w_assign = random.choices(
                range(num_workers),
                weights=assign_worker_probs,
                k=1,
            )[0]
            user_id = f"user_{user_idx}"
            # No sync_from_db — workers have stale heaps
            result = workers[w_assign].get_next_image(user_id)
            if result is None:
                continue
            image_record, _ = result
            global_assigns[image_record.path] += 1
            workers[submit_worker_idx].submit_rating(
                user_id,
                image_record.path,
                image_record.poem_title,
            )

        assigns_per_image = dict(global_assigns)
        if not assigns_per_image:
            self.fail("No assigns recorded")
        spread = max(assigns_per_image.values()) - min(assigns_per_image.values())
        self.assertGreater(
            spread,
            1,
            msg=(
                "Without sync we expect skew (spread > 1). "
                f"Got spread={spread}. If this fails, something changed."
            ),
        )

    def test_multi_worker_distribution_is_fair(self):
        """
        Mimic production:
        - 4 workers, each with its own heap and counts.
        - Same seed so all start with identical heap order.
        - Uneven traffic: most assigns go to one worker, but ALL submits go
          to worker 0.
        - With the fix: each worker syncs from DB before get_next_image.
          We mock get_all_image_rating_counts to return shared counts (updated
          on every submit), so all workers see the same truth and distribution
          stays fair.

        We assert: assign distribution should be fair (max - min <= MAX_SPREAD).
        Without sync (or without fix): test would show skew. With sync: passes.
        """
        num_images = 100
        catalog = make_mini_catalog(num_images)
        seed = 42
        num_workers = 4
        num_users = 200

        assign_worker_probs = [0.7, 0.1, 0.1, 0.1]
        submit_worker_idx = 0

        # Shared "DB" counts: updated on every submit so sync_from_db sees truth
        global_rating_counts = defaultdict(int)

        def mock_get_all_image_rating_counts():
            return dict(global_rating_counts)

        workers = [create_worker(catalog, seed) for _ in range(num_workers)]
        global_assigns = defaultdict(int)

        with patch("core.image_selection.get_all_image_rating_counts", side_effect=mock_get_all_image_rating_counts):
            for user_idx in range(num_users):
                w_assign = random.choices(
                    range(num_workers),
                    weights=assign_worker_probs,
                    k=1,
                )[0]
                user_id = f"user_{user_idx}"

                # Fix: sync from shared "DB" before selecting (as get_evaluation_item does)
                workers[w_assign].sync_from_db()
                result = workers[w_assign].get_next_image(user_id)
                if result is None:
                    continue
                image_record, _ = result
                global_assigns[image_record.path] += 1

                workers[submit_worker_idx].submit_rating(
                    user_id,
                    image_record.path,
                    image_record.poem_title,
                )
                # Update shared counts so next sync_from_db sees this submit
                global_rating_counts[image_record.path] += 1

        assigns_per_image = dict(global_assigns)
        if not assigns_per_image:
            self.fail("No assigns recorded (all get_next_image returned None)")

        total_assigns = sum(assigns_per_image.values())
        min_assigns = min(assigns_per_image.values())
        max_assigns = max(assigns_per_image.values())
        spread = max_assigns - min_assigns

        self.assertLessEqual(
            spread,
            MAX_SPREAD,
            msg=(
                "Rating distribution should be fair (no multi-worker skew). "
                "If this fails, the same images are being over-served because "
                "workers that rarely handle submits have stale heap/counts. "
                f"spread={spread} (max={max_assigns}, min={min_assigns}), "
                f"total_assigns={total_assigns}, num_images_with_assigns={len(assigns_per_image)}. "
                f"Per-image counts (sorted): {sorted(assigns_per_image.values())}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
