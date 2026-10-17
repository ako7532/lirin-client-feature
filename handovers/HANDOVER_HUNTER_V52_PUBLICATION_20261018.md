# Hunter V52 branch publication

Date: 2026-10-18. Current entry point for the branch being published.

The branch replaces the old queue-binding/picker/click wrapper with stock
`player.MetinQueueAdd` plus a separate read-only native observer. Queue outcomes
use requested-VID membership, exclusive ownership and UNKNOWN reconciliation.
The optional recorder-pair module is separate and does not patch stock binding.

Current scheduling samples the measured manual inter-add and refill-wait values
and selects stones in a circular sweep. V51 completes each burst at whatever
count can be filled when a fresh scan has no eligible next target; the next
departure starts one fixed measured wait. An empty exhausted queue schedules a
measured wait without requiring a departure. This is not a fixed four-stone
limit; subsequent bursts can reach five.

V52 uses the exact Hunter spatial snapshot for red radar dots and counts, with
gray stones beyond player reach and a green clipped player-reach outline.
Red is a range indication, not a guarantee of native eligibility or acceptance.

The `-RecorderPairExperiment` launch switch enables native down/up producer
calls around one stock addition attempt. Actual samples are produced only
when the real recorder is naturally enabled. Disabled recording stays disabled.
No cursor, OS button, focus, picked-actor, target or direct packet override is
introduced. This is not proven physical-click equivalence or a logout cure.

Read these current handovers before the earlier plans:

1. `HANDOVER_HUNTER_RADAR_RANGE_20261018.md` - V52 map behavior and limits.
2. `HANDOVER_HUNTER_AVAILABLE_REFILL_20261018.md` - V51 completion policy.
3. `HANDOVER_HUNTER_RECORDER_PAIR_EXPERIMENT_20261018.md` - V50 native experiment.
4. `HANDOVER_MANUAL_QUEUE_LOGGING.md` - passive logger and offline analyzer.

Earlier reimplementation/testing/planning documents describe intermediate
versions. In particular, their fixed one-second cadence, disabled-only startup
and recorder-free baseline descriptions are not the complete current V52
behavior. Existing unavailable gates for Boss Sweep, automatic Reaction,
Yin Yang Duel, Twin Souls and automated channel changes came from the earlier
Hunter reimplementation and remain in this branch; safety detection is retained.

`RADAR_RANGE_LOCAL_VALIDATION_20261018.json` contains the final matched source,
DLL and executable hashes. The older validation JSON files are historical
snapshots, not current source identities. Compiled DLLs, runtime logs, marker
files and staged game-process files are intentionally not part of the commit.

V52 passed 39 offline tests plus feature/logger checks, Git whitespace checks
and the normal feature DLL build. Native guard harness results are documented
in the V50 handover. No live acceptance, visual-fit or logout conclusion follows
from these local checks. The user's ongoing V50 run was left untouched.

The proposed refill-delay slider and five-stone benchmark are design discussion
only and are not implemented in this publication.
