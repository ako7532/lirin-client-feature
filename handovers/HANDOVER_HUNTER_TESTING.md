# Handover — Hunter reimplementation (for the next chat / live testing)

Date: 2026-10-17, Europe/Bratislava.

This document is self-contained: a fresh session with no prior context should be able
to continue building and testing this work from here. Read it fully before touching code.

---

## 1. What this is

A complete redesign of the "Metin Hunter" feature in the Lirin client injector. The old
design patched the game's native `player.MetinQueueAdd` binding and replayed a synthetic
mouse click (with camera projection / input-recorder events). The new design **removes
all of that** and instead:

- leaves the stock `player.MetinQueueAdd` / `MetinQueueRemove` / `MetinQueueSetEnabled`
  bindings untouched;
- adds a **read-only** native observer module `_lirin_hunter_native` that reports the
  authoritative queue (VID list, enabled flag, singleton identity token, stock-binding
  identity) and full native eligibility, without ever writing the queue;
- drives a small deterministic controller in Python that acquires an exclusive lease on an
  **empty + disabled** queue, then continuously refills it via the stock add, one add per
  tick, ≥1000 ms apart, tracking authoritative VID membership and ownership.

This is a **correctness redesign and a controlled experiment**, not a proven fix for the
repeated remote-disconnect problem ("H-AUDIT" hypothesis). The server's audit rule is
unknown; nothing here establishes it.

## 2. Where everything lives

| Path | Purpose |
| --- | --- |
| `C:\Users\andrej-pc\Documents\projects\lirin-client-feature` | main repo (`main`), do not edit here |
| `C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation` | **this worktree** — all implementation lives here |
| `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery` | read-only analysis (native traces) |
| `C:\Users\andrej-pc\Documents\projects\decomp` | read-only analysis (Ghidra project, PyGhidra, decompiled artifacts) |

- Branch: `feature/hunter-reimplementation`
- Worktree base commit: `36dccf64ec46fe6618a7286b9277bc29ca5bf9b7` (main `HEAD`).
- Installed game EXE: `C:\Program Files (x86)\Lirin\app\Lirin.exe`, SHA-256
  `8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0` (matching build).
  **All native RVAs are valid only for exactly this EXE hash.**

## 3. Documents to read, in order

1. `handovers/METIN_HUNTER_FINAL_IMPLEMENTATION_PLAN.md` — the executable spec (this is
   what governs; it supersedes the two older plans).
2. `handovers/HUNTER_PLAN_COMPARISON_VERIFIED_20261017.md` — why the final plan wins.
3. `handovers/HUNTER_NATIVE_API_CONTRACT.md` — verified native contracts (offsets, RVAs,
   CPython 2.7 API addresses, the eligibility predicate).
4. `handovers/HUNTER_AUDIT_EVIDENCE.md` — the bounded recorder-audit investigation
   (incoming config/trigger = PARTIAL, outgoing wire layout = PARTIAL).
5. `handovers/HANDOVER_HUNTER_REIMPLEMENTATION.md` — implementation summary + the
   post-review corrections (also reproduced in §6 below).
6. `C:\Users\andrej-pc\Documents\projects\decomp\HUNTER_IMPLEMENTATION_REVIEW_20261017.md`
   — the independent review that found the P0 crash and the P1/P2 lifecycle defects.

## 4. What is implemented

### Native (`python_loader.cpp`)
- Removed the old wrapper/interception entirely (method-table patch, synthetic click,
  projection, input-recorder calls, the `MetinQueueAdd(0)` sentinel).
- Registers `_lirin_hunter_native` (API v1) via the verified `Py_InitModule4`, exposing:
  - `now_ms()` — `GetTickCount64` as a Python long.
  - `snapshot()` — `{api_version, valid, error, player_cookie, vids, enabled, max_size,
    observed_tick_ms, stock_binding_ok}`. `player_cookie` is an opaque integer token
    (`PyLong` of the player address) — **never** the raw pointer as a PyObject.
    `max_size` is 0 here (the gateway sources it from the stock binding).
  - `admission(vid)` — resolves a fresh actor (`FUN_1405353b0`) and evaluates the full
    native predicate (`FUN_1403ed370`); returns `{valid, eligible, reason, player_cookie}`.
  - `audit_status()` — read-only recorder/app-active observation.
- All observer reads are SEH-guarded and validate the queue vector (alignment,
  `begin <= end <= capacity`, all-null-empty-only, post-copy metadata/singleton recheck).

