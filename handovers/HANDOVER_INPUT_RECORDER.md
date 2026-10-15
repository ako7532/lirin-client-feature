# Lirin Hunter logout — input-recorder finding (handover for the next chat)

Updated: 2026-10-15

## Read this first

This continues the investigation in:

`C:\Users\andrej-pc\Documents\projects\lirin-client-feature`

The long-running question was: **why does the automated "Metin Hunter" get
disconnected (remote close -> NewLoginWindow) after 3-15 minutes, while manual
play and a manual "Diag +1" button (synthetic add at human timing) stayed
connected for 30+ minutes?**

The decisive answer has now been found. The game records real mouse input, and
the feature's synthetic queue-add bypasses that recording.

## The finding

The client has a **mouse-input recorder** at global `DAT_147a6ba20`
(image RVA `0x07A6BA20`). Real mouse events are recorded into it from the
Windows mouse message handler. The synthetic `NativeMetinQueueAdd` wrapper
calls the internal mouse-state handler directly and never produces an input
record.

Evidence (decompiled in `C:\Users\andrej-pc\Documents\projects\decomp`):

- `input_recorder_trace/global_refs/1404fc620.c` is the raw Windows mouse
  message handler. For each real event it calls
  `FUN_140471b10(DAT_147a6ba20, code, x, y)` with codes:

  | Windows message | recorded code |
  | --- | --- |
  | `0x201` WM_LBUTTONDOWN | `1` |
  | `0x202` WM_LBUTTONUP | `2` |
  | `0x203` WM_LBUTTONDBLCLK | `3` |
  | `0x204` WM_RBUTTONDOWN | `4` |
  | `0x205` WM_RBUTTONUP | `5` |
  | `0x207` WM_MBUTTONDOWN | `6` |
  | `0x208` WM_MBUTTONUP | `7` |
  | `0x20A` WM_MOUSEWHEEL | `FUN_140471d20` |

- The **queue-change path is wired to this recorder**. Every add / clear /
  processor-pass / remove calls `FUN_1404710d0(DAT_147a6ba20)`:

  - `metin_queue_trace/1403e41a0.c`  (low-level `CPythonPlayer::MetinQueueAdd`)
  - `metin_queue_trace/1403e4300.c`  (queue clear)
  - `metin_queue_trace/1403e4400.c`  (queue processor)
  - `metin_queue_trace/1403e48e0.c`  (queue remove)

  `FUN_1404710d0` is a "dirty helper":

  ```c
  if (recorder[8] != 0)      // if the recorder is enabled
      recorder[0x90] = 1;    // mark it dirty (needs flush)
  ```

So: while the recorder is enabled, a queue change marks it dirty so its
recorded input log can be flushed and compared against the queue change.

## Why the button worked and the Hunter doesn't

- **"Diag +1" button (stable 30 min):** the user's physical click on the panel
  was a *real* mouse event -> passed through `1404fc620` -> recorded (code
  `1`/`2`). Every queue change had a real input record next to it, so the
  server saw "queue changed + a real click" -> legitimate.

- **Automated Hunter (logged out):** `NativeMetinQueueAdd` calls
  `0x1403E5940` directly and bypasses the Windows input handler entirely, so
  no `FUN_140471b10` record is produced. The queue changes with no input record
  behind them -> detected.

The recorder is off by default (observed `recorder_enabled=0`); it is almost
certainly enabled by the server when it wants to audit a player.

## Current working-tree state

