# Handover: desktop UI for selecting and injecting a Lirin client

## Objective

Build a small Windows desktop application that:

1. Lists every currently running **64-bit Lirin game client**.
2. Lets the user select one client from the list.
3. Injects the existing feature loader into the selected PID when the user
   clicks **Inject**.
4. Shows clear progress, success, and error output in the UI.

This is a new launcher/controller for the existing client feature. Do not
rewrite the in-game feature or invent a second injection implementation for
the first version.

## Repositories and paths

Primary Git repository:

```text
C:\Users\andrej-pc\Documents\projects\lirin-client-feature
https://github.com/ako7532/lirin-client-feature
```

Restored analysis workspace:

```text
C:\Users\andrej-pc\Documents\projects\decomp
```

Installed executables:

- Game target: `C:\Program Files (x86)\Lirin\app\Lirin.exe` (64-bit)
- Launcher to exclude: `C:\Program Files (x86)\Lirin\Lirin.exe` (32-bit)

Read these before changing code:

- `HANDOVER_FEATURE.md`
- `TEST_RESULTS.md`
- `README.md`
- `run_client_feature.ps1`
- `inject.py`
- `python_loader.cpp`

The current in-game feature is v11 in `client_feature.py`. Its local mock
passes. The Git repository intentionally excludes compiled DLLs, runtime logs,
snapshots, process-status files, and generated injection copies.

## Recommended first implementation

Use a **.NET 8 WinForms x64** application in a new subdirectory such as:

```text
LirinFeatureLauncher/
```

Reasons:

- Native Windows process enumeration and a straightforward desktop UI.
- Easy x64 build and administrator manifest support.
- Asynchronous child-process output capture without extra dependencies.
- A self-contained executable can be produced later.

If the next chat selects another UI stack, preserve all process validation,
elevation, runner reuse, and testing requirements in this document.

## MVP user interface

The main window should contain:

- A table/list of valid running game clients.
- Columns: PID, window title, start time, responding state, and executable
  path.
- **Refresh** button.
- Optional automatic refresh every two seconds.
- **Inject** button, enabled only when exactly one valid client is selected.
- Status/output area showing the runner's stdout and stderr.
- A short state label such as `Ready`, `Injecting`, `Injected`, or `Failed`.

Preserve the selected PID during refresh when it is still running. Never
silently switch selection to a different process.

## Process discovery and validation

Enumerate processes named `Lirin`, but list only processes whose resolved
image path matches, case-insensitively:

```text
C:\Program Files (x86)\Lirin\app\Lirin.exe
```

Do not identify the target using the process name or window title alone. The
installation-root launcher has the same filename and must never appear as an
injectable game client.

Process inspection can race with client exit. Handle access denied, an exited
process, a missing main window, and unavailable start-time/path properties per
process without crashing the refresh loop. Revalidate the selected PID and
exact executable path immediately before injection.

## Reuse the existing tested injection path

For the MVP, invoke:

```powershell
run_client_feature.ps1 -TargetPid <selected PID>
```

The UI should start 64-bit PowerShell with `-NoProfile`, pass the script and
PID as separate arguments, redirect stdout/stderr, and read both streams
asynchronously. Do not assemble an unquoted shell command from UI text.

The existing runner already:

- Requires a single target PID.
- Creates a uniquely named DLL copy so `DllMain` runs again.
- Updates and restores `client_feature_active.txt` around failures.
- Calls the existing x64 `inject.py` implementation.
- Waits for PID-specific loader status.
- Requires `Python script returned successfully` before reporting success.
- Confirms whether the selected process remains alive/responding.

The existing `inject.py` also opens the selected process and verifies its
resolved executable path against the exact 64-bit game path before calling
`LoadLibraryW`. Keep that final validation; UI filtering is not a replacement.

Do not port `OpenProcess`, `VirtualAllocEx`, `WriteProcessMemory`, or
`CreateRemoteThread` into the UI during the MVP. A direct managed injector can
be considered later only with equivalent validation and tests.

## Elevation

