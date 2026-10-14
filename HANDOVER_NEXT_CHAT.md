# Lirin Client Feature - Continuation Handover

Updated: 2026-10-14 after implementing and building the v26 native-wrapper fix

## Current continuation brief - read before the historical sections

The user requests investigation and a fix for repeated Hunter logouts. Current
Python source is v26. V25 restored the requested continuous refill behavior
and added partial actor checks, but its live test still disconnected during
sustained Hunter operation. Native comparison then verified the remaining
structural defect: Python `player.MetinQueueAdd` called low-level insertion
directly, bypassing the complete native actor-click wrapper used by a manual
click. V26 changes the loader to redirect that binding through the exact
native wrapper, adds an on-screen projection guard, and fails closed if the
wrapper is unavailable. The v26 loader is built and local tests pass, but it
has not been injected or live-tested. Do not revert to the rejected one-shot
or repeated 8-15 second batch behavior.

### Required Hunter behavior

- Continuous farming with an initial queue of up to five eligible stones.
- Replenish before the queue empties, at one to three entries remaining, with
  greater probability as it shrinks and guaranteed replenishment at one entry
  when an eligible candidate exists. This was the user's earlier requirement.
- The current v23/v24 behavior (finish a batch, then wait 8-15 seconds every
  time) is explicitly unwanted. Do not keep it as the final fix.
- The user would accept an occasional random 5-15 second pause approximately
  once per random 30-60 minute interval. This is a preference, not implemented,
  and must not be presented as a proven fix or a way to defeat enforcement.
- Investigate the actual fault before guessing additional delay values.
- Preserve Auto Reaction behavior. Do not tune it during this investigation.

### Latest controlled live evidence

V25 fresh-client PID 620; Auto Reaction and Boss Sweep OFF:

1. Scanner started at 20:34:20.823 and Hunter started at 20:34:22.934.
   Continuous paced queue additions proceeded without any logged actor-type,
   immune, untargetable, or low-level queue rejection.
2. A Reaction Game was detected at 20:39:32.286. With Auto Reaction OFF, the
   feature paused native automation. The user solved it manually; closure was
   observed at 20:48:47.122 and the 554.9-second pause ended at 20:48:47.124.
3. Hunter restored from queue size zero and resumed continuous paced adds. Its
   last add was at 20:52:00.303: VID 21172175, distance 2314, queue 3->4/5.
4. The Python `net.Disconnect` observer fired with no arguments and no Python
   caller frames at 20:52:07.529. Registration of `NewLoginWindow` stopped
   automation in the same millisecond. Empty Python stack is consistent with a
   call entering from compiled/native code, but does not identify its cause.
5. The game log records `Remote disconnected from game.lirin.to:11035` at
   20:52:56.854, 49.325 seconds later than the feature's login transition.
   Preserve this cross-log discrepancy; ordering/cause is unresolved.
6. Excluding the reaction pause, Hunter had accumulated approximately 8 minutes
   30 seconds of active operation when the feature observed the login exit.
   The user confirmed the logout.

Conclusion: v25's exact `chr.IsStone` guard and observed VID-exclusion filters
did not cure the repeated logout. They remain valid safety fixes, but no guard
rejection was exercised in this run. Sustained low-level Hunter queue activity
remains associated with the failure; causation and whether the relevant defect
is client-state, cadence, a native-only admission rule, or server policy remain
unverified. Investigate the feature/game timestamp split and the compiled call
that invokes `net.Disconnect` before another behavioral change.

Same fresh client PID 29916, v24; Auto Reaction and Boss Sweep OFF:

1. Injection at 19:13:21, no Start: user reported 15 minutes without logout;
   loader reports successful execution and snapshot worker start.
2. Scanner Start 19:29:19; scanning through at least 19:56:06 without logout,
   over 26 minutes. No Hunter or Reaction actions during this stage.
3. Hunter ON 19:56:41, Stop 19:57:28, restarted 19:57:41.
4. Repeated paced batches mostly added three entries, occasionally four, with
   approximately 50-70 second cycles. Adds were about 1-2 seconds apart and
   admission distances included 2396 and 2486 within radius 2500.
