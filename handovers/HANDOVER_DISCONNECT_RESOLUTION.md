# Handover: resolving the Hunter remote-disconnect (logout) — next chat

Date: 2026-10-16
Repository: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`
Branch: `fix/twin-souls-dispatch` (working branch; see "Current state")

This is a continuation of the Hunter logout investigation. It supersedes the
older `HANDOVER_HUNTER_LOGOUT_V35.md` (pre-game-update) and folds in the three
new disconnect sessions captured after the 2026-10-16 game update.

## Read this first

The disconnect is **still not fixed** and is **not caused by click validity**
(offscreen / on-screen / invalid `down=0` clicks). Every Hunter build tested so
far disconnects. Do **not** start by re-testing Hunter again — repeating the
same test adds little information and may contaminate an account/session-side
scoring window. The next action is the **injection control** described in
"Next decisive test" below.

The single most important fact: the user reports that **manual metin-queue use
without injection does not disconnect**, but every injected Hunter run does.
That distinction has not yet been isolated under controlled conditions.

## Current state

- Branch: `fix/twin-souls-dispatch`
- Committed (on this branch, on top of `main`):
  - `647bd30` Implement Twin Souls dispatch via UI handler route
  - `acada3f` Resolve numeric Twin Souls state and clear pending on end
  - `a166220` Bump feature version to force reload on re-inject
- Uncommitted (do not commit without the user asking):
  - `client_feature.py` — Hunter offscreen **deferral** (native result 4 +
    per-VID backoff) and Hunter **camera rotation** (10 Hz sweep-and-stop).
    `FEATURE_VERSION = 47`.
  - `python_loader.cpp` — `ADD_DEFERRED = 4` result, `ReadViewport`, a
    viewport-bounds check before dispatch, and a wrapper capability marker
    (`__main__._lirin_native_queue_capability = 2`).
  - `test_client_feature_local.py` — tests for deferral + camera rotation.
- Built loader `client_feature_loader.dll` SHA-256:
  `504CC90B71DC4EF9E14FB4BB4A6970941731CB447DFCF6882A20C6EE12B0A598`
  (verify before any live test; the DLL is a build artifact not tracked by git).
- Preserve unrelated files (do not commit):
  - `.runtime/yin-yang-duel/yin_yang_duel_history.jsonl` (modified)
  - `ReactionTimingRecorder/`, `ReactionTimingRecorder.Tests/` (untracked)
  - `docs/ui-proposals-20261016/` (untracked)

The Twin Souls minigame work is complete and separate; it is not part of the
disconnect. Leave it intact.

## The problem in one paragraph

The Hunter feature automatically adds metins to the client's native attack queue
by dispatching synthetic clicks through the game's own input path. The server
consistently performs a **remote disconnect** (`Remote disconnected from
game.lirin.to:11035`) after a few minutes of Hunter operation. This happens
regardless of whether the clicks are valid or invalid, on-screen or offscreen,
or whether camera rotation is used. The client never logs the server's reason,
so the cause has to be inferred.

## Disconnect evidence (all known sessions)

| Build | PID | Modes | Result |
|---|---|---|---|
| v26 (projection guard, actor-click wrapper) | — | Hunter-only | ~40m42s, one long run (later judged non-reproducible, not a cure) |
| v28 exact isolated | 17800 | Hunter-only | disconnect ~3m35s, 15 adds |
| v33 (on-screen filter + camera) | 7364 | Hunter-only | disconnect ~8m43s |
| v35 (full-input path) | 4724 | Hunter-only | disconnect, 22 adds, avg gap 13.75s |
| v44 (Twin Souls dispatch) | 34524 | mixed + Hunter | disconnect 19:41:43; 45/60 out-of-viewport `down=0` |
| v46 (deferral) | 30016 | Hunter-only | disconnect 21:56:46; 0 out-of-viewport clicks, 39 clean adds, 1 in-viewport `down=0` |
| v47 (deferral + camera) | 33072 | Hunter-only | disconnect 23:10:08; queue filled 5/5, then disconnect ~26s later during attack phase |

Preserved evidence directories (in `C:\Users\andrej-pc\Documents\projects\decomp\`):

- `logout_pid34524_20261016/` — v44 session (REPORT.md + logs + native exports)
- `logout_pid30016_20261016/` — v46 session (metin_scanner.log + status.txt)
- `logout_pid33072_20261016/` — v47 session (metin_scanner.log + status.txt)

For the v47 run (PID 33072), the cleanest Hunter-only capture with the fix in
place: 25 total dispatches = 18 clean adds (`down=1`), 7 **in-viewport** `down=0`
(projection inside 2560x1369 but the hit-test found nothing), 2 offscreen
deferred. The queue filled 0→5/5, and the disconnect came ~26 s later while the
character was attacking, with no native action in between.

## How the client checks inputs (the verified physical-click chain)

This is the reference for "what the client checks". It comes from
`INPUT_RECORDER_BACKGROUND_PATH_PHASE1.md` and `INPUT_RECORDER_PROJECTION_API_FINDING.md`
(decomp evidence in `decomp/background_input_trace/`, `decomp/input_recorder_trace/`,
`decomp/metin_queue_trace/`). NOTE: those RVA addresses are for the **pre-update**
binary (SHA-256 `DBD69CAD…`); the Oct-16 build moved them (see "Current RVAs").

A physical left click runs, in order:

1. **WndProc admission** (`FUN_1404fc620`):
   - filter 1 (`FUN_14048bcd0`): per-button down-state + **1001 ms rate limiter**;
   - filter 2 (`FUN_14048c440`): focus check (only on `WM_ACTIVATEAPP`);
   - capture management (`GetCapture`/`SetCapture`/`ReleaseCapture`);
   - **down gate** (`FUN_1409bf660`): game-mode flag `[+0xb8]==0` AND
     app-active flag `app[+0x20]!=0`;
   - observer/consume hook;
   - record down `FUN_140471b10(code=1)`; `app[+0x80468]=1`.
2. **Down dispatch** (`FUN_1407e3e70(game, x, y)`):
   - normalize coords `(raw - offset) * logical / viewport`;
   - **UI hit-test** `FUN_1407e68d0` (element bounds);
   - hover-object update (`game[+0xa0]`);
   - pressed-object tracking (`game[+0xb0]`);
   - `OnMouseDown` vtable `+0xf0` → reaches the player press.
3. **Player press** (`FUN_1403e5940`): several gates, sets `player[+0xff]=1`,
   then the click-action router.
4. **Click-action router** (`FUN_1403ec0f0`):
   - early-return if `player[+0xe8]`;
   - reads the client cursor (`FUN_1407e13b0`, `game[+0x20/+0x24]`);
   - **actor hit-test** `FUN_140455b30`: walks the character-manager tree,
     projects each actor, hit-tests the cursor, returns the VID under it;
   - item/ground picks; actor-click `FUN_1403ebdd0` (duplicate/remove gate)
     → queue add `FUN_1403e41a0`.
5. **Queue gates**: eligibility predicate `FUN_1403e31f0`, duplicate handling,
   and a **500 ms same-VID debounce**.
6. **Up dispatch** (`FUN_1407e3fd0`): `OnMouseUp` vtable `+0xf8` → release.

**Input recorder**: `FUN_140471b10(recorder, code, x, y)` is a no-op unless
`recorder[+8]` is set. In background mode (`DAT_147a734c0 + 0x20 == 0`) button
state comes from `player[+0xff/+0x100]`; otherwise `GetAsyncKeyState`.
`FUN_140495ef0` sets `recorder[+0x90]` (dirty) only when `recorder[+8]` is
nonzero — it is not a demonstrated unconditional upload.

The whole post-admission dispatch chain is **coordinate-pure** (no OS cursor/
focus/button reads). OS-touching calls exist only in the WndProc admission layer.

## What the current wrapper does vs. a physical click

The current `python_loader.cpp` (V35 "full-input" route, updated RVAs) drives the
down/up dispatch directly:

- `DispatchClickAt`: `record_input(1)` → `game_down` (`RVA_GAME_DOWN_DISPATCH`)
  → `record_input(2)` → `game_up` (`RVA_GAME_UP_DISPATCH`).
- `NativeMetinQueueAddInner`, in order:
  1. membership pre-check (already present → no click);
  2. mouse-down check (`player[+0xff]`);
  3. live-actor resolve (`RVA_GET_ACTOR_BY_VID`);
  4. re-validate singletons;
  5. project actor to client pixels (`ProjectActorToScreen`);
  6. **viewport-bounds check** (the new deferral → `ADD_DEFERRED=4`);
  7. **override the picked actor** `manager[+0xE0]` (save, install target,
     restore in `__finally`);
  8. `DispatchClickAt`;
  9. membership re-check → result 1/2/3.

So the wrapper **does** run the down/up dispatch (UI hit-test, player press,
click router, queue gates, recorder down/up records) and skips only the WndProc
admission layer.

The one remaining, important deviation from a physical click is step 7: the
**picked-actor override** at `manager+0xE0`. The code comment states the click
router resolves its actor through that field, so supplying it synthetically
means the actor is chosen by the wrapper rather than by the **actor hit-test**
(`FUN_140455b30`) that a real cursor click performs. The V35 handover already
flagged this: "it is still a synthetic picker override … it did not prove
complete identity with a physical user click."

The `INPUT_RECORDER_BACKGROUND_PATH_PHASE1.md` doc describes a candidate
**background route**: drive `FUN_1407e3e70` + `FUN_1407e3fd0` directly with the
target's projected coordinates and **without** any picked-actor override. That
would let the actor hit-test pick the VID from the cursor, removing the last
synthetic step. That route was never built/tested (three Phase-1 gates remain
open, listed in §7 of that doc).

## What has been ruled out

- Offscreen/out-of-viewport clicks (v46/v47 defer them; disconnect persists).
- Camera rotation / projected-on-screen admission (v33/v34 tested; v47 re-tested; disconnect persists).
- Invalid in-viewport `down=0` clicks (they complete before the attack phase).
- Auto Reaction / its click timing, Boss Sweep / channel rotation, Legendary priority transitions.
- Direct low-level `MetinQueueAdd` insertion vs. the higher internal mouse-state path (v35 tested; disconnect persists).
- Raw average add cadence (v26 long run had a similar ~14s average gap to failing runs).

## Ranked remaining hypotheses

1. **Network-visible automated queue pattern / server policy.** Hunter chooses
   targets and replenishes the queue without a real cursor selection. The server
   may reject a sequence that is individually client-valid but implausible as
   manual play (target choice, transition pattern, session history, or a longer
   scoring window). This remains the top suspect.
2. **Detection of injection or the patched Python method table.** The
   injection-only / scanner-only runs historically looked stable, but the current
   patch has not been re-isolated under the current server/account conditions.
3. **The synthetic picked-actor override.** The one concrete, unremoved
   difference from a physical click (see "current wrapper vs physical click").
   Removing it (the Phase-1 background route) is the highest-value *code*
   experiment left, but it requires closing the Phase-1 gates first.
4. **Account/session-side cumulative scoring.** The one long v26 run may have
   been a non-triggering sample rather than proof of a fix.
5. **Ordinary network instability.** Less consistent with repeatability and the
   user's stable manual play, but no server reason is logged, so it cannot be
   eliminated.

## Next decisive test — do this before another Hunter build

Use a fresh Lirin process. Inject the current build (deferral + camera, or a
plain committed build), then keep **every automation mode OFF** (Hunter, Boss,
Reaction, Duel, Twin Souls). Manually use the metin queue for 15–20 minutes
under comparable map/combat conditions.

Interpretation:

- **If the injected/manual run disconnects** → the injection and/or the patched
  method table are the cause. Build a wrapper-disabled diagnostic variant before
  touching Hunter behavior.
- **If it stays connected** → injection is less likely; focus on automated target
  selection and the network-visible queue-transition pattern (and then try the
  Phase-1 "no picked-actor override" route as the smallest code change).

The user's "manual queue never disconnects" observation only counts as this
control if it was done **while injected**. If it was not injected, run the
no-injection control too for an exact comparison.

## Key paths and files

- Repo: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`
- Feature source: `client_feature.py`
- Native loader/wrapper: `python_loader.cpp` (build with `build.ps1 -FeatureOnly`)
- Feature log (per-branch runtime): `.runtime\<branch>\metin_scanner.log`
- Loader status: `.runtime\<branch>\python_window_loader.status.txt`
- Native game log: `C:\Program Files (x86)\Lirin\app\logs\<date>.log`
- Recovered (post-update) decomp workspace: `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery`
  (`recovered_code/`, `decompiled_all/`, `recovered_index/qualified_names.txt`)
