# Phase 1 — Static feasibility of a background input path

Date: 2026-10-16
Branch: `input-recorder-logout` (worktree)
Scope: planning/analysis only. No code, build, injection, or live test performed.

This document records the static investigation of whether the Lirin client supports a
**background** input path — one that reproduces a physical left click without moving the
real Windows cursor, stealing focus, changing OS button state, forcing focus flags,
changing recorder configuration, or fabricating telemetry.

Decompiled evidence lives in the decomp tree under `decomp/background_input_trace/`
(new, this session) and is cross-referenced against the existing
`decomp/input_recorder_trace/` and `decomp/metin_queue_trace/`.

Binary identity assumed throughout: game EXE SHA-256
`DBD69CAD070786DB754E893FEA4887A6D660D52AC19F9300257431D3636D72F2`, PE timestamp
`0x6ACA943D`, image size `0x094C1000`.

---

## 1. Summary conclusion

The client supports a **coordinate-pure dispatch chain**: the game's own down/up
dispatch, hit-testing, and world pick functions operate on passed-in screen
coordinates plus game-internal state, and never read the OS cursor, foreground window,
or physical button state. The input recorder already has an explicit **background
mode** (`DAT_147a734c0 + 0x20 == 0`) in which it derives held-button state from the
player object instead of `GetAsyncKeyState`.

A background route is therefore **feasible in principle**: drive
`FUN_1407e3e70(game, x, y)` + `FUN_1407e3fd0(game, x, y)` directly (bypassing the
window-procedure admission layer), with `x,y` being the target's projected client
coordinates. This is the path Phase 4 should build on.

The gate is **not yet fully demonstrated**: three items remain before the background
route can be declared verified (see §7). They are investigation work, not approved new
native entry points.

---

## 2. The verified physical click path (left button)

### 2.1 Window-procedure admission — `FUN_1404fc620`

`FUN_1404fc620` is the client's input WndProc. For `WM_LBUTTONDOWN` (`0x201`) it runs,
in order:

1. `FUN_1404a4120(DAT_147a6ba28)` — global setup.
2. `FUN_14048bcd0(0x201)` — **filter 1**: per-button down-state tracking plus a
   per-button rate limiter. It returns 0 (reject) when `DAT_1472f1a88` is set (a block
   flag, e.g. screenshot/suspend) after its checks. Internally it may drain the message
   queue (`PeekMessageW`/`DispatchMessageW`) and calls `FUN_14048c6a0`
   (lazy module-presence probe) and `FUN_140492700` (per-button 1001 ms rate limiter).
3. `FUN_14048c440(0x201, ...)` — **filter 2**. For mouse messages this is a no-op; it
   only acts on `WM_ACTIVATEAPP` (`0x1c`), where it calls `FUN_14048c490` — a
   `GetForegroundWindow()`/`GetWindowThreadProcessId()` focus check.
4. Capture management (`GetCapture`/`SetCapture`/`ReleaseCapture`) for capture-managed
   messages.
5. **Down gate** (the actual click admission):
   `FUN_1409bf660()` returns `DAT_147b7ea50 + 8`. The click proceeds only if
   `[+0xb8] == 0` (game-mode gate) AND `app[+0x20] != 0` (application-active flag) AND
   (`app[+0x7d7f8] == 0` OR re-check of the mode gate).
6. `FUN_1409f7680(...)` — an observer/consume hook (non-zero return consumes the
   message before game dispatch).
7. **Record down**: `FUN_140471b10(DAT_147a6ba20, 1, x, y)`.
8. **App down**: `app[+0x80468] = 1`; then `FUN_1407e3e70(DAT_147a6b480, x, y)`.

`WM_LBUTTONUP` (`0x202`) mirrors it: `FUN_140471b10(DAT_147a6ba20, 2, x, y)`,
`app[+0x80468] = 0`, then `FUN_1407e3fd0(DAT_147a6b480, x, y)`.

`x`/`y` come from the message's `lParam` (`sVar3`/`sVar4`), i.e. client-area screen
coordinates of the physical cursor — **not** a world coordinate.

### 2.2 Game down dispatch — `FUN_1407e3e70(game, x, y)`

