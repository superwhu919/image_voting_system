# Why seedream > nano (in v2 / v2.1 / v2.2)

## Summary

**Main reason: seedream has a much higher q1-1 (poem match) correct rate.**  
Under v2-style `q1_joint` scoring, "correct" gets 2–6 points and "incorrect" gets -1–2, so that single dimension dominates the total gap.

## Numbers (from your calc_score reports)

| Version | seedream total | nano total | Who wins |
|---------|----------------|------------|----------|
| v1      | 36.52          | 36.67      | nano (by 0.15) |
| v2      | 37.17          | 37.02      | seedream |
| v2.1    | 36.76          | 36.53      | seedream |
| v2.2    | 36.72          | 36.49      | seedream |

- **v1**: q1-1 and q1-2 are scored separately. seedream q1-1 mean **0.88** vs nano **0.75** (seedream more often picks the right poem). Nano still wins overall in v1 because it does slightly better on many q2-* questions and the q1-1 gap isn’t weighted as heavily.
- **v2+**: `q1_joint` combines q1-1 and q1-2. Correct + high confidence (a) = 6; incorrect + guess (d/e) = 0 or -1. So:
  - **seedream**: ~88% correct → many 4–6 on q1; ~12% incorrect → low q1.
  - **nano**: ~75% correct → many 4–6 on q1; ~25% incorrect → low q1.
  - **q1 mean**: seedream ~4.5, nano ~4.0 (v2.2). That ~0.5 difference on q1 is the main reason seedream’s total is higher.

On **q2-***, nano is often slightly ahead (e.g. q2-3, q2-4, q2-7, q2-8, q2-9 in v2.2), but those gaps are small (0.05–0.15 per question). They don’t offset the q1 gap.

## Conclusion

- **Why seedream > nano in v2/v2.1/v2.2:**  
  Seedream has a **higher q1-1 correct rate** (right poem more often). With `q1_joint`, that turns into a **higher q1 score** (correct path 2–6 vs incorrect path -1–2), and that q1 advantage outweighs nano’s small advantages on several q2-* items.

- **Why nano was ahead in v1:**  
  In v1, q1-1 is only 0/1 (max 1 point), so the 13% correctness gap (0.88 vs 0.75) adds only ~0.13 to seedream’s total. Nano’s better performance on q2-* (e.g. q2-3, q2-4, q2-8, q2-9) was enough to pull ahead overall.