5. Game log: `1014 20:04:01350 :: Remote disconnected from game.lirin.to:11035`.
   This is 20:04:01.350, about 6 minutes 20 seconds after the uninterrupted
   Hunter restart, and about 51 minutes after injection.
6. Add at 20:04:01: VID 20721050, distance 1240. Another add was logged at
   20:04:03: VID 20717281, distance 1985. Last batch emptied at 20:04:43.
   Login UI registration stopped automation at 20:04:47.
7. No Reaction/Boss event or server reason was logged. Loader has an untimed
   `snapshot: atomic replace failed` entry; its timing/cause is unknown.

Interpretation: strong within-session association with sustained automated
queue activity. The same-second add and close have no proven causal order
because feature logs have only whole seconds. The previous assistant
overstated that this isolated the cause or made enforcement the strongest
explanation. Neither a native-state defect nor server policy nor intermittent
network failure has been proved. V24 safety changes did not cure Hunter logout.

Other useful controls: v22 admitted two stones once, shut Hunter down, and
scanner continued from injection 00:30:42 through 00:54:53 without logout.
This does NOT demonstrate five-stone one-shot safety or sustained Hunter safety.
At 08:38, v23 scanner-only disconnected seconds after Start; Hunter was never
enabled. Keep this counterexample in the diagnosis rather than explaining all
events solely through Hunter. User reports ordinary uninjected/manual play
does not log out, and manually clicking stones repeatedly into a five-slot
native queue works. This manual baseline is user-reported, not instrumented.

### Verified native paths - do not rediscover the completed work

Addresses refer to copied `decomp\input\LirinGame.exe`; check build identity
before applying them to another EXE.

- Python `MetinQueueAdd` 0x1403f6360 -> low-level add 0x1403e41a0.
  Native callers: 0x1403e5660, 0x1403e8090, 0x1403ebdd0. Native input paths
  resolve an actor, use eligibility predicate 0x1403e31f0, handle an existing
  queue entry separately, and implement 500ms same-VID debounce. The Python
  binding bypasses those wrapper checks. `CanAttackInstance` is only an
  approximation, not the full queue eligibility predicate.
- The normal actor-click wrapper is 0x1403ebdd0 with effective signature
  `(player, main_actor, vid, flag)`. The ordinary left-button path supplies the
  main actor from 0x1403d1da0 and flag zero. It requires queue mode zero, a live
  actor, predicate 0x1403e31f0, a zero application-state float, and a 500 ms
  same-VID debounce before low-level insertion; it also handles duplicates.
- `chr.GetProjectPosition` at 0x140528aa0 exposes live-actor screen projection.
  V26 combines it with `wndMgr.GetScreenWidth/Height` to reject off-screen
  candidates. This approximates the preceding manual screen-pick gate; it does
  not prove that the actor is unoccluded beneath a particular cursor pixel.
- Queue processor 0x1403e4400, called from player update 0x1403d5940.
- Clear 0x1403f63b0 -> 0x1403e4300. Add/clear update queue state/count through
  0x140243ac0 -> serializer 0x14022e4a0 when native phase byte +0x199 equals 5.
  Dirty helper 0x1404710d0 sets manager +0x90; it is not an unknown packet send.
- SetEnabled 0x1403f6580 writes player +0x457c; true-to-false already clears.
- ClearTarget 0x1403f1a50 -> 0x1403e8570(VID=0, force=1) -> conditional target
  send 0x14037ac80 -> serializer 0x1403446d0. Native queue clear can also
  reset a queued current target through 0x1403eb4b0.
- Serializers require transport +0x58; successful writes append buffered bytes
  via 0x145983080 -> 0x145987ee0. This is not proof of OS/server receipt.
- IsConnect binding 0x14038e200 -> 0x14060e280 simply tests socket +0x48 != -1.
  It does not check peer health. V18 polling cannot close every stale interval.
- SetPhaseWindow binding 0x14039f070 -> 0x140244030 stores a Python UI pointer
  at network +0x2a0 + 8*index (indices <7). It does not set native phase +0x199.
  Phase5 replays deferred UI callbacks; phase1 is just registration. Python
  None remains Py_None; feature v24 ignores those unregister notifications.
