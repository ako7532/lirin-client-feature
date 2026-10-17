# Manual Metin queue logging handover

Updated: 2026-10-17

## Outcome and safety boundary

This work adds an explicitly opt-in, passive observer for manual Metin queue
activity. It uses the existing `_lirin_hunter_native.snapshot()` observer,
`now_ms()` clock, and `audit_status()` query from the existing Python update
thread. The logger does not intercept `MetinQueueAdd`, replace an input handler,
start scanning/Hunter/the native queue/a solver, or call any queue, target,
attack, input, recorder, or network mutation.

The feature version is now **47** so a later, explicitly authorized injection
will replace an older panel instance instead of merely reopening it. No build is
required because no native source changed.

The JSONL records observed queue membership. A newly appearing VID means
**newly observed queue member**, bounded after the previous valid observation
and at or before the current observation. It is not an exact physical click or
add-attempt timestamp. A departure does not prove a kill or manual removal,
and first observation does not prove spawning.

## Changed files

- `client_feature.py`
  - integrates the logger before gameplay/Reaction early returns;
  - supplies read-only map/channel/player/target/automation context;
  - enriches queued actors only at a baseline or membership/order change;
  - stops and flushes the logger when the panel is disposed;
  - changes `FEATURE_VERSION` from 46 to 47.
- `manual_queue_logging.py`
  - Python-2.7-compatible bounded JSONL logger;
  - 100 ms minimum observation interval, approximately 1 Hz heartbeats, and
    one-second buffered flushes;
  - baselines, raw valid/invalid observations, membership/order changes,
    validity/session transitions, coverage gaps, recorder status, and explicit
    stop records;
  - logging failure reports through the ordinary feature log and disables only
    this logger.
- `scripts/analyze_manual_metin_queue.py`
  - offline counts/rates, gap distribution, batches and time bounds, occupancy
    timeline/durations, vacancy-to-refill delay, target distance patterns,
    recorder/foreground comparison, and data-quality limitations.
- `test_manual_queue_logging.py`
  - focused logger and analyzer regression checks.
- `run_client_feature.ps1`
  - stages `manual_queue_logging.py` beside `client_feature.py`;
  - writes run metadata containing Git HEAD/dirty identity and executable,
    staged-Python, and staged-DLL SHA-256 hashes before an authorized injection.
- `handovers/HANDOVER_MANUAL_QUEUE_LOGGING.md`
  - this handover.

Pre-existing modified/untracked Hunter-reimplementation work was preserved. No
commit, push, injection, game launch, live test, or native rebuild was done.

## Exact opt-in and opt-out

The switch is a sentinel file and defaults **OFF**. Merely staging/injecting the
feature does not create it and cannot start Hunter.

From PowerShell, before the manual test:

```powershell
$runtime = 'C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation\.runtime\feature-hunter-reimplementation'
New-Item -ItemType Directory -Force -Path $runtime | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $runtime 'manual_queue_logging.enabled') | Out-Null
Test-Path -LiteralPath (Join-Path $runtime 'manual_queue_logging.enabled')
```

The last command must print `True`. Then, only when ready to perform the manual
test, use the existing worktree launcher with the intended PID:

```powershell
Set-Location 'C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation'
.\run_client_feature.ps1 -TargetPid <PID>
```

That launcher stages the Python files and metadata. It does not turn on the
scanner, Hunter, the native queue, or a solver. The logger begins on the first
game/Python update after loading and writes a `session_start`, a validity
transition, and then a valid baseline when available.

To opt out while the panel is still loaded:

```powershell
$runtime = 'C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation\.runtime\feature-hunter-reimplementation'
Remove-Item -LiteralPath (Join-Path $runtime 'manual_queue_logging.enabled')
```

Within approximately one second, the logger writes `session_stop` and flushes.
Removing this sentinel does not alter the queue or any automation state. The
JSONL is retained. Disposing/replacing the feature panel also records a stop
when the native monotonic clock remains available.

## Exact runtime paths

- JSONL:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation\.runtime\feature-hunter-reimplementation\manual_metin_queue.jsonl`
- opt-in sentinel:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation\.runtime\feature-hunter-reimplementation\manual_queue_logging.enabled`
- staged metadata:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation\.runtime\feature-hunter-reimplementation\manual_queue_runtime_metadata.json`
- ordinary error/status log:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation\.runtime\feature-hunter-reimplementation\metin_scanner.log`

The JSONL is append-only across runs. To isolate a new test without deleting
prior evidence, rename an old JSONL before enabling:

```powershell
$runtime = 'C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation\.runtime\feature-hunter-reimplementation'
$log = Join-Path $runtime 'manual_metin_queue.jsonl'
if (Test-Path -LiteralPath $log) {
    Move-Item -LiteralPath $log -Destination (Join-Path $runtime ('manual_metin_queue.before-{0}.jsonl' -f (Get-Date -Format 'yyyyMMdd-HHmmss')))
}
```

## Ten-minute manual test

1. Use a fresh Lirin process and note its PID. Do not start the test if the
   intended account/map/channel differs materially from the failed runs.
2. Rename any prior JSONL, create the sentinel, and explicitly run the existing
   launcher for that PID. This is a manual action; nothing in this change
   injects automatically.
3. In the panel, confirm:
   - farming scanner/`Start` is OFF;
   - Metin Hunter is OFF and shows no automatic additions;
   - Boss Sweep is OFF;
   - Auto Reaction is OFF;
   - Yin Yang Duel and Twin Souls solvers are OFF.
4. Do not enable/disable the native queue through the feature. Use the game's
   normal manual Metin queue controls only. The server may independently change
   recorder settings; do not manipulate them for this test.
5. For 10 minutes, play normally and manually fill/replenish the queue. It is
   useful to note wall-clock times for unusual pauses, a full queue, a map or
   channel transition, or a disconnect, but do not change cadence to imitate
   Hunter.
6. After 10 minutes, remove the sentinel and wait at least two seconds for the
   explicit stop and flush. Keep the game open while doing this if possible.
7. Confirm the final JSONL contains `session_stop` and that `metin_scanner.log`
   contains no `Manual queue log: ... disabled` write error.
8. Analyze it offline:

```powershell
$repo = 'C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation'
$log = Join-Path $repo '.runtime\feature-hunter-reimplementation\manual_metin_queue.jsonl'
& 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe' (Join-Path $repo 'scripts\analyze_manual_metin_queue.py') $log
& 'C:\Users\andrej-pc\AppData\Local\Programs\Python\Python311\python.exe' (Join-Path $repo 'scripts\analyze_manual_metin_queue.py') $log --json --output (Join-Path $repo '.runtime\feature-hunter-reimplementation\manual_metin_queue.analysis.json')
```

## Recorded fields and unavailable measurements

Each raw scheduled observation includes run/session/PID/feature identity,
monotonic and UTC time, observer validity/error/API and verified stock-binding
identity, player token/gameplay epoch, queue enabled/capacity/full ordered VIDs,
previous valid observation, observed deltas and their bounds, interval/gap
coverage, Hunter/automation state, and recorder enabled/sample/flush/app-active
status or an explicit unknown value.

At baselines and membership/order changes, verified existing getters also add
map/channel, player position/current target, queued actor VID/name/race/position,
stone status, player/anchor distance, and any matching latest scanner-candidate
record with snapshot age. The logger never starts scanning to obtain these.

The current verified read-only interfaces do **not** provide safe movement or
attack state, actor HP/dead state, exact click duration/events, or native
eligibility for every scanner candidate. Existing scanner snapshots also do not
retain a true candidate first-observed time. These fields are recorded as
unavailable with reasons; no unverified native function or input hook was added.

## Comparison with the two failed Hunter runs

Use the analyzer's `newly_observed_member_count`, observed batch bounds,
inter-observation/gap distribution, occupancy timeline, estimated full/empty
durations, vacancy-to-next-observed-addition delay, distance patterns, and
recorder/app-active buckets.

- The isolated v35 Hunter-only failure recorded 22 reported successful Hunter
  additions, 1.00-30.09 s inter-add gaps (13.75 s mean, 14.03 s median), and
  target distances 724-2403 (1748 mean). Compare these reported Hunter add
  timestamps with manual **observed membership** intervals, not as identical
  event types.
- The later audit-on failure records about seven Hunter adds while
  `recorder_enabled=1`/`sample_ms=40`, followed later by a remote close. Compare
  manual observations in the matching recorder/app bucket and the refill/full
  pattern.

Those older logs lack continuous authoritative queue snapshots, so they cannot
retroactively supply exact occupancy, reorder/removal changes, bounded manual
batches, every recorder interval, or manual click timestamps. Neither old nor
new evidence proves add attempts, physical click timing, kills, a server rule,
or logout causality. Reproducing manual timing is not claimed as a fix; collect
comparable evidence first.

## Local verification

Passed without launching/injecting/building:

```text
Manual queue logging local checks: OK
Hunter redesign local checks: OK
Python ASCII compile: OK
PowerShell parse: OK
```

Focused coverage includes empty/populated baselines, one/multiple additions,
removal, reorder-only, simultaneous add/remove with unchanged size, invalid
observations, coverage gaps, player/epoch changes, Hunter OFF, recorder unknown,
absence of gameplay mutation calls, throttling, heartbeat, logger-only failure,
and analyzer metrics.
