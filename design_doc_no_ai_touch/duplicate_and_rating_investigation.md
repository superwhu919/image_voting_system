# Investigation: Duplicate Images/Poems and Rating Distribution

## What you observed

1. **Users seeing the same image multiple times** — test_db_validation reports (user, image_path) with count > 1.
2. **Users seeing the same poem multiple times** — (user, poem_title) with count > 1.
3. **Rating distribution skew** — 587 images with 1 rating, 100 with 2, 8 with 3, 3 with 4; expectation was more balance and no duplicate exposure.

## How to run the investigation script

From project root:

```bash
python utils/investigate_duplicates_and_ratings.py
```

With `--no-catalog` you skip catalog coverage (avoids loading catalog if `all_images` or CSV is missing):

```bash
python utils/investigate_duplicates_and_ratings.py --no-catalog
```

The script prints:

- Duplicate (user, image) and (user, poem) with **time deltas** between first and second evaluation (≤2 min → "likely concurrent request").
- **Rating breakdown**: how many images have duplicate submissions (same user, same image) vs distinct users.
- Optional: catalog size vs number of images that have at least one evaluation.

---

## Root cause 1: Duplicate (user, image) and (user, poem)

### Where it comes from in the code

- **Selection uses only `seen_titles` (poem title), and only in memory until submit.**

  - `core/image_selection.py`: `get_next_image()` checks `image_record.poem_title not in user_state.seen_titles` (line 185). So the same poem is not supposed to be shown twice to the same user.
  - `user_state.seen_titles` is loaded from the DB in `get_user_state()` via `load_user_state(user_id)` (lines 144–146). So the **only** place the server “remembers” what a user has seen is the DB (`users.seen_titles`).
  - That DB state is **updated only on submit**: in `submit_rating()` we call `save_user_state(user_id, user_state.seen_titles, set())` (line 228). There is no write when we **assign** an image (e.g. at start or when returning the next image).

So the timeline is:

1. User gets image A (poem P) — e.g. via Start or “next” after submit.
2. **No DB write yet** for “user has seen P”.
3. If the same user triggers **another** “give me the next image” (second tab, double Start, or second worker) **before** submitting for A:
   - The second request loads `seen_titles` from the DB; it still does not contain P.
   - So the second request is allowed to be assigned an image for poem P again — either the **same image** (same path) or **another image for the same poem** (e.g. same poem, different model: nano vs seedream).
4. Both evaluations are then submitted → two rows for (user, image_path) and/or two rows for (user, poem_title).

So:

- **Duplicate (user, image_path)** = same user was assigned the same image twice (two “next image” flows before either submit; e.g. two tabs or two workers).
- **Duplicate (user, poem_title)** = same user was assigned the same poem twice. This can be either the same image (so both duplicates above) or two different images for the same poem (e.g. 早寒江上有怀_nano and 早寒江上有怀_seedream).

The script’s **time deltas** support this: many duplicate pairs are within a few seconds (“likely concurrent request”); some are 10–17 minutes apart (e.g. two tabs, or one tab submitted and the other submitted later, but the second tab had been assigned the same poem before the first submit was persisted).

### Summary

- **Cause:** `seen_titles` is persisted only on **submit**, not when an image is **assigned**. Any second “get next image” for the same user before the first submit sees stale/empty `seen_titles` and can get the same poem/image again.
- **Concurrency:** Two tabs, double-click, or multiple workers all allow two assignments before either submission is written.

---

## Root cause 2: Rating distribution (many 1-rated, some 2–4)

### Two contributing factors

1. **Same-user duplicate submissions**  
   The script reports “Images that have at least one same-user duplicate” and “Evaluations that are 'extra' (same user, same image)”. Those extra evaluations **inflate** the per-image count. So part of “100 images with 2 evaluations” is from the same bug as above: one user evaluating the same image twice. If you remove duplicate (user, image) submissions, some of those images would drop from 2 to 1.

2. **No strict “one evaluation per image per user” in the queue**  
   The selection system prefers low-rated images (priority queue), but:
   - Assignments are not committed to the DB until submit.
   - So the same (or another) image for the same poem can be assigned again to the same user before submit, and then submitted twice.
   - Timeouts return an image to the queue; that image can be assigned again to the same or another user. So the **order** in which images get their 1st, 2nd, … evaluation is not strictly round-robin; it’s affected by concurrency and who submits when.

So the skew (587 with 1, 100 with 2, …) is partly:

- **Duplicate bug:** some of the “2” (and higher) counts are from the same user submitting the same image/poem twice.
- **Normal variation:** the rest is from different users; the exact distribution depends on traffic and timing, not a perfect round-robin.

### “Many images with 0 ratings”

- The validation output says “Number of images with rating = 0: 0” — meaning **among images that appear in the evaluations table**, none has zero evaluations.
- If by “many images with 0 ratings” you mean **catalog images that have never been evaluated**, that’s: (total catalog size) − (unique image_path in evaluations). The script’s “Catalog coverage” section (when run without `--no-catalog`) reports how many catalog images have 0 evaluations.

---

## Summary table

| Observation | Cause |
|------------|--------|
| Same user sees same image twice | Second `get_next_image` before first submit; `seen_titles` not persisted until submit. |
| Same user sees same poem twice (same or different image) | Same as above; poem is the key in `seen_titles`, so same poem can be assigned again. |
| Rating skew (587 with 1, 100 with 2, …) | (1) Duplicate submissions inflate counts for some images. (2) Assignment order depends on concurrency and timeouts, not strict round-robin. |
| Images with 0 ratings (in catalog) | Those are catalog images that have never been assigned/evaluated yet; count = catalog size − evaluated. |

No application code was changed for this investigation. The script `utils/investigate_duplicates_and_ratings.py` is additive and only reads the DB (and optionally the catalog).
