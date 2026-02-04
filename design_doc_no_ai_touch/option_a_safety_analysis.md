# Option A: Comprehensive Safety Analysis (No Implementation Yet)

This document analyzes **Option A** (persist “pending” assignment when we assign an image) so that implementing it will not damage the system. It covers every touch point, edge cases, failure modes, and mitigations.

---

## 1. What Option A Changes (Summary)

- **Semantic change:** Use the existing `users.seen_paths` column to store **pending paths** (image paths currently assigned to this user but not yet submitted), instead of leaving it always empty.
- **New behavior:** (1) When we assign an image in `get_next_image`, we persist that user’s pending paths immediately. (2) When we load user state, we treat `seen_paths` as “pending” and skip assigning any of those paths (and their poems) to that user. (3) On submit and on timeout we update and persist pending so it stays in sync.

**No schema change** if we reuse `seen_paths`. No new columns. No change to `seen_titles` semantics (still “poem titles the user has completed”).

---

## 2. Full Inventory of Touch Points

### 2.1 Code that reads/writes user state

| Location | What it does today | Impact of Option A |
|----------|--------------------|--------------------|
| **core/image_selection.py** | Loads `seen_titles` from DB; ignores `seen_paths`. Uses in-memory `pending_images`. Persists only on submit (`save_user_state(seen_titles, set())`). | **Must change:** Load `seen_paths` as pending; persist pending on assign, submit, and timeout; skip assignment when poem/path is in pending. |
| **data_logic/storage.py** | `load_user_state` returns `seen_titles` and `seen_paths`. `save_user_state(user_id, seen_titles, seen_paths)` writes both. `save_user_seen_titles` / `save_user_seen_paths` update one column. | **Interpretation only:** We start passing non-empty `seen_paths` (pending) from image_selection. Storage API stays the same. No change required in storage unless we need a new format for “pending + timestamp” (see §5). |
| **core/session.py** | Calls `store_user_demographics(uid)` for **new** users only, then `get_evaluation_item(uid)`. Never reads/writes `seen_*` directly. | **No change.** |
| **core/evaluation.py** | Calls `check_timeouts()` then `get_next_image(user_id)`. | **No change.** |
| **web/routes.py** | Uses session/evaluation APIs only. | **No change.** |

### 2.2 Code that writes to the users table

| Location | Operation | Impact |
|----------|-----------|--------|
| **storage.store_user_demographics** | `INSERT OR REPLACE` with only `(user_id, user_age, user_gender, user_education, created_at)`. Called **only for new users** in `start_session`. | Does not touch `seen_titles`/`seen_paths`. New row has NULL for those. **No conflict with Option A.** |
| **storage.save_user_state** | `UPDATE users SET seen_titles=?, seen_paths=? WHERE user_id=?` | Will now receive non-empty `seen_paths` (pending) from image_selection. **No change to signature.** |
| **storage.save_user_seen_paths** | `UPDATE users SET seen_paths=? WHERE user_id=?` | Could be used to persist only pending (e.g. after assign) without touching `seen_titles`. Optional. |
| **create_test_user_full.py** | Inserts/updates user then `save_user_state(uid, seen_titles_set, set())`. When updating existing user, only updates demographics columns (does not touch seen_*). | Passing `set()` for paths = no pending. **No change needed.** |
| **utils/rebuild_db_from_csv.py** | Rebuilds users from CSV; schema includes `seen_titles`, `seen_paths`. | No schema change. After Option A, CSV dumps will contain pending in `seen_paths`; rebuild restores it. **No change needed.** |

### 2.3 Code that reads from the users table

| Location | What it reads | Impact |
|----------|----------------|--------|
| **storage.load_user_state** | `seen_titles`, `seen_paths` | Already returns both. Image_selection will use `seen_paths` as pending. **No change to storage.** |
| **storage.get_user_demographics** | `user_age`, `user_gender`, `user_education`, `user_limit` | Does not use seen_*. **No impact.** |
| **storage.get_user_limit** | `user_limit` | **No impact.** |
| **storage.increase_user_limit** | `user_limit` then UPDATE | **No impact.** |

