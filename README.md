# Lirin DLL loading test

See [TEST_RESULTS.md](TEST_RESULTS.md) for the chronological test log and
verified results.
For a new-chat project handover, see [handovers/HANDOVER_FEATURE.md](handovers/HANDOVER_FEATURE.md).

## Windows injector UI

`LirinFeatureLauncher` is a .NET 8 WinForms x64 controller for the existing
injection path. It lists only running 64-bit processes whose resolved image is
exactly `C:\Program Files (x86)\Lirin\app\Lirin.exe`; the installation-root
32-bit launcher is excluded. Select one PID, then click **Inject** to run
`run_client_feature.ps1 -TargetPid <pid>`. Standard output and standard error
are streamed into the window, with Ready, Injecting, Injected, and Failed
states.

The executable has a `requireAdministrator` manifest. It also revalidates the
selected PID, architecture, and exact path immediately before starting the
runner. The existing `inject.py` validation remains the final guard; the UI
does not contain a second native injector.

Build and run it from this repository:

```powershell
dotnet build .\LirinFeatureLauncher\LirinFeatureLauncher.csproj -c Release
& '.\LirinFeatureLauncher\bin\Release\net8.0-windows\LirinFeatureLauncher.exe'
```

Run the dependency-free local checks without injecting into Lirin:

```powershell
dotnet run --project .\LirinFeatureLauncher.Tests\LirinFeatureLauncher.Tests.csproj -c Release
```

The current marker, snapshot, status, and feature-log files are shared. This
MVP therefore manages only one successfully injected PID at a time and warns
before replacing it with a different PID. During the first live UI test,
switch **Auto Reaction OFF** immediately after the v11 panel appears. It
defaults to ON, and the general Stop button does not disable it.

## Metin radius scanner feature

The first feature is implemented in `client_feature.py`. It opens an in-game
panel with Start and Stop, a radius field, recent scan messages, and a large
coordinate map with a radius ring, N/S/E/W labels, and nearby entity markers.
The default radius is 2500 game units. Every second while running, it checks visible characters for
metin stones within the selected radius. The optional Metin Hunter toggle adds
the nearest eligible stone to the client's existing metin queue, up to five
targets and no more than the client's current native capacity. Turning the
toggle off clears and disables the queue, releases the current attack/target,
and stops new additions. Stop applies the same cleanup. It also appends the scan output to
`metin_scanner.log` in this directory.

Anchor fixes the circle at the character's current world position. While
anchored, the map and hunter include only entities inside that fixed circle;
Unanchor makes the circle follow the character again. Left Ctrl+F8 hides or
opens the panel. Scanning continues while the panel is hidden. V7 adds the
client's movable panel flag so the title bar can be dragged.

Mark Boss stores the selected boss type and exact world position separately
from the Metin farming anchor. Boss Sweep watches the large-map timer, pauses
and clears the normal Metin queue, and uses a temporary one-target native queue
so the client chases the boss instead of swinging in place. It checks each
channel with one second of post-load settling and a three-second absence scan,
then returns to the original Metin channel and anchor. Return movement is
retried until the character is within 120 units or the 30-second timeout is
reached.

V10 adds Auto Reaction, ON by default. When the yin-yang themed reaction
window appears, it requests Start through that window and clicks each new lit
slot through the existing UI handler. It logs each action and pauses Boss Sweep
deadlines until the reaction window closes. Local behavior passed the mock;
live hit/score and attack resumption still need verification. The panel toggle
can turn this automation off.

V19 tightens native-queue safety. Hunter candidates must remain valid Metin
entities and stay within the selected radius of both the current player and
the fixed anchor immediately before admission. Stop and Hunter OFF now clear
and disable the native queue. Rejected VIDs are not remembered as queued, and
Boss Sweep relies on the one-target native queue instead of sending a separate
pre-queue target selection.

V20 fills the Hunter queue immediately on activation, up to the native capacity
and the five-target feature limit. After that initial fill it waits until the
queue has three or fewer entries and attempts one replacement per scan: 35%
at three entries, 70% at two, and 100% at one or zero. Queue sizes four and
five are left alone.

