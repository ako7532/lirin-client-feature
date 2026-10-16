# Input recorder — projection API finding

Date: 2026-10-16
Branch: `fix-duel-stuck` (worktree)
Status: fix applied in code; **live re-verification pending**.

> **Correction.** An earlier version of this note concluded that
> `player.GetProjectPosition` "legitimately accepts actor VIDs". That was wrong.
> A live-instrumented run disproved it: every Metin/boss add was rejected with
> the projection returning `(-100,-100)`. This document records the corrected
> finding and its consequences.

## Summary

`_queue_add` was projecting click coordinates with the wrong binding. The client
exposes **two** projection bindings that return the same `(x, y)` / `(-100,-100)`
shape but resolve the VID through **different registries**:

| Binding | RVA | VID resolution | Result for Metin/boss VIDs |
| --- | --- | --- | --- |
| `player.GetProjectPosition` | `1403fa410` | `FUN_1403e2dc0(DAT_147a6b8e8, vid)` — a separate manager map | `(-100,-100)` — does **not** resolve them |
| `chr.GetProjectPosition` | `140528aa0` | walks the character-manager tree at `DAT_147a6b450 + 0xf8` | correct client-pixel coordinates |

The Hunter's VIDs come from the entity snapshot, which walks `DAT_147a6b450 +
0xf8`. Only `chr.GetProjectPosition` resolves the same tree, so it is the
correct binding.

## Decomp evidence

- `1403fa410` (`decomp/.../metin_feature_apis.c`): `lVar6 = FUN_1403e2dc0(DAT_147a6b8e8, vid)`,
  then `FUN_14061e430(...)`; on miss returns `(-100,-100)`.
- `140528aa0` (`decomp/metin_queue_trace/140528aa0.c`): reads the tree head
  `DAT_147a6b450 + 0xf8`, walks it comparing the node `vid` at `+0x20`, reads the
  actor at node `+0x28`, then projects via `FUN_14061e430`; on miss returns
  `(-100,-100)`.

The loader's `WriteVisibleVidsSnapshot` (`python_loader.cpp`) walks the same
`DAT_147a6b450 + 0xf8` tree (`RVA_CHARACTER_MANAGER = 0x07A6B450`, `CharacterNode`
`vid` at `+0x20`, `actor` at `+0x28`). The VIDs the Hunter receives are therefore
resolvable by `chr.GetProjectPosition`, but not by `player.GetProjectPosition`.

## Live confirmation (2026-10-16, PID 10324)

With `_queue_add` using `player.GetProjectPosition`, every world add was rejected
before any native dispatch:

```
metin_scanner.log:
  Queue rejected VID 27928627, queue 0->0, call 0.00ms     (repeated for many VIDs)
  Boss Sweep error: RuntimeError('temporary boss queue rejected VID 27941580',)

python_window_loader.status.txt:
  (no "queue input diagnostic", "route:", or "result:" lines at all)
```

The absence of any native-diagnostic line proves `player.MetinQueueAdd(vid, x, y)`
was never called — `_queue_add` raised `QueueAddRejected` at the projection step
first. The Yin Yang Duel worked in the same run because it uses a different path
(`emit_synthetic_click` + direct card callback), not `_queue_add`.

## Implication for the earlier release runs

Release `(2)` (reviewed in `decomp/LOGOUT_RELEASE2_REVIEW_20261016.md`) used the
same `_queue_add` that silently fell back to `player.MetinQueueAdd(vid)` whenever
projection returned `(-100,-100)`. Because `player.GetProjectPosition` returns
`(-100,-100)` for Metin VIDs, **every** "Queued" line in those runs was almost
certainly the **legacy picker-override fallback**, not the new full-dispatch
route. The review's finding #1 ("the new route can silently become the old
route") was therefore not just a latent risk — it was the path that actually ran.

Consequence: the full-dispatch world route has **not yet been observed to work
live**. It must be re-tested with `chr.GetProjectPosition` before any claim that
the new route lands on the target is made.

## Where the earlier reasoning went wrong

`FUN_1403ec0f0` (the click router) resolves a *picked* VID via
`FUN_1403e2dc0(DAT_147a6b8e8, …)`. That only shows `DAT_147a6b8e8` is a registry
the click path uses for already-picked targets; it does **not** mean it is the
registry that holds the Hunter's monster-stone VIDs. The Hunter's VIDs come from
the `DAT_147a6b450 + 0xf8` tree, which is a different manager.

## The fix

`client_feature.py` `_queue_add` now projects via `chr.GetProjectPosition`:

```python
project = getattr(chr, "GetProjectPosition", None)
...
projected = project(vid, PROJECT_CLICK_HEIGHT)
```

The "no silent fallback" behaviour is unchanged and correct: a Metin that does
not project on screen (off-screen / despawned / behind camera) is rejected
explicitly (`QueueAddRejected`) rather than queued through the old
picker-override path. This is the surfaced design constraint — the faithful
route can only click on-screen targets.

## Verification status

- Local test (`test_client_feature_local.py`), `build.ps1`, and `git diff --check`
  all pass with the fix.
- **Live re-verification is pending**: a fresh Lirin process must be injected and
  a Hunter-only run observed, expecting `route: full-dispatch vid=… x=… y=…`,
  `down=1 up=1 fault=0`, and `result: … code=1` for on-screen Metins.

## Related fixes in this same change set

Alongside the projection fix, the dispatch/acknowledgement contracts from
`LOGOUT_RELEASE2_REVIEW_20261016.md` were fixed:

- `_queue_add` no longer silently falls back to the single-argument binding.
- `_dispatch_native_add` maps a certain pre-dispatch rejection to `REJECTED` and
  any other dispatch exception to `UNKNOWN` (never an immediate retry); fixed the
  truthy-string `validate()` check; retains `UNKNOWN` actions for diagnostics.
- `FeedMetinQueue` treats only `result == 1` (requested VID newly present) as
  success, not `new_size > size`.
- `python_loader.cpp` `DispatchClickAt` captures/logs down/up results and adds a
  fault-safe release; the fallback path sets `pressed` before the press call;
  route/result/button-state diagnostics added.