- MainStream.SetLoginPhase 0x1419337e0 calls net.Disconnect before constructing
  NewLoginWindow; its constructor 0x1419c3d40 registers login index1.
  Disconnect 0x14038d850 -> 0x140243f10 (native phase0/callback reset) ->
  0x14060caa0 (socket -1 and transport teardown 0x145982040, transport null).
  Normal login registration cleanup therefore happens after teardown.
- Scanner getter downstream paths were checked: actor race/name, character
  tree/database lookup, actor position 0x1404a2ec0 -> 0x140862130, and player
  position 0x1403d1d50. Position access copies a scratch/cache coordinate value;
  no movement, target, attack, or network send was found in these paths.

### Implemented v24-v26 fixes and remaining risks

Verified local fixes: loader removes its successful one-shot WH_CALLWNDPROC
hook; phase observer ignores None and logs UI registration accurately; terminal
and socket handling no longer clear twice; queue shutdown relies on the native
disable clear once; scanner-only Stop/exit preserves unowned manual queue and
target state. Existing local tests and C++ build passed. No live injection was
performed by the assistant. Users injected and ran the controlled tests.

V25 native comparison verified that predicate 0x1403e31f0 accepts a Metin only
when its live actor passes 0x1404a09b0 (`chr.IsStone`) and its VID is absent
from the global untargetable set tested by 0x1403d0860. `CanAttackInstance`
does not implement this predicate. Hunter now rechecks `chr.IsStone`, observes
the Python `SetMetinQueueVIDImmune` and `SetMetinQueueVIDUntargetable` setters,
and rejects observed excluded VIDs before `MetinQueueAdd`. It restores the
continuous 35/70/100 percent refill policy at queue sizes 3/2/1, with a
guaranteed refill at zero, while retaining 0.65-1.45 second add spacing.
Queue logs now have millisecond timestamps, pre/post sizes, and call duration;
Python `net.Disconnect` calls log a bounded caller stack. The full local mock,
ASCII compile, and diff check passed. V25 was live-tested and still
disconnected as recorded above.

V26 patches the exact-build `player.MetinQueueAdd` method-table entry so the
existing Python call enters native wrapper 0x1403ebdd0 on the game window
thread, using the native player singleton and main actor with normal-click flag
zero. The shim returns success only when queue size increases. Hunter and Boss
Sweep refuse to start if the original binding did not match and the redirect
could not be installed. Hunter additionally rejects candidates whose
`chr.GetProjectPosition` lies outside the client screen. Local mock tests,
ASCII parsing, `git diff --check`, the feature DLL build, and the non-feature
window-loader build pass. Built `client_feature_loader.dll` is 144,384 bytes,
SHA-256 `330E1C30B6223BBB6D92399AE029C291B7FC751BE5EF14B14D97E42CBA27AEEB`.
No live v26 injection has occurred.

The observed exclusion sets are deliberately conservative but incomplete:
state already present before injection and state changed only by native calls
cannot be recovered through these Python wrappers. Conversely, a native reset
can leave a stale observed exclusion, which may skip a valid VID but does not
admit an excluded one. The exact native actor check is complete for the Metin
branch. This verified mismatch is a concrete defect, not proof that it caused
the 20:04 remote close.

Remaining risks to review, not confirmed causes:

- User-proposed hypothesis: a dummy/bait Metin entity could be classified as a
  stone yet be hidden or non-interactive. V26 now routes admission through the
  full native actor-click predicate and rejects off-screen projections, but
  projection is not an exact occlusion/cursor-pick test. There is no evidence
  that this server deliberately creates bait entities.
- Native snapshot worker traverses the entity tree without synchronization or
  lifetime protection. SEH catches faults, not inconsistent reads.
- FindRuntimeObject processes up to 10000 objects but can accumulate many more
  references; full collections are materialized before slicing and fallback
  gc.get_objects is unbounded. Discovery runs with Auto Reaction OFF before
  scanner Start. Changes affecting reaction discovery need explicit attention
  to the user's Auto Reaction boundary; do not silently tune it.
- Marker writes are non-atomic and snapshot writers share .tmp ownership on
  reinjection/multiple clients. Fresh PID29916 had only one injection.
