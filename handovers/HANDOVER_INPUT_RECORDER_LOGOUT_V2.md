# Handover — Input recorder / logout: current status and next investigation

Date: 2026-10-16
Branch: `fix-duel-stuck` (== `main` at `94c60df`)
Feature: Lirin (Metin2-like), embedded Python 2.7.

This is a **continuation** handover. The original handover is
`handovers/HANDOVER_INPUT_RECORDER_LOGOUT.md`; the static-analysis notes are
`INPUT_RECORDER_BACKGROUND_PATH_PHASE1.md` (both in the repo).

> **Read this first.** An independent review of the release-2 logout exists at
> `decomp/LOGOUT_RELEASE2_REVIEW_20261016.md` (in the separate `decomp` tree, not
> this repo). It found several defects that **supersede** parts of this handover;
> see §8. The two most important: (a) the new dispatch can **silently fall back**
> to the old picker-override route when the projection fails, so "queue adds
> succeeded" does **not** prove the new route ran; (b) the `bg=` diagnostic added
> in `3e4069e` has a **pointer bug** and would report the wrong byte.

---

## 1. TL;DR for the next chat

The client has a mouse-input recorder that the server can enable (audit mode,
`sample_ms=40`) and, apparently, compare queue changes against. The feature adds
Metins to the queue synthetically; the goal was to make those synthetic clicks
faithful to a physical click so the server does not remote-disconnect.

Work so far (this branch) made the world-queue add go through the client's real
mouse dispatch, with projected screen coordinates. **It works functionally — the
Hunter queues Metins successfully — but the logout STILL occurs.** The single
most important open question is: was the recorder in **background** or
**foreground** mode during the audit window, because that decides whether the
button-state in the recorder snapshot was consistent or not. A diagnostic was
added for this (`bg=`), but the logout run that was just observed used an older
release **without** that diagnostic. **The next run must use a release that
includes commit `3e4069e`.**

---

## 2. What has been implemented (all on `main`)

| Commit | What |
| --- | --- |
| `ac938fe` | Phase 3 wrapper correctness (ownership guard, VID-membership check, membership ack, exception-safe cleanup) + **world dispatch** via `1407e3e70`/`1407e3fd0` |
| `bbb1adc` | Phase 1 gap-closure notes (OnMouseDown hop, focus flag, recorder writers, projection) |
| `40cc85e` | UI-click primitive + UI adapters (reaction/duel) — **later reverted** |
| `8c6a797` | `NativeActionCoordinator` state machine + full wiring |
| `35117b8` | Fix: `QueueVectorValid` rejected the empty queue (every add skipped) |
| `a67e96e` | **Revert** the UI-adapter dispatch (reaction/duel) — the `GetGlobalPosition`-based click missed the control |
| `3e4069e` | Add `bg=<DAT_147a734c0+0x20>` to the per-add diagnostic |
| `94c60df` | Close the Yin-Yang Duel result screen after a match |

The world adapter (`MetinQueueAdd(vid, x, y)` → `DispatchClickAt` →
`1407e3e70`/`1407e3fd0`, with coords from `player.GetProjectPosition(vid,
PROJECT_CLICK_HEIGHT=100)`) is the **kept** core change. The UI adapters
(reaction/duel) were reverted to the old `emit_synthetic_click()` + direct
callback, because the full-dispatch UI click missed the controls.

---

## 3. Live findings (the two logout runs)

Both runs used the world dispatch; the Hunter queued Metins successfully
(`Queued Metin of Death [VID …], queue 0->1/5 …` repeatedly), so the projected
coordinate click **lands on the target**.

Run (release `528a57d`, in `release (2)`): the recorder flipped to **enabled,
`sample_ms=40`** for ~90 s (ticks ~123608187→123701812), then back to disabled;
the `net.Disconnect` came at `12:57:23.861` with an **empty** Python stack
(server-initiated), ~3 minutes after the audit window ended.

Conclusion: the full-dispatch change is **not sufficient** to stop the logout.

---

## 4. The leading hypothesis (button state)

The recorder snapshot (`FUN_1404704b0`) derives the held-button state two ways,
selected by `DAT_147a734c0 + 0x20`:

- **background** (`+0x20 == 0`): from `player+0xff/+0x100` — which the dispatch
  **does** set, so a synthetic "down" looks like "button pressed" (consistent).
- **foreground** (`+0x20 != 0`): from `GetAsyncKeyState(VK_LBUTTON)` — which the
  synthetic click **cannot** touch (constraint: the real Windows mouse must stay
  untouched). So a synthetic "down" carries "button **not** pressed".

If the recorder was in **foreground** mode during the audit window, the button
state is implausible and that is a strong candidate for the disconnect. If it
was in **background** mode, this hypothesis is wrong and we look at down/up
timing (0 ms), coordinate values, or click pacing instead.

This is exactly why `bg=` was added (commit `3e4069e`). The observed logout run
was on `release (2)` = `528a57d`, which predates that commit, so **`bg=` was not
captured**.

---

## 5. Immediate next step

1. Get a release that includes **`3e4069e`** (or later). Wait for
   `autobuild-3e4069e…` / `autobuild-94c60df…` on GitHub; do **not** use
   `release (2)` (it is `528a57d`).
