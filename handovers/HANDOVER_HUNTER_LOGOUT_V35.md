# Lirin Hunter logout investigation - v35 handover

Updated: 2026-10-15 after the isolated v35 Hunter-only logout at 15:48:50
(Europe/Bratislava).

## Read this first

Continue the existing investigation in:

`C:\Users\andrej-pc\Documents\projects\lirin-client-feature`

Do not start by reverting to an older version, re-adding the on-screen filter,
rotating the camera, or injecting another Hunter build. The current committed
source is v35 and its full-input native wrapper has now failed in a clean
Hunter-only live test.

The user reports that using the Metin queue manually without injection does not
cause a logout. The next useful isolation is therefore manual queue use with
v35 injected but every automation mode OFF. This separates the installed
injection/method-table patch from automated Hunter queue calls.

## User constraints and preferences

- Investigate with read-only source/log/decompilation work first.
- Do not inject on the user's behalf. The user performs live injection/tests.
- Do not tune or rewrite Auto Reaction as part of this problem.
- Preserve continuous Hunter replenishment in the production feature. Do not
  replace it with five-stone batches and long waits without explicit approval.
- Do not re-add the projected-on-screen condition or camera rotation. Both are
  disproven as a sufficient fix by live evidence.
- Preserve unrelated uncommitted files, especially
  `ReactionTimingRecorder/` and `ReactionTimingRecorder.Tests/`.
- Do not commit or push again unless the user explicitly asks.
- Keep feature logs, native game logs, and user observations separate. Their
  timestamps have repeatedly disagreed, so do not infer exact causal order
  across files.

## Current committed state

- Branch: `main`
- Commit: `0ea318e637707cfac8fa057297535ba62a281286`
- Commit time: `2026-10-15 15:30:51 +0200`
- Subject: `Route automation through full native input path`
- Pushed: yes, `origin/main` points to the same commit.
- `FEATURE_VERSION = 35`
- Source SHA-256:
  `A1013285179FD68AF68AD8A2A2F0B48180D0B68BC4C6DDE95AA4A27647A7BA1F`
- Built `client_feature_loader.dll`: 144,896 bytes
- DLL SHA-256:
  `594F3B7B0EBB2E34D9960174F59E3DD99AE400ECF079E06B7C1E6BD7BABA075B`

The only uncommitted items before this handover was written were:

```text
?? ReactionTimingRecorder.Tests/
?? ReactionTimingRecorder/
```

This handover file itself is newly created and uncommitted.

## Important paths

- Current repository:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`
- Current source:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\client_feature.py`
- Native loader/wrapper:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\python_loader.cpp`
- Feature log:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\metin_scanner.log`
- Loader status:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\python_window_loader.status.txt`
- Saved configuration:
  `C:\Users\andrej-pc\Documents\projects\lirin-client-feature\client_feature_config.txt`
- Native game log:
  `C:\Program Files (x86)\Lirin\app\logs\15-10-2026.log`
- Native picker decompilation:
  `C:\Users\andrej-pc\Documents\projects\decomp\native_picker_trace`
- Broader queue decompilation:
  `C:\Users\andrej-pc\Documents\projects\decomp\metin_queue_trace`
- Exact isolated v28 test handover:
  `C:\Users\andrej-pc\Downloads\lirin-client-feature-main\lirin-client-feature-main\HANDOVER_BASELINE_V28_TEST.md`
- Exact isolated v28 copy:
  `C:\Users\andrej-pc\Downloads\lirin-client-feature-main\lirin-client-feature-main`

## What v35 changed

V26-v34 patched the exposed Python `player.MetinQueueAdd` method-table entry,
but the replacement wrapper called the internal actor-click function directly:

- actor-click RVA: `0x003EBDD0` (`0x1403EBDD0` at image base)

That was only the final actor-specific stage of a normal client click. Native
decompilation showed that the normal internal mouse path first runs:

- player mouse-state handler RVA: `0x003E5940` (`0x1403E5940`)
- press handler RVA: `0x003EC0F0` (`0x1403EC0F0`)
- character picker: `0x140519060`
- live actor lookup RVA: `0x003D1D40` (`0x1403D1D40`)

The press path checks higher player/input state, cooldowns, ground-item picking,
the picked character, terrain/background picking, the current target, and only
then enters actor-click when appropriate.

V35 changed `NativeMetinQueueAdd` to:

1. Resolve the requested VID to a live native actor through `0x1403D1D40`.
2. Fail closed if the player/character manager is missing or the internal mouse
   state at player offset `0xFF` is already held.
3. Save the character manager's current picked-actor pointer at offset `0xE0`.
4. Temporarily install the requested actor as the picked actor.
5. Execute press and release through `0x1403E5940`.
6. Restore the original picker pointer in an SEH `__finally` block.
7. Report success only if the native queue vector size increased.

Important precision: this executes the higher internal `CPythonPlayer`
mouse-state path, but it is still a synthetic picker override. It is not a real
Windows cursor/UI-dispatch click. V35 therefore tested whether the skipped
internal player/input gates were the missing fix; it did not prove complete
identity with a physical user click.

V35 also removed all Hunter dependencies on:

- `IsActorOnScreen`
- `chr.GetProjectPosition`
- screen bounds from `wndMgr`
- `app.RotateCamera`
- all Hunter camera-search state, polling, timeouts, and test mocks

Continuous refill, Legendary priority, Boss Sweep, and Auto Reaction remained.

## Local verification before live tests

All checks passed:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python .\test_client_feature_local.py
python -c "import ast, pathlib; ast.parse(pathlib.Path('client_feature.py').read_text(encoding='ascii')); print('ASCII syntax compile: OK')"
git diff --check
.\build.ps1 -FeatureOnly
```

