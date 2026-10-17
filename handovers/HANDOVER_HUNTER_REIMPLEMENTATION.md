# Handover: Hunter reimplementation (local implementation)

Date: 2026-10-17, Europe/Bratislava. Status: local implementation, revised after an
independent implementation review (`decomp/HUNTER_IMPLEMENTATION_REVIEW_20261017.md`).
The review's P0/P1 blockers are corrected (see "Post-review corrections"). Live behavior,
audit coverage and H-AUDIT acceptance remain pending user-run validation, which must use a
fresh process and the newly rebuilt DLL (see "Artifact identities").

## Branch / worktree / base

- New branch: `feature/hunter-reimplementation`.
- New worktree: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature-hunter-reimplementation`.
- Base commit (main repository HEAD, recorded before any edit):
  `36dccf64ec46fe6618a7286b9277bc29ca5bf9b7` (`main`, `FEATURE_VERSION = 46`).
- Main checkout and other worktrees were left untouched. The two planning
  documents were copied (not modified) into this worktree's `handovers/`.

## Baseline identities (recorded before editing)

| Item | SHA-256 |
| --- | --- |
| `client_feature.py` | `3EC01E52E5FED55A4592706491E08675515A135B8164E6032494621D78DE77B6` |
| `python_loader.cpp` | `5CE22B1BF4DD8D2B97658B6EFC38D35D569A70B2BB0A4B40E3F9CE23924D9C05` |
| installed `app\Lirin.exe` | `8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0` |
| old `client_feature_loader.dll` | `6DA1779250FF557052EAE947D1EF2954C801DB6C04B9256F4AB2357334004F2D` |
| baseline `test_client_feature_local.py` | passed (`...: OK`) |

The installed executable hash matches the analyzed build, so the native RVAs in
`handovers/HUNTER_NATIVE_API_CONTRACT.md` remain valid.

## Implemented behavior

- **Removed** the old method-table interception and synthetic-click Hunter
  (`InstallNativeMetinQueueWrapper`, `NativeMetinQueueAdd*`, `DispatchClickAt`,
  `EmitSyntheticClick`, projection/picker/input helpers, wrapper result codes,
  the `MetinQueueAdd(0)` sentinel, and every `emit_synthetic_click` call).
- **Replaced** it with a stock-route redesign: the native observer is read-only;
  every queue mutation goes through the unmodified stock `player.MetinQueueAdd`
  / `MetinQueueRemove` / `MetinQueueSetEnabled` bindings.
- **Native observer module `_lirin_hunter_native`** (API v1), registered in
  `python_loader.cpp` via the verified `Py_InitModule4`, exposes `now_ms()`
  (`GetTickCount64`), `snapshot()`, `admission(vid)` and `audit_status()`
  (read-only recorder/app-active observation). Full contract in
  `handovers/HUNTER_NATIVE_API_CONTRACT.md`.
- **Python components** in `client_feature.py` (Python 2.7-compatible, ASCII,
  dependency-injected): `HunterQueueGateway` (authoritative membership outcomes
  `ADDED/ALREADY_PRESENT/REJECTED_PRECALL/REJECTED_NATIVE/REMOVED/
  ALREADY_ABSENT/UNKNOWN/CANCELLED_PRECALL`), `HunterCandidateSelector`
  (immutable per-scan snapshot, nearest-then-VID, squared-distance radius,
  Legendary name match), `HunterController` (states OFF/STARTING/RUNNING/WAITING/
  RECONCILING/PAUSED/STOPPING/ERROR, monotonic epoch, exclusive lease,
  ownership ledger, one-add-per-tick with >=1000 ms spacing, 2 s rejection
  backoff, 2 s UNKNOWN deadline with freeze/quarantine, owned-only Stop cleanup,
  Reaction pause/resume, Legendary priority state machine gated by
  `priority_enabled=False`).
- **Reaction safety preserved** (detection still pauses the owned queue) while
  the automatic solver is unavailable; the `reaction_enabled` toggle reports
  "solving unavailable".
- **Temporarily disabled** (entry points report "unavailable" before any
  gameplay side effect): Boss Sweep, automatic Reaction solver, Yin Yang Duel,
  Twin Souls, automated channel changes. Their code is retained for later repair.

## Changed files

- `python_loader.cpp` — wrapper removed; observer module + registration added.
- `client_feature.py` — old Hunter/interception removed; gateway/selector/
  controller/priority/audit-observer added; disabled-feature gates; Reaction rewrite.
- `test_client_feature_local.py` — rewritten for the new architecture + regressions.
- `handovers/HUNTER_NATIVE_API_CONTRACT.md` (new).
- `handovers/HUNTER_AUDIT_EVIDENCE.md` (new).
- `handovers/HANDOVER_HUNTER_REIMPLEMENTATION.md` (this file, new).
- `native_contracts/` (new, untracked) — decompilation artifacts and the
  PyGhidra scripts used to derive the verified RVAs.

## Post-review corrections (2026-10-17)

The independent review flagged a P0 and several P1/P2 defects. All are corrected here:

1. **P0 — raw pointer as Python object (crash cause).** `snapshot()`/`admission()`
   inserted the native `player` pointer directly as a `PyDict_SetItemString` value,
   letting refcounting write into the player object. Now `player_cookie` is an opaque
   `PyLong_FromUnsignedLongLong` token (`None` when invalid); the raw pointer is never
   exposed as a `PyObject*`.
2. **P1 — Stop/pause hid failed cleanup.** `_cleanup_owned` now returns an explicit
   result; `stop()`/`pause()` propagate `ERROR` on failure and disable a still-owned
   enabled empty session; UI status is derived from the controller.
3. **P1 — UNKNOWN expiry.** Unresolved requests now enter an epoch-scoped `quarantine`
   (not a 2 s backoff), preserve request history, and drive bounded owned cleanup.
4. **P1 — foreign membership / disable revocation.** `_run` revokes exclusive ownership
   (ERROR, freeze adds) on foreign queue members or an externally disabled queue, and
   reconciles naturally-departed ledger VIDs.
5. **P1 — Reaction resume.** `resume` re-enables/reacquires the empty queue via a stock
   `MetinQueueSetEnabled(1)` and verifies it; `start` refuses while a safety pause is active.
6. **P1 — gateway dispatch guards.** `add_once`/`remove_once`/`set_enabled_once` use a
   fresh snapshot, enforce `stock_binding_ok`, cookie identity and a dispatched-once guard,
   and re-run native admission; `set_enabled_once` no longer mutates on an invalid snapshot.
7. **P1 — session epoch / fresh checks.** A replacement phase-5 window bumps the epoch;
   the controller enforces the scan epoch; final revalidation reads fresh player position,
   radius, anchor and compares the live race to the candidate's recorded race.
8. **P1 — audit instrumentation.** Added `HunterAuditObserver` (explicitly enabled,
   independent of Hunter ON) which polls the verified `audit_status()` on the update thread,
   logs first observation / state and interval changes / 1 Hz heartbeat with max gap, and
   runs maintenance/observation before the Reaction early return.
9. **P2 — vector validation.** `ReadQueueVids` rejects inconsistent null triples, requires
   4-byte alignment and `begin <= end <= capacity`, and rechecks begin/end/capacity and the
   singleton around the copy. Priority ADDING honors the add interval and the intended VID;
   priority completion no longer replays stale state.

## Tests / build / artifacts

- `python -B test_client_feature_local.py` -> `Hunter redesign local checks: OK`.
- `.\build.ps1 -FeatureOnly` -> success (no warnings emitted under `/W4`).
- `git diff --check` -> clean (only LF/CRLF notices).
- `client_feature.py` ASCII-decodes and parses under Python 3 (`ast.parse`);
  Python 2.7 compatibility is by construction (ASCII-only, no f-strings/
  annotations/enums/dataclasses) but was not executed under a Python 2.7 parser
  (none is installed) — reported as a limitation.

### Artifact identities (rebuilt after the corrections)

| File | SHA-256 |
| --- | --- |
| `client_feature_loader.dll` | `5B5A608EC61305B979A7165D8FAC774A8972E91C03B83812C2A4A18990E0A5DD` |
| `client_feature.py` | `E61CFB93265A177E1588D0A27108B362C3E7024011586939944516A76FF03589` |
| `python_loader.cpp` | `C5C46EB185FCC1C967415C57BB5AFD06312B19B906FEACD8E8C3E4472F2C59AF` |
| `test_client_feature_local.py` | `A6EE26B4D267470A600EEF3E923489EEFA1855D013F1C9F10D85C7487FE6A66D` |

The earlier reported DLL hash (`6C807D65…AECD`) predates these corrections and must not be
injected. Re-run `.\build.ps1 -FeatureOnly` and re-hash before any live run; the runner
(`run_client_feature.ps1`) copies the current `client_feature_loader.dll` into the
per-branch runtime directory on every invocation.

## Audit investigation / instrumentation status

- `handovers/HUNTER_AUDIT_EVIDENCE.md`:
  - A (incoming config/trigger): **PARTIAL** — adapter `FUN_1403c1000` and
    config `FUN_140498eb0` verified (enabled @+0, sample @+2, flush @+4;
    100/200 ms zero-substitution and buffer/coordinate resets); the receive
    dispatch, registration index, and any opcode are **UNRESOLVED**.
  - B (outgoing record/flush): **PARTIAL** — in-memory 0x50-byte sample stride
    and the sampler/append/flush/sender chain verified; the wire serializer
    `FUN_14033e2e0` and its framing/opcode/field encoding are **UNRESOLVED**.
  - Read-only `audit_status()` implemented and verified against the recorder
    (`+8` enabled, `+0xA` sample_ms, `+0xC` flush_ms) and app (`+0x20` active)
    fields already exercised by the loader. It is now wired into an explicitly
    enabled `HunterAuditObserver` session (independent of Hunter ON) that logs the
    first observation, state/interval changes, and a 1 Hz heartbeat with max gap.
- No live capture/replay, packet transmission, or recorder manipulation was
  performed. The recorder-comparison hypothesis (H-AUDIT) remains unestablished.

## Temporarily unavailable features

Boss Sweep, automatic Reaction solving, Yin Yang Duel, Twin Souls, and automated
channel changes all report "unavailable" and perform no gameplay actions. Their
exact disabled entry points: `ToggleBossSweep`, `StartBossAttack`,
`ToggleYinYangDuel`, `ToggleTwinSouls`, and the Reaction solver path inside
`PollReactionGame`.

## Specific unresolved blockers / pending user-run live tests

- **Unverified at runtime (requires live process):** the exact CPython 2.7 object
  RVAs used by the loader are matched-build decompilation-derived (documented in
  the contract), not live-verified. A fresh process must confirm the observer
  module registers and `snapshot()`/`admission()`/`audit_status()` behave.
- **Pending user-run live ladder** (plan §13): matched uninjected manual control;
  injected removal/stub control; observer/discovery-only; one stock add; bounded
  continuous Hunter; priority + Reaction pause/resume. These are user-run; no
  local claim of live behavior or server acceptance is made.
- H-AUDIT acceptance is **untested** until an enabled-recorder live exposure is
  recorded with the §13.1 coverage matrix.

## Next specific action

Fresh game process, new loader (`client_feature_loader.dll`), stock binding
untouched, observer/controller disabled initially; confirm the observer module
registers and the uninjected/injected-stub controls are stable before any
automatic stock add. Do not hot-swap into a process that ran an older patched DLL.
