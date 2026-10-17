# Hunter native recorder-pair experiment - V50

Date: 2026-10-18 (Europe/Bratislava).

This is the explicitly requested experiment of adding native recorder down/up snapshots around each stock Hunter queue-add attempt. It is OFF by default and is not a verified manual-click equivalent or a disconnect fix. The earlier comparison's NO SAFE IMPLEMENTATION YET verdict for a faithful background native-click replacement remains unchanged; the user subsequently requested this narrower experiment for testing.

## Exact behavior

When launched with `-RecorderPairExperiment`, startup reads the mode once. After existing fresh identity, membership and eligibility checks, the gateway calls the separate native experiment's `begin_queue_add(vid)`. If the recorder is enabled and its context is valid, that calls verified `FUN_140497840(recorder,1,x,y)`. The gateway rechecks identity/membership and calls untouched stock `player.MetinQueueAdd(vid)` at most once. A `finally` block calls `end_queue_add(vid)` once, which revalidates the paired context before calling the same producer with code 2.

Coordinates come from cached game coordinates when active or the recorder's stored logical coordinates when inactive, as in native periodic sampling. Both events use the coordinates captured at begin. No coordinates are projected onto the requested actor. The constructor reads real existing client/OS state; there is no picked-VID, held-button, UI, target or sample-field override. The requested VID is correlation metadata, not a claim that the recorder sampled that VID.

When recording is disabled, begin returns 0, creates no event and does not enable recording. The single stock queue call proceeds normally; no end call is needed. Thus enabling this experiment does not guarantee any recorder-event coverage: enabled intervals must be observed naturally.

Recorder calls use the client's normal sample constructor, append/compression and scheduled serialization. There is no direct packet construction, socket/serializer call, forced flush or duplicate queue notification. A full sample buffer can flush through the native producer's existing cap behavior.

## Source scope

- `client_feature.py`: FEATURE_VERSION 50; startup mode reader/import; optional gateway begin/end integration and bounded logging; controller halts further additions after a latched experiment error. Existing circular selection, refill timing, stock binding, requested-VID acknowledgement, ownership, UNKNOWN reconciliation and Stop/cleanup remain intact.
- `python_loader.cpp`: separate `_lirin_recorder_pair_experiment` module, independent of the unchanged read-only `_lirin_hunter_native` observer. The verified producer is RVA `0x00497840`; its four arguments follow the current exported caller/assembly contract. No stock method-table patch.
- `run_client_feature.ps1`: explicit `-RecorderPairExperiment` switch; runtime mode on/off file and metadata field; exact EXE SHA-256 gate when the experiment is requested. Default launch writes mode `off`.
- `test_hunter_recorder_pair.py`: offline tests using the actual extracted gateway/controller definitions and fake native boundaries.

No manual/Boss queue member is removed by the experiment. New additions halt on experimental faults; existing native queue processing can continue until the normal Stop/cleanup action is used. A latched native experiment fault requires a fresh process, not another toggle/retry.

## Native guard and status contract

Before a producer call, check the registration thread, current active-DLL marker, exact producer byte prefix, required native singleton pointers, game phase 5, transport presence and untouched stock binding. Dimensions must fit the native u16 dimension fields and coordinates must not overflow native signed multiplication by 10000. The end operation additionally compares recorder/player/app/game/stream/transport identities, effective sample/flush settings and deadlines, dimensions, app-active state and requested VID.

The native pending pair is consumed before attempting end. Exceptions during a producer call are uncertain side effects, not safe failures to replay. Python marks the request before a begin attempt; repeating that request cannot create another event pair. An unavailable experiment module or negative/exceptional begin result never silently falls back to stock queue addition.

Status values:

| Value | Meaning |
| --- | --- |
| 0 at begin | Recorder disabled: no producer call, no up event; stock path proceeds |
| 1 | Producer call returned normally; does not prove packet generation, delivery or server acceptance |
| -1 | Rejected native precondition or invalid pending/thread state |
| -2 | Producer fault: append/cap flush may already have happened; never retry |
| -3 at end | Paired context/configuration changed or became unavailable; no up appended into that context |

An up failure cannot hide a confirmed queue addition or turn an uncertain queue call into a safe rejection. Requested-VID membership plus the existing return/invariant rules still determine the queue outcome. UNKNOWN is reconciled without redispatch before any further work. Experimental faults latch, and the controller stops new additions on its next normal maintenance pass.

