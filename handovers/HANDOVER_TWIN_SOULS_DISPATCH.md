# Handover: Twin Souls "waiting for verified background input" (dispatch not implemented)

Date: 2026-10-16
Branch: `main` (fix to be applied on a fresh branch)
Repository: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`

This is a bug report + code map for a fresh chat. It is the **next** defect after
`HANDOVER_MINIGAME_OWNER_AND_CLOSE_FIX.md`: that handover's two bugs (minigame-slot
arbitration + duel result dismissal) are fixed and merged, and Twin Souls now correctly
takes the slot — but it stops at a dispatch stub and never actually plays.

No code has been changed for this defect. Everything below is investigation + a fix
plan.

## The reported defect

With both Yin Yang Duel and Twin Souls enabled, Twin Souls now shows:

```
Twin Souls: idle; waiting for verified background input
```

(or, while a board is active, `... - background input unverified`). The solver stays ON
but never starts a board or flips a card.

This is *progress* over the previous bug: Twin Souls is no longer stuck on
"waiting for Yin Yang Duel". It now owns the slot and reaches the input-dispatch stage,
but that stage was never implemented.

## Root cause

The Twin Souls controller is a full solver (observe → choose → record), but the actual
**dispatch** of the two UI actions is stubbed out:

- `MemoryActionAdapter.is_verified()` (lines 1441–1442) hard-returns `False`, so
  `_TwinSoulsHandleIdle` (line 3244) and `_TwinSoulsHandlePlaying` (line 3193) always
  bail before dispatching.
- Even in the "verified" branch, the controller only calls `mark_pending_start()` /
  `mark_pending_flip()` and **never calls a dispatch method**. There is no
  `dispatch_start`/`dispatch_flip` anywhere in the codebase.

The adapter docstring says the gate exists because the "background-input feasibility"
(`INPUT_RECORDER_IMPLEMENTATION_PLAN`) was not verified. That reasoning was
over-applied — see "Why the safe route already exists" below.

## Why the safe route already exists (the key finding)

The disconnect-safety investigation concluded that the input recorder only audits the
**world-click** route (Hunter / Boss `_queue_add` → native full-dispatch → actor pick).
See `INPUT_RECORDER_PROJECTION_API_FINDING.md`, which states:

> The Yin Yang Duel worked in the same run because it uses a different path
> (`emit_synthetic_click` + direct card callback), not `_queue_add`.

UI minigames (Yin Yang Duel, the reaction game) already dispatch through a proven,
safe route that Twin Souls can reuse verbatim:

1. `emit_synthetic_click()` (line 151) — records a bare click via the VID-0 sentinel
   (`player.MetinQueueAdd(0)`), so the recorder sees a real click next to the action.
2. Invoke the client's own UI handler directly — no world projection, no cursor move.

Reference call sites:

| Minigame | Action | Code |
|---|---|---|
| Duel | play a card | `emit_synthetic_click()` then `card.OnMouseLeftButtonDown()` (lines 2679–2681) |
| Duel | start | `getattr(window, "_YinYangDuelWindow__OnStartClicked")()` (lines 2762–2764) |
| Reaction | start | `emit_synthetic_click()` then `window._ReactionGameWindow__OnClickPlay()` (2386) |
| Reaction | slot | `emit_synthetic_click()` then `window._ReactionGameWindow__OnClickSlot(slot)` (2416) |

Twin Souls is the same category — a board of UI cards. It must use the same route, not
the audited world route.

## Confirmed handler names (from decomp, not guesswork)

The game's `uiyinyangmemory` module was decompiled at:

`C:\Users\andrej-pc\Documents\projects\decomp\decompiled_all\modules\uiyinyangmemory.c`

The `/* Qualified names: … */` headers list the real Python members:

- **Start:** `uiyinyangmemory.YinYangMemoryWindow.__OnStartClicked` (file line 82019).
  Name-mangled to the instance attribute `_YinYangMemoryWindow__OnStartClicked`.
- **Flip:** `uiyinyangmemory.MemoryCard.OnMouseLeftButtonDown` (file line 13150).
  Public method (not name-mangled) — same shape as the duel card's
  `OnMouseLeftButtonDown` that `HANDOVER_YIN_YANG_DUEL.md` documents as "the correct
  way to play a card".
- Other useful members (for state/transition reference): `OnCardClicked` (82344),
  `Open` (83309), `Close` (29628), `__ResetToIdle` (17611), `OnStartResult` (3066),
  `OnFlipResult` (4260), `OnGameFinished` (4879), `__CanPlayAgain` (36204).

So the dispatch targets are exactly the ones the current comments already name in the
"never call directly" notes — the notes were about *routing through the adapter*, not
about the names being wrong.

## Code map (root `client_feature.py`, committed `main`)

| Concern | Location |
|---|---|
| `emit_synthetic_click()` (safe click record) | line 151 |
| `MemoryActionAdapter` (stub `is_verified` → `False`) | lines 1431–1442 |
| tracker pending markers | `mark_pending_flip` 1391, `mark_pending_start` 1421 |
| Duel reference: play card | 2679–2681 |
| Duel reference: start | 2762–2764 |
| Reaction reference: start/slot | 2386 / 2416 |
| `DiagnosticTwinSouls` (dumps fields + card attrs, NOT window methods) | 2964 |
| Twin Souls play handler (gate + missing dispatch) | `_TwinSoulsHandlePlaying` 3170 |
| Twin Souls cell resolution | `_TwinSoulsResolveCell` 3209 |
| Twin Souls idle handler (gate + missing dispatch) | `_TwinSoulsHandleIdle` 3233 |
| Tests | `test_client_feature_local.py` — adapter at 1080; controller tests ~1400–1503 |

## Fix direction

Implement the dispatch in `MemoryActionAdapter` and wire the controller to call it.
Recommended design (route through the adapter, matching the existing "never call the
handler directly" intent):

1. **Replace the `MemoryActionAdapter` stub** (lines 1431–1442) with a real adapter:

   ```python
   class MemoryActionAdapter(object):
       """Dispatch boundary for Twin Souls UI actions.

       Twin Souls is a UI minigame, like Yin Yang Duel and the reaction game, so its
       start and flips go through the same proven route: record a synthetic click, then
       invoke the client's own UI handler directly (no world projection, no cursor
       move, no audited world-click path).
       """

       def dispatch_start(self, window):
           start = getattr(window, "_YinYangMemoryWindow__OnStartClicked", None)
           if not callable(start):
               return False
           emit_synthetic_click()
           try:
               start()
               return True
           except Exception:
               return False

       def dispatch_flip(self, card):
           if card is None:
               return False
           click = getattr(card, "OnMouseLeftButtonDown", None)
           if not callable(click):
               return False
           emit_synthetic_click()
           try:
               click()
               return True
           except Exception:
               return False
   ```

   Note: `is_verified()` is removed (or kept returning `True` if you want minimal churn);
   the controller below no longer gates on it — it relies on the dispatch return value.

2. **Wire `_TwinSoulsHandlePlaying`** (lines 3191–3207): replace the `is_verified()`
   gate and the bare `mark_pending_flip` with a real dispatch. Dispatch **before**
   marking pending, and mark pending only on success, so a failed click retries next
   poll instead of wedging in "waiting for reveal":

   ```python
       self._TwinSoulsRecordEvent(
           self._TwinSoulsDecisionEvent(snapshot, knowledge, decision))
       card = self._TwinSoulsResolveCell(window, snapshot, decision["cell_index"])
       if card is None:
           self._TwinSoulsStatus("chosen cell unavailable; revalidating")
           return
       if not self.twin_souls_adapter.dispatch_flip(card):
           self._TwinSoulsStatus(
               "%s; next cell %d (%s) - flip unavailable" %
               (self._TwinSoulsSummary(snapshot), decision["cell_index"],
                decision["mode"]))
           return
       tracker.mark_pending_flip(decision["cell_index"], snapshot)
   ```

3. **Wire `_TwinSoulsHandleIdle`** (lines 3244–3253): replace the `is_verified()` gate
   and the bare `mark_pending_start()` with a real dispatch:

   ```python
       if (self.twin_souls_tracker.has_pending_start() or
               bool(getattr(window, "openPending", False))):
           self._TwinSoulsStatus("start pending")
           return
       if not self.twin_souls_adapter.dispatch_start(window):
           self._TwinSoulsStatus("idle; start unavailable")
           return
       self.twin_souls_tracker.mark_pending_start()
       self._TwinSoulsStatus("start dispatched")
   ```

4. **(Optional, recommended)** Extend `DiagnosticTwinSouls` (line 2964) to dump the
   window's action members so the handler names can be re-confirmed live:

   ```python
   members = [n for n in dir(window)
              if any(t in n.lower()
                     for t in ("start", "click", "open", "begin", "play", "result"))]
   self.AddLine("  memory window action members = %s" % ascii_text(repr(members)))
   ```

5. **Update the tests** (`test_client_feature_local.py`). The controller tests around
   lines 1400–1503 assert the old "unverified" behavior and a `VerifiedAdapter` that only
   has `is_verified()`. They must change to:
   - a `RecordingAdapter` (records `dispatch_start`/`dispatch_flip` calls) to assert the
     controller dispatches exactly once and marks pending only on success, and
   - a direct test of `MemoryActionAdapter.dispatch_start`/`dispatch_flip` against fakes
     that expose `_YinYangMemoryWindow__OnStartClicked` and `OnMouseLeftButtonDown`.

   The fake `MCard`/`FakeMemoryWindow` need those two handlers added for the real-adapter
   test. The "waiting for verified background input" (test line 1456) and
   "background input unverified" (test line 1492) assertions must be removed/replaced.

## Verification

- `python .\test_client_feature_local.py` must stay green (with the updated controller
  tests).
- Live: enable both minigames, let the duel finish, then confirm Twin Souls starts a
  board and begins flipping cards (log lines `Twin Souls: start dispatched`,
  `Twin Souls: … pairs`, and the per-decision lines) instead of
  "waiting for verified background input".
- Capture the `memory window action members = …` diagnostic line to re-confirm the two
  handler names against the live build (they are already confirmed by decomp above, so
  this is a sanity check, not a blocker).

## Constraints

- Python-only change in `client_feature.py` + `test_client_feature_local.py`. Do not touch
  the launcher/updater, `python_loader.cpp`, or the injection runner.
- Do not change the world-click path (`_queue_add`, Hunter/Boss). This fix only adds the
  UI-minigame dispatch that the duel and reaction game already use.
- Preserve unrelated work: `.runtime/yin-yang-duel/yin_yang_duel_history.jsonl` (modified)
  and the untracked `ReactionTimingRecorder/`, `ReactionTimingRecorder.Tests/` are
  unrelated and must not be committed.
- The runtime `state` values and the exact post-finish / post-flip transitions are still
  reverse-engineered; treat the solver's state classification as hypothesis. The
  dispatch handler names, however, are confirmed by the decomp above.