- HasActiveNativeAutomation uses mode state, not full per-resource ownership;
  reaction safety intentionally pauses the native queue even with solver OFF.
- SetPhaseWindow remains a conservative UI lifecycle hint, not authoritative
  phase telemetry. Do not assume its name proves a socket transition.

### Concrete next work

Read the required files below and preserve the worktree. The manual-versus-
Python queue comparison is now complete enough for the bounded v26 test.
Separately, the original event entering MainStream.SetLoginPhase and the code
emitting remote-close logs remain unidentified. Plain `Remote disconnected
from` string search in the copied EXE did not locate the message; existing code
may use encoded strings.

Use `scan_metin_queue_calls.py`, `disassemble_metin_callers.py`, workspace-local
`analysis_deps` (Capstone), existing Ghidra project/scripts, and recovered C.
Relevant helpers also include `run_queue_trace.py`,
`ghidra_scripts/TraceMetinQueuePath.py`, and `queue_trace_scripts`.
Do not assume a script's name means all downstream paths are already decoded.

V25 now logs Python `net.Disconnect` caller stacks, queue pre/post state and
duration, and millisecond timestamps. Native calls may bypass Python hooks;
raw TCP capture can distinguish FIN/RST/timeout but may reveal no server reason.
Avoid a broad intrusive packet hook until its necessity and method are clear.

The next bounded test is a clean v26 Hunter-only run: fresh game process,
Auto Reaction OFF, Boss Sweep OFF, Start, then Hunter ON for 15 minutes. Record
the feature log and game log without changing other modes. This exceeds the
previous uninterrupted v24 failure interval of about 6 minutes 20 seconds.
Do not claim success from immediate responsiveness; compare every queue add and
any rejection or Python disconnect record against the millisecond remote-close
time. The optional rare 5-15 second pause remains unimplemented and separate
from this defect test. A fresh process is required because an already injected
DLL leaves its method pointer in process memory and a later loader deliberately
refuses to overwrite an unexpected binding. No live injection, commit, or push
is currently requested.

Current modified tracked files to preserve:
`HANDOVER_NEXT_CHAT.md`, `README.md`, `TEST_RESULTS.md`, `client_feature.py`,
`python_loader.cpp`, `test_client_feature_local.py`. Earlier v21-v24 changes
remain uncommitted; check git status/diff rather than replacing with HEAD.
Launcher remains usable at `LirinFeatureLauncher\bin\Release\net8.0-windows`;
it invokes the repository runner and rebuilt loader. For new loader behavior,
fully restart the game before injection so old injected DLLs cannot remain.

The older sections below retain useful historical material. This continuation
brief supersedes their stale task descriptions, working-tree lists, live-version
claims, and hypothesis rankings.

This is the current continuation handover for a new chat. The first task is to
investigate the repeated game-server disconnects by tracing this feature's code
and the already unpacked/decompiled client functions. Do not start by injecting
again or by changing Auto Reaction.

## 1. Read this first

Work in:

`C:\Users\andrej-pc\Documents\projects\lirin-client-feature`

The decompilation/reference tree is:

`C:\Users\andrej-pc\Documents\projects\decomp`

Before changing anything, read these files completely:

1. `HANDOVER_NEXT_CHAT.md` (this file)
2. `HANDOVER_FEATURE.md`
3. `HANDOVER_INJECTOR_UI.md`
4. `TEST_RESULTS.md`
5. `README.md`
6. `client_feature.py`
7. `test_client_feature_local.py`
8. `run_client_feature.ps1`
9. `inject.py`
10. `python_loader.cpp`
11. `C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\metin_queue_bindings.c`
12. `C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\metin_feature_apis.c`

Preserve all existing user changes. Do not commit or push unless the user asks.

## 2. First task for the new chat

Perform a read-only source/decompilation investigation of what could be causing
the remote logout. In particular:

- trace the native Metin queue add, clear, processing, target, movement, and
  attack paths;
- identify the two unknown calls made by native queue add/clear;
- trace `net.IsConnect`, the socket-disconnect path, phase changes, and any
  server error or popup path that might contain a reason not written to the log;
- look for unsafe timing, stale VIDs, excessive range, invalid state, packet
  cadence, or channel-transition interactions in our feature;