The context comparison detects changed values; it is not a native configuration-generation token. A same-object reset with indistinguishable values cannot be conclusively detected. The implementation adds no hooks to manufacture such a token.

## Remaining uncertainty

- This does NOT reproduce real cursor travel, physical button transitions, UI capture/dispatch, picked-actor refresh, manual click dwell time or conditional manual target selection. Down/up snapshots may be in the same native millisecond and may describe a different picked VID or no VID at all.
- No server requirement to pair each queue mutation with these samples has been proven. No server receipt, acceptance or disconnect cause is established.
- Native objects/ABI and append/serialization behavior are static evidence; local tests do not execute the actual client producer.
- Effective recorder settings may change naturally. Disabled coverage is not evidence the experiment generated samples.
- A producer return and the parameter/context logs do not expose the final serialized sample bytes or count exact socket sends.

## Local validation

The exact final paths, hashes, commands and outcomes are in `RECORDER_PAIR_LOCAL_VALIDATION_20261018.json` beside this handover. The scoped patch and preserved dirty baseline are under:

```text
C:\Users\andrej-pc\Documents\projects\decomp\recorder_pair_experiment_20261017
```

Validation scope:

- 18 new offline experiment tests: default-off, pair ordering, one stock dispatch, duplicates/admission, unavailable module, disabled recorder, faults, changed identity, late membership, UNKNOWN outcomes, logger failure and controller halt.
- Existing Hunter/feature and manual queue logging checks.
- PowerShell parse check and scoped ASCII/Python syntax checks.
- Native guard harness compiled from the actual candidate guard functions with only the two producer pointer expressions replaced by a stub. It uses process-local fake native state and real SEH fault handling. It verifies disabled/thread/byte-prefix/transport/pointer/arithmetic/config/session/VID checks, pairing and no retry after producer faults. It never executes Lirin code or touches another process.
- Normal `build.ps1 -FeatureOnly` x64 DLL build and Git whitespace checks.

No injection, game launch, traffic capture, live test, commit, push, reset, cleanup or deletion of worktree content is part of this implementation. Existing unrelated dirty/untracked changes are preserved. Runtime staging is left untouched; the approved user-run launcher command will stage the matched V50 source and newly built DLL later.

## Fresh-process test commands - for the user only

Use a separate fresh game process for baseline and experiment. Close the prior game normally, then verify that no Lirin process remains:

```powershell
Set-Location -LiteralPath 'C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation'
if (Get-Process -Name Lirin -ErrorAction SilentlyContinue) {
    throw 'Close Lirin normally first; this test requires a fresh process.'
}
```

Start Lirin through your normal launcher and log in. Keep other automation off. In PowerShell, select the single new game process and load the experiment:

```powershell
$gameProcesses = @(Get-Process -Name Lirin -ErrorAction Stop)
if ($gameProcesses.Count -ne 1) { throw 'Expected exactly one fresh Lirin game process.' }
$gameProcessId = $gameProcesses[0].Id
& '.\run_client_feature.ps1' -TargetPid $gameProcessId -RecorderPairExperiment
```

For a baseline in a different fresh process using the same V50 DLL, omit `-RecorderPairExperiment`. Both commands stage only at execution time; neither was executed by this implementation session. The experiment does not turn Hunter on. Begin with Hunter off to verify mode/identity and recorder coverage, then enable Hunter for a bounded test if you choose. Do not force recording on to obtain coverage.

Native call statuses and requested-VID/context coordinates are in:

```text
.runtime\feature-hunter-reimplementation\python_window_loader.status.txt
```

Gateway statuses, effective-recorder observations and existing queue outcomes are in:

```text
.runtime\feature-hunter-reimplementation\metin_scanner.log
```

Inspect those logs without modifying game state:

```powershell
Get-Content -LiteralPath '.\.runtime\feature-hunter-reimplementation\python_window_loader.status.txt' -Tail 40
Get-Content -LiteralPath '.\.runtime\feature-hunter-reimplementation\metin_scanner.log' -Tail 60
```

Look for down/up status 1 during naturally enabled recording, and status 0 while disabled. A negative/unknown result halts additions; use normal Stop and preserve logs. Record PID, identity, settings, recorder coverage, duration and native/feature logs. A stable run establishes only that run's duration and conditions, not resolution of the logout issue.