Expected regression summary:

```text
Local map, safe hunter queue, boss flow, config persistence, reaction, hotkey, and gameplay-exit guard: OK
```

An `rg` check confirmed there were no functional Hunter references to
`IsActorOnScreen`, `HunterCamera`, `HUNTER_CAMERA`, `GetProjectPosition`,
`RotateCamera`, or `wndMgr` in `client_feature.py` or its local test.

## Exact historical baseline that matters

### v26 successful run, but not proof of a cure

Commit `65fbe44`/v26 once ran Hunter for approximately 40 minutes 42 seconds,
including about 24 minutes 14 seconds uninterrupted. It used the partial
actor-click wrapper and on-screen projection. This was initially treated as a
fix, but later repeatable failures show it was only a successful run.

That v26 run made 169 queue additions. Its average inter-add gap was about
14.59 seconds, close to later failing runs. Therefore raw average add frequency
alone is not a sufficient explanation.

### Exact isolated v28 failure

The isolated Downloads copy was verified to match:

- commit: `25ea2964f4518bbbe6fe6b301d569e060e9ac0a7`
- commit time: `2026-10-15 00:52:22 +0200`
- subject: `Refine Hunter targeting and panel close behavior`
- `client_feature.py` SHA-256:
  `36E80F8451B685828E7C259AA5E4E331571AA7657FE026DAF14B659ADB4EE78B`
- loader DLL SHA-256:
  `5C2E8E7EA8869334CB9F369E08F42D7FF4703BDD629EA54DDCCA25D94DE0ADD8`

PID 17800 loaded that exact v28 build. Hunter started at `14:50:29` with
Auto Reaction and Boss Sweep OFF. V28 did not contain Legendary priority or
camera rotation. The feature observed `net.Disconnect`/login transition at
`14:54:03`; the native log contains a remote disconnect at `14:54:24.807`.
Do not infer ordering between those files. Hunter lasted about 3 minutes
35 seconds and made 15 queue additions.

This proves the logout is not a regression introduced by v29-v35.

### v33 on-screen failure

Fresh PID 7364 restored the conservative on-screen condition and performed a
real camera-search trigger/stop. It still returned to login after about
8 minutes 43 seconds of Hunter operation. Thus on-screen projection is not a
sufficient fix.

## v35 live test 1 - mixed modes

PID 25896:

- panel/full-input wrapper active: `15:27:04.076`
- Hunter ON: `15:27:28.434`
- Boss Sweep ON: `15:27:32.036`
- Auto Reaction ON: `15:29:20.230`
- full Boss Sweep later killed the boss across the available channels and
  restored Hunter at `15:34:13.755`