- distinguish a feature defect from ordinary connection loss or server-side
  enforcement. The present logs do not prove which one occurred;
- report a verified call graph and ranked candidate defects before making a
  behavioral change.

Do not perform another live injection until this read-only investigation and
the local non-injection checks pass. If code is changed, make the smallest
testable change and update `TEST_RESULTS.md` with exact evidence.

## 3. Evidence rules

Keep these categories separate:

- Verified: direct source/decompiler result, exact log line, local test result,
  or observed live behavior.
- Inference: a conclusion supported by evidence but not directly observed.
- Hypothesis: a possible explanation still needing a test.

Do not state that the feature caused the server to disconnect. The game log only
says that the remote peer disconnected. Also, a successful DLL load, immediate
in-game responsiveness, or process survival does not prove long-term/server
acceptance.

## 4. Current source and live-version state

The working source is now `FEATURE_VERSION = 26` in `client_feature.py`.
The default radius is 2500.

The latest source changes are local only:

- v14: gameplay phase guard around `net.SetPhaseWindow`; loading pauses work and
  terminal phases stop/clear automation.
- v15: separate Metin return anchor and exact marked-boss position; repeated
  return movement until arrival or timeout.
- v16: Save, Load, and Auto-load for static configuration.
- v17: local-map compass labels `N`, `S`, `E`, `W`, and default radius 2500.
- v18: 10 Hz `net.IsConnect()` guard; ordinary socket loss immediately stops
  and clears automation, while expected Boss Sweep channel-transition
  disconnects temporarily pause and preserve the sweep state.
- v19: live Metin revalidation and player-distance admission immediately before
  queue add; Stop/Hunter OFF now clear and disable native automation; rejected
  VIDs are not remembered; Boss Sweep removed the redundant pre-queue target.
- v20: activation fills the native Hunter queue to its capacity, up to five;
  later scans add at most one target with 35%/70%/100% chances at queue sizes
  3/2/1 (and 100% at zero), while sizes 4-5 receive no addition.
- v21: reaction-window safety detection remains active when Auto Reaction is
  OFF. A visible challenge clears/disables native automation and releases the
  target; OFF requires manual completion and ON retains automatic clicks.
  Hunter restores only after the window closes.
- v22: temporary one-shot Hunter diagnostic. Activation admits one initial
  batch of up to five targets, performs no replenishment, and clears/disables
  Hunter when that native queue becomes empty.
- v23: production-oriented safe batch cycling. Candidate admission adds the
  live `CanAttackInstance` guard used to approximate the native click wrapper,
  serializes adds by a random 0.65-1.45 seconds, never tops up an armed nonempty
  batch, and waits a random 8-15 seconds after zero before the next batch.
- v24: the successful loader unhooks `WH_CALLWNDPROC` after its one-shot Python
  execution because the snapshot writer is already independent. The Python
  observer now treats `net.SetPhaseWindow` as UI registration, ignores `None`
  unregister calls, removes duplicate terminal/socket cleanup, and preserves
  native queue/target state during scanner-only Stop/exit when no feature
  automation is active. Queue shutdown performs only one native clear instead
  of explicit clear followed by a disabling clear. Auto Reaction and Hunter
  batching are unchanged.
- v25: restores continuous refill at queue sizes 3/2/1/0 using
  35/70/100/100 percent admission chances, keeps paced additions, requires the
  live actor to pass `chr.IsStone`, and filters VIDs observed through the
  Python immune/untargetable setters. It also adds millisecond queue diagnostics
  and a bounded Python `net.Disconnect` caller stack. Local tests passed; v25
  was live-tested and still disconnected after approximately 8 minutes 30
  seconds of active Hunter time.
- v26: redirects the exact-build Python queue-add binding through the native
  manual actor-click wrapper, requires an on-screen actor projection, and
  disables Hunter/Boss Sweep if the redirect is unavailable. Local tests and
  both affected C++ loader builds pass; v26 has not been live-tested, and the
  disconnect cause remains unverified until that bounded test.