Injection previously failed with Windows error 5 from a non-elevated process
and succeeded from administrator PowerShell. Prefer an application manifest
with `requireAdministrator` for the first version.

If the UI is not elevated, it must not claim that no clients exist merely
because process paths could not be queried. Show an explicit elevation/access
error and offer to restart as administrator.

## Build artifact handling

`client_feature_loader.dll` is intentionally excluded from Git. The UI must
look for it beside the existing scripts and show a clear `Feature loader
missing` error when absent. Do not download or substitute a DLL automatically.

Build it from an appropriate Visual Studio developer environment with:

```powershell
& '.\build.ps1' -FeatureOnly
```

Changing only `client_feature.py` does not require rebuilding the C++ loader.
Changing `python_loader.cpp` does.

For development, resolve paths relative to the repository/application base
directory rather than hard-coding a second checkout. Packaging the UI, script,
Python runtime, and DLL is a later task.

## Important multi-client limitation

The UI may list multiple running game clients, but the current feature runtime
is not yet safe for persistent simultaneous injection into several clients:

- `client_feature_active.txt` is shared across all processes using this
  feature directory.
- Each injection changes that marker, causing an older loader's native
  snapshot thread to stop when it detects the mismatch.
- `client_feature_vids.txt`, `python_window_loader.status.txt`, and
  `metin_scanner.log` are also shared files.

Therefore, the MVP must support **one actively managed injected client at a
time**. If the user injects another PID, show a warning explaining that the
previous client's native snapshot feed may stop.

True simultaneous multi-client support requires a separate change first:

- Make active marker, snapshot, status, and preferably feature-log paths
  PID-scoped.
- Pass or derive the target PID consistently in both native and Python code.
- Ensure each injected client reads only its own snapshot/status files.
- Add a test with two clients before removing the single-active warning.

Do not hide this limitation merely because process enumeration finds several
clients.

## Existing Auto Reaction mechanics and pending observation

This section records the current state of the yin-yang reaction-window work so
the next chat does not have to rediscover it. It is background for integration
and diagnosis, not part of the injector UI MVP. Do not change or extend the
reaction solver while building the UI.

### What the current v11 implementation does

`client_feature.py` contains an **Auto Reaction** toggle which defaults to ON.
The implementation is based on the runtime `ReactionGameWindow` object and the
decompiled `uireactiongame` module. It is distinct from `uicaptcha` and the
yin-yang card minigames. Relevant native/client strings include
`SendReactionGameStart` and `SendReactionGameClick`.

The current state and timing are:

- `REACTION_POLL_SECONDS = 0.05`, so a cached/visible window is checked at up
  to 20 Hz.
- `REACTION_DISCOVERY_SECONDS = 5.0`, limiting expensive rediscovery when the
  window object is missing.
- Discovery is skipped while Auto Reaction is OFF unless an existing reaction
  pause still has to be released.
- The cached object must expose `IsShow`,
  `_ReactionGameWindow__OnClickPlay`, and
  `_ReactionGameWindow__OnClickSlot`.
- When a visible prompt is detected, normal Python feature processing pauses
  and the log records `Reaction game visible; combat paused`.
- If the game is not playing and the Play button is visible, the code calls
  `_ReactionGameWindow__OnClickPlay()` and records `start requested`.
- During play it reads `isPlaying`, `activeSlot`, `slotButtons`,
  `firstBallSpawned`, and `lastBallMoveTime`.
- A ball is identified by `(lastBallMoveTime, activeSlot)`. The current slot
  is clicked once per newly observed ball through
  `_ReactionGameWindow__OnClickSlot(slot)`. This allows the same slot to be
  clicked for two different balls.
- When the prompt closes, the code clears the start/ball tracking state and
  shifts Boss Sweep deadlines by the time spent paused.
- A distinct runtime exception is logged once and the cached window reference
  is discarded so discovery can run again.

`PollReactionGame()` runs near the start of the panel's `OnUpdate`, before the
general `running` check. Consequently, pressing the feature panel's general
**Stop** button does **not** disable Auto Reaction. For an isolated test, the
user must explicitly switch **Auto Reaction** OFF.