2. Run Hunter-only (Auto Reaction / Boss / Duel off), with the game window
   **unfocused** (background). Watch `python_window_loader.status.txt` during the
   `recorder_enabled=1 sample_ms=40` window and record the `bg=` value:
   - `bg=0` → background mode → button state consistent → look elsewhere
     (timing, coords, pacing).
   - `bg≠0` → foreground mode → button-state mismatch is likely the cause.

Also note: release downloads are quarantined by Defender (the injected DLL is a
classic AV target) — the `client_feature_loader.dll` must be restored/allow-listed
from a folder exclusion or it silently disappears.

---

## 6. Code map (addresses / offsets, already verified)

- Game EXE SHA-256 `DBD69CAD…D3636D72F2`, PE timestamp `0x6ACA943D`, image size `0x094C1000`.
- `RVA_GAME_DOWN_DISPATCH = 0x007E3E70` (`FUN_1407e3e70`) — mouse-down dispatch (pick + OnMouseDown).
- `RVA_GAME_UP_DISPATCH = 0x007E3FD0` (`FUN_1407e3fd0`) — mouse-up dispatch.
- `RVA_APP_GLOBAL = 0x07A734C0` (`DAT_147a734c0`); `+0x20` = background/foreground flag.
- `RVA_INPUT_RECORDER = 0x07A6BA20` (recorder global, a pointer).
- `RVA_RECORD_INPUT = 0x00471B10` (`FUN_140471b10`) — record down/up.
- `RVA_SET_MOUSE_STATE = 0x003E5940` (`FUN_1403e5940`) — player press/release (the old direct path).
- `player+0x4588` / `+0x4590` — the Metin queue `std::vector<int>` begin/end.
- `player+0xff` — left-button-down flag.
- `player.GetProjectPosition` = `FUN_1403fa410` (world→screen projection; returns client pixels via `FUN_14061e430`).
- `PROJECT_CLICK_HEIGHT = 100` in `client_feature.py` — the vertical lift applied to the projected click (tunable; not yet live-verified beyond "it lands").

Files:
- `python_loader.cpp` — the C++ wrapper (built by `build.ps1 -FeatureOnly`).
- `client_feature.py` — the Python feature (Hunter/Boss/Priority `_queue_add`, coordinator, duel).
- `test_client_feature_local.py` — local tests (Python 3, no game).
- Decomp traces: `decomp/background_input_trace/` (in the separate `decomp` tree).

---

## 7. Honest status

- Fixed and working: queue adds (full dispatch lands on target), reaction, duel
  (including result-screen close).
- Not resolved: the **logout** — it still happens, and the leading hypothesis
  (button state) is untested because the diagnostic release wasn't used.
- The server's actual comparison rule remains **unknown**; do not promise a cure.

---

## 8. Release-2 review (supersedes parts of §2–§7)

`decomp/LOGOUT_RELEASE2_REVIEW_20261016.md` (decomp tree) reviewed `release (2)`
and, via offline reproduction, found these defects. They are more authoritative
than the earlier parts of this handover where they disagree.

1. **The new route can silently become the old route.** `_queue_add` falls back
   to `player.MetinQueueAdd(vid)` (old picker-override path) when the projection
   is missing, negative, or raises; the try/except also covers the dispatch call
   itself. `player.GetProjectPosition` (`1403fa410`) resolves its argument via
   `1403e2dc0(DAT_147a6b8e8, id)`, whereas the queue wrapper resolves the actor
   via `1403d1d40` (a different manager) — so the projection may return
   (-100,-100) for Metin VIDs and trigger the fallback. **Therefore the "Queued"
   lines in §3 do not prove the new dispatch ran**; they may all have been the old
   route. This is the single most important correction.
2. **The `bg=` diagnostic in `3e4069e` has a pointer bug.** It reads
   `*(base + 0x07A734C0 + 0x20)` (a byte near the pointer slot) instead of
   dereferencing the app pointer at `0x07A734C0` first and then `+0x20`. Fix it
   before relying on any new `bg` log; it was not in the failed release anyway.
3. **Dispatch lacks completion/cleanup.** `DispatchClickAt` ignores the down/up
   return values and has no finally-based release/cancel on exception; the
   legacy `pressed=true` is set after the press call, so a fault between press
   and the flag leaves `pressed=false` and skips release. No re-entrancy check
   that the current thread is the game/window thread.
4. **Python defeats the stronger ack.** `FeedMetinQueue` uses
   `if result == 1 or new_size > size`, so UNKNOWN/REJECTED plus unrelated queue
   growth reads as success. `_dispatch_native_add` calls `coordinator.finish`
   on UNKNOWN (deleting the unresolved action) and converts exceptions to 0;
   `validate()` returns a truthy string `"rejected"` that `if not validate(...)`
   does not reject.
5. **Tests/logging miss the route.** The local tests provide no
   `GetProjectPosition`, so they exercise the fallback, not the 3-arg dispatch;
   the DLL logs recorder state but not route selection, projection result,
   requested/picked VID, button state, or raw result.

The review's next step: fix the dispatch/acknowledgement contracts and add
bounded route diagnostics; first establish whether `GetProjectPosition` accepts
the real target identity and whether hit-testing selects that same VID. Do not
silently fall back to the old path on verification failure. A fresh-process
live control should start with automation OFF and observation-only diagnostics,
then one narrowly scoped background action, then Hunter-only.