### 2.4 Tests and utilities

| Item | Dependence | Impact |
|------|------------|--------|
| **tests/test_user_login.py** | Uses USERS_DB for setup; does not assert on seen_titles/seen_paths. | **No change.** |
| **tests/test_db_validation.py** | Dumps users table; does not interpret seen_*. | **No change.** |
| **tests/test_realtime_load.py** | Reads `IMAGE_SELECTION_SYSTEM.users` and `user_state.pending_images` (in-memory). | Option A keeps the same in-memory structure; may also persist it. **No change.** |
| **utils/investigate_selection_logic.py** | Rebuilds “seen” from evaluations CSV only. | **No impact.** |
| **utils/investigate_duplicates_and_ratings.py** | Reads evaluations DB only. | **No impact.** |

**Conclusion:** Only **core/image_selection.py** needs code changes. Storage and all other callers can stay as-is unless we introduce a “pending + timestamp” format (§5).

---

## 3. Backward Compatibility and Existing Data

- **Current DB:** All existing code passes `set()` for `seen_paths` when calling `save_user_state`. So existing rows have `seen_paths` = NULL or `'[]'`.  
  **Option A:** We interpret NULL/empty as “no pending.” No migration script needed.

- **Existing users:** No row is ever replaced by `store_user_demographics` (only new users get that). So existing `seen_titles`/`seen_paths` are never wiped by demographics.

- **create_test_user_full:** Writes `save_user_state(..., set())` for paths; that remains “no pending.” If it updates an existing user, it only updates demographics; it does not clear seen_*.

- **rebuild_db_from_csv:** Restores `seen_titles` and `seen_paths` from CSV. Old CSVs have empty paths; new CSVs (after Option A) will have pending. Both are valid.

---

## 4. Order of Operations and User Row Existence

- **New user flow:** `start_session` validates → `store_user_demographics(uid)` (creates row) → `get_evaluation_item(uid)` → `get_next_image(uid)` → `load_user_state(uid)` (row exists).  
  So when we first persist pending, the user row already exists. **No risk of UPDATE affecting 0 rows** for normal new users.

- **Resume flow:** User already in DB; we never call `store_user_demographics` again. So we only ever read/update existing row.

- **Edge case:** If something called `get_next_image(uid)` without the user row existing (e.g. bug or alternate entry point), `load_user_state` would return `None`; we’d create an in-memory `UserState` with empty seen/pending. Then saving pending would do `UPDATE ... WHERE user_id=?` and affect 0 rows. So we’d fail to persist pending but wouldn’t corrupt data. **Mitigation:** Keep ensuring the user row is created in `start_session` before any `get_evaluation_item`; no new call paths that bypass that.

---

## 5. Server Restart and Pending Format

- **Today:** After restart, `IMAGE_SELECTION_SYSTEM` is re-created; `users` dict is empty. When a user requests an image, we load `seen_titles` from DB (and ignore `seen_paths`). In-memory `pending_images` is empty, so we have no record of “assigned but not submitted.”

- **Option A (minimal):** Store in `seen_paths` only a list of paths, e.g. `["path1", "path2"]`. On load we restore a set of pending paths and **skip** assigning those paths (and their poems) to that user. We do **not** restore `pending_images` with timestamps.  
  **Consequence:** After restart we cannot run `check_timeouts` on those entries (we don’t have `assigned_at`). So those paths stay “blocked” for that user forever until the user submits. If the user never submits (e.g. closed tab), that image is stuck: it’s still in the heap and could be assigned to **another** user, so we’d have the same image “pending” for user A (in DB) and assigned to user B. That is a **double-assignment** again.  
  So **if we only store paths without timestamps**, we fix duplicate for “same user, two requests before submit” but **not** for “restart + same image assigned to another user while first user’s pending is still in DB.”

