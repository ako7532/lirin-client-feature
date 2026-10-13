# Lirin client injection test results

Target: `C:\Program Files (x86)\Lirin\app\Lirin.exe` (64-bit), tested at the
login screen and in the playable world on 2026-10-12. Live game PID for the
tests below: 20872.

| Test | Result observed in Lirin | Evidence | Status |
| --- | --- | --- | --- |
| `load_probe.dll` | `LoadLibraryW` returned success; DLL wrote target PID. | `load_probe.dll.loaded.txt` contains `20872`. | Passed |
| `python_loader.dll` | Initially stopped at `waiting for Python GIL`; later status shows GIL acquisition, script return, and release. | `python_loader.status.txt` | Delayed; worker timing uncertain |
| `python_window_loader.dll` (v1) | Window thread owned the Python GIL; Python runner returned successfully. Output file was initially zero bytes and locked. | `python_window_loader.status.txt`; `python_probe.loaded.txt` | Python call passed; initial file result ambiguous |
| `python_window_loader_v2.dll` | Python script returned and wrote a 45-byte probe: Python `2.7.18`, 152 loaded modules. | `python_window_loader.status.txt`; `python_probe_v2.loaded.txt` | Passed |
| `python_window_loader_v3.dll` | DLL loaded, GIL acquired, Python call failed, no inventory file. The client log records `LookupError: unknown encoding: utf-8` in `clean()`. | `python_window_loader.status.txt`; `app/logs/12-10-2026.log` | Failed; cause identified |
| `python_window_loader_v4.dll` | Python call returned successfully and wrote 158 module records (3,267 bytes) at the login screen. | `python_window_loader.status.txt`; `python_modules_v4.txt` | Passed |
| `python_window_loader_v5.dll` | Python call returned successfully and wrote 2,332 symbol records (94,755 bytes) across 14 selected modules. | `python_window_loader.status.txt`; `python_symbols_v5.txt` | Passed |
| `python_window_loader_v6.dll` | In the playable world, DLL loaded and Python returned successfully; report lists 419 modules, including `game`. Runner reported PID 20872 still running and responding immediately afterward. | `python_window_loader.status.txt`; `python_ingame_v6.txt` | Passed |
| Metin radius feature v1, local (2026-10-13) | Dedicated x64 feature loader and original one-shot window loader compiled; feature script passed a Python 3 syntax check and mocked lifecycle test covering radius filtering, scan path, circle creation/deletion, and file logging. PowerShell runner parsed successfully. | `client_feature_loader.dll`; `test_client_feature_local.py` | Local checks passed; embedded Python 2 and in-game behavior unverified |
| Metin radius feature v1, live attempt (2026-10-13) | Runner stopped before injection because no `Lirin` process was running in this session. No feature DLL was loaded into the game by this attempt. | `run_client_feature.ps1` returned `NoProcessFoundForGivenName` | Not run |
| Metin radius feature v1, PID 46844 (2026-10-13) | User confirmed the character was in the playable world. This session's medium-integrity process could see the PID but `OpenProcess` returned Windows error 5 before injection. PID 46844 remained responsive. No feature DLL or scan log was created by this attempt. | `run_client_feature.ps1 -TargetPid 46844`; `whoami /groups` | Blocked by Windows process access; retry from administrator PowerShell |
| Metin radius feature v1, user-run PID 46844 (2026-10-13) | Panel opened and Start/Stop worked. After Start, the log showed `client_feature_vids.txt` missing once per second; no metin list or ground circle appeared. Loader status reported successful Python execution. | `metin_scanner.log` at 07:56-07:57; `python_window_loader.status.txt` | UI passed; scan/circle failed |
| Metin radius feature v2, local fix (2026-10-13) | Ground effect update no longer depends on a successful entity scan. Added a panel radar circle with metin markers, snapshot/wake-thread diagnostics, and a reliable wake message. Dedicated x64 loader compiled and local panel/scanner test passed. | `client_feature.py`; `python_loader.cpp`; `test_client_feature_local.py` | Local checks passed; live retest pending |
| Metin radius feature v3, ground circle isolation (2026-10-13) | Start now attempts the ground circle immediately. Radius input and ground circle refresh run before and independently of the once-per-second entity scan. A mocked test confirmed the circle appeared and resized with no entity snapshot, persisted with a valid zero-entity snapshot, then logged metins when entities appeared. Python syntax check passed. PID 46844 was still responding when checked. | `client_feature.py`; `test_client_feature_local.py`; `python test_client_feature_local.py`; `python -m py_compile client_feature.py` | Local checks passed; ground effect visibility and entity snapshot in Lirin still need live retest |
| Metin radius feature v3, user-run PID 46844 (2026-10-13) | Panel and radius input worked, but no metin results or visible ground circle. Script logged `Ground circle: pvp_safe_zone_circle.mse`, which only confirms the effect API returned an ID. Every scan reported the snapshot file missing. Loader status ended at `feature wake thread started`; no snapshot or snapshot-error diagnostic appeared. | `metin_scanner.log` at 08:07-08:09; `python_window_loader.status.txt`; absent `client_feature_vids.txt` | UI passed; entity scan and ground rendering failed |
| Metin radius feature v4, local map and snapshot fix (2026-10-13) | Removed ground effect calls. Panel now draws a large coordinate map, a permanent radius ring, player center, metin markers, and other entity markers. Native snapshot writer now polls once per second from its own read-only thread, independent of later window-hook messages. Python mock test and syntax check passed; x64 feature DLL compiled. | `client_feature.py`; `python_loader.cpp`; `test_client_feature_local.py`; `build.ps1 -FeatureOnly` | Local checks passed; live map markers and snapshot still need retest |
| Metin radius feature v4, local live-load attempt (2026-10-13) | The runner selected PID 46844, but `OpenProcess` returned Windows error 5 before loading the new DLL. No v4 panel or snapshot was tested in game. The active marker was restored to the prior DLL name. The runner now restores that marker automatically after injector failure. | `run_client_feature.ps1 -TargetPid 46844`; `inject.py` traceback; unchanged loader status | Blocked by process access in this session; administrator PowerShell run needed |
| Metin radius feature v4, user-run PID 46844 (2026-10-13) | User reported the in-panel map looks great but both axes are reversed. Native `client_feature_vids.txt` is now updating; scanner log reported no metins within radius 1000 during the observed interval. No live target or queue behavior was established. | User report; `client_feature_vids.txt` at 08:18; `metin_scanner.log` at 08:17-08:18 | Map and snapshot working; orientation needs correction; target classification unverified |
| Metin radius feature v5, local hunter implementation (2026-10-13) | Inverted both map marker axes. Added a Metin Hunter toggle that enables the existing native metin queue, selects the nearest visible metin within the chosen radius, and adds at most one new target per scan while respecting both a five-target cap and the client's native capacity (which decompilation showed can be 3, 5, or 6). Turning the toggle off or stopping the panel leaves existing queue entries intact. Python mock tests checked map orientation, duplicate avoidance, 5 and 3 target caps, and file logging; syntax check passed. | `client_feature.py`; `test_client_feature_local.py`; `metin_queue_bindings.c`; `python test_client_feature_local.py` | Local checks passed; live queueing and combat need verification |
| Metin radius feature v6, anchored circle and hotkey (2026-10-13) | Added Anchor/Unanchor. When anchored, the circle center stays at the character's saved world position; map markers and Metin Hunter candidates are filtered against that fixed center while the character marker moves. When unanchored, the circle follows the character. Added a separate visible UI watcher that keeps scanning while the panel is hidden and toggles the panel on Left Ctrl+F8 key-down edge. A mock test checked anchored and following target selection, character marker motion, hidden scanning, and hotkey edge behavior; Python syntax check passed. | `client_feature.py`; `test_client_feature_local.py`; `python test_client_feature_local.py`; `python -m py_compile client_feature.py` | Local checks passed; live hotkey, anchor, queueing, and combat need verification |
| Metin radius feature v6, user-run PID 46844 (2026-10-13) | Loader reported Python success. The log recorded anchoring at world positions, one-second anchored scans of named Metin of Gorillas and Metin of Death stones, Metin Hunter ON with native queue limit 5, and successive `Queued` entries reaching 5/5 and later refilling to 5/5. It also recorded Left Ctrl+F8 panel minimize/open events; scans and queue additions continued while minimized. The user confirmed the hotkey works and reported the panel could not be moved. A single `Permission denied` read of the snapshot at 08:36:22 was transient. Some hotkey events at 08:39:05 occurred in quick succession. PID 46844 was still responding when inspected. These are client log observations; actual stone destruction and exact map/anchor visual behavior were not independently confirmed. | `metin_scanner.log` at 08:33-08:58; `python_window_loader.status.txt`; `client_feature_vids.txt`; process check; user report | Live scan and queue additions observed; hotkey user-verified; panel dragging failed; combat and map visuals unconfirmed |
| Metin radius feature v7, movable panel fix (2026-10-13) | Added the client's `movable` and `float` flags to the panel after `BoardWithTitleBar` initialization, and bumped the feature version so the next injection replaces the existing panel. Python syntax check and local feature lifecycle test passed. The mock cannot prove native window dragging. | `client_feature.py`; `python test_client_feature_local.py`; `python -m py_compile client_feature.py` | Local checks passed; title-bar dragging needs an in-game retest |
| Metin radius feature v8, local Boss Sweep implementation (2026-10-13) | Added Mark Boss and Boss Sweep controls. Marking saves the selected boss VNUM/name plus the character anchor, map, and current channel, then performs a non-combat runtime check for the timer, HP monitor, and channel count. When the atlas timer reaches zero, the state machine saves and pauses Metin Hunter, clears/disables the native Metin queue, requires a fresh 100% target-HP update, starts normal target/auto-attack and movement, confirms disappearance, and checks each channel through the existing move-channel dialog. After a channel load it waits one second; an absent boss is rescanned for three seconds before continuing. It returns to the original channel and anchor and restores the prior hunter/queue/mouse state. The mock covered runtime discovery, the full-HP gate, queue pause, attack start, channel timing, return, and restoration. Python 3 syntax and local mock tests passed; no Python 2 executable was installed for a separate offline compile. | `client_feature.py`; `test_client_feature_local.py`; `python -m py_compile dll_injection_test/client_feature.py dll_injection_test/test_client_feature_local.py`; `python dll_injection_test/test_client_feature_local.py` | Local checks passed; atlas timer lookup, HP hook, channel dialog, normal attack/movement, kill confirmation, and return require incremental live verification |
| Metin radius feature v9, boss chase correction (2026-10-13) | Live v8 changed channels and detected the full-HP boss, but setting its target and holding the normal attack key only swung in place. Replaced that engagement path with a cleared, temporary one-target native queue: explicitly allow the marked boss VNUM with `AddMetinQueueAllowedRace`, enable the queue, add the boss VID, verify its size increased, and clear/disable it before every channel change. | `client_feature.py`; `test_client_feature_local.py`; `python -m py_compile dll_injection_test/client_feature.py dll_injection_test/test_client_feature_local.py`; `python dll_injection_test/test_client_feature_local.py`; ASCII source check | Local compile and full mock passed, including one-target queue admission and queue shutdown before channel change; live chase/attack still required |
| Metin radius feature v10, Auto Reaction (2026-10-13) | Decompiled `uireactiongame` exposes `ReactionGameWindow`, Play and slot-click handlers, `activeSlot`, ball timing, and server start/click responses. The game binary contains a yin-yang reaction theme, separate from `uicaptcha` and yin-yang card games. Added an ON by default panel toggle that discovers a visible reaction window, requests Start once, clicks each newly active slot once through the existing UI handler, logs actions, and pauses Boss Sweep deadlines until the window closes. The mock checked start, one click per ball including a repeated slot, and closing/resume. Python syntax check passed. | `decompiled_all/modules/uireactiongame.c`; `input/LirinGame.exe` strings; `client_feature.py`; `test_client_feature_local.py`; local compile and mock commands | Local checks passed; live window discovery, slot timing, server hit/score, and attack resumption remain unverified |
| Metin radius feature v11, performance guards (2026-10-13) | Reduced work on the UI thread without changing reaction click decisions. Reaction discovery is skipped while OFF, missing-window discovery is limited to once per five seconds, and a discovered hidden window remains cached. Player/map refresh is limited to 10 Hz; Boss Sweep checks are 5 Hz while active and 2 Hz while waiting for its timer. Crowded scans stop requesting positions for ordinary entities once their marker pool is full. Native entity traversal remains capped at 4,096 with a one-second sleep. | `client_feature.py`; `python_loader.cpp`; `test_client_feature_local.py`; `python -m py_compile dll_injection_test/client_feature.py dll_injection_test/test_client_feature_local.py`; `python dll_injection_test/test_client_feature_local.py`; ASCII source check | Local compile and full mock passed, including disabled-discovery and cached-window regression checks; live frame-time behavior still required |

