# Hunter native API contract (mandatory evidence gate)

Date: 2026-10-17, Europe/Bratislava. Status: contracts verified from matching-build
decompilation; implementation references these RVAs only (never a guessed offset).

- Feature repository: `C:\Users\andrej-pc\Documents\projects\lirin-client-feature`.
- Matching binary: `C:\Program Files (x86)\Lirin\app\Lirin.exe`, SHA-256
  `8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0`.
- Ghidra project: `decomp\ghidra_project\LirinClient_20261016` (program `LirinGame.exe`).
- Image base: `0x140000000`; every RVA below is used as `base + RVA` at runtime.

Native trace sources (recovery workspace `native_traces\queue\`, `native_traces\recorder\`)
are the current-build exports. New decompilations performed for this task are stored in
this worktree under `native_contracts\` (files `140401300.c`, `140401210.c`, `140401290.c`,
`1404012c0.c`, `1403edec0.c`, `1403ed5a0.c`, `1403ed2f0.c`, plus the CPython API files).

## 1. Queue layout (verified)

`player` singleton pointer: `DAT_147ccaf00`, RVA `0x07CCAF00` (loader `RVA_PLAYER_SINGLETON`).

| Field | Offset | Type | Evidence |
| --- | --- | --- | --- |
| enabled flag | `+0x457C` | byte (bool) | `1404013e0.c`, `1404012c0.c` |
| queue begin | `+0x4588` | `uint32*` (std::vector begin) | `1403ed760.c`, `1403edec0.c` |
| queue end | `+0x4590` | `uint32*` | same |
| queue capacity | `+0x4598` | `uint32*` | `1404011c0.c` sibling `1403e41a0.c` (old build pattern) |
| current attack VID | `+0x433C` | `uint32` | `1403edec0.c`, `1403ed9c0.c` |

Element width is 4 bytes (VIDs are `uint32`; vector arithmetic is `>>2`). Enabled is
`+0x457C` (confirmed by `MetinQueueIsEnabled` binding `1404012c0.c` reading
`*(char *)(DAT_147ccaf00 + 0x457c)`).

## 2. Stock add (verified)

Binding `player.MetinQueueAdd` = `FUN_1404011c0` (RVA `0x004011C0`), method-definition slot
`RVA 0x07525770`, function slot `RVA 0x07525778`. Decompilation `1404011c0.c`:

- Parses one int (`FUN_1408c7020`, `"i"`), on failure calls `FUN_1408c7320` (returns NULL).
- Calls `FUN_1403ed760(DAT_147ccaf00, vid)` and returns its result via
  `Py_BuildValue("i", result)` (`FUN_140aa5ea0`, format `DAT_1468fb3cc`).

`FUN_1403ed760` (`1403ed760.c`):

- `std::find(begin, end, vid)`; if found (iterator != end) returns `1` (duplicate, no insert).
- Counts entries where `FUN_1403ed5a0(*entry) == 0` (i.e. not in the native exclusion
  set) into `uVar9`.
- Capacity `uVar8`: `FUN_1404f9fc0(game_cfg, 0x2ef, 0)` == -1 => `3`; else
  `(9999 < level) + 5` => `5` or `6` (level via `FUN_14018d050(DAT_147ccaa18)`).
- If `uVar9 < uVar8`: resolve actor (`FUN_1405353b0(manager, vid)`), mark it queued
  (`FUN_1404bf290(actor, 1)`), `push_back` vid, store a timestamp in the map at
  `player+0x45A0` keyed by vid, call `FUN_14037fbe0` (queue state/count send) and
  `FUN_140495ef0` (recorder dirty). Returns `1`.
- Else returns `0` (capacity branch).

Consequences (as the plan requires): returns `1` for an existing VID as well as an
insertion, so a truthy return is never proof of a new add; `0` is the capacity branch;
there is **no** call to full eligibility `FUN_1403ed370`; add marks actor/queue, records a
timestamp, and invokes state/count + recorder-dirty paths. None of those effects are
suppressed by the observer. `FUN_140495ef0(recorder)` sets `recorder+0x90 = 1` only when
`recorder+8 != 0` (enabled), i.e. recorder queue-list dirtying is conditional on the
recorder being enabled (`140495ef0.c`).

## 3. Remove (verified)

Binding `player.MetinQueueRemove` = `FUN_140401300` (RVA `0x00401300`), method-definition
slot `RVA 0x07525790`, function slot `RVA 0x07525798`. Decompilation `140401300.c`:

- Parses one int, calls `FUN_1403edec0(DAT_147ccaf00, vid)`, returns truthy.

`FUN_1403edec0` (`1403edec0.c`):

- `std::find(begin, end, vid)`; if not found (== end) returns `0` (no-op).
- Resolve actor (`FUN_1405353b0`), mark not-queued (`FUN_1404bf290(actor, 0)`).
- Erase exactly that element (`memmove` + `end -= 4`), erase its timestamp from the
  `+0x45A0` map.
- If `player+0x433C == vid` (that VID is the current attack target): clear the picker/attack
  state (`FUN_1404d33e0`, `+0xF8 = 0`, `+0xCC = 0`, `FUN_1403f42b0`, `+0xEC = 0`).
- Calls `FUN_14037fbe0` + `FUN_140495ef0`. Returns `1`.

Verified: removes exactly the requested VID; updates queue/timestamps; stops that VID's
active queue attack when necessary; does **not** clear unrelated VIDs. Return is `1` on
removal, `0` when absent (never only a truthy check). The old `decomp/metin_queue_trace/1403e48e0.c`
and `1403f64a0.c` (previous build) match this structure.

## 4. Disable/clear (verified)

Binding `player.MetinQueueSetEnabled` = `FUN_1404013e0` (RVA `0x004013E0`), decompilation
`1404013e0.c`: on a true->false transition of `player+0x457C` it calls `FUN_1403ed8a0`
(full clear). `FUN_1403ed8a0` (`1403ed8a0.c`) marks every queue entry not-queued, clears the
attack target/picker state, empties the vector and the `+0x45A0` map, then state/count +
recorder-dirty. `player.MetinQueueClear` = `FUN_140401210` (`140401210.c`) calls the same
`FUN_1403ed8a0`. Disable is therefore **not** a reversible flag: true->false clears all
entries and can affect combat/send state.

## 5. Size / enabled queries (verified)

`player.MetinQueueGetSize` = `FUN_140401290` (`140401290.c`): returns `(end - begin) >> 2`.
`player.MetinQueueIsEnabled` = `FUN_1404012c0` (`1404012c0.c`): returns `player+0x457c != 0`.

## 6. Full native eligibility (verified)

`FUN_1403ed370` (RVA `0x003ED370`, `1403ed370.c`), signature
`int FUN_1403ed370(player*, actor*)`:

- `param_2 != 0` and global gate `FUN_1403ed2f0() == 0` (gate returns nonzero when the
  current map is `"dungeons/spyral_abyss"`, `1403ed2f0.c`).
- `actor_vid = FUN_1404b48f0(actor)`; `FUN_1403ed5a0(actor_vid) == 0` (VID not in the
  native exclusion hash set — `FUN_1403ed5a0` is the exclusion-set lookup, `1403ed5a0.c`).
- `FUN_1404b6340(actor) != 0` => eligible.
- `FUN_1404b5780(actor) != 0`, then `vnum = FUN_1404b48c0(actor)`; eligible when the allowed-
  race set `player+0x4670` contains vnum (`FUN_1403e4e20`), or vnum is in the
  `player+0x4600` list, or (level > 9999) a `FUN_1403ddd60` lookup passes a level-race gate.
- Returns `0` otherwise.

This is the exact current native predicate used by the queue processor `FUN_1403ed9c0`
(`1403ed9c0.c`). The observer's `admission(vid)` resolves a fresh actor via
`FUN_1405353b0` (RVA `0x05353B0`, `1405353b0.c`) and calls `FUN_1403ed370(player, actor)`
directly. Its decompiled body reads player/actor/global state only (no writes or sends
observed in the function body or its direct callees); it is a predicate, not a mutator.
It is never substituted with `CanAttackInstance` or the removed Python observer mirror.
Stone/race/position/radius filtering remains the selector's Python responsibility
(`chr.IsStone`, `nonplayer.IsMonsterStone`) in addition to this native predicate.

## 7. Observation bridge (new private module)

The player method table exposes only `MetinQueueAdd` / `MetinQueueRemove` /
`MetinQueueClear` / `MetinQueueGetSize` / `MetinQueueGetMaxSize` / `MetinQueueIsEnabled`
(`MetinQueueAdd` def `0x7525770`, `MetinQueueRemove` def `0x7525790`, both confirmed by
read-only PE method-table inspection). There is no Python authoritative-membership API, so
the loader now registers a read-only private module `_lirin_hunter_native` (API version 1)
exposing `now_ms()`, `snapshot()`, `admission(vid)` and `audit_status()` per the plan. All
queue mutations stay in the stock Python bindings; the module never writes the queue.

## 8. Embedded CPython 2.7 API registration (verified RVAs)

Mapped for the matching build (SHA `8B6F5EA9…A75A0`). Each RVA is used as `base + RVA`.

| Function | RVA | Evidence |
| --- | --- | --- |
| `PyGILState_Ensure` | `0x00AF2750` | loader (live-tested) |
| `PyGILState_Release` | `0x00AF2800` | loader (live-tested) |
| `PyImport_AddModule` | `0x00B0D5D0` | loader + `140b0d5d0.c` |
| `PyModule_GetDict` | `0x00B07000` | loader + `140b07000.c` |
| `PyRun_StringFlags` | `0x00AF7090` | loader (live-tested) |
| `Py_InitModule4` | `0x00AA5ED0` | `modinit_140aa5ed0.c` (checks `module_api_version == 0x3f5`) |
| `PyCFunction_NewEx` | `0x00AEAA30` | called by `Py_InitModule4` |
| `PyDict_SetItemString` | `0x00AE8D30` | called by `Py_InitModule4` |
| `PyDict_SetItem` | `0x00AE8C30` | `140aa6430.c`, `140b0d5d0.c` |
| `PyDict_New` | `0x00AE8AE0` | `140b07000.c` |
| `PyTuple_New` | `0x00AE0F10` | `140aa65f0.c` |
| `PyInt_FromLong` | `0x00ACE140` | `140aa6700.c` (small-int cache −5..256) |
| `PyLong_FromUnsignedLongLong` | `0x00AD2390` | `140aa6700.c` (`K` case) |
| `PyString_FromString` | `0x00ADB610` | `140b0d5d0.c` |
| `Py_BuildValue` | `0x00AA5EA0` | loader (live-tested) + `140aa5ea0.c`/`140aa6c40.c` |
| `PyArg_ParseTuple` (`"i"`) | `0x008C7020` | loader (live-tested) |
| `PyArg` argument-error | `0x008C7320` | loader (live-tested) |
| `Py_None` global | `0x075437D8` | `1408c73e0.c` |
| int format `"i"` | `0x068FB3CC` | loader (`RVA_INTEGER_FORMAT`) |

Object header (verified from every DECREF site in the decompiles, e.g. `140b0d5d0.c`,
`140b07000.c`): `ob_refcnt` at `+0`, `ob_type` at `+8`; `tp_dealloc` at `ob_type + 0x30`.
This is used only for the small inline `Py_INCREF`/`Py_DECREF` helpers in the loader; the
same layout is what the game's own bindings use.

Refcount policy in the loader: every object returned by the observer functions is a new
reference; intermediate values are released with the inline `Py_DECREF`; tuple items are
assigned with `PyTuple_SET_ITEM` semantics (steal the `PyInt_FromLong` reference); module
registration uses `Py_InitModule4` (static-lifetime `PyMethodDef[]`, `METH_NOARGS`/`METH_VARARGS`).
On partial registration failure the partial module is removed and Hunter is left unavailable.

`player_cookie` is an **opaque integer token** (`PyLong_FromUnsignedLongLong` of the player
address, or `None` when invalid). The raw C++ `player` pointer is never inserted into a
Python container as a `PyObject*`; doing so would let refcounting write into the player
object (a P0 memory-safety defect found in the first review, since corrected).

`max_size` is **not** derived in the native observer. The gateway sources it from the stock
`player.MetinQueueGetMaxSize()` binding (the verified stock query, binding `FUN_140401230`),
and validates that it is positive; the native `snapshot()` reports `max_size: 0`.

## 9. Observer validation (copy before trusting)

`snapshot()` validates before copying: singleton non-null; an all-null empty vector is
accepted; otherwise begin/end must be non-null and aligned, `begin <= end`, byte span
divisible by 4, and length/capacity bounded by 1024 elements (a corruption guard, not the
native capacity). The VIDs are copied into a local buffer, then the singleton and vector
metadata are re-read and compared; a change invalidates the snapshot. Access faults are
caught and return `valid=False` with a stable ASCII reason (never "empty"/"absent").
`stock_binding_ok` is `*(void**)(base+0x7525778) == base+0x004011C0`.

## 10. Executable identity gate

`EXPECTED_TIMESTAMP = 0x6AD21E5A`, `EXPECTED_IMAGE_SIZE = 0x09735000` (loader PE check).
If the installed `app\Lirin.exe` SHA-256 is not `8B6F5EA9…A75A0`, none of these RVAs,
bindings, or layouts are valid and native work must stop until re-established.
