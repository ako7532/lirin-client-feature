# Handover — Yin-Yang Duel automation

Date: 2026-10-16
Branch: `yin-yang-duel`
Target game: Lirin (Metin2-like), embedded Python 2.7.

This is a handover for the **Yin-Yang Duel** minigame automation so a new chat
can pick it up. It is separate from the input-recorder / logout problem
(see `INPUT_RECORDER_LOGOUT_REVIEW.md` for that).

---

## 1. The game

A 9-round card duel vs a computer, done up to 8 times/day with a cooldown.

- Both players hold cards **0..8** (9 each).
- **Even = black, odd = white.**
- **Higher card wins the round**; a tie scores nothing and the round just
  advances.
- Each card is used once → 9 rounds.
- **Win more than half (5+) to win**; the match ends early once the result can
  no longer change.
- You only see the **colour** of the opponent's card (not its value).
- Sometimes we lead, sometimes the opponent leads.

(The exact score effect of a tie, and the next-leader rule, are still
unconfirmed — see open questions.)

## 2. Runtime API (discovered by live diagnostics)

Window class: `YinYangDuelWindow`. Found via
`FindRuntimeObject("YinYangDuelWindow", ())` (the object exists once the window
has been opened at least once in the session).

### Window fields

- `state` — `0` idle/lobby/cooldown, `2` playing (our pick), `3`/`4`
  opponent turn / reveal.
- `round` — current round (1..9).
- `playerScore` / `opponentScore`.
- `leadInfo` — dict `{'leads': bool, 'black': bool, 'round': int}`.
  - `leads=True` → we lead (play blind); `leads=False` → opponent led, we follow
    (and `black` is their led card's colour).
- `playerCards` / `opponentCards` — dict `{value: DuelCard}` (keys 0..8).
- `duelsUsedHwid` / `duelsMaxHwid` (=8).
- `cooldownEnd` (game-time), `startPending`, `reveal`.

### Window methods

- `CanPickCard()` — **takes no argument**; returns whether we may pick now.
- `OnCardClicked(card)` — play a card (takes the DuelCard object).
- `Open()`, `Close()`, `IsShow()`, `GetCooldownRemaining()`.
- `_YinYangDuelWindow__OnStartClicked()` — start the duel (name-mangled).

### Card (`DuelCard`)

- `value` (0..8), `played` (bool), `faceUp` (bool; ours True, theirs False).
- **`OnMouseLeftButtonDown()`** — the correct way to play a card (what a real
  click triggers). `OnCardClicked(card)` returns None and did **not** reliably
  play; `card.OnMouseLeftButtonDown()` worked.

## 3. Implementation layout (all in `client_feature.py`, pure Python)

- **Bitmask helpers** — `duel_mask_cards/count/remove/color`,
  `round_score_delta`, `terminal_duel_value`.
- **`DuelSnapshot`** — immutable snapshot (masks, scores, `we_lead`,
  `visible_color`, `exact_opponent_led_value`, `exact_value_confident`);
  `decision_key()` and `rounds_left`.
- **`DuelBaselineModels`** — uniform opponent response/lead + leader alternation
  (`next_leader`).
- **`DuelSolver`** — memoized expectimax over the match; exact-follow /
  color-follow / lead recurrences; 20 ms deadline (`DUEL_SOLVER_BUDGET_SECONDS`)
  with a deterministic fallback; `warm()` for cache warming. Verified against a
  no-memo brute force on random ≤4-card hands.
- **`DuelRoundTracker`** — mask read/validation, new-match detection, opponent
  led-card tracking (colour-matched), pending-click protection.
- **`DuelTrainedModels`** + `load_trained_duel_models()` — loads an offline
  frequency table with Laplace smoothing + uniform fallback.
- **Controller** (`PollYinYangDuel` + `_Duel*` helpers) — lifecycle + click.
- **`train_yin_yang_duel.py`** — offline trainer → `yin_yang_duel_model.json`.

### Controller behaviour

- Pauses only while Boss Sweep is **busy** (`BOSS_SWEEP_BUSY_STATES`), runs in
  parallel with the Hunter.
- Stops at the daily limit (`duelsUsedHwid >= duelsMaxHwid`).
- Cooldown is only a gate when **idle** (`state == 0`); during an active duel
  `GetCooldownRemaining()` is the *next*-duel countdown and must not stall us.
- Records JSON-lines history (`yin_yang_duel_history.jsonl`): `play`,
  `decision`, `result`, `finish` events.

## 4. Current state

**Done and unit-tested:**
- Pure solver (expectimax + memoization + deadline + fallback), brute-force
  reference tests, mask helpers, terminal values.
- Tracker + controller wiring, pending-click protection, daily limit, cooldown
  gating, Boss-Sweep gating.
- Versioned JSON-lines history + offline trainer.
- Cache warming during non-pick states.

**Open / broken:**
1. **"duel in progress, doesn't solve"** — last live run: label stuck on
   "duel in progress", no card played. A one-line diagnostic was added
   (`Yin Yang Duel: state=… round=… we_lead=… our=… opp=…`, throttled) but has
   **not been re-injected / read back**. Likely: stuck in state 3/4, or
   `build_snapshot` rejecting the mask counts.
2. **History encoding** — `str.encode("ascii")` raised
   `LookupError('unknown encoding: ascii')` (stripped Python 2.7 codec table).
   Fixed to write raw bytes on Python 2, not re-tested live.
3. **Not end-to-end validated** — never confirmed it plays a full duel.

**Unconfirmed game facts (block solver confidence):**
- tie scoring (assumed nothing),
- next-leader rule (assumed alternation),
- whether `opponentCards[value].played` exposes the exact led value before our
  response (assumed yes),
- whether the opponent is deterministic or probabilistic,
- tied-final-score result.

## 5. Build / test / deploy

- The duel work is **pure Python** — no C++ change, so no DLL rebuild is needed
  beyond the existing `client_feature_loader.dll`.
- Local tests: `python .\test_client_feature_local.py`.
- Deploy: re-inject via the launcher / `run_client_feature.ps1`. `FEATURE_VERSION`
  is 40; bump it if the panel shape changes and you need a fresh recreate.

## 6. Next steps

1. Re-inject and read the `state=… round=… we_lead=… our=… opp=…` diagnostic to
   fix the "doesn't solve" stall.
2. Live-validate one duel: reconstruct every round from the JSON-lines history
   and confirm scoring / tie / exact-lead / next-leader.
3. Fold in the trained model after ≥20 reconstructable matches.

## 7. Files on this branch

- `client_feature.py` — solver + controller + strategy + history.
- `test_client_feature_local.py` — solver/tracker/controller tests.
- `train_yin_yang_duel.py` — offline opponent-model trainer.
- `INPUT_RECORDER_LOGOUT_REVIEW.md`, `YIN_YANG_DUEL_REVIEW.md` — reviews.
- (plus the `handovers/` folder and `INPUT_RECORDER.md` from earlier work.)