The v1 output file was later observed at 45 bytes, and the original worker
thread also eventually reported success. The available logs do not establish
exactly which delayed write completed the v1 file, so v2 remains the clear
proof of Python script execution and file output.

## V4 inventory findings

The login-screen inventory contains `newlogin`, `newloginwindow`,
`networkmodule`, `ServerStateChecker`, `app`, `net`, `player`, `ui`, and many
other client modules. `app` has 731 names, `net` 594, and `player` 673.
Most client modules report no `__file__` path; this inventory identifies live
modules but does not recover their source code. Some of the 158 modules may
have been loaded by earlier probes in the same process. The client log later
showed that v3 failed while decoding a byte string as UTF-8: its embedded
Python runtime reported `unknown encoding: utf-8`.

## V5 symbol findings

The login module exposes `NewLoginWindow`, `AccountWindow`, and several UI
classes. The network module exposes `MainStream` and `PopupDialog`. The
`system` module exposes `EterPackModuleFinder`, `EterPackModuleLoader`, and
`__hybrid_import`. The `pack` module exposes `Exist`, `Get`, and `LoadModule`.
The `__main__` namespace includes names left by our probes, so it is not a
clean list of original client globals. The live class names correspond to
functions in `decompiled_all/modules/newlogin.c` and
`decompiled_all/modules/networkmodule.c`. Symbol names and types establish
that those objects are present, but they do not establish method behavior.