- Legendary priority ran from `15:40:42.864` to `15:41:57.938`
- Python observed `net.Disconnect` and login transition at `15:42:02.163`
- native game log records `Remote disconnected ...:11035` at `15:42:57.766`

This run proves only that v35 can still disconnect in combined operation. It
does not isolate Hunter, Boss, Reaction, or priority. No Reaction Game event or
solver click was logged despite Auto Reaction being enabled.

## v35 live test 2 - decisive Hunter-only failure

Fresh Lirin PID 4724 started at approximately `15:43:28`.

Loader/status evidence:

```text
PID 4724: native full-input queue wrapper installed
PID 4724: Python script returned successfully
```

Feature evidence:

```text
2026-10-15 15:43:47.723 Native full-input queue wrapper: active
2026-10-15 15:43:53.358 Metin Hunter ON; queue limit 5
2026-10-15 15:48:50.312 Python net.Disconnect called args=() kwargs={} stack=
2026-10-15 15:48:50.312 Automation stopped: phase window 1 registered: NewLoginWindow
```

Mode isolation:

- saved config had `reaction_enabled=0`
- no Boss Sweep ON/event occurred
- no Reaction Game start/click occurred
- no Legendary priority event occurred
- no camera/on-screen path exists in v35
- only ordinary `Metin of Death` Hunter activity occurred
- minimizing the panel at `15:43:54.780` intentionally left automation running

Queue statistics from this run:

- 22 successful queue additions
- first add: `15:43:54.542`
- last add: `15:48:43.270`
- distance minimum: 724
- distance maximum: 2403
- distance average: 1748.0
- pre-add queue sizes: `0:1, 1:1, 2:3, 3:17`
- inter-add minimum: 1.00 seconds
- inter-add maximum: 30.09 seconds
- inter-add average: 13.75 seconds
- inter-add median: 14.03 seconds

The native game log independently records:

```text
1015 15:48:21583 :: Remote disconnected from game.lirin.to:11035
```

The native log time precedes the Python observation by about 29 seconds, while
other runs show the opposite ordering. Treat the logs as independent evidence
of a real remote close, not as a precise causal timeline. In particular, do not
claim that the last queue add seven seconds before the Python observation
caused the close.

Conclusion: the v35 higher internal mouse-state path did not cure the logout.
Boss Sweep, Auto Reaction, Legendary priority, camera rotation, on-screen
admission, and post-v28 feature work are not required for the failure.

## Verified native queue semantics

- Exposed Python binding `player.MetinQueueAdd`:
  `0x1403F6360`
- Low-level `CPythonPlayer::MetinQueueAdd`:
  `0x1403E41A0`
- Queue clear:
  `0x1403E4300`
- Queue processor:
  `0x1403E4400`
- Actor-click wrapper:
  `0x1403EBDD0`
- Eligibility predicate:
  `0x1403E31F0`
- Higher player mouse-state handler:
  `0x1403E5940`
- Press handler:
  `0x1403EC0F0`

The original Python binding calls low-level insertion directly. The native
actor-click path additionally checks queue enablement, live actor lookup, the
eligibility predicate, global state, duplicate handling, and a 500 ms same-VID
debounce. Low-level add changes the local queue and calls `0x140243AC0`, whose
downstream path reaches `0x14022E4A0` and serializes queue state/count when the
native phase is game phase 5. `0x1404710D0` is a dirty helper, not itself a
packet sender.

`net.IsConnect` only checks that the stored socket handle is not `-1`; it does
not prove peer health. `net.SetPhaseWindow` registers a Python UI window; it is
not authoritative network phase state. Normal login setup itself calls
`net.Disconnect`, so the Python observer does not identify the original native
caller that reacted to the remote close.

Scanner getters examined so far (VID, name, race, position, database lookup)
have no identified outgoing gameplay/network path.

## What the evidence currently rules out

The following are not individually required for the logout:

- Auto Reaction or its click timing
- Boss Sweep or channel rotation
- Legendary Metinstone priority transitions
- camera rotation
- projected-on-screen admission
- v29-v35 feature additions
- direct use of only the low-level Python `MetinQueueAdd` binding
- bypass of only the higher internal `CPythonPlayer` mouse-state gates