1. `FUN_1407e4ea0(game)` — pre-click UI bookkeeping.
2. Store raw `x,y` at `game[+0x28/+0x2c]`; compute normalized client coordinates into
   `game[+0x20/+0x24]`:
   `nx = (x - game[+0x30]) * game[+0x08] / game[+0x1c]`,
   `ny = (y - game[+0x34]) * game[+0x0c] / game[+0x18]`.
3. `FUN_1407e68d0(game, nx, ny)` — **UI hit-test**: walks the element list
   (`game[+0xe8]`, then `game[+0x100]`) and returns the element whose bounds contain
   `(nx, ny)` via `FUN_1407f7ef0`/`FUN_1407fe020` (point-in-bounds tests).
4. Hover-object update: set `game[+0xa0]` to the picked element, call the previous
   element's leave (`vtable +0x80`) and the new element's enter (`vtable +0x78`).
5. Pressed-object tracking: if `picked[+0x13] & 0x80 == 0`, record `game[+0xb0] =
   picked` (with modal-child traversal via `FUN_1407f7d30` when `picked[+0x13] & 0x10`).
6. `FUN_1407f7b80` + `FUN_1408020e0` — child-space coordinate transform (scales `x,y`
   into the element's local space when `element[+0x114] > 0`).
7. `FUN_1405fc300(element)` returns `element + 0x74` (a world/position vector); the
   client stores the pick offset at `game[+0x38/+0x3c]`.
8. Invoke the picked element's **OnMouseDown** virtual method (`vtable +0xf0`), returning
   whether it was handled.

### 2.3 Game up dispatch — `FUN_1407e3fd0(game, x, y)`

1. Early-return gate on `game[+0x48/+0x4c]` using `timeGetTime()` (release debounce).
2. Recompute normalized coordinates as in down.
3. If a pressed object is tracked (`game[+0xb0]`), call its **OnMouseUp**
   (`vtable +0xf8`); otherwise re-pick (`FUN_1407e68d0`) and call the picked element's
   `vtable +0xf8`.

### 2.4 Player press → action — `FUN_1403e5940` → `FUN_1403ec0f0`

`FUN_1403e5940(player, press, param3)` is the player-level press/release:

- `FUN_1403d1da0()` resolves a global actor/manager object.
- Gates: `FUN_1403d0670`, `FUN_14049f570`, `FUN_1403d78b0` (returns `player[+0x42a0]`),
  `FUN_1404a0980`.
- **Press** (`press == 1`): `player[+0xff] = 1`, then `FUN_1403ec0f0(player, global,
  param3)`.
- **Release** (`press == 0`): `player[+0xff] = 0`, then `FUN_1403ebb30(...)`.

`FUN_1403ec0f0(player, global, param3)` is the click-action router:

- Early-return if `player[+0xe8]`.
- Reads the game's internal cursor via `FUN_1407e13b0` (`game[+0x20/+0x24]`).
- Item/actor/ground picks: `FUN_1403d7620`, `FUN_1403d75a0`, `FUN_1403d75e0`.
- **Actor hit-test** `FUN_140455b30`: iterates the character-manager actor tree, projects
  each actor to a screen rect, and hit-tests the cursor against it; returns the VID of
  the actor under the cursor.
- Routes: item action (`FUN_1403e4d70` etc.); a newly-picked actor VID reaches
  `FUN_1403ebdd0` (the queue duplicate/remove gate); ground reaches
  `FUN_1403e4300`/`FUN_1403eb4b0`.

Cross-reference (from `metin_queue_trace/index.txt`): `FUN_1403e5940` calls
`FUN_1403ec0f0`; `FUN_1403ec0f0` calls `FUN_1403ebdd0`; `FUN_1403ebdd0` reaches the
queue add `FUN_1403e41a0`.

### 2.5 Input recorder internals

- `FUN_140471b10(recorder, code, x, y)` — record a click sample; no-op unless
  `recorder[+8]` is set. Builds a snapshot (`FUN_1404704b0`) and appends/aggregates it
  (`FUN_140471b80`).
- `FUN_1404704b0` — builds the snapshot. **Background branch** (§3) is the key finding.
- `FUN_140471b80` — aggregates an identical consecutive snapshot (increments a counter)
  or appends a new one with a timestamp; flushes at > 0x3f entries.
- `FUN_140472870` — periodic tick: code-0 samples, queue-list send (`FUN_1404729b0`),
  and flush (`FUN_140470be0`).
- `FUN_1404729b0` — on dirty (`recorder[+0x90]`), copies the queue VID list and sends it
  via `FUN_14037a6c0`.
- `FUN_140470be0` — flushes input records via `FUN_14037a730`.
- `FUN_1404720c0` — recorder configuration (enabled flag, sample_ms default 100,
  flush_ms default 200). `FUN_1403ba7b0` is a thin config-adapter wrapper around it.

---

## 3. The client's existing background mode (key finding)

`FUN_1404704b0` (snapshot builder) reads `DAT_147a734c0 + 0x20`:

- **`== 0` (background/unfocused)**: held-button state is derived from the player
  object — `player[+0xff]` (left) / `player[+0x100]` (right). `GetAsyncKeyState` is
  **not** called.
- **`!= 0` (foreground)**: held-button state is read from `GetAsyncKeyState(VK_LBUTTON)`
  etc.

`FUN_1404720c0` stores this flag at `recorder[+0x98]`, and `FUN_140471130` detects
transitions of it. The recorder therefore already distinguishes background from
foreground and, in background mode, does not touch OS key state.

This is a verified branch in the code, not yet a fully explained focus model. Writers of
`DAT_147a734c0 + 0x20` have not yet been enumerated (see §7.2).

---

## 4. Coordinate-purity of the dispatch chain

Every function on the post-admission dispatch path is **coordinate-pure** — it uses
passed-in `x,y` plus game-internal state and performs no OS cursor/focus/button reads:

| Function | Role | OS-state reads |
| --- | --- | --- |
| `FUN_1407e3e70` | down dispatch | none |
| `FUN_1407e3fd0` | up dispatch | `timeGetTime()` only (timer) |
| `FUN_1407e68d0` | UI hit-test | none |
| `FUN_140455b30` | actor projection + hit-test | none |
| `FUN_1407f7ef0` / `FUN_1407fe020` | point-in-bounds | none |
| `FUN_1408020e0` | child-space coordinate transform | none |
| `FUN_1407e13b0` | cursor getter (`game[+0x20/+0x24]`) | none |
| `FUN_1403e5940` | player press/release | none |
| `FUN_1403ec0f0` | click-action router | none |

OS-touching calls exist **only in the WndProc admission layer** (`FUN_1404fc620`):
`GetCapture`/`SetCapture`/`ReleaseCapture`, `PeekMessageW`/`DispatchMessageW`, and
(via filter 2) `GetForegroundWindow` for the `WM_ACTIVATEAPP` path. `GetAsyncKeyState`
appears only in the recorder snapshot's foreground branch. None of these are on the
dispatch path that `FUN_1407e3e70`/`FUN_1407e3fd0` traverse.

---

## 5. Candidate background route

Drive the verified dispatch directly (game thread / window thread, GIL-owned), without
any Windows mouse message:

1. Compute the target's client coordinates `(x, y)` from its world position using the
   client's own projection (see §7.3 — the forward projection still needs to be located;
   `FUN_140455b30` is the inverse, screen→actor).