### Known integration risks

The implementation has two important unresolved state-machine issues:

1. Returning early from Python `OnUpdate` pauses Python feature decisions, but
   it does not automatically stop an already-running native Metin/Boss queue.
   A correct future pause/resume integration must explicitly capture, stop,
   and restore the native queue/combat state. The present v11 deadline shift
   alone does not do this.
2. After requesting Play, the code immediately sets its local
   `reaction_started` latch. The UI/server transition is asynchronous, so a
   rejected or delayed request can leave local state ahead of authoritative
   game state. Any future integration fix should use a bounded retry and
   confirm authoritative state before latching success.

Runtime discovery can also retain a stale or hidden window object. Prefer a
currently visible valid instance, and invalidate a cached object after bounded
repeated failures. Direct local mocks are useful but insufficient: an
integration test must exercise the full `OnUpdate` path with an active native
queue, asynchronous start confirmation, window closure, deadline adjustment,
and combat/queue restoration.

The local Auto Reaction mock passed, but that only established Python-side
calls and state transitions. It did not verify server acceptance, score/hit
registration, successful minigame completion, or correct resumption of combat.

### Observed disconnect timeline

One recorded run produced this sequence in the feature log:

- `13:50:47` - reaction window visible and combat pause recorded.
- `13:50:47` - reaction-game start requested.
- `13:50:48` - slots `5, 4, 1, 5, 2` clicked within roughly one second.
- `13:50:49` - reaction window closed.
- `13:50:49` - pause ended after approximately 1.6 seconds.
- `13:50:55` - another server message was still received.
- `13:51:49` - the remote server closed the connection, approximately one
  minute after the reaction window closed.
- `13:52:13` - world/rendering/reconnect activity appeared.
- `13:53:05` - the user explicitly switched Auto Reaction OFF.

The game process stayed alive, so this was a server disconnect rather than a
client crash. Network pings were healthy and Windows showed no adapter error.
The logs contained no authoritative disconnect reason. There was also an
earlier remote disconnect at `13:47:14`, before this recorded reaction event.
The timing is suspicious but does **not** prove the automated interaction
caused the disconnect.

After disconnect, the feature continued scanning because Python objects and a
native snapshot could remain alive or stale. Continued feature log activity is
therefore not proof that the character is still in the playable world. A
future gameplay-phase guard is desirable, but it is outside the injector UI
MVP.

### Passive/manual tracking procedure prepared for the next prompt

Use this procedure to collect evidence without changing the reaction behavior:

1. Explicitly switch **Auto Reaction** OFF. Do not rely on the general Stop
   button.
2. When the prompt appears, do not press Play or click a circle yet. Record the
   time and announce that the reaction window is up.
3. Before interacting, passively capture the game-log tail, feature-log tail,
   target PID and responsiveness, server network connections, and snapshot
   freshness/count.
4. Manually press Play and complete the prompt, then record the completion
   time immediately.
5. Capture the same evidence again and monitor logs and connections for at
   least 70 seconds. The prior disconnect occurred about 60 seconds after the
   prompt closed.
6. Check whether any `Reaction game...` entries appear while Auto Reaction is
   OFF. Such entries would indicate a toggle/state bug.
7. Compare manual event timing, server messages, and whether a disconnect
   occurs. Report correlation separately from demonstrated causation.

For stronger A/B isolation, first restart the client without injection and
manually play for 10-15 minutes. If stable, inject v11, immediately turn Auto
Reaction OFF and Hunter OFF, test scanner-only behavior, and only then test
Hunter separately. The observation should remain passive; do not automate the
manual recording experiment or use it to tune reaction-click decisions.

### Injector UI implications

- The first injector UI validation should explicitly turn Auto Reaction OFF
  immediately after the v11 panel appears, because it defaults to ON.
- The UI must not claim that Auto Reaction or its server-side result has been
  validated merely because injection succeeds.
- An `Open logs` convenience can be considered later, but it is not required
  for the MVP.