The v35 test does not rule out every difference from a physical click because
the target actor was still supplied synthetically to the native picker.

The similar average add gaps in successful v26 and failing v28/v35 runs mean a
simple fixed frequency threshold is not established. A server-side detector
can still use target choice, queue transition patterns, spatial validity,
session/account history, or a longer scoring window.

## Ranked remaining hypotheses

1. **Network-visible automated queue pattern or server policy.** Hunter chooses
   targets and replenishes the queue without real user cursor selection. The
   server may reject or score a sequence that is individually client-valid but
   implausible as manual interaction.
2. **Detection of injection or the patched Python method table.** Historical
   injection-only/scanner-only runs were stable, but the current v35 patch has
   not been re-isolated under the current server/account conditions.
3. **Client/server queue-state interaction not fixed by input admission.**
   Repeated automatic queue state/count updates may eventually produce a state
   the peer closes, even though every local add reports success.
4. **Account/session-side cumulative scoring or server-side policy change.**
   The one long v26 run may have been a non-triggering sample rather than proof
   of a client fix.
5. **Ordinary network instability.** Less consistent with repeatability and the
   user's stable manual play, but no server disconnect reason is available, so
   it cannot be eliminated absolutely.

## Next decisive test - do this before another Hunter build

Use a fresh Lirin process. Inject the committed v35 build, but keep:

- Hunter OFF
- Boss Sweep OFF
- Auto Reaction OFF

Then use the game's Metin queue manually for 15-20 minutes under comparable map
and combat conditions. Starting the read-only scanner is optional, but do not
turn on Hunter.

Interpretation:

- If the injected/manual run disconnects, focus next on the injection and
  method-table patch itself. Build a wrapper-disabled diagnostic variant before
  changing Hunter behavior.
- If the injected/manual run remains connected, injection and the installed
  patch become less likely; focus on automated target selection and the
  network-visible queue transition pattern.

The user already reports that manual queue use without injection does not fail,
but record a timed no-injection control under the same map/account conditions
if exact comparison is needed.

Do not run Hunter again before this isolation. Repeating the same Hunter test
adds little information and may contaminate an account/session-side scoring
window.

## Follow-up only after the manual-with-injection control

If manual use with injection is stable, the smallest next diagnostic should
change one factor only and remain clearly marked diagnostic. Candidate options:

1. Log-only Hunter discovery with no queue calls, confirming scanner stability
   in the same environment.
2. User-confirmed one-add diagnostic, where Hunter proposes a VID but a real
   user action triggers admission.
3. A controlled one-target automatic queue diagnostic to compare target choice
   and transitions, only with explicit user approval because it temporarily
   differs from the requested continuous replenishment behavior.
4. Add native diagnostics around queue serialization/state transitions before
   another long live run. Avoid logging sensitive or excessively noisy data.

Do not jump directly to arbitrary long waits or reintroduce five-target batches.
The current data does not show that average cadence alone is the cause.

## Repository and safety notes

- Commit `0ea318e` is already pushed. Do not amend or force-push it.
- Preserve `ReactionTimingRecorder/` and `ReactionTimingRecorder.Tests/`.
- `client_feature_loader.dll` is a built artifact and is not represented by the
  Git commit hash; verify its SHA-256 before a live test.
- Use the existing selected-PID launcher/injection flow. Do not rewrite
  injection internals.
- The two launcher EXEs previously found were byte-identical. The recommended
  path is:
  `LirinFeatureLauncher\bin\Release\updated\LirinFeatureLauncher.exe`
- Do not attach/inject into an old login-screen PID. Close the client fully and
  use a fresh game process for each controlled test.
- Do not interpret successful DLL loading, local mocks, queue-size growth, or a
  few minutes of play as proof that the server accepts the behavior long-term.

## Concise continuation request for the next chat

Read this entire file, then inspect the current Git status and the latest v35
log segment. Treat v35 Hunter-only logout as confirmed. Do not modify code yet.
First help run or evaluate the fresh manual-queue-with-v35-injected control. If
that control is stable, design the smallest single-factor diagnostic that
separates automated target selection from queue serialization, while preserving
the production requirement for continuous refill and leaving Auto Reaction,
Boss Sweep, screen projection, and camera rotation untouched.