- **Option A (recommended):** Store **pending with timestamp**, e.g. `seen_paths` as JSON array of objects: `[{"path": "...", "at": "2026-01-30T12:00:00"}]`. On load we parse and restore into `pending_images` as `path -> (ImageRecord, datetime)`. We need `ImageRecord`; we can get it from `all_images` by path (catalog is loaded at startup). Then:
  - `check_timeouts()` (called at start of `get_evaluation_item`) can clear timed-out entries from `pending_images` and **persist** the updated pending for affected users.
  - After restart, we load pending with timestamps, restore `pending_images`, and the next `check_timeouts` will return timed-out images to the heap and clear them from that user’s pending in DB.

So to **not damage** the system and to avoid new double-assignment after restart, we should use **pending with timestamp** and implement **persist after timeout** in `check_timeouts` (and optionally in `handle_timeout` if it’s ever used). That implies:

- **Format:** `seen_paths` stores something like `[{"p": "<path>", "at": "<iso datetime>"}]` (short keys to keep JSON small if needed). Parsing in `load_user_state` or in image_selection: if the value is a list of dicts, treat as pending-with-time; if it’s a list of strings (current possibility), treat as path-only for backward compatibility.
- **Storage:** Either keep using `save_user_state(user_id, seen_titles, pending_paths)` but with a serialized form that includes timestamps, or introduce a small helper that serializes/deserializes “pending list with at” in image_selection and passes a single string (e.g. JSON) for the second argument so storage still just writes `seen_paths` as TEXT.

**Conclusion:** Option A should store **pending paths with assigned_at** and persist after timeout so that restarts and timeouts do not leave stale pending or cause double assignment. This is part of “doing Option A safely.”

---

## 6. Multi-Worker (Multiple Processes)

- Each process has its own `IMAGE_SELECTION_SYSTEM` and in-memory `users` dict. So the **only** way worker B knows that worker A assigned image X to user U is the **database**.

- Option A: Worker A assigns X to U, then **immediately** persists pending (e.g. `save_user_seen_paths(uid, {X})` or full `save_user_state` with updated pending). Worker B then loads user state and sees X in pending, so it won’t assign X (or the same poem) to U again.  
  So **persisting right after assign** is required for multi-worker. Doing it inside the same critical section (before returning from `get_next_image`) minimizes the window where another request could load before the commit.

- **Lock:** We hold `_lock` only within one process. So we need the DB to be the source of truth for “who has what pending.” Option A achieves that.

---

## 7. Failure Modes and Mitigations

| Failure | Consequence | Mitigation |
|---------|-------------|------------|
| **Save pending fails after we add_pending** | In-memory we assigned the image; DB has no pending. Another request could assign the same (or same poem) to the same user. | After `add_pending`, try save; **on failure** remove from `pending_images` and re-raise (or return None / raise). Do **not** return the image to the client if we failed to persist. |
| **Save pending succeeds but commit is slow** | Another request might load before commit and still see old state. | Keep save + commit in the same `WRITE_LOCK` section in storage; minimize work between assign and return in get_next_image. |
| **User row does not exist when we save** | UPDATE affects 0 rows; pending not persisted. | Already ensured by flow: user is created in start_session before get_evaluation_item. Add a check if desired: if `load_user_state(uid)` is None and we’re about to assign, we could create the user row first (but that would be a new behavior; current flow already guarantees existence). |
| **check_timeouts clears pending but save fails** | In-memory pending is cleared and image is back in heap; DB still has that path in pending. So we might assign that image to another user while the first user’s DB still lists it as pending. | Persist in the same try/commit as the timeout clear. On save failure, we could re-add the timed-out entry to pending_images (rollback in-memory) and not add back to heap, then re-raise. So we don’t double-assign. |
| **Corrupt or invalid JSON in seen_paths** | load_user_state already uses try/except for JSON and defaults to empty set. | Same; no new risk. If we add a new format (list of objects), parse with fallback: if not list of dicts, treat as legacy (list of strings) or empty. |

