# Hunter radar range alignment - V52

Date: 2026-10-18. Display update on the exact V51 dirty baseline.

## Problem and resulting behavior

The previous radar counted Metins inside the anchored circle. Hunter's range
snapshot additionally filters by exact distance from the current character.
These are two equal-radius circles with different centers. Their overlap is
the spatial selection area; the mismatch is not evidence of a world-unit
conversion error. Increasing the radius can make a displayed target pass both
checks. The old map also rounded distance to an integer before testing range,
which could include a target just outside the exact boundary.

V52 publishes one Hunter candidate snapshot per scan and uses that same
snapshot for red Metin dots, red counts, grouped Metin log counts and the
controller's `on_scan`. It does not run a different approximation of Hunter's
range test for red dots. Red means in the spatial range snapshot, not guaranteed
native eligibility or queue acceptance. Already queued candidates can be red.

- Red: Metins in Hunter's exact spatial range snapshot.
- Gray: visible Metins inside the anchored circle but outside player reach.
- Blue outline: anchored radius (or the current player radius when following).
- Green outline: current player-radius boundary clipped to the anchored circle.
- Yellow: character. White: other visible actors within the displayed circle.

The green boundary updates with the existing character-marker poll. Dots and
counts update at the existing scanner cadence (about one second), not every
frame. In following mode both circles coincide, so the existing blue outline
alone represents the range. The geometric outline is a 96-point display
approximation. Actual red membership uses the unchanged exact candidate filter.

The existing orientation and `radar_pixels / radius` projection are unchanged.
Counts include all candidates even if the existing 32-dot pool cannot render
every red Metin. A separate 32-dot gray pool and 96-dot green outline use native
Python widgets; no browser or external overlay is added.

## Source scope and preserved behavior

`client_feature.py` version 52 adds the drawing-only
`radar_player_reach_offsets` helper and updates `MetinScanner.__init__`,
`ClearMap`, `UpdateMap`, `UpdatePlayerMarker` and `Scan`. There are no other
production source edits. The standalone test is `test_hunter_radar_range.py`.

HunterCandidateSelector, HunterController (including V51 available-fill
completion), HunterQueueGateway and all recorder/native code are unchanged.
Existing manual/Boss ownership, requested-VID acknowledgement, UNKNOWN handling,
Stop/safety behavior, circular order and timing remain intact. No queue call,
input event, recorder configuration write, picked actor/cursor/button/focus
override or network action is added by the map update.

V51's explicitly requested available-fill policy is included for the next
load. The user's continuing V50 process and staged runtime files are left
untouched. No restart or live test is performed by the agent.

## Verification and remaining limits

The adjacent `RADAR_RANGE_LOCAL_VALIDATION_20261018.json` records final source,
DLL and installed executable hashes, preserved baseline file hashes and checks.
Backups, the inherited dirty diff, scoped/full final diffs and test/build output
are under:

`C:\Users\andrej-pc\Documents\projects\decomp\radar_range_20261018`

Ten new offline checks exercise the real display methods and selector against
fake world/UI objects: exact shared red membership, fractional boundaries,
movement, following mode, clipped/disjoint outlines, clear/failure handling and
render-pool limits. Existing 11 available-fill and 18 recorder-pair tests,
feature checks, passive logger checks, `git diff --check` and the normal
`build.ps1 -FeatureOnly` build are also run. The complete delta is reviewed and
unchanged selection/controller/gateway/native source identities are checked.

Native font/color rendering and overlap/readability still need a future
user-run visual check. Local geometry tests cannot prove visual alignment with
the live game's camera or native admission. Movement between a scan and the
dispatch-time revalidation can still change whether an addition is allowed.
The map does not display full native eligibility, backoff or ownership state.
The manual-click equivalence and logout-cause questions remain unresolved.

## Future fresh-process test - user only

Continue the current run if desired. Before loading V52 later, preserve the
old logs/metadata, close Lirin normally, start a fresh game and log in. From the
feature worktree:

```powershell
$gameProcesses = @(Get-Process -Name Lirin -ErrorAction Stop)
if ($gameProcesses.Count -ne 1) { throw 'Expected exactly one fresh Lirin game process.' }
.\run_client_feature.ps1 -TargetPid ($gameProcesses[0].Id) -RecorderPairExperiment
```

Passive logging remains enabled through its existing marker. Use Start then
Metin Farm/Hunter ON, with other automation OFF for comparison. Recorder samples
remain conditional on the real client recorder's naturally enabled intervals.
Inspect gray-to-red changes as the character moves and verify that range
increases affect both the displayed range and Hunter's candidates together.

No injection, game launch/stop, network capture, commit, push, cleanup or deletion
is part of this local implementation.