V20 was live-tested with Hunter and disconnected after about seven minutes.
V21 was live-tested with Hunter and disconnected again after about 3 minutes
20 seconds. No reaction window was detected during that run. The earlier v14
run remains the last live Boss Sweep test. The v20 panel was injected into PID
35200 at 23:04:12; Auto Reaction was
OFF at 23:05:34, Hunter started at 23:05:58, the feature observed phase 1 at
23:13:06, and the game log recorded a remote disconnect at 23:13:27. After
reconnecting, scanner-only operation exposed a visible Reaction Game while
Hunter, Boss Sweep, and Auto Reaction were OFF. This is evidence for the v21
safety fix, but it does not yet prove the challenge caused the disconnects.

`client_feature_loader.dll` exists in the feature repository and was rebuilt
for v24 on 2026-10-14 (142,848 bytes; SHA-256
`5C66BD62CC80800F635D0D9A45CEB8991900AE12EB32C5DC260AC4C5ACC9BF01`).
The local config currently enables auto-load with Auto Reaction OFF, radius
2500, and a saved CH6 `world/mount_sohan` anchor.

## 5. Exact disconnect evidence

### Historical disconnect: 2026-10-13 21:46

Runtime: live v14 in PID 48804.

- Auto Reaction was explicitly OFF at 21:33:29.
- Boss Sweep completed at 21:35:05.
- Metin Hunter then continued alone.
- The game log says:
  `1013 21:46:11712 :: Remote disconnected from game.lirin.to:11029`
- The feature still scanned/queued at 21:46:13 and 21:46:34 because the client
  remained in a stale game phase after the socket closed.
- At 21:46:34 the feature finally logged:
  `Automation stopped: client phase changed to 1`
- There was no preceding Python exception and no authoritative reason for the
  remote close.

Verified conclusion: v14 had an approximately 23-second post-disconnect window
in which it could act on stale world state. V18 adds `net.IsConnect()` polling,
but later native analysis confirms the handle check can itself remain stale. It
does not explain why the server closed the connection in the first place.

### Previous disconnect: 21:15

Runtime: live v12.

- Game log: `Remote disconnected from game.lirin.to:11005` at 21:15:41.
- Auto Reaction was OFF.
- Boss Sweep had been OFF since 21:08.
- Hunter alone was active from 21:11.
- The feature continued queueing stale targets at 21:15:45 and 21:16:20, then
  the user pressed Stop at 21:16:23.
- Again, no preceding reason or Python exception was logged.

### Other same-day remote disconnect records

The game log also contains remote disconnects at:

- 09:22:42, port 11029
- 12:54:55, port 11047
- 13:47:14, port 11029
- 13:51:49, port 11029
- 21:15:41, port 11005
- 21:46:11, port 11029

The 13:47 disconnect occurred before the known 13:50 Auto Reaction run, so the
reaction feature cannot explain every disconnect.

### Reaction timeline that must not be overinterpreted

At approximately 13:50:47 the reaction window appeared; the feature requested
start and clicked slots 5, 4, 1, 5, and 2. It closed at 13:50:49, a server
message appeared at 13:50:55, and a disconnect occurred at 13:51:49. This is a
timeline, not proof of causation.

## 6. Logs and artifacts

Feature repository:

- `metin_scanner.log`
- `python_window_loader.status.txt`
- `metin_entities.txt`
- `metin_entities.status.txt`
- `client_feature.py`
- `test_client_feature_local.py`

Game logs (latest evidence is in the 2026-10-14 file):

`C:\Program Files (x86)\Lirin\app\logs\13-10-2026.log`

`C:\Program Files (x86)\Lirin\app\logs\14-10-2026.log`

Relevant decompiled/reference material:

- `C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\metin_queue_bindings.c`
- `C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\metin_feature_apis.c`
- `C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\python_symbols_v5.txt`
- `C:\Users\andrej-pc\Documents\projects\decomp\decompiled_all\modules\networkmodule.c`
- `C:\Users\andrej-pc\Documents\projects\decomp\recovered_code\networkmodule_MainStream_SetPhaseWindow_1.c`
- `C:\Users\andrej-pc\Documents\projects\decomp\recovered_code\networkmodule_MainStream___ChangePhaseWindow_1.c`
- `C:\Users\andrej-pc\Documents\projects\decomp\recovered_code\networkmodule_MainStream_SetLoginPhase_1.c`
- `C:\Users\andrej-pc\Documents\projects\decomp\recovered_code\networkmodule_MainStream_SetGamePhase_1.c`
- the other `recovered_code\networkmodule_MainStream_*.c` phase/connect files

