# Handover: Metin Lirin client feature

Workspace: `C:\Users\andrej-pc\Documents\projects\decomp` on Windows.
Read this file and `dll_injection_test/TEST_RESULTS.md` before changing the
feature. This is the user's **Metin Lirin client feature**, not a server
project. The target is the 64-bit game at
`C:\Program Files (x86)\Lirin\app\Lirin.exe`; the installation-root
`Lirin.exe` is a separate 32-bit Tauri launcher. Analysis uses the copied
binary `input/LirinGame.exe`; installed game files have not been modified.

The current feature is **v11** in `dll_injection_test/client_feature.py`. It
opens an in-game panel with Start/Stop, radius 100-10000, an eight-line debug
view, a coordinate map, an always visible radius ring, character and entity
markers, Metin Hunter ON/OFF, Anchor/Unanchor, and Boss Sweep controls. It logs each scan and
feature event in `dll_injection_test/metin_scanner.log`. Left Ctrl+F8 hides or
opens the panel; a separate UI watcher keeps scanning while it is hidden.
V10 adds an Auto Reaction toggle, ON by default, for the yin-yang themed
reaction prompt. It uses the existing reaction window's Play and slot-click
handlers, clicks each new `activeSlot` once, and pauses Boss Sweep deadlines
until that window closes. Its behavior passed a local mock; server hits,
completion, and resumed attacks have not been verified in game.
V11 adds performance guards without changing reaction click decisions. A
discovered reaction window remains cached, missing-window discovery is skipped
while Auto Reaction is OFF and otherwise runs at most once every five seconds,
player/map position refresh runs at 10 Hz, and Boss Sweep state polling runs at
5 Hz (2 Hz while only waiting on the timer). The normal scan and bounded native
snapshot remain once per second.
V7 adds the client's `movable` and `float` flags so the panel can be dragged
by its title bar. V9 contains the Boss Sweep
state machine. Mark Boss requires a selected boss and saves its VNUM/name plus
the character's anchor position, map, and channel. Boss Sweep watches the
large-map cursed-boss timer, pauses and clears the normal Metin queue, requires a
fresh 100% target-HP reading, then calls `AddMetinQueueAllowedRace` and creates a
temporary one-target native queue for the marked VID so the native engine chases
and attacks it. The old target plus attack-key path was removed after a live test
showed that it only swung in place. The temporary queue is cleared and disabled
before every channel change. The state machine checks all channels through the
existing channel dialog, then returns to the
saved channel and anchor and restores the previous Hunter/queue/mouse state.
It waits one second after a verified channel load and scans an absent boss for
three seconds before changing again. Local checks pass; the corrected temporary
boss-queue chase still needs incremental in-game verification.
The ground effect approach was abandoned because the API returned an ID but
the user saw no circle on the ground. The in-panel map uses a coordinate grid,
not terrain imagery.

**Live state as of 2026-10-13:** The user reported the v4 map looked good but
both marker axes were reversed; v5 inverted them. The user then ran v6 in
game PID 46844. The live log shows anchored scans, named metin stones, native
queue additions reaching 5/5 and refilling, and Ctrl+F8 minimize/open events.
The user confirmed Ctrl+F8 works but reported the v6 panel could not move.
Scans and queue additions continued while minimized. The log does not prove
that the character destroyed stones or that the corrected map orientation
looked right; ask for those observations only after reviewing current logs.
One snapshot read returned transient `Permission denied` at 08:36:22, then
scans resumed. Several Ctrl+F8 events occurred close together at 08:39:05;
investigate only if the user sees unwanted repeat toggles.

## What was recovered from the client

- `STATUS.md` records 404 retained script paths and 19,097 qualified names
  across 235 modules. 18,299 names map to at least one Ghidra function;
  26,003 distinct game function pseudocode files were exported. There are
  759 failed game-function addresses and 364 names without a Ghidra function
  reference. These counts are analysis coverage, not original source recovery.
- The game EXE is about 131 MB and embeds Python 2.7 plus compiled Cython
  game logic. `decompiled_all/modules/` has grouped C-like pseudocode for
  235 inferred modules; `decompiled_all/functions/` has individual exports.
  `recovered_index/` maps retained filenames and qualified names to code.
  Useful starting points include `newlogin.c`, `networkmodule.c`, and the
  module matching the selected feature.