### Python (`client_feature.py`, Python 2.7-compatible, ASCII)
- `HunterQueueGateway` — synchronous mutation facade with outcomes
  `ADDED / ALREADY_PRESENT / REJECTED_PRECALL / REJECTED_NATIVE / REMOVED /
  ALREADY_ABSENT / UNKNOWN / CANCELLED_PRECALL`. Dispatch-time guards: fresh snapshot,
  `stock_binding_ok`, cookie identity, dispatched-once, native admission.
- `HunterCandidateSelector` — immutable per-scan candidate snapshot; deterministic
  nearest-then-VID selection; squared-distance radius; Legendary name match.
- `HunterController` — states `OFF / STARTING / RUNNING / WAITING / RECONCILING / PAUSED /
  STOPPING / ERROR`; monotonic epoch; exclusive lease; ownership ledger; epoch-scoped
  `quarantine` (separate from 2 s rejection `backoff`); one add per tick ≥1000 ms; 2 s
  UNKNOWN deadline; owned-only Stop cleanup; Reaction pause/resume; Legendary priority
  (gated by `priority_enabled=False`).
- `HunterAuditObserver` — explicitly-enabled, read-only audit observation (polls
  `audit_status()` ≤100 ms, logs first observation / state+interval changes / 1 Hz
  heartbeat with max gap), independent of Hunter ON.

### Temporarily disabled (report "unavailable", no side effects)
Boss Sweep (`ToggleBossSweep`/`StartBossAttack`), automatic Reaction solver, Yin Yang
Duel (`ToggleYinYangDuel`), Twin Souls (`ToggleTwinSouls`), automated channel changes.
Reaction **safety detection** (pause/resume of the owned queue) still runs.

## 5. Build / test / inject

All commands run from the worktree in an **administrator** PowerShell.

```powershell
cd C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation

# build the loader (x64, /W4, MSVC)
.\build.ps1 -FeatureOnly

# local mock tests (Python 3; no game, no native code)
python -B test_client_feature_local.py

# whitespace/consistency check
git diff --check
```

Inject (game open, in the playable world, **fresh process**):

```powershell
.\run_client_feature.ps1                 # auto-selects the Lirin window
# or
.\run_client_feature.ps1 -TargetPid <pid>
```