Useful symbol inventory entries already confirmed:

- `net.Disconnect`
- `net.IsConnect`
- `net.SetOfflinePhase`
- `net.SetPhaseWindow`

## 7. Native queue entry points already identified

From `metin_queue_bindings.c`:

- Python binding `player.MetinQueueAdd`: `0x1403f6360`
- native `CPythonPlayer.MetinQueueAdd`: `0x1403e41a0`
- native `CPythonPlayer.MetinQueueClear`: `0x1403e4300`

The recovered queue-add implementation appears to:

1. reject duplicates and enforce a capacity;
2. mark the entity;
3. append its VID and store a time value;
4. call
   `FUN_140243ac0(DAT_147a6b358, *(undefined1 *)(DAT_147a6b358 + 0x98))`;
5. call `FUN_1404710d0(DAT_147a6ba20)`.

Queue clear calls the same two unknown functions. The next investigation should
identify those functions and all callers/callees. Determine whether either
causes a packet, movement state reset, attack state change, UI refresh, or some
other state transition relevant to disconnects.

Also locate the periodic native queue processor: how it validates VIDs, chooses
targets, moves, attacks, removes missing/dead targets, and controls cadence.
Check whether the Python feature can mutate the queue while that processor is
iterating or during a loading/channel phase.

## 8. Specific candidate issues to evaluate

These are hypotheses, not findings:

1. Stale or vanished VID passed to the native queue during rapid entity changes.
2. A native queue call during an unplayable, loading, or partially disconnected
   state. V14 only reacted to the delayed phase change; v18 adds socket state.
3. Queue cadence or native movement/attack packets that the server considers
   invalid or too regular.
4. Targets admitted by anchor distance while currently far from the character.
   The feature intentionally filters eligibility against the fixed anchor, but
   logs `player_distance`. Prior logs included queued targets at approximately
   3043 and 3247 while radius was 2500 because the player had moved away from
   the anchor. Decide whether this is safe for the native queue.
5. Queue clear/add overlap with Boss Sweep channel transitions.
6. A problem in the injected window hook/feature loader independent of Hunter.
7. Ordinary network/server instability or server-side enforcement. There is no
   current evidence distinguishing these.

Do not simply add more guards until the call paths are understood. In
particular, v18's socket guard is a post-disconnect safety fix, not a confirmed
root-cause fix.

## 9. Current behavior and prior boss findings

Live v14 successfully swept channels CH5, 1, 2, 3, 4, 6, 7, and 8, created
one-target boss chase queues, and observed kill confirmations.

The then-current `MarkBoss` behavior overwrote the Metin anchor. The sweep
finished at 21:35:05 and claimed it was back at the anchor, but Hunter found no
stones until the user unanchored at 21:35:31. V15 fixes this locally by storing:

- `anchor_position`: Metin farming/return anchor;
- `boss_position`: exact selected boss position from `chr.GetPixelPosition`.

Mark Boss now preserves an existing Metin anchor. If none exists, it creates a
return anchor from the player's current position. This has passed the mock but
has not been live-tested.

The intended combined flow is:

1. Hunter destroys stones and fills/uses its queue.
2. A boss at the marked position interrupts and clears the Metin queue.
3. The character runs to and kills the boss.
4. Boss Sweep checks the other configured channels, then returns to the
   original channel and Metin anchor.
5. Hunter resumes stone farming.

## 10. Auto Reaction boundary

Do not change, extend, or tune Auto Reaction during the logout investigation.
Its native-queue and asynchronous-state concerns are already documented in the
older handover and tests.

Important live rule: Auto Reaction defaults ON when no saved configuration is
loaded. The general Stop button does not disable it. During the first live test
of any newly loaded panel, explicitly switch Auto Reaction OFF after the panel
appears and verify the log line before continuing.

