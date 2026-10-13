# Lirin Client Feature - Continuation Handover

Date: 2026-10-13

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

The working source is now `FEATURE_VERSION = 20` in `client_feature.py`.
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

Only v14 was last tested live. V15-v20 have not been injected. The last live
injection was PID 48804 at 21:24:47, and that process is no longer running.
`python_window_loader.status.txt` contains the successful loader sequence. Do
not treat it as evidence that v18 ran.

`client_feature_loader.dll` exists in the feature repository and was last
observed as a 64-bit x64 DLL (PE machine `0x8664`, 142,848 bytes). The local
config file does not currently exist, so a newly loaded feature would use its
defaults unless a config is created.

## 5. Exact disconnect evidence

### Latest disconnect: 21:46

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
in which it could act on stale world state. V18 locally closes that window by
checking `net.IsConnect()`. This fixes unsafe behavior after a disconnect; it
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

Game log:

`C:\Program Files (x86)\Lirin\app\logs\13-10-2026.log`

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
Git. It is currently absent.

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
