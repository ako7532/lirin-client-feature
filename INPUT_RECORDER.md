# Input recorder — finding and fix

> Why the automated "Metin Hunter" was being remotely disconnected after a few
> minutes while manual play (and a manually-clicked "Diag +1" button) stayed
> connected, and how the feature now counters it.

## The mechanism

The client has a **mouse-input recorder** at global `DAT_147a6ba20`
(image RVA `0x07A6BA20`). It is a pointer to a recorder struct. Real mouse
events are recorded into it from the Windows mouse message handler
(`FUN_1404fc620`); every real event calls
`FUN_140471b10(DAT_147a6ba20, code, x, y)`.

The **metin queue-change path is wired to this recorder**. Every add / clear /
processor-pass / remove calls `FUN_1404710d0(DAT_147a6ba20)`:

- `FUN_1403e41a0` — low-level `CPythonPlayer::MetinQueueAdd`
- `FUN_1403e4300` — queue clear
- `FUN_1403e4400` — queue processor
- `FUN_1403e48e0` — queue remove

`FUN_1404710d0` is a "dirty helper":

```c
if (recorder[8] != 0)      // if the recorder is enabled
    recorder[0x90] = 1;    // mark it dirty (needs flush)
```

So, while the recorder is enabled, a queue change marks it dirty so the
recorded input log can be flushed and compared against the queue change.

The recorder is **off by default** (`recorder_enabled=0`); it is almost
certainly enabled by the server when it wants to audit a player.

## Why manual worked and the Hunter didn't

- **Manual click / "Diag +1" button**: the physical click passed through
  `FUN_1404fc620` and produced a real input record (codes `1`/`2`). Each queue
  change had a real click next to it -> legitimate.
- **Automated Hunter**: `NativeMetinQueueAdd` called the internal mouse-state
  handler (`FUN_1403e5940`) directly, bypassing the Windows handler, so no
  `FUN_140471b10` record was produced. Queue changes with no input record ->
  detected.

## Key addresses (do not re-derive)

| Symbol | RVA | Purpose |
| --- | --- | --- |
| `DAT_147a6ba20` | `0x07A6BA20` | input recorder pointer (global) |
| `DAT_147a6b480` | `0x07A6B480` | game instance global (arg to cursor getter) |
| `FUN_140471b10` | `0x00471B10` | record input `(recorder*, char code, int x, int y)` |
| `FUN_1404710d0` | `0x004710D0` | dirty helper `(recorder*)` |
| `FUN_1407e13b0` | `0x007E13B0` | get game cursor position `(instance*, int* x, int* y)` |
| `FUN_1403e5940` | `0x003E5940` | internal mouse press(1)/release(0) `(player*, int, char)` |

### Recorder struct offsets

- `+0x08` (byte): enabled flag
- `+0x0A` (WORD): sample_ms (observed `40`)
- `+0x0C` (WORD): flush_ms (observed `200`)
- `+0x90` (byte): dirty flag (set by `FUN_1404710d0`)
- `+0x9C` / `+0xA0` (int): stored cursor x / y

### `FUN_140471b10` codes

| code | event |
| --- | --- |
| 1 | left button down |
| 2 | left button up |
| 3 | left button double-click |
| 4 | right button down |
| 5 | right button up |
| 6 | middle button down |
| 7 | middle button up |
| 8 | mouse wheel (via `FUN_140471d20`) |

`FUN_140471b10` is a **no-op while `recorder[8] == 0`**, so calling it is always
safe.

## The fix

In `python_loader.cpp`, the synthetic queue-add path now emits the same down/up
records a real left click would produce, and a `vid == 0` sentinel exposes a
bare click for UI automations that never touch the metin queue.

- `EmitSyntheticClick()` — records down (code `1`) + up (code `2`) at the
  game's own cursor position.
- `NativeMetinQueueAdd` — for a real VID, records down/up around the existing
  press/release; for `vid == 0`, emits only the bare click (no queue change).
- Cursor position comes from `FUN_1407e13b0` (the same source the recorder uses
  for its movement samples), **not** the OS cursor, so it stays on the recorded
  movement path even while the window is unfocused / in the background.

In `client_feature.py`, `emit_synthetic_click()` calls `player.MetinQueueAdd(0)`
(the sentinel) and is invoked before:

- Reaction game `_ReactionGameWindow__OnClickPlay()` and `__OnClickSlot(slot)`.
- Boss channel dialog `AcceptButton()`.

Coverage:

| Path | Click emitted? |
| --- | --- |
| Hunter `MetinQueueAdd(vid)` | yes (wrapper) |
| Boss target selection `MetinQueueAdd(vid)` | yes (wrapper) |
| Boss channel dialog accept | yes (`emit_synthetic_click`) |
| Reaction game play + slot click | yes (`emit_synthetic_click`) |

## Caveats

- The exact server check is still unproven. The "Diag +1" counterexample
  (click on the panel, not on a stone) suggests position is not strictly
  validated, so a down/up pair at the game cursor position is expected to
  suffice. If the server later proves to check mouse-path continuity or
  stone-accurate positions, this needs extending.
- Reaction slot clicks use the game cursor position, not the slot's screen
  position (see above).
- `SetAttackKeyState` / `ClearTarget` / `MetinQueueClear` are keyboard/queue
  operations, not mouse clicks, so they are intentionally not recorded here.