If Auto Reaction is ever revisited separately, direct synchronous mocks are not
enough: exercise the complete `OnUpdate` path, visible window discovery,
asynchronous server state, active boss/native queues, window close, deadline
adjustment, and restoration.

## 11. Configuration behavior

`client_feature_config.txt` uses schema version `1` and stores:

- radius;
- Metin anchor, map, and channel;
- boss VNUM/name, exact boss position, map, and channel;
- Auto Reaction preference;
- Auto-load flag.

Load/Auto-load restores only settings. It must not auto-start scanner, Hunter,
Boss Sweep, attacks, or channel changes. The file is intentionally ignored by
Git. It is currently present with auto-load enabled and Auto Reaction OFF.

## 12. Current local verification

The latest local checks passed:

```powershell
python .\test_client_feature_local.py
```

Expected summary:

`Local map, safe hunter queue, boss flow, config persistence, reaction, hotkey, and gameplay-exit guard: OK`

Use an in-memory ASCII compile because `__pycache__` was once locked:

```powershell
python -c "from pathlib import Path; [compile(Path(p).read_text(encoding='ascii'), p, 'exec') for p in ('client_feature.py','test_client_feature_local.py')]; print('ASCII syntax compile: OK')"
```

Diff whitespace check:

```powershell
git diff --check -- .gitignore README.md TEST_RESULTS.md client_feature.py test_client_feature_local.py
```

CRLF warnings are expected on this Windows checkout. A prior direct
`python -m py_compile` failure was caused by a locked `__pycache__`, not a syntax
error.

## 13. Safe investigation and test sequence

Recommended order:

1. Read all files listed above.
2. Re-run the local mock, in-memory compile, and diff check.
3. Treat the native queue and disconnect call graphs as completed investigation.
4. Review the v19 queue-safety patch and its regression coverage.
5. Before any live injection, use one narrow test with exact start/end times.

A useful later A/B matrix, after code review, is:

1. Fresh client, no injection, 20-30 minutes of comparable manual activity.
2. Injection with Auto Reaction OFF, scanner only, Hunter OFF, Boss Sweep OFF.
3. Hunter only, Auto Reaction OFF, Boss Sweep OFF.
4. Boss flow only after earlier stages are stable.

Change one factor at a time. Record feature log, game log, channel, port,
feature version, and exact timestamp. Do not jump directly to combined modes.

## 14. Injector desktop UI status

The desktop launcher MVP is present in:

- `LirinFeatureLauncher\`
- `LirinFeatureLauncher.Tests\`

It is .NET 8 WinForms x64, requests administrator privileges, lists only the
exact 64-bit game path
`C:\Program Files (x86)\Lirin\app\Lirin.exe`, excludes the root 32-bit launcher,
preserves PID selection, invokes `run_client_feature.ps1`, streams stdout and
stderr, shows Ready/Injecting/Injected/Failed, and manages only one active
client because marker/snapshot/status/log files are shared.

The redesign is an 840x560 dark layout with 720x480 minimum size. Automated UI
logic tests passed 5/5 groups: filtering, selection preservation, arguments,
immediate process-exit races, and visible errors. The normal output EXE was
locked during one build, so the newest launcher was placed at:

`LirinFeatureLauncher\bin\Release\updated\LirinFeatureLauncher.exe`

This launcher work is not the first task for the next chat.

## 15. Working-tree state to preserve

At handover time, Git reported:

```text
 M .gitignore
 M README.md
 M TEST_RESULTS.md
 M client_feature.py
 M test_client_feature_local.py
?? HANDOVER_INJECTOR_UI.md
?? LirinFeatureLauncher.Tests/
?? LirinFeatureLauncher/
```

This handover is also new/untracked. `HANDOVER_INJECTOR_UI.md` predates this
handover work and must not be overwritten or deleted. Treat all unrelated and
uncommitted changes as user-owned.

## 16. Concise next deliverable

The read-only call-graph investigation and v19-v20 queue patches are complete. The
next useful deliverable should provide:

- a review of the v19-v20 diff and local test evidence;
- one controlled live-test plan, beginning with Auto Reaction OFF and no Boss
  Sweep;
- exact feature/game log timestamps and whether a disconnect occurs;
- no claim that v19 fixed the disconnect until that live evidence exists.