- Branch `main`, HEAD `0ea318e` ("Route automation through full native input
  path", i.e. the committed v35).
- Uncommitted modifications (do not discard):
  - `client_feature.py` — `FEATURE_VERSION = 38`, time-driven refill, random
    target, scan jitter, "Diag +1" button + CSV logging.
  - `python_loader.cpp` — adds `RVA_INPUT_RECORDER = 0x07A6BA20` and an
    observe-only `LogQueueInputState(vid)` that logs the recorder state.
  - `test_client_feature_local.py` — updated for the new Hunter behavior.
- Untracked (preserve):
  - `HANDOVER_HUNTER_LOGOUT_V35.md` (the older, detailed v26-v35 history)
  - `ReactionTimingRecorder/`, `ReactionTimingRecorder.Tests/`
  - `metin_diag_adds.csv` (button-press log: index, wall_time, elapsed_s,
    gap_s, vid, vnum, name, dist_player, dist_center, queue_before,
    queue_after, size_grew, call_ms, result)

Current Hunter behavior (working tree):

- Random target (`random.choice` of eligible in-circle stones).
- Time-driven refill: once the queue is full, wait a random
  `HUNTER_REFILL_MIN..MAX` = `35.0..70.0` s, then burst-fill to 5.
- Burst gap `HUNTER_BURST_DELAY_MIN..MAX` = `0.70..2.50` s.
- Scan cadence jittered: `next_scan = now + random.uniform(0.85, 1.15)`.
- "Diag +1" button calls `DiagnosticManualAddOne` (one synthetic add at a time,
  human-paced) and appends to `metin_diag_adds.csv`.

## Key paths

- Repo: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`
- Feature source: `client_feature.py`
- Native loader/wrapper: `python_loader.cpp`
- Feature log: `metin_scanner.log`
- Loader status (incl. recorder diagnostics): `python_window_loader.status.txt`
- Decomp root: `C:\Users\andrej-pc\Documents\projects\decomp`
  - Input recorder trace: `decomp\input_recorder_trace\` (events.c, functions.c,
    global_refs\*.c, index.txt)
  - Queue trace: `decomp\metin_queue_trace\`
  - Picker trace: `decomp\native_picker_trace\`

Recorder struct offsets used by the diagnostic (validate these):

- offset `8` (byte): enabled flag
- offset `10` (WORD): sample_ms (observed `40`)
- offset `12` (WORD): flush_ms (observed `200`)
- offset `0x90` (byte): "dirty" flag (set by `FUN_1404710d0`)

Observed diagnostic lines look like:

```text
PID <n>: queue input diagnostic: tick=<t> vid=<v> recorder_enabled=0 sample_ms=40 flush_ms=200
```

## Already ruled out (history)

- Nearest-target selection (random still logged out).
- Whole-second click gaps (scan jitter made gaps non-integer; still logged out).
- High queue occupancy (drain-to-1 and drain-to-0 variants still logged out).
- Camera/inventory "activity" (client-local, no packets; no heartbeat/input-API
  or anti-cheat product found in the decompiled client).
- Injection / method-table patch alone (manual queue with injection was stable
  15-20 min).
- The synthetic click per se (the "Diag +1" button was stable 30 min).

## Next steps for the new chat

1. Trace the recorder's **full data flow**: how does it get enabled (server
   packet / command?), and how do its records reach the server? Find the code
   that reads the `0x90` dirty flag and sends the recorded input log (likely
   near `FUN_140471d20` / the flush path, `flush_ms=200`).
2. Validate the recorder struct offsets (`enabled@8`, `sample_ms@10`,
   `flush_ms@12`, `dirty@0x90`) against the decompiled functions
   (`FUN_1404710d0`, `FUN_140471b10`, `FUN_140471d20`, and the functions in
   `input_recorder_trace\functions.c`).
3. Determine exactly what the server checks (does each queue add require a
   recorded click? a click within what window?).

## Constraints and preferences

- This file is read-only context for the new chat; do not assume the user wants
  code changed just because it is described here.
- Preserve all uncommitted/untracked files listed above.
- The launcher was consolidated to a single build at
  `LirinFeatureLauncher\bin\Release\net8.0-windows\LirinFeatureLauncher.exe`
  (the duplicate `...\Release\updated` copy was deleted and the project rebuilt).
- Do not commit or push unless explicitly asked.