V21 separates reaction safety from automatic solving. The feature now watches
for a visible reaction window even when Auto Reaction is OFF. It immediately
clears/disables the native queue and releases attack/target state. OFF leaves
the challenge for manual completion; ON uses the existing Start/click handler.
Hunter is restored and refilled only after the reaction window closes. A Boss
attack interrupted by the reaction restarts through the normal boss-find path.

V22 is a one-shot Hunter diagnostic for the repeated remote disconnect. Hunter
adds one initial batch of up to five valid Metins, never replenishes that batch,
and automatically clears/disables itself after the native queue becomes empty.
This isolates initial queue processing from the repeated queue-add cadence.

V23 follows the client click path more closely. Each candidate must also pass
the exposed live `CanAttackInstance` check. Adds are serialized with a random
0.65-1.45 second delay instead of a same-frame burst. Once a batch is armed it
is never topped up; after the queue becomes completely empty, Hunter waits a
random 8-15 seconds before beginning another paced batch.

V24 removes the successful loader's no-longer-needed persistent window hook.
It also treats `net.SetPhaseWindow` correctly as phase-window registration,
ignores registrations whose window is `None`, avoids duplicate exit cleanup,
and does not clear a native queue or target during scanner-only Stop/exit when
Hunter, Boss Sweep, and reaction safety do not own active automation. Auto
Reaction behavior and Hunter batching are unchanged. Queue shutdown now also
uses the native enabled-to-disabled clear instead of issuing a second explicit
clear first.

V25 restores continuous Hunter refill: after the paced initial fill, queue
sizes 3/2/1 use 35/70/100 percent refill chances and zero refills immediately
when a candidate exists. It closes the verified actor-type difference from
manual queue admission by requiring the live actor to pass `chr.IsStone`, and
it observes the client's Python immune/untargetable VID setters before calling
the low-level queue binding. Queue-add logs now include millisecond
timestamps, pre/post sizes, and call duration, and Python `net.Disconnect`
calls record a bounded caller stack. These checks remove a concrete unsafe
admission path but are not proof of the remote-close cause. Exclusions already
present before injection, or changed only through native code, are not visible
to the observer. The later controlled Hunter tests kept Auto Reaction and Boss
Sweep off.

V26 removes the remaining verified difference between scripted and manual
queue admission. The stock Python `player.MetinQueueAdd` binding calls the
low-level queue insertion routine directly; a real actor click instead passes
through the native actor-click wrapper, which checks the live actor, the full
queue predicate, button mode, a global application state, duplicate handling,
and the 500 ms same-VID debounce. On the supported executable build, the
feature loader redirects that Python binding to the native actor-click wrapper
on the game's window/Python thread. Hunter also requires the actor's projected
point to be on screen as a conservative approximation of the preceding mouse
pick. If the exact wrapper cannot be installed, Hunter and Boss Sweep refuse to
start. The subsequent v26 live test ran substantially beyond every earlier
failure window without logout. That supports the bypass as the corrected
client defect, although it cannot independently prove server-side intent.