## V6 in-game findings

The in-game snapshot lists 419 modules, versus 158 at the login screen. A
direct comparison found 261 new names and none removed. The added names
include `game`, `gamewindow`, `interfacemodule`, `uichat`, `uicharacter`, and
many other UI modules. The v6 run confirms that the same DLL-loading and
embedded-Python execution path worked after entering a character. The runner
checked only immediate process survival and responsiveness; it did not test
longer-term behavior or server-side enforcement.

## Reproduce the in-game test

After entering a character and reaching the playable world, leave the client
open and run this in administrator PowerShell:

```powershell
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_python_ingame_test_v6.ps1'
```

The runner accepts `-TargetPid <pid>` if it cannot select one Lirin process.
It uses a new DLL filename and writes `python_ingame_v6.txt` with the Python
version, module count, whether `game` is present, and all module names. It
also reports whether the process is still running immediately afterward.
This is a read-only script; it does not call game functions. The module
comparison above is against `python_modules_v4.txt` from the login screen.
Map the live class names and read-only properties to the Ghidra pseudocode
before calling game methods.

## Injection-check observations

The `LoadLibraryW` probe and v2, v4, and v5 Python runs succeeded in the
login-screen process, and PID 20872 was still running after v5. The inspected
top-level app files were the game EXE, BugSplat crash-reporting files, and
data directories; no separately named anti-cheat component was apparent in
that listing. Searches of the recovered module pseudocode and the 2026-10-12
client log found no explicit anti-cheat warning tied to these runs. These
observations do not establish that the client or server lacks integrity checks
or that later gameplay will accept injected code.

