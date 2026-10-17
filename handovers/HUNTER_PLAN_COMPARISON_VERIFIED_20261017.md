# Verified comparison of the two Hunter plans

Reviewed: 2026-10-17, Europe/Bratislava.

Feature repository: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`.

## Conclusion

Use Plan A's clean queue/controller architecture, with corrections below. Plan B is useful for locating shared callers and preserving continuous replenishment, but its decision to retain synthetic clicks is not established by the evidence. Neither plan establishes a disconnect cure.

The user's clarification during this review takes precedence over both documents: **focus on Hunter; breaking dependent features temporarily is acceptable; repair those separately later.** Therefore shared Boss/minigame dependencies do not justify keeping the old patched queue binding. Disable affected automation explicitly, remove its obsolete telemetry calls, and record the temporary limitations. Do not implement a second compatibility transport just to preserve those features.

The executable plan is [METIN_HUNTER_FINAL_IMPLEMENTATION_PLAN.md](METIN_HUNTER_FINAL_IMPLEMENTATION_PLAN.md). This review explains the decisions and evidence limits.

## Inputs and verified baseline

- **Plan A:** `handovers\METIN_HUNTER_REIMPLEMENTATION_PLAN.md`.
- **Plan B:** repository-root `HUNTER_REIMPLEMENTATION_PLAN.md`.
- Current checkout: `main`, HEAD `36dccf64ec46fe6618a7286b9277bc29ca5bf9b7`.
- Current Python source says `FEATURE_VERSION = 46`. Version numbers alone do not identify historical source variants.
- `client_feature.py` SHA-256: `3EC01E52E5FED55A4592706491E08675515A135B8164E6032494621D78DE77B6`.
- `python_loader.cpp` SHA-256: `5CE22B1BF4DD8D2B97658B6EFC38D35D569A70B2BB0A4B40E3F9CE23924D9C05`.
- Installed `C:\Program Files (x86)\Lirin\app\Lirin.exe` SHA-256: `8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0`, matching the current recovery traces.
- Existing `python test_client_feature_local.py` passed during this review. It is a Python 3 mock harness for the Python 2 feature; it does not validate native execution or server acceptance.
- `git diff --check` passed for the pre-existing tracked changes. Existing dirty/untracked files were inspected and preserved. No application source, configuration, build, injection, or live game state was changed for this review.

## Comparison and claim verification

| Topic | Plan A | Plan B | Verified result and decision |
| --- | --- | --- | --- |
| Main queue route | Unmodified stock binding | Keep patched binding and synthetic projected click | These are incompatible choices. Current-build binding `0x4011C0` calls low-level add `0x3ED760` directly. Stock route is a legitimate client API, but its long-term automated acceptance is unknown. Choose it for a smaller auditable design, not as a proven fix. |
| Removal scope | Removes Python Hunter and native interception | Removes Python Hunter; retains shared wrapper | B correctly found shared callers. Latest user instruction permits temporary breakage. Remove interception; explicitly disable affected modes. |
| Shared callers | Recognizes them but requires separation before removal | Correctly identifies `_dispatch_native_add`, Boss Sweep, and `emit_synthetic_click` | Verified at `client_feature.py:152`, `1475`, `1488`, `2630`, `2660`, `2924`, `2983`, `2993`, `3814`, `3866`. Merely deleting the wrapper while leaving `MetinQueueAdd(0)` is unsafe: the stock binding does not implement the telemetry sentinel. |
| Requested VID acknowledgement | Authoritative membership | Wrapper return codes | Current wrapper already checks membership at `python_loader.cpp:417` and `497`. Keep that invariant through a separate observer after removing the patch. Never copy wrapper codes into the stock API contract. |
| Stock return semantics | Under-specified | Not applicable to its chosen transport | `0x3ED760` returns `1` for an existing VID as well as an insertion. A truthy result is not proof of a new addition. It returns `0` on its capacity branch. Membership is decisive. |
| Native admission | Python race/stone/observer checks | Similar checks; calls `CanAttackInstance` an approximation | Both leave a gap if using stock add. Low-level add does not call full native eligibility `0x3ED370`. The Python observer only sees setters after installation. Require a verified native eligibility query and current native state, not the observer as authority. |
| Projection/offscreen | Removes it from Hunter | Claims wrapper skips off-viewport targets | B describes historical v46/v47 changes, not this checkout. Current `NativeMetinQueueAddInner` projects then dispatches with no viewport bounds check. The current `_queue_add` docstring overstates on-screen rejection. No projection is needed for the chosen VID API. |
| Rejection certainty | Separates pre-call and post-call uncertainty | Treats wrapper `0` as rejection/backoff | Current native `DispatchClickAt` can fault after side effects; its caller and outer SEH return `0`. Therefore `0` is not universally pre-dispatch rejection. Fix via a new request contract, not by copying that mapping. |
| Unknown requests | Retain and reconcile | No immediate retry | A is stronger. Current Hunter delays and can reselect the same unknown VID; coordinator retention is diagnostics, not a dispatch lock. B does not define timeout resolution. Final plan stops additions after unresolved uncertainty and requires explicit restart. |
| Historic unknown-set bug | Warns about incorrect confirmed state | Relies on current result handling | Earlier memory concerned another checkout. Current main's `result == 3` branch does **not** add to `hunter_queued_vids`; the existing mock asserts that. The current problem is unsafe subsequent retry and lack of authoritative reconciliation, not the already-fixed historical set insertion. |
| Stop/ownership | Claims clear/disable only owned entries | Keeps existing broad clear/pause | Neither makes this concrete. `MetinQueueSetEnabled(0)` on a true-to-false transition calls full clear. Selective removal exists: current PE method table exposes `MetinQueueRemove` at RVA `0x401300`. Its current semantics still require decompilation; old `0x3E48E0` demonstrates VID removal and combat cleanup. Final plan gates live mutation on verifying removal. |
| Manual queue coexistence | Allows a pre-existing queue but promises selective cleanup | Broad current cleanup remains | A's guarantee needs provenance and a verified remove operation. Baseline will acquire an empty, disabled queue exclusively; it will not adopt/clear a manual queue. Unexpected foreign members revoke exclusive ownership. Arbitrary concurrent manual edits cannot be reliably attributed from snapshots alone. |
| Continuous replenishment | Describes continuous operation but leaves concrete interval open | Explicit requirement, probabilistic refill design left open | Keep continuous refill. Specify deterministic bounded scheduling; no 35–70 s timer or randomized human-imitation behavior. Test-only one-add stages are temporary experiments. |
| Legendary priority | Omits destructive priority in baseline | Defers decision | Both leave production scope unclear. Final plan includes a separate, explicit priority stage after normal Hunter works, using only verified removals of Hunter-owned entries. No global clear or persistent allowed-race modification. |
| Phase identity | Requires generation | Claims existing coordinator uses generation | Current coordinator gets `lambda: self.gameplay_phase` at `client_feature.py:1878`. That is a phase number, not a generation; `5 -> 4 -> 5` or a new game window can reuse it. Add a monotonically increasing Hunter session epoch. |
| Focus and held state | No focus requirement | Unfocused `bg=0` | Native recorder branch is verified: raw `app+0x20 == 0` uses player held state, nonzero uses `GetAsyncKeyState`. The log variable named `bg` is the raw app-active byte. Use explicit `app_active`/`background` labels. Neither branch proves all synthetic state is coherent. Stock route needs no focus forcing. |
| Recorder cursor samples | No fabrication | Possible movement/timing fabrication | Traces confirm background code-0 samples read stored `+0x9C/+0xA0`. The sampled down/up function and game dispatch do not directly update those recorder fields. The findings document's claim that down/up refreshes the stored pair is unsupported by these exports. Do not build a new design on that claim. |
| Raw input | Excludes it | Excludes it | Supported for the traced mouse accumulator: `0x513ED0` reads/resets deltas and calls camera math `0x633730`. Recorder is not a reader. This does not establish absence of every other possible input/device signal; raw-keyboard readers were not exhaustively enumerated. |
| Server-visible channels | Queue vs recorder separated | Says 'exactly two' and 'only remaining differences' | The inspected queue and recorder paths are distinct, but neither review exhaustively proves all game traffic or indirect behavior. Local picker/admission state can change target/movement/attack traffic. Do not claim exact server equivalence from absence of a field. |
| Timing gates | Avoids guessing delays | Treats debounce/limiter as excluded causes | 500 ms same-VID debounce is verified in old actor-click `0x3EBDD0`, **not** in current low-level `0x3ED760`; the latter stores a timestamp but has no such comparison. 1001 ms threshold exists in filter `0x4C1F10`, but its activation/counter conditions matter. Findings' claim that 0.65–1.45 s exceeds 1001 ms is arithmetically wrong. Neither gate identifies the disconnect cause. |
| Reaction settings | Preserve unrelated behavior | Says preserve 0.50–0.85 s | Current source uses empirical samples clamped to 0.30–0.99 s with jitter 0.025. Do not change these to match historical prose. Latest scope allows disabling dependent automation; Reaction safety pause must still work. |
| Manual injected control | Useful first live control | Calls it decisive separation | Useful evidence, not causal proof. One disconnect can include network/session confounders; a stable 15–20 minute sample cannot exclude injection or cumulative behavior. Separate stock/uninjected, injected/stub, observer-only, then automatic queue experiments. |
| 'Disproven' variants | Mixes failed fixes and untested ideas | Strong causal exclusions | Existing sessions show those variants are insufficient fixes. They do not prove camera/click validity/cadence never contributes. Jitter/movement fabrication lacks a controlled cure demonstration; do not label it experimentally disproven if untested. |

## What each plan found that the other missed

**A contributes the better architecture:** an untouched stock API, separate read-only observation, authoritative VID membership, exactly-once requests, explicit pending state, removal checkpoint, lifecycle ownership, and no recorder fabrication. Its weaknesses are broad preservation requirements, incomplete native admission, imprecise selective cleanup, and no concrete refill/priority contract.

**B contributes a useful caller inventory and product constraints:** shared Boss/minigame dependencies, continuous replenishment, historical experiment context, and a proposed injection control. Its weaknesses are preserving the failed transport by assumption, stale source behavior, incomplete uncertainty handling, and treating inferred network equivalence and causality as established.

**New findings in this review:** current API has `MetinQueueRemove`; disabling clears everything; full native admission is not in stock add; wrapper `0` can follow side effects; phase 'generation' is only a phase number; background recorder stored-pair claims conflict with exports; current main lacks the claimed viewport deferral; current Reaction constants differ from B; the historical unknown-set bug is not present here.

## Evidence and its limits

Paths below are absolute roots or relative to the named root. Source/decompilation was read directly; historical run summaries are distinguished from raw logs.

### Feature repository

- `client_feature.py:134-188`: patched-binding gate, sentinel, stock-named wrapper call.
- `client_feature.py:191-317`: coordinator state machine and numeric mapping; UNKNOWN is terminal and expires.
- `client_feature.py:1688-1753`: Python observer of native exclusion setters; not an initial native-state snapshot.
- `client_feature.py:1878-1879`: phase-number getter.
- `client_feature.py:2320-2344`: global disable/clear/target cleanup.
- `client_feature.py:2572-2585`, `2676-2706`: Reaction pause/resume.
- `client_feature.py:3686-3732`, `3805-3819`: Boss coupling and queue mutation before its add.
- `client_feature.py:4177-4361`, `4363-4458`, `4460-4518`: dispatch, unknown retry, priority, scan coupling.
- `client_feature.py:37-54`, `4568-4582`: actual version/settings and scanner cadence.
- `python_loader.cpp:73-107`: membership observer, currently insufficient bounds/error distinction.
- `python_loader.cpp:269-312`, `400-553`: partial side effects and overloaded return codes.
- `python_loader.cpp:556-601`, `798-821`: method-table patch, lifecycle, wrapper marker.
- `python_loader.cpp:745-754`: 'EXE build matched' checks PE timestamp/image size; it does not compute the full EXE SHA-256.
- `test_client_feature_local.py`: existing local mock suite, passed once during review.

### Recovery root

`C:\Users\andrej-pc\Documents\projects\lirin-client-recovery`

- `native_traces\queue\1404011c0.c`, `1403ed760.c`: stock binding, duplicate/capacity/insert behavior and normal queue/recorder dirty side effects.
- `native_traces\queue\1403ed370.c`, `1403ed9c0.c`: eligibility and queue processor.
- `native_traces\queue\1404013e0.c`, `1403ed8a0.c`: disable invokes full clear.
- `native_traces\queue\14037fbe0.c`, `1402d0790.c`: phase-5 state/count path. Some serializer helpers are opaque in the available exports; absence of every possible packet field was not independently rederived end to end.
- `native_traces\queue\1401c6570.c` is only a thunk export. Do not mistake that single file for a complete VID-list serialization proof. `native_traces\recorder\140499480.c` directly shows copying the queue vector for dirty recorder snapshots.
- `native_traces\recorder\1404939e0.c`, `140497840.c`, `140497650.c`, `140497a50.c`, `140499340.c`, `140498eb0.c`: held-state branch, click construction, stored-pair readers/writers/config reset.
- `native_traces\dispatch\140826c30.c`, `140826d90.c`: internal cursor/UI side effects and dispatch returns.
- `native_traces\rawinput\513ed0.c`, `633730.c`: camera accumulator consumer.
- `docs\NATIVE_QUEUE_RECORDER_FINDINGS.md`: useful index, but correction banner does not fix every overstatement listed above.
- `docs\RAW_MOUSE_ACCUMULATOR.md`, `RESULT_REPORT_RAW_MOUSE.md`: follow-up correction; keyboard enumeration limitation is explicit.

### Decomp root and installed executable

`C:\Users\andrej-pc\Documents\projects\decomp`

- `metin_queue_trace\1403ebdd0.c`: old actor-click checks 500 ms at `player+0x45E0/+0x45E4`.
- `metin_queue_trace\1403f64a0.c`, `1403e48e0.c`: old remove binding/implementation; current removal semantics need re-verification.
- `logout_pid34524_20261016\REPORT.md`: independent preserved investigation. Native remote-close time is 19:41:38.390; feature handling is 19:41:43.473. Several later summaries conflate those clocks/events.
- `logout_pid30016_20261016\python_window_loader.status.txt`: directly confirms PID 30016 recorder samples enabled=1/sample_ms=40; label `bg` is the raw active flag.
- `logout_pid33072_20261016\metin_scanner.log`: directly confirms feature disconnect handling at 23:10:08.592. These copied logs include earlier PIDs/sessions: filter by PID and session; filename alone is insufficient.
- The other historical v25/v26/v28/v33/v35 outcomes were reviewed through handovers, not all independently recalculated from their original captures. They remain historical evidence, not new live verification.
- Read-only PE method-table inspection of the matching installed EXE confirms `MetinQueueAdd` function slot RVA `0x7525778 -> 0x4011C0`; `MetinQueueRemove` definition RVA `0x7525790`, function slot `0x7525798 -> 0x401300`; clear `0x401210`; size `0x401290`; enabled query `0x4012C0`. This proves exported API presence/addresses, not removal's complete current behavior.

## Explicit limits of this review

The server implementation and its disconnect reason are unavailable. No experiment here establishes a safe cadence, accepted automation policy, or cure. The final plan specifies local correctness and a controlled live-validation ladder separately. Native removal semantics, complete admission-query safety, and the new observer's CPython registration details are mandatory implementation prerequisites with explicit evidence gates, not facts to guess.

## Audit-evidence clarification, 2026-10-17

The initial final plan under-specified the recorder-comparison hypothesis. Its revised sections 1.1, 3.3, 10.1 and 13.1 now explicitly define H-AUDIT, bounded incoming-config/opcode and outgoing-wire-layout investigations, separate read-only status observation, and coverage/interpretation criteria for every live stage. Both investigations require a documented attempt/status; full protocol recovery is optional for local implementation and mandatory before precise protocol claims.

The stock API generates no accompanying click record itself, but this does **not** imply an empty recorder stream: enabled periodic cursor/button samples and deferred dirty queue snapshots continue independently. Recorder dirtying is conditional on enabled state; it is not proof of immediate transmission/server receipt. Whether the stock profile is accepted during enabled recording is explicitly untested until suitable live exposure is recorded. Neither the observed 100-to-40-ms change nor a coincident disconnect establishes the server comparison algorithm.