- The installation has 27 custom asset packs. The likely script/layout packs
  `root`, `lib`, and `ui` are **not decoded**. Their original Python files and
  UI layouts are not available; do not claim that every client file was
  decompiled. `PACKS.md` explains the inspected format and uncertainty.
- The launcher frontend was recovered separately under `recovered_launcher/`.
  It is distinct from the game runtime targeted by this feature project.
- The client's Python modules visible at login include `newlogin`,
  `networkmodule`, `system`, `pack`, `app`, `net`, `player`, and `ui`. The live
  symbol list shows `newlogin.NewLoginWindow`,
  `networkmodule.MainStream`, `system.EterPackModuleFinder`, and
  `pack.Get`/`pack.LoadModule`. After entering the game, modules including
  `game`, `gamewindow`, `interfacemodule`, `uichat`, and `uicharacter` appear.
  Live names show what is present; read the pseudocode and test before
  assuming signatures or behavior.

## Verified execution

- `dll_injection_test/inject.py` loads an x64 DLL into the game through
  `LoadLibraryW`. The user runs the PowerShell scripts from **administrator
  PowerShell**; a non-elevated process got access denied.
- `dll_injection_test/python_loader.cpp`, compiled with `USE_WINDOW_HOOK`,
  installs a one-shot hook on the visible window titled `Lirin` and executes
  `dll_injection_test/python_probe.py` inside the game's embedded Python 2.7
  runtime. It checks the EXE build before using mapped native API addresses.
- Login-screen v2 successfully wrote `Python version: 2.7.18` and reported
  152 modules. V4 listed 158 loaded modules. V5 listed 2,332 symbols from
  14 selected modules.
- **In-game v6 succeeded after the user entered a character.** Its status
  reports DLL load, GIL acquisition, Python script success, and GIL release.
  `python_ingame_v6.txt` lists 419 modules, including `game`. The runner
  reported game PID 20872 still running and responding immediately afterward.
  Compared with the login snapshot, 261 module names were added and none
  removed. This confirms in-game Python execution; it does not prove that
  every game API call is safe or that later server checks are absent.
- `dll_injection_test/TEST_RESULTS.md` has the full chronological evidence.

## Useful files

- `dll_injection_test/README.md`: project and loader explanation.
- `dll_injection_test/TEST_RESULTS.md`: test results and limits.
- Root `README.md`, `STATUS.md`, `PACKS.md`, `AUTO_HUNT.md`, and
  `NETWORK_MODULE.md`: decompilation overview and code pointers.
- `dll_injection_test/python_loader.cpp`: native loader and window-thread hook.
- `dll_injection_test/inject.py`: process/path-checked injector.
- `dll_injection_test/client_feature.py`: current v11 panel, scanner, map,
  Hunter, Anchor, Boss Sweep, hotkey watcher, and disk log.
- `dll_injection_test/test_client_feature_local.py`: local feature checks.
- `dll_injection_test/client_feature_loader.dll` and
  `run_client_feature.ps1`: dedicated loader and live runner.
- `dll_injection_test/metin_feature_apis.c` and `metin_queue_bindings.c`:
  native binding pseudocode used to check entity access and queue behavior.
- `dll_injection_test/metin_scanner.log`, `client_feature_vids.txt`,
  `python_window_loader.status.txt`, and `client_feature_active.txt`: scan
  events, entity snapshot, loader status, and active DLL marker.
- `dll_injection_test/python_probe.py` and
  `run_python_ingame_test_v6.ps1`: earlier read-only runtime probes.
- `dll_injection_test/python_modules_v4.txt`, `python_symbols_v5.txt`, and
  `python_ingame_v6.txt`: live module/symbol inventories.
- `decompiled_all/modules/newlogin.c`, `networkmodule.c`, and other module
  files: Ghidra C-like pseudocode for compiled client logic.
- `dll_injection_test/references/`: cloned uBot-Rebuild,
  MetinPythonLibV2-Rebuild, and cheatengine-mcp-launcher repos. Their offsets
  and 32-bit assumptions are not Lirin-specific.
- `dll_injection_test/HANDOVER_FEATURE.md`: this document.