`run_client_feature.ps1` stages the current `client_feature.py` + freshly built
`client_feature_loader.dll` into `.runtime\feature-hunter-reimplementation\` (per-branch),
copies the loader to a fresh GUID-named DLL, injects it via `inject.py`, and tails the
status log. `inject.py` requires 64-bit Python (the script hardcodes
`C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe`).

### Logs to inspect after injecting
- `.runtime\feature-hunter-reimplementation\python_window_loader.status.txt` — loader
  progress. On success it must contain, for the **new** PID:
  `EXE build matched`, `Hunter observer module registered`,
  `Python script returned successfully`.
- `.runtime\feature-hunter-reimplementation\metin_scanner.log` — feature/UI/Hunter log.
  Look for `Native Hunter observer: active` at panel creation, then `Hunter: …` lines for
  state transitions, `Hunter: added VID N (queue x/5)`, `Hunter: ownership conflict`,
  `Hunter: session invalidated: …`, and `Hunter: audit …` lines.

### Current artifact hashes (post-review build)
| File | SHA-256 |
| --- | --- |
| `client_feature_loader.dll` | `5B5A608EC61305B979A7165D8FAC774A8972E91C03B83812C2A4A18990E0A5DD` |
| `client_feature.py` | `E61CFB93265A177E1588D0A27108B362C3E7024011586939944516A76FF03589` |
| `python_loader.cpp` | `C5C46EB185FCC1C967415C57BB5AFD06312B19B906FEACD8E8C3E4472F2C59AF` |
| `test_client_feature_local.py` | `A6EE26B4D267470A600EEF3E923489EEFA1855D013F1C9F10D85C7487FE6A66D` |

**Do not inject the earlier `6C807D65…AECD` DLL** (pre-fix, has the P0 bug). Always
re-run `build.ps1 -FeatureOnly` and re-hash before a live run.

## 6. Crash history and the corrections

The first live attempt crashed the instant the user clicked Metin Hunter. Root cause
(review P0): `snapshot()`/`admission()` passed the raw C++ `player` pointer into
`PyDict_SetItemString` as a Python object; refcounting then wrote into the player's first
word (`ob_refcnt`) and corrupted memory. A secondary risk was deriving `max_size` by
calling two game functions with signatures inferred from one decompile.

The independent review (`decomp/HUNTER_IMPLEMENTATION_REVIEW_20261017.md`) then listed
P1/P2 lifecycle defects. All of these are corrected:

1. `player_cookie` is now an opaque `PyLong` token; raw pointer never exposed as PyObject.
2. Removed the unverified native `max_size` getters; `max_size` comes from the stock
   `player.MetinQueueGetMaxSize()` binding.
3. `ReadQueueVids` rejects inconsistent null triples and enforces alignment +
   `begin <= end <= capacity` + post-copy/singleton rechecks.
4. Stop/pause propagate `ERROR` on failed cleanup; disable a still-enabled empty owned
   session; UI status derived from controller.
5. UNKNOWN expiry → epoch-scoped `quarantine` + owned cleanup (not a 2 s backoff).
6. Foreign queue membership / external disable revoke ownership (ERROR, freeze adds);
   naturally-departed VIDs leave the ledger.
7. Reaction `resume` re-enables via stock `MetinQueueSetEnabled(1)`; `start` refuses while
   a safety pause is active.
8. Gateway enforces fresh-snapshot `stock_binding_ok`/cookie/dispatched-once/admission.
9. A replacement phase-5 window bumps the epoch; controller enforces scan epoch; final
   revalidation reads fresh player position/radius/anchor and compares live race.
10. `HunterAuditObserver` wires the audit query into an explicit observation session;
    maintenance/observation runs before the Reaction early return.
11. Priority ADDING honors the add interval and intended VID.

The local mock suite passes (`Hunter redesign local checks: OK`) and includes regressions
for these cases, but it uses **fake** observer/gateway and does not exercise native code.

## 7. How to test live (the ladder — plan §13)

A fresh game process for every variant. Never hot-swap into a process that ran an old or
crashed DLL. Keep Auto Reaction/Boss/Duel/Twin Souls OFF. The ladder:

1. **Matched uninjected manual control** — 15–20 min, no DLL, manual queue use.
2. **Injected stub control** — new loader, stock binding untouched, Hunter **OFF**
   (just scan), manual queue under comparable conditions, 15–20 min.
3. **Observer/discovery only** — native queries + candidate selection, zero mutations.
4. **One request** — exactly one eligible stock add; verify immediate authoritative
   membership + combat/consumption; verify Stop/owned cleanup in valid gameplay.
5. **Bounded continuous Hunter** — small capacity first, ~15 min; then capacity 5 and
   longer 45–60 min runs only when earlier stages are stable.
6. **Priority + Reaction** — separate fresh trials (priority is still `priority_enabled=False`
   in code; it must be validated before enabling).

At the first remote disconnect, native fault, wrong-VID membership, unexpected clear,
stuck attack after Stop, ownership conflict, or unreadable state: **stop that trial**,
preserve the status + feature logs, and investigate that specific failure. Do not add
jitter, recorder events, projection, or another dispatch route to "fix" it.

A stable control reduces hypotheses but never proves injection caused/avoided a
disconnect. Multiple comparable runs and manual controls improve evidence only.

## 8. Safety rules (do not violate)

- **Never** inject into a process that already ran the old wrapper or the crashed build;
  always a fresh game process.
- **Never** run the observer mutation path against a live process to "discover" a crash —
  verify native object ownership by reading `python_loader.cpp`, not by injecting.
- Hunter only starts on an **empty + disabled** queue; stop your manual queue first.
- Do not capture/replay live packets or send diagnostic packets (the user runs live tests).
- Do not weaken requirements to make a test pass. If a mandatory native/safety contract
  cannot be verified, stop at that gate and report the exact blocker.

## 9. Known limitations / unresolved (report honestly)

- **CPython 2.7 RVAs** are matched-build decompilation-derived and not live-verified;
  a fresh-process run must confirm registration + `snapshot()`/`admission()`/`audit_status()`.
- **Audit protocol** is only PARTIAL (incoming opcode and outgoing wire serializer are
  UNRESOLVED); full protocol recovery is optional and does not block local implementation.
- **H-AUDIT acceptance is untested** until an enabled-recorder exposure is recorded with
  the §13.1 coverage matrix (recorder-enabled / sample_ms / flush_ms / app-active, gaps,
  request correlation).
- **Priority** is implemented but gated off (`priority_enabled=False`); validate before use.
- **Temporarily unavailable:** Boss Sweep, automatic Reaction solver, Duel, Twin Souls,
  channel automation.
- Local success (tests, build, growing queue, loaded DLL) does **not** fix the disconnect
  or prove server acceptance. Report "local implementation verified" separately from
  "live behavior pending/observed" and "H-AUDIT acceptance untested/observed".

## 10. Next specific action

With a fresh Lirin process in the playable world, run `.\run_client_feature.ps1`, confirm
`Hunter observer module registered` + `Python script returned successfully` for the new
PID, then run the **stub control** (Hunter OFF) before any automatic add. Only then move
to the one-request stage.
