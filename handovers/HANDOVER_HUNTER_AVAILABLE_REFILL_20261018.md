# Hunter available-fill completion - V51

Date: 2026-10-18. User-requested queue policy change on top of V50.

## Resulting behavior

The former policy left a refill burst active until the queue reached five. If
the eligible population could not fill the queue, that burst could add each
newly available stone immediately for an extended period.

V51 completes a burst either when the native queue reaches capacity or when a
fresh, same-epoch scan yields no eligible next candidate. The achieved queue
count is recorded for that cycle; it is not fixed at four or a new permanent
capacity. Counts one, two, three and four all follow the same rule.

For a nonempty completed fill, wait for the first observed departure below that
achieved count. At that point sample one existing manual vacancy-to-refill delay
and keep that deadline through further departures. When it expires, begin a new
circular burst using the existing short measured inter-add delays. Every new
burst can again fill to five if eligible candidates are available. A newly
available stone alone does not reopen a completed burst before that cycle.

If no candidates are available and the queue is empty, the next maintenance
tick schedules the same measured delay without requiring an impossible queue
departure. This prevents an empty session from waiting forever for a vacancy.
Missing, wrong-epoch, missing-timestamp, future-timestamp or stale scans do not
prove exhaustion. UNKNOWN requests continue reconciliation before refill work.

Eligibility continues to include existing membership/exclusions and rejection
backoff. Therefore temporary rejection can end the current burst; later bursts
can reconsider a target after the normal backoff. No new native eligibility
rule or special threshold is introduced.

## Scope and preserved behavior

- `client_feature.py`: version 51; `HunterController.reset`,
  `_invalidate_session`, `start`, `resume`, `_run` and the existing priority-exit
  reset in `_advance_priority`. New per-cycle `refill_completed_count` state.
- `test_hunter_available_refill.py`: integration checks of the actual Python
  selector/controller/gateway against fake client boundaries.
- This handover and the adjacent `AVAILABLE_REFILL_LOCAL_VALIDATION_20261018.json`.

The stock queue call, requested-VID membership authority, no-redispatch UNKNOWN
handling, ownership, Stop/safety paths, circular direction/order and measured
delay distributions remain unchanged. There are no C++ or launcher edits.
The real native recorder integration remains opt-in with
`-RecorderPairExperiment` and produces down/up samples only during naturally
enabled recording intervals. No recorder enable/configuration, picked actor,
cursor, OS button, focus, target or packet override was added.

The original comparison's NO SAFE IMPLEMENTATION YET verdict for faithful
manual-click equivalence or an evidence-supported logout cure is unchanged.
This is an explicitly requested scheduling policy, not a protocol remedy.

## Range discrepancy remains

The map/scanner display filters by distance from the anchored circle center
(with integer-rounded display distance). Hunter candidate publication and final
revalidation additionally require exact distance within the configured radius
of the moving character. Therefore a displayed stone can be absent from Hunter
candidates. Increasing range can change the overlap of these two regions. This
change leaves both checks intact and does not prove the exact exclusion of the
particular stone reported during PID 38816.

## Local validation and artifacts

The adjacent validation JSON records final source/DLL/executable hashes and
commands/results. The scoped change, preexisting dirty diff, source/binary
backups and test/build output are preserved under:

`C:\Users\andrej-pc\Documents\projects\decomp\available_refill_20261018`

Checks include available counts 1-4, capacity five on the next burst, fixed
manual wait deadlines, circular selection plus one recorder pair per stock
attempt, disabled-recorder behavior, empty recovery, stale scans, UNKNOWN,
recorder faults, Stop/restart and session changes. Existing recorder, Hunter
and passive logger tests are also run, along with `git diff --check` and the
normal `build.ps1 -FeatureOnly` DLL build. These are offline/local checks only.

The existing V50 running process and staged runtime files are not changed by
the implementation. No injection, live test, process launch/stop, network
capture, commit, push, cleanup or deletion is performed by the agent.

## User-run fresh-process test

Preserve previous logs/metadata before running the launcher again. The passive
logging marker is already enabled and persists; it does not configure the
client input recorder. Close the old game normally, start a fresh game through
the normal launcher and log in. In PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation'
$gameProcesses = @(Get-Process -Name Lirin -ErrorAction Stop)
if ($gameProcesses.Count -ne 1) { throw 'Expected exactly one fresh Lirin game process.' }
.\run_client_feature.ps1 -TargetPid ($gameProcesses[0].Id) -RecorderPairExperiment
```

Click Start, then turn Metin Farm/Hunter ON. Keep the other automation OFF for
this test. The new log message is `manual refill burst complete: no eligible
candidate (queue N/5)`. The UI says `filled available N/5; waiting for departure`.
After a departure, expect `manual refill scheduled in ... ms`; further queue
changes or newly available stones must not bypass or reset that deadline.

Native producer status 1 means the call returned, not delivery or server
acceptance. Status 0 means recorder disabled and no sample. No live conclusion
about logout prevention or the complete manual-click contract is established.