2. `FUN_1407e3e70(game, x, y)` — full down dispatch (pick → OnMouseDown → player press →
   action → queue add).
3. `FUN_1407e3fd0(game, x, y)` — full up dispatch (OnMouseUp → release).

The recorder down/up records that the physical WndProc emits (`FUN_140471b10` with code
1/2) sit in the admission layer, not in `FUN_1407e3e70`/`FUN_1407e3fd0`. Whether the
background adapter must emit them itself, and how that reconciles with Phase 4's "no
synthetic recorder calls", is an open design point recorded in §7.4.

---

## 6. What this contradicts in the earlier review

- The dispatch path is **not** gated on the foreground window for mouse messages: the
  focus check (`FUN_14048c490`) runs only on `WM_ACTIVATEAPP`. The mouse down gate is a
  game-mode flag (`FUN_1409bf660()+0xb8`) plus an application-active flag (`app[+0x20]`).
- `FUN_1407e13b0` is confirmed as a **cursor-coordinate getter** (`game[+0x20/+0x24]`),
  not a world↔screen projection.
- `FUN_140455b30` is the actor→screen projection used for the **pick** (screen→actor),
  confirming a projection exists and implying a forward (world→screen) counterpart.

---

## 7. Remaining Phase 1 investigation (gate not yet closed)