`EXE build matched` in the status output is our DLL's compatibility check,
not a client approval. The client log did capture the v3 script exception,
showing that in-client Python errors can be recorded even when the loader's
own status only says `Python call failed`.

## First feature: metin radius scanner

The selected feature is an in-game panel with Start and Stop buttons, an
editable radius (100-10000 game units), an eight-line debug display, a
one-second list of the metin types visible within that radius, and a local
coordinate map with a radius circle centered on the character. The same messages are appended to
`metin_scanner.log` beside the script. The native window hook takes a fresh
snapshot of visible entity IDs each second in `client_feature_vids.txt`; the
Python panel uses the client's read-only `chr`, `nonplayer`, and `player`
functions to classify and measure them. The feature does not send game or
network commands.

The native entity-map layout was checked against the decompiled character
bindings in `metin_feature_apis.c`. V3 proved the ground effect API returned
an ID but the user saw no ground circle. V4 uses a larger in-panel coordinate
map instead. Its circle is drawn by UI widgets and remains visible even when
there are no entities. The map is centered on the character; its background is
a coordinate grid, not terrain imagery. Markers require a valid entity snapshot.
The v3 snapshot writer did not run after the initial hook call, so v4 moves
the snapshot poll to a repeating native thread. Its live result is pending.

After opening Lirin and entering a character, run this in administrator
PowerShell:

```powershell
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_client_feature.ps1'
```

Use `-TargetPid <pid>` if several Lirin processes are present. The runner
copies the feature DLL under a new filename for each run, then prints the
loader status and tail of `metin_scanner.log`. Click Start in the panel. The
map circle represents the radius entered in the panel. The original v6 probe
script and its loader remain available separately.
