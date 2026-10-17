# Metin Hunter clean-removal and reimplementation plan

Date: 2026-10-17
Planning workspace: `C:\Users\andrej-pc\Documents\projects\decomp`
Implementation repository: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`
Recovery/decompilation repository: `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery`

## 1. Objective

Remove the current Metin Hunter implementation completely while preserving its existing UI surface, then rebuild Hunter as a small, auditable controller based only on behavior confirmed in the current decompiled client.

The replacement must:

- keep the existing Metin Hunter button, card placement, and status text;
- contain no callable or fallback path into the old Hunter implementation;
- use the stock queue operation as the only queue mutation in the first implementation;
- never manufacture raw mouse data, cursor movement, recorder samples, or human-like timing;
- validate a requested VID through authoritative requested-VID membership, not queue-size growth;
- distinguish pre-call rejection, confirmed membership, and uncertain outcome;
- issue at most one queue mutation for one request;
- fail closed on phase changes, stale actors, missing capabilities, and ambiguous outcomes;
- preserve the real Windows cursor, focus, and OS mouse-button state;
- preserve unrelated scanner, radar, Boss Sweep, Reaction, Duel, Twin Souls, UI, launcher, and updater work.

This is an implementation plan, not authorization to edit, build, inject, or live-test the client.

## 2. What is confirmed

### 2.1 Queue traffic

Verified on the 2026-10-16 game build:

- Queue-change packets contain the queue VID list plus state/count.
- They do not contain click coordinates, click method, raw mouse movement, or `pick_code`.
- `player+0xEC`/`pick_code` is local client state and is not serialized directly.
- The stock Python `player.MetinQueueAdd` binding reaches the low-level native queue add.
- The manual actor-click path adds extra local admission behavior before reaching the same low-level add: live actor resolution, native eligibility, duplicate handling, and a 500 ms same-VID debounce.

Implementation consequence: the first clean replacement should send only the queue request that the stock binding already represents. It must not add invented input telemetry around that request.

### 2.2 Input recorder traffic

Verified on the same build:

- The server can enable the input recorder and change its sample interval; a live transition from disabled/100 ms to enabled/40 ms was observed.
- The recorder can send logical cursor samples, click records, held-button state, and a dirty queue VID-list snapshot.
- Recorder click codes are separate from the queue packet.
- In background mode, code-0 cursor samples use the recorder's stored cursor pair.
- The current synthetic dispatch can produce a jumping/static logical cursor and effectively immediate down/up records.

What is not known:

- The server-side comparison or disconnect rule.
- Whether a click record is required for every queue mutation.
- Whether timing, target choice, queue transitions, injection, method-table patching, or account/session history contributes to the disconnect.

Implementation consequence: do not fabricate recorder records or tune them to look human. The recorder remains client-owned. If the minimal stock queue path is rejected in a controlled test, stop and collect evidence instead of inventing another recorder pattern.

### 2.3 Raw input

The follow-up raw-input trace supersedes the earlier raw-mouse hypothesis:

- `WM_INPUT` mouse deltas are consumed locally by the camera/cursor path.
- The recorder tick and flush do not read that accumulator.
- Raw mouse deltas are not uploaded.
- Raw keyboard state is also a local input table in the traced path.

Implementation consequence: Hunter must not emulate or validate raw mouse activity. Raw-input work is out of scope for the replacement and for disconnect testing.

### 2.4 What repeated testing already ruled out as an individual cure

Do not reintroduce any of these as a supposed fix:

- direct low-level queue insertion;
- the higher internal mouse-state route;
- picked-actor override at `manager+0xE0`;
- camera rotation or forcing a target on screen;
- rejecting offscreen coordinates alone;
- adding synthetic recorder down/up records;
- arbitrary movement samples, coordinate jitter, or human-like sleeps;
- changing only the average add cadence;
- treating one long/stable run as proof of server acceptance.

The repeated remote disconnect remains correlated with sustained automated Hunter operation. The server reason is not present in the client logs.

## 3. Baseline and repository protection

Before implementation:

1. Record `git status --short --branch`, HEAD, branch, and all staged/unstaged/untracked files.
2. Preserve these known unrelated items currently present in the feature repository:
   - `.runtime/yin-yang-duel/yin_yang_duel_history.jsonl`
   - `ReactionTimingRecorder/`
   - `ReactionTimingRecorder.Tests/`
   - `docs/ui-proposals-20261016/`
   - untracked recovery handovers
3. Create a dedicated implementation branch/worktree only when the user authorizes implementation.
4. Record hashes of `client_feature.py`, `python_loader.cpp`, and the target game executable.
5. Confirm the game executable still matches SHA-256 `8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0`. If it does not, stop: all native RVAs and struct offsets require re-verification.
6. Do not commit, push, inject, or run the game as part of removal or local implementation unless separately requested.

## 4. Preserve only the Hunter UI shell

Keep the existing native UI elements and layout:

- `hunter_title`
- `hunter_button`
- `hunter_label`
- the existing farming card and callback location

During removal, temporarily connect the button to a stub that leaves it OFF and reports `Queue: rebuilding` or `Queue: unavailable`. This creates a hard boundary: after the removal commit/checkpoint, pressing the button cannot reach any old Hunter behavior.

Do not redesign the compact-tab UI, replace native widgets, or change scanner/radar geometry.

## 5. Complete removal inventory

Removal is complete only when a repository-wide search proves that no old Hunter behavior remains reachable.

### 5.1 Remove from `client_feature.py`

Delete or replace all Hunter-specific behavior, including:

- `HUNTER_LIMIT`, burst/refill timing constants, and priority-Metin constants;
- `QueueAddRejected` and `_queue_add`;
- old Hunter state such as `hunter_queued_vids`, `hunter_logged_rejections`, `hunter_initial_fill`, `hunter_batch_add_count`, `hunter_refilling`, `hunter_next_refill`, and `hunter_next_add`;
- `_dispatch_native_add`, `ScheduleHunterRefill`, and `FeedMetinQueue`;
- the existing `ToggleMetinHunter` body;
- Legendary/priority Metin queue replacement logic: `StartPriorityEventMetin`, `FinishPriorityEventMetin`, `HandlePriorityEventMetin`, and its state;
- Hunter-specific error/retry/status paths;
- Hunter candidate feeding from `Scan` while preserving scanner/radar discovery;
- config serialization or autoload fields that start/restore Hunter, if present;
- stale tests that assert old batch, refill, jitter, priority, projection, picker, or wrapper behavior.

`hunter_initial_fill` and `hunter_batch_add_count` are especially important removal targets: current code assigns them repeatedly but they are not meaningful state for the clean design.

### 5.2 Remove cross-feature Hunter coupling

Refactor the following so other features do not retain dead Hunter state:

- Reaction pause/resume must no longer save or restore `hunter_enabled` through old fields.
- Boss pause/restore must no longer mutate old Hunter queues or refill timers.
- gameplay phase transitions, Stop, and cleanup must call the new controller interface or the temporary stub, not old Hunter methods.
- `HasActiveNativeAutomation` must not report removed Hunter state.
- scanner `Scan` must continue updating radar/log output without automatically feeding the queue until the replacement controller is connected.

Preserve the broader rule already learned from Reaction: stopping Python updates alone does not stop an active native queue. The new controller must explicitly own and release only the queue state it created.

### 5.3 Remove or isolate the native wrapper in `python_loader.cpp`

The current method-table interception is part of the old Hunter design. Remove Hunter use of:

- `InstallNativeMetinQueueWrapper` / `RestoreNativeMetinQueueWrapper`;
- replacement of the stock `player.MetinQueueAdd` method entry;
- `NativeMetinQueueAdd` / `NativeMetinQueueAddInner`;
- picked-actor override at `manager+0xE0`;
- Hunter projection, viewport, click dispatch, and Hunter-specific native logs;
- `vid == 0` as a special `MetinQueueAdd` sentinel;
- the `_lirin_native_queue_wrapper` capability and corresponding Python gate.

Before deleting shared code, inventory every non-Hunter caller. Current code also couples `emit_synthetic_click()` and some Boss/minigame behavior to the patched binding. Separate those dependencies first so removal does not silently break another feature. No other feature should continue to call a queue API merely to emit recorder telemetry.

The loader should finish this phase without altering the stock `player.MetinQueueAdd` entry.

### 5.4 Removal checkpoint

At the end of removal:

- the Hunter UI button exists but cannot mutate queue state;
- scanner/radar still work;
- no old Hunter timer, retry, priority, projection, picker override, recorder fabrication, or native wrapper is reachable;
- the stock `player.MetinQueueAdd` method pointer is untouched by the loader;
- Boss/Reaction/minigames pass their own regression tests;
- repository-wide searches for removed names are empty except documentation/test-history references.

Create this checkpoint before writing the new controller. It prevents accidental reuse of old behavior under new names.

## 6. Replacement architecture

Use three narrow components with explicit ownership.

### 6.1 `HunterController` - lifecycle only

Responsibilities:

- states: `OFF`, `STARTING`, `RUNNING`, `WAITING`, `STOPPING`, `ERROR`;
- respond to the existing UI button;
- own pending requested VIDs;
- request at most one queue mutation at a time;
- stop on phase loss, queue disablement, Stop, Boss ownership, or Reaction safety pause;
- update the existing status label;
- never call recorder/raw-input functions.

The controller must not contain projection, cursor, camera, synthetic-click, or OS-input code.

### 6.2 `HunterCandidateSelector` - read-only target selection

Consume the scanner's existing snapshot rather than rescanning the same actor repeatedly.

Required selection checks:

1. positive VID from the current scanner snapshot;
2. confirmed Metin race from `nonplayer.IsMonsterStone(vnum)`;
3. current distance within the configured radius/anchor circle;
4. not already confirmed queued or pending;
5. immediately before dispatch, one lightweight live revalidation:
   - actor still resolves;
   - `chr.IsStone(vid)` when available;
   - queue admission guard does not report immune/untargetable;
   - `player.CanAttackInstance(vid)` when available.

Do not repeat name, race, distance, and position calculations multiple times in the same update. The snapshot owns discovery data; the final live check only protects against despawn/state change.

Selection order must be deterministic in the first version (nearest eligible, then VID as tie-breaker). Do not use random target choice or priority-Metin queue cancellation in the baseline. Those add behavior without being required by the queue contract.

### 6.3 `QueueGateway` - one mutation and authoritative observation

The baseline gateway must:

1. verify game phase and queue enabled state;
2. capture an authoritative queue snapshot or requested-VID membership before the request;
3. if the VID is already present, return `ALREADY_PRESENT` without calling add;
4. call the unmodified stock `player.MetinQueueAdd(vid)` exactly once;
5. reconcile the requested VID against authoritative queue membership with bounded, non-blocking polls;
6. return one of:
   - `ADDED`: requested VID became present;
   - `ALREADY_PRESENT`: present before mutation, no call issued;
   - `REJECTED`: failure was certain before the mutation;
   - `UNKNOWN`: the call may have executed but requested membership was not confirmed before timeout;
   - `CANCELLED`: phase/owner changed before dispatch.

Queue size growth is diagnostic context only. It must never turn another VID's insertion/removal into success for the requested VID.

If Python exposes no authoritative VID-list/member API, add a read-only native queue-inspection capability. It must not:

- replace `player.MetinQueueAdd`;
- mutate the queue;
- call dispatch/input/recorder code;
- write picked-actor or mouse state;
- infer membership from size.

Expose it under a separate, clearly named capability rather than changing the stock add binding's return contract. Validate queue vector bounds before reading. If that read-only capability is unavailable or invalid, Hunter stays unavailable rather than falling back to size-based acknowledgement.

## 7. Queue lifecycle and ownership

### Start

1. Require gameplay phase 5, scanner running, and no competing queue owner.
2. Read the current queue enabled state and membership snapshot.
3. Do not clear a pre-existing/manual queue.
4. Enable the queue only if Hunter needs it and record that Hunter changed it.
5. Set button ON only after prerequisites succeed.

### Running

1. Reconcile the pending VID before selecting a new one.
2. Never have more than one ambiguous request.
3. Add only when capacity is available.
4. On `UNKNOWN`, retain VID identity and wait for reconciliation; do not immediately retry.
5. On `REJECTED`, wait for the next normal scan; do not invoke an alternate route.
6. Do not use random jitter as a safety mechanism. Use a simple bounded control interval intended only to avoid duplicate calls and keep UI responsive.

### Stop/pause

1. Cancel pre-dispatch requests.
2. Do not undo a request that may already have executed.
3. Clear/disable only Hunter-owned queue state; never clear a queue that existed before Hunter or is currently owned by Boss/manual play.
4. Restore queue enabled state only when ownership and phase are still valid.
5. Update the button and label even if cleanup encounters an exception.

### Boss and Reaction integration

Use an explicit queue-owner coordinator (`NONE`, `MANUAL`, `HUNTER`, `BOSS`) rather than scattered saved booleans.

- Boss requests ownership; Hunter pauses and releases only its owned state.
- Reaction safety pauses all active native automation, captures controller state, and resumes only after authoritative gameplay/queue checks.
- Hidden/minimized UI must not alter ownership semantics.

## 8. Input handling policy

The new baseline has no Hunter input adapter. It calls the stock queue binding and leaves the recorder under client control.

Explicit prohibitions:

- no Windows messages;
- no OS cursor movement;
- no focus stealing or focus-flag forcing;
- no OS button-state changes;
- no raw mouse/keyboard fabrication;
- no direct calls to recorder `record_input`;
- no invented code-0 movement path;
- no artificial down/up duration or coordinate jitter;
- no picked-actor override;
- no camera rotation to make an offscreen target clickable;
- no fallback from one dispatch method to another after an uncertain call.

This is both simpler and evidence-correct: queue packets do not need those fields, raw mouse is local only, and the server-side recorder rule is unknown.

If the minimal stock path still disconnects, that does not authorize adding fake input. It means the experiment failed and the cause remains automation/policy, queue-transition behavior, injection/patching, or another unknown.

## 9. Logging

Log enough to reconstruct state without producing high-volume telemetry:

- build identity, feature version, and whether the stock binding is untouched;
- Hunter lifecycle and queue-owner transitions;
- request id, requested VID, pre-membership, post-membership, and result class;
- phase generation and cancellation reason;
- queue size only as supporting context;
- recorder enabled/sample interval as observation only, if already safely available;
- disconnect observation and source log path.

Do not log synthetic input traces because the replacement does not generate them. Do not infer exact causal ordering across Python, loader, and native logs unless their clocks/buffering are verified.

## 10. Tests required before any live run

### 10.1 Removal tests

- UI button/card/status still construct in the native UI.
- Button stub performs no queue call.
- Scanner/radar continue updating.
- Stop and phase-loss paths do not reference removed fields.
- Boss, Reaction, Duel, and Twin Souls regression tests pass.
- Loader test proves the stock `MetinQueueAdd` method pointer is unchanged.

### 10.2 Controller unit tests

- OFF -> STARTING -> RUNNING and RUNNING -> STOPPING -> OFF.
- start rejected outside gameplay phase or without membership capability.
- only one request can be pending.
- same VID is not dispatched twice while pending or already present.
- unrelated queue-size growth is not success.
- requested membership is success even if total size is unchanged.
- exception after mutation becomes `UNKNOWN`, not `REJECTED`.
- `UNKNOWN` is reconciled before any retry.
- phase change cancels only pre-dispatch work.
- Stop does not clear/disable manual or Boss-owned queue state.
- stale/disappeared actor fails the final live check without a queue call.
- scanner snapshot avoids duplicated race/distance work.

### 10.3 Native read-only capability tests

- validates player singleton and queue vector bounds;
- returns exact requested-VID membership;
- performs no writes;
- does not install/replace a method-table entry;
- fails closed on wrong executable hash or changed layout;
- survives empty/full queues and phase transitions without access faults.

### 10.4 Local gates

- Python 2.7-compatible syntax/ASCII check;
- full local mock suite;
- focused native tests where available;
- `git diff --check`;
- `build.ps1 -FeatureOnly` only after code review and authorization;
- verify the produced DLL hash and embedded feature version;
- review every changed file and confirm unrelated dirty files remain untouched.

Local success proves only internal behavior. It does not prove server acceptance or resolution of the disconnect.

## 11. Controlled live-validation ladder

The user performs all live injection/testing. Use a fresh game process for every stage and change one factor at a time.

### Gate A - no-Hunter control

- Build with Hunter removed/stubbed.
- Inject with every automation mode OFF.
- Use the queue manually for 15-20 minutes under comparable conditions.

Interpretation:

- disconnect: investigate injection/loader/method changes before Hunter;
- stable: proceed to the minimal replacement.

### Gate B - discovery only

- New Hunter controller ON in observe-only mode.
- Select/log candidates but issue no queue calls.
- Run for the same comparison window.

Disconnect here implicates injection/controller-side behavior rather than queue mutation.

### Gate C - one requested VID

- Permit exactly one stock queue add.
- Confirm requested-VID membership.
- Stop automatic additions and observe for the comparison window.

### Gate D - bounded operation

- Permit one request at a time with a small fixed capacity.
- No priority replacement, camera, projection, recorder calls, or alternate route.
- Stop immediately on first remote disconnect or state invariant failure.

### Gate E - intended continuous operation

Only after A-D are stable, test the intended queue capacity and refill behavior. A single stable run is not sufficient; record multiple comparable runs and a manual control. Do not claim a cure without repeated evidence.

For every stage, preserve:

- exact source commit/diff and feature version;
- DLL SHA-256 and game EXE SHA-256;
- PID and fresh-process confirmation;
- automation toggles;
- feature, loader, and native log copies;
- requested VID outcomes and queue ownership transitions;
- wall-clock start/end and remote-disconnect evidence.

## 12. Stop conditions

Stop implementation/testing and investigate before proceeding if:

- target executable identity changed;
- stock `MetinQueueAdd` is still patched after the removal checkpoint;
- requested-VID membership cannot be observed authoritatively;
- a call can execute twice through fallback/retry;
- an unknown result is recorded as success;
- manual/Boss queue state is cleared by Hunter;
- a remote disconnect occurs;
- logs cannot identify the exact build/runtime;
- a proposed change depends on guessing the server's anti-bot rule.

## 13. Definition of done

Implementation is complete only when:

- old Hunter code and native wrapper behavior are absent and unreachable;
- the existing UI button controls only the new controller;
- queue mutation is one stock call per request;
- authoritative requested-VID membership drives acknowledgement;
- no raw-input, camera, cursor, picker-override, or recorder fabrication exists;
- queue ownership is explicit and safe across Stop, phase change, Boss, and Reaction;
- all local gates pass with unrelated files preserved;
- live stages are documented separately as observed evidence;
- no document claims the disconnect is fixed unless repeated controlled runs support that conclusion.

## 14. Sources and precedence

Use sources in this order when they conflict:

1. `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\RESULT_REPORT_RAW_MOUSE.md`
   - final answer on raw mouse; supersedes the earlier possible-audit interpretation.
2. `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\docs\RAW_MOUSE_ACCUMULATOR.md`
   - detailed raw-input consumer trace and local camera/cursor conclusion.
3. `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\docs\NATIVE_QUEUE_RECORDER_FINDINGS.md`
   - current-build queue packet, recorder, pick state, audit trigger, and timing findings; read its correction banner first.
4. `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\RESULT_REPORT.md`
   - relocation/decompilation summary; its raw-mouse suspicion is superseded by sources 1-2.
5. `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\handovers\HANDOVER_DISCONNECT_RESOLUTION.md`
   - disconnect sessions, ruled-out variants, current wrapper comparison, and testing cautions.
6. `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\INPUT_RECORDER_BACKGROUND_PATH_PHASE1.md`
   - physical click chain and coordinate-pure dispatch evidence; older-build addresses require current-build mapping.
7. `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\INPUT_RECORDER_LOGOUT_REVIEW.md`
   - recorder behavior and live audit transition; its suggestions to fabricate movement/timing are historical hypotheses and are not approved by this plan.
8. `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\handovers\HANDOVER_HUNTER_LOGOUT_V35.md`
   - pre-update controlled logout evidence and rejected approaches.
9. Current source at implementation time:
   - `client_feature.py`
   - `python_loader.cpp`
   - `test_client_feature_local.py`

Supporting decompiled evidence:

- `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\native_traces\queue\`
- `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\native_traces\recorder\`
- `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\native_traces\dispatch\`
- `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\native_traces\rawinput\`
- `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\native_traces\index.md`
- `C:\Users\andrej-pc\Documents\projects\lirin-client-recovery\recovered_index\native_relocation_map.csv`

Historical evidence directories:

- `C:\Users\andrej-pc\Documents\projects\decomp\logout_pid34524_20261016\`
- `C:\Users\andrej-pc\Documents\projects\decomp\logout_pid30016_20261016\`
- `C:\Users\andrej-pc\Documents\projects\decomp\logout_pid33072_20261016\`

## 15. Handoff instruction

The implementing chat should first read this entire plan and the first five precedence sources, then inspect current Git state and source before editing. Implement the removal checkpoint separately from the replacement. Do not reuse old Hunter functions for convenience, and do not perform live injection or testing without explicit user authorization.