V26 then completed approximately 40 minutes 42 seconds of user-controlled
Hunter operation without a logout, including a final uninterrupted run of
about 24 minutes 14 seconds. V27 keeps the native wrapper and every actor/
queue safety check, but removes the extra camera projection restriction so an
eligible Metin does not require manual camera rotation. V27 also completed a
full eight-channel Boss Sweep and returned to the anchor before restoring the
paced Hunter queue. V28 removes the extra `Min` title-bar button and changes X
to hide the panel without stopping scanning, Hunter, or Boss Sweep. Left
Ctrl+F8 uses the same non-stopping hide/show behavior. V29 also checks the
current actor snapshot every 0.5 seconds while Boss Sweep waits, so a visible
marked boss starts a new sweep even when the map timer remains stale at zero.
V30 waits a fresh random 0.50-0.85 seconds after observing each Reaction Game
ball before clicking it. Boss Sweep now sends one return command and watches
for progress; after three seconds without meaningful progress, it restores
Hunter if the character is already inside the configured Metin circle. If the
character is outside the circle, it retries at that slower stall interval.
V31 recognizes any validated Metin whose case-insensitive name contains
`Legendary Metinstone`. While Hunter is ON and the stone is inside the current
circle/radius, it clears the ordinary queue and starts a one-target priority
queue through the native manual-click wrapper. After the priority VID has been
absent for 1.5 seconds, normal paced Hunter refill resumes. Reaction safety and
an active Boss Sweep retain priority over this event path.
V32 replaces v30's uniform Reaction delay with the user's measured manual
profile: 37 clean clicks from four standalone-recorder rounds. Each ball draws
one recorded clean latency plus random +/-25 ms jitter, clamped to 0.30-0.99
seconds. The measured clean profile has a 522 ms median, 539 ms mean, and about
658 ms p90. Three samples involving wrong clicks were deliberately excluded
because Auto Reaction does not intentionally click an incorrect slot.
V33 restores the conservative on-screen projection requirement for both
ordinary and Legendary Metin queue admission. When Hunter has at most two
queued targets, at least one eligible Metin remains inside the configured
circle, and none of those Metins is currently projected inside the client
window, the client-native `app.RotateCamera` control rotates the camera. A
10 Hz visibility check stops rotation as soon as an in-circle Metin becomes
visible and schedules an immediate scan. Rotation also stops for Hunter OFF,
Stop, Reaction safety, Boss Sweep, gameplay exit, or a queue above two. Each
search is capped at eight seconds and waits two seconds before retrying.
V34 corrects the first live camera-search defect: visibility from a stone that
is already in the native queue no longer suppresses rotation. Camera search
filters out every VID already admitted by Hunter and the active Legendary VID,
then asks whether any remaining unqueued in-circle target is visible. Thus a
visible current combat target can coexist with camera rotation searching for
the next target.

V35 removes the projected-on-screen admission filter and the entire camera
rotation/search path. It also replaces the partial native actor-click wrapper:
each Hunter/Boss queue request now resolves the live native actor, scopes it as
the character manager's picked actor, and executes the client's complete
mouse-state press/release handler before restoring the prior picker state. This
runs the higher client input/player/item/terrain gates that the v26-v34 wrapper
skipped. Continuous Hunter refill and the other automation modes are unchanged.
The implementation passes local regression and x64 build checks but still
requires a fresh Hunter-only live test; it is not yet a confirmed logout cure.

Auto Reaction has also completed a live Reaction Game: it requested Play,
clicked all five observed slots, detected the window closing, and ended the
safety pause without an error. That live v29 sequence used uniformly fast
53-55 ms clicks; v30's requested randomized timing has passed local tests but
still requires a fresh live Reaction Game. The isolated solver test had Hunter
and Boss Sweep OFF; manual-reaction testing separately verified Hunter
pause/restoration.

V16 adds Save, Load, and Auto-load controls. The local
`client_feature_config.txt` stores the radius, Metin anchor, boss identity and
exact position, and Auto Reaction preference. Auto-load restores only these
static settings; it never starts the scanner, Metin Hunter, Boss Sweep,
attacks, or channel changes.

Build the dedicated loader when changing its C++ code:

```powershell
& '.\dll_injection_test\build.ps1' -FeatureOnly
```

With Lirin open in the playable world, run this from administrator PowerShell:

```powershell
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_client_feature.ps1'
```

The runner accepts `-TargetPid <pid>` if needed and uses a fresh DLL filename
for each run. V4's map and entity snapshot ran in game, but the user found both
map axes reversed. V5 corrects the orientation and adds Metin Hunter. V6 adds
Anchor/Unanchor and the Left Ctrl+F8 panel toggle. V6's live log shows named
metin scans and queue additions; the user verified Ctrl+F8, but could not move
the panel. V7's dragging fix passed local checks and awaits an in-game retest.
V9's corrected Boss Sweep chase path passed local checks; its temporary
boss-queue chase and attack behavior remains unverified in game.
V10's Auto Reaction also awaits an in-game test.
V11 reduces main-thread work without changing the click decisions: it caches
the discovered reaction window, skips discovery while Auto Reaction is OFF,
backs missing-window discovery down to once every five seconds, updates the
player marker at 10 Hz, and polls active Boss Sweep states at 5 Hz. The normal
entity scan and bounded native snapshot remain at once per second.
See
`TEST_RESULTS.md` for the evidence and limits.