---

## 8. What Must Not Change (Guarantees)

- **seen_titles:** Must remain “poem titles the user has **completed** (submitted).” Only updated on **submit**, never on assign or timeout. All existing logic that uses “user has seen this poem” for deduplication should keep using `seen_titles` only for completed.
- **Demographics:** `store_user_demographics` must remain the only writer for demographics columns and must only run for new users (no REPLACE of existing users). No change.
- **Evaluations table:** No change to schema or write logic. Option A only affects how we **assign** images (and what we store in users.seen_paths).
- **API contract:** `get_evaluation_item(user_id)` and `submit_rating(...)` signatures and return values unchanged. Session and routes unchanged.

---

## 9. Risks Summary and Mitigations

| Risk | Mitigation |
|------|------------|
| Reusing `seen_paths` for “pending” confuses future readers | Document clearly in storage and image_selection that `seen_paths` = “pending paths (with optional timestamps),” not “completed paths.” |
| Stale pending after restart if no timestamp | Store pending with `assigned_at`; restore to `pending_images` and run `check_timeouts`; persist after clearing timeouts. |
| Double assignment under load or multi-worker | Persist pending immediately after assign, before returning; use same DB for all workers. |
| Save failure after assign | Do not return the image if save fails; remove from pending and re-raise. |
| More DB writes (per assign, per timeout) | Acceptable for correctness; same WRITE_LOCK as today. If needed later, can batch or relax (e.g. persist only pending, not full state) with `save_user_seen_paths`. |

---

## 10. Implementation Checklist (When You Implement)

- [ ] **image_selection.get_user_state:** When loading from DB, restore pending from `seen_paths` (support both legacy list-of-strings and new list-of-{path, at}). Populate `pending_images` (with ImageRecord and datetime) using `all_images` for lookup. If no timestamp in DB, treat as “no timeout” (e.g. assign at = now) or skip restoring to pending_images and only use for “skip” set.
- [ ] **image_selection.get_next_image:** After `add_pending`, persist pending (e.g. `save_user_seen_paths` or `save_user_state`). On save failure, remove from pending_images and re-raise. In the “skip” check, treat path as assigned if it’s in pending (path or pending_paths set).
- [ ] **image_selection.submit_rating:** After `add_seen`, persist with updated pending (current `pending_images` keys) so DB matches.
- [ ] **image_selection.check_timeouts:** After removing an entry from a user’s `pending_images` and re-adding to heap, persist that user’s updated pending (so DB no longer lists that path for them).
- [ ] **image_selection.handle_timeout** (if ever used): Same as above: remove from pending, persist updated pending.
- [ ] **Storage:** Decide format for `seen_paths` (e.g. JSON array of `{"p":" path","at":"..."}`). If storage only ever receives a JSON string, no change to storage.py. If we want to keep storage generic, serialization/deserialization can live in image_selection and we pass a single string for “paths” that includes timestamps.
- [ ] **Tests:** Run test_db_validation, test_user_login, test_realtime_load after implementation. Optionally add a small test that two concurrent get_next_image for same user get different images (or second gets None if only one left).

---

## 11. Conclusion

- Option A **can be done without damaging the system** if:
  1. Only **core/image_selection.py** (and optionally storage format/helpers) is changed; all other code and APIs stay as-is.
  2. Pending is stored **with timestamps** and restored on load so that **check_timeouts** and persist-after-timeout keep DB and heap consistent after restarts.
  3. We **never return** an image to the client if we **fail to persist** pending after assign.
  4. We keep **seen_titles** semantics (completed only) and **do not** let demographics or evaluations logic be affected.

- The only semantic change is the **meaning of `seen_paths`** (from “unused / completed paths” to “pending paths”). No other reader of `seen_paths` exists in the codebase, so this is safe.

- Backward compatibility: existing DBs and CSVs with empty/NULL `seen_paths` continue to work; new format can support both legacy and timestamped pending for a smooth rollout.