- Pre-update decomp traces: `C:\Users\andrej-pc\Documents\projects\decomp\`
  (`background_input_trace/`, `input_recorder_trace/`, `metin_queue_trace/`,
  `native_picker_trace/`, plus the `logout_pid*_20261016/` evidence dirs)
- Key investigation docs in the repo root: `INPUT_RECORDER_BACKGROUND_PATH_PHASE1.md`,
  `INPUT_RECORDER_PROJECTION_API_FINDING.md`, `INPUT_RECORDER_LOGOUT_REVIEW.md`,
  and `handovers/HANDOVER_HUNTER_LOGOUT_V35.md`.

## Current native RVAs (Oct-16 build, in `python_loader.cpp`)

- `RVA_CHARACTER_MANAGER = 0x07CCAB10`
- `RVA_PLAYER_SINGLETON = 0x07CCAF00`
- `RVA_GAME_INSTANCE = 0x07CCAB50`
- `RVA_GAME_DOWN_DISPATCH = 0x00826C30` (down dispatch = the post-update address of the physical down path)
- `RVA_GAME_UP_DISPATCH = 0x00826D90`
- `RVA_RECORD_INPUT = 0x00497840`
- `RVA_GET_ACTOR_BY_VID = 0x003EE6D0`
- `RVA_PROJECTION_SETUP = 0x0065B530`, `RVA_PROJECT = 0x0065CEF0`
- `RVA_CAMERA = 0x07CCAB48`, `RVA_POS_Y_OBF = 0x068FCCF0`
- `CHARACTER_MANAGER_PICKED_ACTOR_OFFSET = 0xE0`, `PLAYER_MOUSE_DOWN_OFFSET = 0xFF`

Game EXE (Oct-16) SHA-256: `8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0`.

## Safety notes and constraints

- Do not inject on the user's behalf; the user performs live tests.
- Do not commit/push without the user asking. Keep the unrelated uncommitted files.
- Use a fresh game process for each trial; do not hot-swap a DLL into a process
  that already loaded one. The loaded DLL keeps its method pointer in process memory.
- Do not infer exact causal ordering across the feature log, loader status, and
  native game log — their clocks repeatedly disagree.
- "successful DLL load", "queue grew", or "a few minutes of play" are not proof
  the server accepts the behavior long-term.
- Preserve continuous Hunter replenishment unless the user approves a different shape.

## Concise continuation request for the next chat

Read this file and `handovers/HANDOVER_HUNTER_LOGOUT_V35.md`, then inspect the
current `git status` and the latest `.runtime\<branch>` logs. Treat the Hunter
disconnect as confirmed and not caused by click validity. First help run or
evaluate the **injection control** (all automation OFF, manual queue while
injected, 15–20 min). If that is stable, the highest-value code experiment is to
remove the synthetic picked-actor override and drive the down/up dispatch with
the target's projected coordinates so the client's own actor hit-test
(`FUN_140455b30`) performs the pick — closing the three open Phase-1 gates first.