- Changes to Auto Reaction, its click logic, native queue behavior, or
  gameplay-phase detection must remain a separate, explicitly tested change.

## State and error handling

While injection is running:

- Disable Refresh and Inject, or otherwise prevent duplicate concurrent runs.
- Keep the selected PID visible.
- Stream output into the status box without blocking the UI thread.
- Allow a bounded timeout and report it clearly.

Expected errors should have actionable messages:

- No valid game clients are running.
- Selected client exited; refresh the list.
- Access denied; restart the UI as administrator.
- Feature loader missing; run `build.ps1 -FeatureOnly`.
- Python executable or runner missing.
- Loader build mismatch after a game update.
- Script did not report success; show status/log paths.

Do not show success merely because `LoadLibraryW` returned a nonzero value.
Success requires the runner's existing embedded-Python confirmation.

## Testing sequence

Keep discovery, command construction, and UI presentation separable enough to
test without injecting into the game.

### Local automated checks

1. Path filtering accepts only the exact `app\Lirin.exe` target.
2. The 32-bit installation-root launcher is excluded.
3. Refresh preserves selection by PID.
4. An exited process is removed without crashing.
5. Inject is disabled with zero or multiple selections.
6. The PowerShell filename and PID are passed as separate arguments.
7. Stdout/stderr completion and failure update UI state correctly.
8. Missing script/DLL and access-denied errors are visible.

Keep the existing feature checks passing:

```powershell
python .\test_client_feature_local.py
python -m py_compile .\client_feature.py .\test_client_feature_local.py
```

### Manual non-injection checks

1. With only the launcher open, the list is empty.
2. With one game client open, exactly that PID appears.
3. With two game clients open, both valid PIDs appear.
4. Closing one client removes only that row.
5. Refresh never changes a still-valid selection unexpectedly.

### First live injection check

Use one game client with a character in the playable world:

1. Build `client_feature_loader.dll` if absent.
2. Run the new UI as administrator.
3. Confirm the displayed PID/path against Task Manager or PowerShell.
4. Select that row and click Inject once.
5. Require `Python script returned successfully` in UI output.
6. Confirm the in-game v11 panel appears.
7. Immediately switch **Auto Reaction** OFF to isolate this UI/injection test.
8. Confirm the client remains responsive.
9. Review `python_window_loader.status.txt` and `metin_scanner.log`.
10. Append exact results to `TEST_RESULTS.md`.

Do not combine the first UI test with Boss Sweep, channel changing, or other
live behavior. First prove only process discovery, selection, injection, panel
appearance, and client responsiveness.

## Scope boundaries for the first change

In scope:

- Desktop UI project.
- Accurate process list and selection.
- Administrator handling.
- Calling the existing runner for one selected PID.
- Captured progress/errors and local tests.
- Documentation updates.

Out of scope until the MVP passes:

- Rewriting the native injector in C#.
- Automatic injection as soon as a client starts.
- Injecting every listed client simultaneously.
- Changing Boss Sweep, Hunter, Auto Reaction, or other in-game behavior.
- Extending, tuning, or validating the reaction solver during the UI change.
- Bundling Python, Visual Studio tools, or proprietary executables.

## Suggested first message in the new chat

> Work in `C:\Users\andrej-pc\Documents\projects\lirin-client-feature` and
> read `HANDOVER_INJECTOR_UI.md`, `HANDOVER_FEATURE.md`, `TEST_RESULTS.md`,
> `run_client_feature.ps1`, and `inject.py` before changing anything. Build
> the first version of a Windows desktop UI that lists only running 64-bit
> `C:\Program Files (x86)\Lirin\app\Lirin.exe` processes, lets me select one,
> and invokes the existing runner with that PID when I click Inject. Use the
> existing validation and embedded-Python success signal. Keep the MVP to one
> actively managed injected client because the current marker/snapshot files
> are shared. Read the Auto Reaction mechanics and observation section, but do
> not modify that behavior as part of the UI. During the first live UI test,
> explicitly switch Auto Reaction OFF after the panel appears. Add local tests
> and do not perform a live injection until the non-injection checks pass.