## How this feature runs

`client_feature_loader.dll` is the dedicated x64 loader built from
`python_loader.cpp` with the feature-script option. Its one-shot window hook
runs `client_feature.py` on the game window thread in the embedded Python 2.7
runtime. A native background thread writes visible entity IDs each second to
`client_feature_vids.txt`; the Python feature checks that snapshot's PID and
age, classifies entities with `chr` and `nonplayer`, and optionally adds a
candidate through the existing `player.MetinQueueAdd` binding. The queue is
limited to five entries or the client's smaller current native capacity.
The separate older probe loader reads `python_probe.py`; do not confuse it
with the feature loader.

Each runner invocation copies the prebuilt feature DLL to a unique name and
sets `client_feature_active.txt`. Old native poll threads stop when that
marker changes. The feature version controls replacement of an old panel in
the Python runtime; bump it for new panel behavior. Code-only changes to
`client_feature.py` need no C++ rebuild. After `python_loader.cpp` changes,
run `& '.\dll_injection_test\build.ps1' -FeatureOnly` from the workspace.

Use Python 2.7-compatible code. An earlier probe hit `LookupError: unknown
encoding: utf-8`; low-level ASCII `os.open`/`os.write` logging worked.
The hook expects a visible window titled `Lirin`. The injector checks that
the selected process image is the 64-bit game executable. This session's
medium-integrity attempts got `OpenProcess` error 5, so the user runs the
loader from administrator PowerShell. If injection fails, the runner restores
the previous active marker. `EXE build matched` is the loader's compatibility
guard, not evidence of game or server approval.

## Immediate next test

V11 is locally checked but has **not** been injected into the live game. First
confirm the current PID, because PID 46844 may change. With a character in
the playable world, run from administrator PowerShell:

```powershell
Get-Process Lirin | Select-Object Id,MainWindowTitle,Responding
& 'C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\run_client_feature.ps1' -TargetPid <current PID>
```

First retest panel dragging, Ctrl+F8, and ordinary scanning. When the reaction
prompt appears, watch for `Reaction game visible`, `start requested`, and
`clicked slot` lines in `metin_scanner.log`; compare them with visible circle
glows and the game's hit/score display. Confirm the reaction window closes
and attacks resume. Turn Auto Reaction OFF if it selects the wrong circle.
The code path is grounded in `decompiled_all/modules/uireactiongame.c` and
binary strings showing the yin-yang reaction theme and
`SendReactionGameStart`/`SendReactionGameClick`. This is distinct from the
client's `uicaptcha` and yin-yang card minigames. For Boss Sweep,
use an incremental controlled test: open the M atlas so its boss panel exists,
select the intended boss, click Mark Boss, and verify the log records the
correct name/VNUM, coordinates, map, and original channel. Do not turn Boss
Sweep ON until that evidence is correct. The next live step should verify only
that the timer, target-board HP monitor, and channel dialog objects are found;
normal attack, channel rotation, and return movement remain unverified. The
local checks are:

```powershell
python dll_injection_test/test_client_feature_local.py
python -m py_compile dll_injection_test/client_feature.py
```

Read `metin_scanner.log`, `python_window_loader.status.txt`, and
`client_feature_vids.txt` for exact evidence, then append a row to
`TEST_RESULTS.md`. Queue-addition log entries do not prove that the character
actually attacked or destroyed stones. Ask the user about real combat, the
corrected map orientation, and the anchored circle's visual behavior after
reviewing the new run. The radius ring on the UI map is independent of
entities; the abandoned ground effect should not be retried by default.

## Suggested first message in the new chat

> Please read `C:\Users\andrej-pc\Documents\projects\decomp\dll_injection_test\HANDOVER_FEATURE.md`
> and `TEST_RESULTS.md`. Continue my Metin Lirin client feature. V6 ran in
> game: Ctrl+F8 works, scans and queue additions appeared in the log, but the
> panel could not be moved. V9 has a Boss Sweep with a temporary native queue;
> its corrected chase remains unverified live. V10 adds Auto Reaction for the
> yin-yang themed reaction prompt, using the client's own Play and slot-click
> handlers. Test the prompt's start, glowing-slot clicks, completion, and
> attack resumption in game, and update the test log from exact evidence.