1. **Viewport OnMouseDown identity.** `FUN_1407e3e70` calls the picked element's
   `vtable +0xf0`. The exact implementation for the game-world viewport — and its
   confirmation that it reaches `FUN_1403e5940` — has not been traced. This is the one
   unverified hop between the down dispatch and the player press, and the place where a
   focus/mode dependency could still hide.
2. **Writers of `DAT_147a734c0 + 0x20`.** Needed to characterize "unfocused" vs
   "minimized" and to confirm the flag is a property of window activation rather than
   something the adapter must not force.
3. **Forward world→screen projection.** `FUN_140455b30` does screen→actor; the inverse
   (world position → client `x,y`) must be located so the background route can compute
   target coordinates without touching the OS cursor.
4. **Recorder down/up records.** The physical WndProc emits `FUN_140471b10` code 1/2
   around the dispatch. Decide whether the background adapter reproduces those (as the
   physical path does) or relies on the recorder's background snapshot, and reconcile
   with the Phase 4 constraint against synthetic recorder calls.

---

## 8. Files produced this session (decomp tree, not committed)

- `decomp/background_input_trace/*.c` — decompiled: `1407e3e70`, `1407e3fd0`,
  `1407e13b0`, `1409bf660`, `14048bcd0`, `14048c440`, `1409f7680`, `140471b80`,
  `1403ba7b0`, `1407e68d0`, `140455b30`, `1407e4ea0`, `14048c6a0`, `14048c490`,
  `140492700`, `1407f7d30`, `1407f7b80`, `1405fc300`, `1408020e0`.
- `decomp/run_background_input_trace.py`, `decomp/run_background_input_trace2.py` —
  reproducible PyGhidra runners.

---

## 9. Gap closure (continued)

### 9.1 Viewport OnMouseDown hop (was §7.1)

The press chain is confirmed by xref: `FUN_1403e5940` (`CPythonPlayer::SetMouseState`)
→ `FUN_1403ec0f0` (click-action router) → `FUN_1403ebdd0` (queue duplicate/add) →
`FUN_1403e41a0` (queue add). `FUN_1403e5940`'s only **direct** code callers are the
Python `player.SetMouseState` binding (`FUN_1403f8190`, cases 0 and 5) and
`FUN_1403ec0f0`'s own release call. It is also present in a `.rdata` slot at
`1492157b8` (adjacent to `FUN_1403e5280` at `149215770`, a per-frame "mouse held →
`FUN_1403ec0f0`" updater), so the physical viewport OnMouseDown reaches the press via an
indirect (vtable) call. The wrapper's direct `FUN_1403e5940` call is therefore the same
function the physical path reaches; the wrapper only skips the UI-element pick that
tracks the pressed object (`game[+0xb0]`).

### 9.2 Background-mode flag (was §7.2)

`DAT_147a734c0 + 0x20` is read (never written) by every referencing function in the
recorder/input set; only a `.rdata` slot references its absolute address (`147a734e0`).
It is the **app-active/focus flag**: `0` = unfocused/background (recorder derives button
state from player `+0xff/+0x100`), non-zero = focused (`GetAsyncKeyState`). It does **not**
distinguish minimized from merely-unfocused (both leave it `0`); a minimized check would
need window visibility/iconic state, which is not captured by this flag.

### 9.3 Recorder `+0x9C/+0xA0` writers

Four writers, all inside the recorder module: `FUN_140471d20`, `FUN_140471920`,
`FUN_140472870` (foreground branch, refreshed from `FUN_1407e13b0`), and
`FUN_1404720c0` (setup, zeroes the pair).

### 9.4 Cursor refresh ordering

`game[+0x20/+0x24]` (the client cursor) is written by `FUN_1407e3e70`/`FUN_1407e3fd0`
on mouse down/up. The recorder's periodic tick `FUN_140472870` reads those values in
foreground mode, or the stored `+0x9c/+0xa0` in background mode, for its code-0 samples.

### 9.5 Config-adapter caller

`FUN_1403ba7b0` has **no direct code caller**; it is referenced only from a `.rdata`
slot at `149212c80` (a method/callback table). It is a table-registered recorder-config
adapter (wrapping `FUN_1404720c0`), not a server-audit command path.
