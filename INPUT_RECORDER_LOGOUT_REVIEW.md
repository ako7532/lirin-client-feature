# Input-recorder logout — review

Date: 2026-10-16
Branch: `yin-yang-duel` (the recorder fix originated on `main`)

Focused review of the **logout / anti-bot input recorder** problem, with the
evidence gathered so far. This is the information needed to write a fix plan.

---

## 1. Recap: the original finding

The client has a **mouse-input recorder** at global `DAT_147a6ba20`
(RVA `0x07A6BA20`), a pointer to a recorder struct. Real mouse events are
recorded from the Windows message handler (`FUN_1404fc620`), which calls
`FUN_140471b10(recorder, code, x, y)`.

The **metin queue-change path is wired to the recorder** — every add / clear /
processor-pass / remove calls `FUN_1404710d0(recorder)`, which does:

```c
if (recorder[8] != 0)      // if enabled
    recorder[0x90] = 1;    // mark dirty
```

So a queue change marks the recorder dirty so its input log can be flushed and
compared against the queue change.

The **automated Hunter** called the internal mouse-state handler
(`FUN_1403e5940`) directly, bypassing the Windows handler, so no `FUN_140471b10`
record was produced → detected.

## 2. The fix we applied

In `python_loader.cpp`, the synthetic `MetinQueueAdd` path now records a
down/up pair around the press/release:

```c
record_input(recorder, 1, x, y);   // code 1 = down
set_mouse_state(player, 1, 0);
record_input(recorder, 2, x, y);   // code 2 = up
set_mouse_state(player, 0, 0);
```

plus a `vid == 0` sentinel (`emit_synthetic_click`) for UI automations
(reaction game, boss channel dialog).

Coordinates come from `FUN_1407e13b0` (the game's internal cursor position),
not the OS cursor.

## 3. New evidence: logout under audit

The latest logout:

```
09:00:39  Boss Sweep starts (8 channels)
09:04:26  Boss Sweep ends, Hunter resumes
09:06:19  last add while recorder_enabled=0  (sample_ms=100)
09:07:24  recorder_enabled flips 0 -> 1     (sample_ms 100 -> 40)
09:07:24..09:08:18  Hunter adds ~7 metins  (each emits synthetic down/up)
09:09:09  net.Disconnect (empty args/stack) -> remote close
```

From `python_window_loader.status.txt`:

```
tick=110006984 vid=27498078  recorder_enabled=0 sample_ms=100
tick=110071906 vid=27499028  recorder_enabled=1 sample_ms=40   <- audit ON
... 6 more adds, recorder_enabled=1 sample_ms=40
```

**Conclusion:** the server turned the recorder on (and tightened `sample_ms`
100 → 40, i.e. mouse position sampled every 40 ms), watched ~7 queue adds, and
disconnected ~1.5 min later. This is the first time `recorder_enabled=1` was
observed; every earlier "stable" test (including the "Diag +1" button) ran with
`recorder_enabled=0`, so the fix was **never validated under audit**.

## 4. What the recorder actually records (from decompilation)

Struct offsets (validated against the decompiled functions):

- `+0x08` (byte): enabled flag
- `+0x0A` (WORD): sample_ms (40 when auditing, 100 otherwise)
- `+0x0C` (WORD): flush_ms (200)
- `+0x90` (byte): dirty flag (set by `FUN_1404710d0`)
- `+0x9C` / `+0xA0` (int): stored cursor x / y

Key functions:

- `FUN_140471b10` (RVA `0x00471B10`) — record input `(recorder, code, x, y)`;
  codes: 1=down, 2=up, 3=dblclk, 4/5=right, 6/7=middle. No-op when disabled.
- `FUN_1404710d0` (RVA `0x004710D0`) — dirty helper.
- `FUN_1407e13b0` (RVA `0x007E13B0`) — game cursor position `(instance, &x, &y)`.
- `FUN_1403e5940` (RVA `0x003E5940`) — internal press(1)/release(0).
- `FUN_140472870` — tick: while enabled, records a **code-0 movement sample**
  every `sample_ms`, and flushes.
- `FUN_1404729b0` — flush the dirty queue diff to the server.
- `FUN_140470be0` — flush the recorded input log to the server.

The record built by `FUN_1404704b0` normalizes coordinates:
`(x * 10000) / granularity` (granularity read from `DAT_147a6b480` +8/+0xc).

So the input log the server receives is a **time series**:

- **code 0** — mouse position, sampled every `sample_ms` (40 ms while auditing);
- **code 1 / 2** — click down / up, recorded when real clicks happen.

The server therefore reconstructs a **mouse path with clicks** and compares it
against the queue changes.

## 5. Why the synthetic input is insufficient

The synthetic input records a down/up pair, but it is not a plausible click
sequence:

1. **Down/up are 0 ms apart.** `EmitSyntheticClick` calls `record_input(1)` then
   `record_input(2)` back-to-back. A real press→release is ~50–100 ms. The
   `FUN_140471b10` records are stamped with the current tick, so down and up
   land on essentially the same tick.

2. **Every click is at one fixed position.** The coordinate is `FUN_1407e13b0`
   (the game's internal cursor), which does not change between adds. Seven
   stones were added, each at a different screen position, but all clicks
   report the same position.

3. **No movement.** The code-0 samples (every 40 ms) show the cursor sitting
   still; there is no path toward the stone, no approach, no settle — just a
   click appearing at a static point.

So the gap is not a *missing* record — it is an *implausible* one, and a 40 ms
sampler is detailed enough to see all three defects.

## 6. What the server most likely checks (hypotheses, unverified)

The definitive rule is unknown, but the evidence supports one or more of:

- **H1 — a click must exist near each queue change** (our current fix covers
  only this).
- **H2 — the click position must correspond to the stone's screen position**
  (not covered: we use the fixed cursor).
- **H3 — the mouse must move toward the click point before the click** (not
  covered: no code-0 movement).
- **H4 — press duration / click cadence must be human-like** (not covered:
  0 ms down/up).

The recorder's movement sampling (code 0 every 40 ms) exists precisely so the
server can test H3; a static cursor with instantaneous clicks fails that
immediately.

## 7. Open questions

- Which of H1–H4 (or which combination) actually triggers the disconnect?
- Does the server compare the click coordinate to the *stone's* projected
  position, or only to the movement path?
- What is the acceptable press duration and cadence?
- Is a single click per queue add enough, or does the server expect a
  pick-then-click (hover/move) sequence?

These need a controlled live test (one factor changed at a time), or more
decompilation of the server-side comparison (which is not in the client).

## 8. Recommended directions for the fix

1. **Resolve the target actor's screen position** (world→screen projection; the
   client has `FUN_1407e13b0` for cursor→world and a picker for the reverse).
   Then record the click at that position instead of the static cursor.

2. **Emit movement samples** (code 0) toward the target before the click, so the
   recorded path ends at the click point.

3. **Add a human-like press duration** (e.g. 50–80 ms with jitter) between the
   down and up records, and reasonable inter-click cadence.

4. If projecting to screen is too risky initially, do the **cheap win first** —
   realistic down/up timing + position jitter — and re-test to isolate which
   factor matters.

All of this is in `python_loader.cpp` (C++), so any change requires a DLL
rebuild and a live re-injection.
