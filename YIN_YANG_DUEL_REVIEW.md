# Yin-Yang Duel + input-recorder — Review

Date: 2026-10-16
Branch: `yin-yang-duel`

This is a review of the current working state, written so a follow-up can turn
it into an implementation plan. It covers two distinct pieces of work that are
now entangled:

1. The **input-recorder fix** (started on `main`, now in this branch) — the
   anti-bot countermeasure.
2. The **Yin-Yang Duel solver** (this branch) — a minigame automation.

---

## 1. The blocker: input recorder audit caused a logout

This is the most important open problem.

### Timeline of the latest logout

```
09:00:39  Boss Sweep starts (8-channel sweep, boss killed on every channel)
09:04:26  Boss Sweep finishes, Hunter resumes
09:06:19  last queue add while recorder_enabled=0  (sample_ms=100)
09:07:24  recorder_enabled flips 0 -> 1           (sample_ms 100 -> 40)
09:07:24..09:08:18  Hunter adds ~7 metins (all with synthetic down/up records)
09:09:09  net.Disconnect (empty args, empty stack) -> remote close / NewLoginWindow
```

Key evidence, from `python_window_loader.status.txt`:

```
tick=110006984 vid=27498078  recorder_enabled=0 sample_ms=100
tick=110071906 vid=27499028  recorder_enabled=1 sample_ms=40   <- server enabled audit
... (6 more adds, recorder_enabled=1 sample_ms=40)
```

### What this tells us

- The server **enabled the input recorder** at ~09:07:24 and tightened
  `sample_ms` from 100 to 40 (i.e. it began sampling mouse position every 40ms).
- It watched ~7 synthetic queue adds, then disconnected ~1.5 min later.

### Why the synthetic input is still detected

The synthetic input **is** being emitted for each queue add (down code 1 / up
code 2 via `FUN_140471b10`). The problem is the records are not *plausible*:

1. **Down and up are 0 ms apart** — `EmitSyntheticClick()` calls
   `record_input(1)` then `record_input(2)` back-to-back. A real press→release
   is ~50–100 ms.
2. **Every click is at the same fixed position** — it uses `FUN_1407e13b0`
   (the game's internal cursor), which does not move between adds. The ~7
   stones are at different screen positions.
3. **No mouse movement** — the recorder's code-0 movement samples (every 40 ms)
   show the cursor sitting still while stones are added, instead of a path to
   each stone.

So the gap is not a *missing* input; it is an *implausible* one, and the
40 ms sampler is detailed enough to see it.

### Related uncertainty

Earlier the "Diag +1" button stayed connected 30 min with a *real* click, but
that was with `recorder_enabled=0`. This logout is the first observation with
`recorder_enabled=1`, so we cannot yet know exactly which of (1)/(2)/(3) the
server flags. The input-recorder fix has **not been validated under audit**.

---

## 2. Yin-Yang Duel solver — status

Implemented on this branch (all pure-Python in `client_feature.py`, plus a
standalone trainer):

- **Bitmask helpers** (`duel_mask_cards/count/remove/color`), `round_score_delta`,
  `terminal_duel_value`.
- **`DuelSnapshot`** — immutable validated snapshot with `decision_key()`.
- **`DuelBaselineModels`** — uniform response/lead models + leader alternation.
- **`DuelSolver`** — memoized expectimax over the 9-round match with
  exact-follow / color-follow / lead recurrences, a 20 ms deadline, and a
  deterministic fallback. Verified against a no-memo brute force on random
  ≤4-card hands.
- **`DuelRoundTracker`** — mask reading/validation, new-match detection, opponent
  led-card tracking (colour-matched), pending-click protection.
- **Controller** (`PollYinYangDuel` + helpers) — gated on Boss Sweep busy state,
  daily limit (8/HWID), cooldown (idle only), history recording.
- **`DuelTrainedModels`** + `load_trained_duel_models` — loads an offline-trained
  frequency table (Laplace smoothing + uniform fallback).
- **`train_yin_yang_duel.py`** — offline trainer producing
  `yin_yang_duel_model.json`.

### Open bugs / unresolved

1. **"duel in progress, doesn't solve"** — last live test showed the label stuck
   on "duel in progress" with no card played. A one-line diagnostic was added
   (`state=… round=… we_lead=… our=… opp=…`) but has **not been re-injected /
   read back**, so the cause is still unknown. Likely candidates: stuck in
   state 3/4 (never our turn), or `build_snapshot` rejecting the mask counts.
2. **History encoding** — `str.encode("ascii")` raised `LookupError('unknown
   encoding: ascii')` in the embedded Python 2.7 (stripped codec table). Fixed
   to write raw bytes on Python 2, but not re-tested live.
3. The solver itself is **unit-tested but not live-validated** — no end-to-end
   evidence it plays a full duel correctly.

### The plan document's unresolved live facts

From `YIN_YANG_DUEL_SOLVER_IMPLEMENTATION_PLAN.md`, still unknown:

- the score change for win / loss / tie (tie assumed to score nothing);
- how the next round's leader is selected (assumed alternation);
- whether `opponentCards[value].played` exposes the exact led value before our
  response (assumed yes);
- whether the opponent response is deterministic or probabilistic;
- the match result when the final scores are tied.

---

## 3. Recommended priorities for the follow-up plan

1. **Input recorder (logout) — highest priority.**
   Decide between:
   - (a) full realistic input: resolve the target stone's screen position,
     emit movement samples toward it, and a ~50–80 ms down/up with jitter; or
   - (b) cheap win first: realistic down/up timing + position jitter only, to
     confirm which aspect the server flags.
   This is in C++ (`python_loader.cpp`), so it needs a rebuild.

2. **Yin-Yang Duel "doesn't solve"** — re-inject and read the
   `state=… round=… we_lead=… our=… opp=…` diagnostic line, then fix the
   turn-detection / snapshot-validation path.

3. **Live-validate the solver** — run one manual + one automated duel and
   reconstruct every round from the JSON-lines history, confirming scoring,
   tie handling, exact-lead visibility, and the next-leader rule before
   trusting the solver.

4. **Fold the trained model back in** only after ≥20 reconstructable matches.

---

## Summary

- The **input-recorder fix is real but insufficient** — it passes a
  disabled-recorder test but fails under a 40 ms audit because the synthetic
  clicks have no movement, no position variance, and no press duration.
- The **Yin-Yang Duel solver is structurally complete and unit-tested**, but has
  an unresolved live "doesn't solve" bug and has never been end-to-end
  validated.

The logout should be treated as the primary blocker; the duel solver is
secondary until the anti-bot input path is made plausible.