Target: `C:\Program Files (x86)\Lirin\app\Lirin.exe` (64-bit game process).
The installation-root `Lirin.exe` is a separate 32-bit launcher.

## References

- [MetinPythonLibV2-Rebuild](https://github.com/ikevin127/MetinPythonLibV2-Rebuild): useful design reference for a DLL that exposes functions to Metin2's Python runtime and runs a local `script.py`. Its published build uses a 32-bit GameForge client and 32-bit Python 2.7 dependencies; it cannot be loaded as-is into Lirin's 64-bit game.
- [uBot-Rebuild](https://github.com/ikevin127/uBot-Rebuild): example Python scripts that depend on that library's `eXLib` module. Its game-specific offsets, signatures, and bot features do not establish compatibility with Lirin.
- [cheatengine-mcp-launcher](https://github.com/ikevin127/cheatengine-mcp-launcher): optional live memory inspection tooling. It is not itself a DLL injector or a Python script loader.

## Probe project

- `build.ps1` builds the x64 `load_probe.dll` with Visual Studio.
- `inject.py <pid>` attempts to load it into the installed Lirin game process.
- `smoke_test.py` verifies the DLL and injector in a disposable x64 Python process.
- The DLL writes `load_probe.dll.loaded.txt` beside itself with the target PID when it loads.
- `python_loader.dll` uses native Python APIs mapped for this game build to run
  `python_probe.py`, recording each step in `python_loader.status.txt`.
- `run_python_test.ps1` selects the visible Lirin window and runs that test.

On 2026-10-12, the disposable-process test passed. A first attempt against
the game executable at the login menu (PID 20236) returned Windows error 5
(access denied). The same result occurred for a separate direct-launch
process (PID 9728). The user then ran `inject.py` from an administrator
PowerShell against the login-menu game process PID 20872. `LoadLibraryW`
returned success, and `load_probe.dll.loaded.txt` recorded PID 20872. This
confirms that the x64 DLL loaded inside Lirin.

The direct-launch PID 9728 did not present a normal main window. Attempts to
stop it and send it `WM_CLOSE` were also denied. It may require closing through
the game's own control or a suitably privileged process manager. Leave the
user's login-menu process alone when cleaning up the test process.

The EXE exports only the AMD/NVIDIA GPU selection variables; it does not
export Python APIs, and `python27.dll` is not in its static import table.
Ghidra reference and decompilation scans identified candidates for the GIL,
module access, and script execution functions. Do not assume GameForge
offsets, signatures, or `python27.dll` exports exist in Lirin.

## Python loader test

The mapped entry points are `PyGILState_Ensure` (RVA `0xAB1520`),
`PyGILState_Release` (`0xAB15D0`), `PyImport_AddModule` (`0xABED90`),
`PyModule_GetDict` (`0xAA9820`), and `PyRun_StringFlags` (`0xAB5E60`). The
last identification is supported by Lirin's own call with file-input flag
`0x101` and an inline Python function definition. The loader checks the
EXE timestamp and image size before using these addresses.

The x64 DLL compiled on 2026-10-12. A disposable-process test confirmed the
EXE mismatch guard. The first in-game test reached `waiting for Python GIL`
and produced no probe output. To reproduce it, open administrator PowerShell
with Lirin at the login menu:

```powershell
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_python_test.ps1'
```

Success requires both `Python script returned successfully` in the status
file for the current game PID and a nonempty probe output file containing a
Python version. The DLL can crash or hang the client if any inferred native
call signature is wrong. Rebuild only after the client is closed, since
Windows keeps loaded DLL files locked.

## Window-thread retry

The first in-game `python_loader.dll` test against PID 20872 reached
`waiting for Python GIL` and did not create `python_probe.loaded.txt`. The
worker did not report acquiring the interpreter lock; it may be blocked or
have failed inside that call.

`python_window_loader.dll` instead installs a temporary `WH_CALLWNDPROC`
hook on Lirin's visible window thread, sends a wake message, and checks that
this thread owns the current Python thread state before calling any Python
function. If that check fails, it logs `window thread does not own Python GIL;
call skipped`. The hook is removed after its one-shot callback.

The window hook was tested in a disposable x64 GUI process with a window named
Lirin. It fired, logged the DLL load, and stopped at the EXE build mismatch
guard. In the live Lirin process (PID 20872), it reported that the window
thread owned the Python GIL, acquired it, returned successfully from the
Python runner, and released it. However, `python_probe.loaded.txt` was created
as a zero-byte file and could not be read while the client held it open. This
does not establish that the probe's file-writing code completed.

`python_probe.py` now writes to `python_probe_v2.loaded.txt` using low-level
`os.open`, `os.write`, and `os.close`. `python_window_loader_v2.dll` is the
same tested DLL under a new filename, so Windows will execute its load path
again in the running client. `run_python_window_test_v2.ps1` reports only new
status lines for this attempt and prints the output file's byte length.
With the game at the login menu, run from administrator PowerShell:

```powershell
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_python_window_test_v2.ps1'
```

The script prints status lines for the current game PID and the probe output,
if any. The earlier worker thread may remain blocked until the game exits.

The user ran the v2 test against Lirin PID 20872 on 2026-10-12. The status
reported that the window thread owned and acquired the Python GIL, then that
the script returned successfully and the GIL was released. The new output file
contained 45 bytes: `Python version: 2.7.18` and `Loaded modules: 152`.
This verifies that our script executed inside the game's embedded Python
interpreter and wrote its output. It does not yet verify that arbitrary game
modules or API calls are safe or available in this context.

## Loaded-module inventory

The next read-only test snapshots `sys.modules` and writes each loaded module's
name, `__file__` path when present, and symbol count to
`python_modules_v3.tsv`. It does not import game modules or call game APIs.
The successful v2 script is preserved as `python_probe_v2.py`; the active
`python_probe.py` is now the inventory script. `python_window_loader_v3.dll`
has a new filename so its load path runs in the existing game process.
From administrator PowerShell with the game at the login menu:

```powershell
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_python_window_test_v3.ps1'
```

The runner prints status from this attempt and a short preview of the TSV.
PowerShell parsing, Python syntax, and a local inventory smoke test passed.
In Lirin PID 20872, the v3 Python call failed before creating the TSV. The
loader did not expose the Python exception, so the cause remains unknown.

The v3 script is preserved as `python_probe_v3.py`. The v4 script is preserved
as `python_probe_v4.py`; it uses plain byte-string formatting and records an
exception traceback in `python_probe_v4.error.txt` if it fails. A fresh DLL
filename, `python_window_loader_v4.dll`, ran it in the current process.
Its runner prints the status, inventory preview, and any traceback:

```powershell
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_python_window_test_v4.ps1'
```

The v4 PowerShell parse, Python syntax, and local inventory smoke test passed.
The live run also succeeded and wrote 158 module records. See
`TEST_RESULTS.md` for findings and the next test. The active `python_probe.py`
now takes a read-only module snapshot for the v6 in-game test. The v5 script
is preserved as `python_probe_v5.py`.

The v6 run also succeeded after entering a character: the snapshot contained
419 modules, including `game`, and the runner reported the process still
responsive immediately afterward. See `TEST_RESULTS.md` for the comparison
with the login-screen snapshot.

## Private launcher updater

See [setup, packaging, recovery, and validation](docs/LAUNCHER_UPDATER.md). The updater uses each user's GitHub authorization and supports portable installs in any folder outside a Git checkout. Live two-account verification is still pending.
