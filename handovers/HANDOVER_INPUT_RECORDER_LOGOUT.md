# Handover — Input recorder / logout problem

Date: 2026-10-16
Branch: `yin-yang-duel`
Feature: Lirin (Metin2-like), embedded Python 2.7.

This handover is for the **anti-bot input recorder / remote-logout** problem, so a
new chat can start the implementation. A detailed implementation plan already
exists (read it first):

> `C:\Users\andrej-pc\Documents\projects\decomp\INPUT_RECORDER_IMPLEMENTATION_PLAN.md`

That plan is **outside the repo** (in the decomp tree). This handover summarises
the state and points at it; the plan is the authoritative next-step document.

---

## 1. The problem

The client has a mouse-input recorder wired to the metin queue. A synthetic
queue add must look like a legitimate mouse click or the server may remote-
close the session. The current wrapper records a bare down/up pair but does not
reproduce the full physical click path, and a remote logout still occurred.

The server-side comparison rule is **unknown**; do not assume one exists from
client-side recording alone.

## 2. Current repo state

- Repo: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`.
- Branch: `yin-yang-duel`.
- HEAD (at review time): `0e83fbc` — "Add focused input-recorder logout review".
- Python feature version: 40.
- Loader source SHA-256:
  `E477ADA9ABFEEC7F8D47866B54D32ABC6A75AE35D610B082DADBF4D6FD254A2E`.
- Game EXE SHA-256 (analysis copy == installed copy):
  `DBD69CAD070786DB754E893FEA4887A6D660D52AC19F9300257431D3636D72F2`.
- Loader currently checks PE timestamp `0x6ACA943D` and image size `0x094C1000`
  (not a full identity check).
- Preserve untracked `ReactionTimingRecorder/`, `ReactionTimingRecorder.Tests/`,
  and `yin_yang_duel_history.jsonl`.

## 3. The current wrapper (what we have)

`python_loader.cpp` intercepts `MetinQueueAdd` and, per add:

```c
record_input(recorder, 1, x, y);   // code 1 = down
set_mouse_state(player, 1, 0);
record_input(recorder, 2, x, y);   // code 2 = up
set_mouse_state(player, 0, 0);
```

plus a `vid == 0` sentinel (`emit_synthetic_click`) for UI actions (reaction,
boss channel, duel card). Coordinates come from `FUN_1407e13b0`.

The plan's Phase 3 lists several **correctness defects** to fix independently
(ownership/re-entrancy, VID-membership acknowledgement instead of size growth,
exception-safe cleanup, phase-generation guards, VID-zero path hardening, and
method-table install/restore hardening).

## 4. Key addresses and struct (verified)

Recorder global: `DAT_147a6ba20` (RVA `0x07A6BA20`), a pointer to the struct.

| Offset | Type | Meaning |
| --- | --- | --- |
| `+0x08` | byte | enabled flag |
| `+0x0A` | WORD | sample_ms (40 when auditing, else 100) |
| `+0x0C` | WORD | flush_ms (200) |
| `+0x90` | byte | dirty flag (`FUN_1404710d0` sets it) |
| `+0x9C`/`+0xA0` | int | stored cursor x / y |

Functions:

| Function | RVA | Purpose |
| --- | --- | --- |
| `FUN_140471b10` | `0x00471B10` | record input `(recorder, code, x, y)` |
| `FUN_1404710d0` | `0x004710D0` | dirty helper (queue-change hook) |
| `FUN_1407e13b0` | `0x007E13B0` | **cursor-coordinate getter** `(instance, &x, &y)` — not a world projection |
| `FUN_1403e5940` | `0x003E5940` | player press(1)/release(0) |
| `FUN_140472870` | — | periodic tick: code-0 samples + flush |
| `FUN_1404729b0` | — | copies the queue VID list, sends via `14037a6c0` |
| `FUN_140470be0` | — | flushes input records via `14037a730` |

## 5. Verified physical click path (vs the wrapper)

| Stage | Physical client | Wrapper today |
| --- | --- | --- |
| Admission | `1404fc620` → filters `14048bcd0`/`14048c440`, capture, `1409f7680` | bypassed |
| Down gate | `1409bf660()+0xB8`, app `+0x20` | only player left-down byte checked |
| Record down | `140471b10(recorder,1,x,y)` | same, but picker pre-overridden |
| App down | app `+0x80468=1`, `1407e3e70(game,x,y)` | skipped |
| Player press | `1403e5940(player,1,0)` → `+0xFF`, `1403ec0f0` | entered directly |
| Pick/action | `1403ec0f0` → actor `1403ebdd0`, queue `1403e41a0` | only manager `+0xE0` overridden |
| Record up | code 2, `1407e3fd0` | direct record/release, app/UI skipped |
| Snapshot | `1404704b0` normalized x/y + event/button/world/picked/UI bits | captures surrounding state, does not create missing transitions |

## 6. Corrections to the earlier review (important)

The prior `INPUT_RECORDER_LOGOUT_REVIEW.md` contains several **unverified**
claims. The plan corrects them:

- "First enabled-recorder run" is **false** — PID 17456 already had 27 enabled +
  197 disabled calls (~65 min run).
- The recorder transition was in a ~65 s observation gap, **not** exactly 09:07:24.
- `FUN_1407e13b0` is **not** a world↔screen projection; it returns two cursor
  integers. Projection must be located separately.
- Code-0 samples use **recorder-stored** coords in one mode (`DAT_147a734c0 +0x20
  == 0`) and the cursor getter otherwise.
- `FUN_1404729b0` sends the whole queue VID list, not a per-item delta.
- "Missing/implausible clicks caused the logout" is **unproven**; the server rule
  is unknown.

## 7. Recommended approach (from the plan)

The plan explicitly rejects fabricating movement records, coordinate jitter, and
arbitrary 50–80 ms delays. Instead:

1. **Phase 1** — complete static feasibility of a *background* input path (real
   Windows mouse/focus untouched). If no such route exists, document the
   incompatibility rather than forging foreground state.
2. **Phase 2** — observation-only diagnostics (bounded ring buffer, no per-frame
   disk writes) distinguishing "not sampled / unavailable / disabled / requested /
   accepted / send attempted".
3. **Phase 3** — independent wrapper correctness fixes (see §3), tested alone.
4. **Phase 4** — separate world-action and UI-action adapters through verified
   client dispatch, with asynchronous acknowledgement (`requested → validated →
   dispatched → awaiting → completed`, plus `cancelled`/`rejected`/`unknown`).
5. **Phase 5** — local verification (fault injection, focus matrix, exact-once,
   method-table conflicts, `build.ps1 -FeatureOnly`, `git diff --check`).
6. **Phase 6** — separately authorised controlled live validation, one factor at a
   time, with a baseline build for comparison.

Read the plan document for the exact acceptance gates per phase.

## 8. Constraints (hard requirements)

- The real Windows mouse must remain **untouched** (no `SetCursorPos`, no focus
  stealing, no OS button-state changes, no forced focus flags).
- Background operation must remain supported; distinguish unfocused vs minimised.
- Do **not** force the recorder on, change its configuration, or fabricate
  telemetry.
- Do not promise a logout cure; it is an empirical claim requiring live evidence.

## 9. Where things live

- Loader/wrapper: `python_loader.cpp` (C++ → rebuild via `build.ps1 -FeatureOnly`).
- Feature: `client_feature.py`.
- Tests: `test_client_feature_local.py`.
- Decomp traces: `decomp/input_recorder_trace/`, `decomp/metin_queue_trace/`.
- Reviews: `INPUT_RECORDER_LOGOUT_REVIEW.md` (partly superseded), the plan above.
