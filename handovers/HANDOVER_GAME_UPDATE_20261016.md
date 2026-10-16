# Handover: 2026-10-16 game update — RVA re-derivation

Target: 64-bit game `C:\Program Files (x86)\Lirin\app\Lirin.exe`.

## Build identity change

| Field | Old (2026-10-10) | New (2026-10-16) |
| --- | --- | --- |
| SHA-256 | `DBD69CAD…D3636D72F2` | `8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0` |
| PE timestamp | `0x6ACA943D` | `0x6AD21E5A` |
| SizeOfImage | `0x094C1000` | `0x09735000` |
| Entry point | `0x065C62D0` | `0x067DB140` |
| File size | 131,253,248 | 133,787,648 |

The update grew `.text` by ~2.2 MB (code added) and changed at least one struct
offset. All RVAs in `python_loader.cpp` were re-derived and the loader rebuilt.

## How the RVAs were re-derived

The autopatcher (Tauri/Rust launcher) pulls `config.json` + `files.json` from
`https://live.lirin.dev/`. 14 of 31 files changed; `Lirin.exe` and 13 asset
packs. Only `Lirin.exe` matters for the injected offsets.

Method (no full Ghidra re-analysis needed):
1. Byte-signature matching with RIP-relative / rel32 / address-immediate
   wildcards (Capstone). The embedded Python 2.7.18 and most Cython wrappers
   are byte-identical except for displacements.
2. Xref relocation for the data globals: a RIP-relative reference inside an
   already-relocated function gives the global's new address.
3. `.reloc`-free .bss handling: `INPUT_RECORDER` lives past `.data`'s raw size,
   so it was resolved from two independent code xrefs (both agreed).

## Final RVA map (old -> new)

Python API (RunProbe):
- GIL_ENSURE            `0x00AB1520 -> 0x00AF2750`
- GIL_RELEASE           `0x00AB15D0 -> 0x00AF2800`
- IMPORT_ADD_MODULE     `0x00ABED90 -> 0x00B0D5D0`
- MODULE_GET_DICT       `0x00AA9820 -> 0x00B07000`
- RUN_STRING_FLAGS      `0x00AB5E60 -> 0x00AF7090`
- TLS_GET_VALUE         `0x00ACA170 -> 0x00B069C0`
- AUTO_INTERPRETER_STATE `0x07B9AC88 -> 0x07DFB058`
- CURRENT_THREAD_STATE  `0x07B9AC70 -> 0x07DFB040`
- AUTO_TLS_KEY          `0x07B9AC90 -> 0x07DFB060`

Feature:
- CHARACTER_MANAGER     `0x07A6B450 -> 0x07CCAB10`
- PLAYER_SINGLETON      `0x07A6B6B0 -> 0x07CCAF00`
- METIN_QUEUE_ADD_METHOD `0x072ECA18 -> 0x07525778`
- METIN_QUEUE_ADD_BINDING `0x003F6360 -> 0x004011C0`
- PARSE_TUPLE_INTEGER   `0x00897B40 -> 0x008C7020`
- ARGUMENT_ERROR        `0x00897E40 -> 0x008C7320`
- BUILD_VALUE           `0x00A6B650 -> 0x00AA5EA0`
- INTEGER_FORMAT        `0x066E218C -> 0x068FB3CC`
- GET_ACTOR_BY_VID      `0x003D1D40 -> 0x003EE6D0`
- RECORD_INPUT          `0x00471B10 -> 0x00497840`
- INPUT_RECORDER        `0x07A6BA20 -> 0x07CCB198`
- GET_CURSOR_POSITION   `0x007E13B0 -> 0x00824180`
- GAME_INSTANCE         `0x07A6B480 -> 0x07CCAB50`
- GAME_DOWN_DISPATCH    `0x007E3E70 -> 0x00826C30`
- GAME_UP_DISPATCH      `0x007E3FD0 -> 0x00826D90`
- APP_GLOBAL            `0x07A734C0 -> 0x07CD3168`
- GET_ACTOR_POSITION    `0x004A2EC0 -> 0x004D2E40`
- PROJECTION_SETUP      `0x0061CA10 -> 0x0065B530`
- PROJECT               `0x0061E430 -> 0x0065CEF0`
- CAMERA                `0x07A6B678 -> 0x07CCAB48`
- POS_Y_OBF             `0x066E6050 -> 0x068FCCF0`

`SET_MOUSE_STATE` (`0x003E5940`) is dead code since v35 and was left stale with
a `STALE` comment; it is never referenced.

## Struct offsets — verified unchanged

- Queue vector `player+0x4588/0x4590`: confirmed in new low-level
  `MetinQueueAdd` (now `0x1403ED760`, reached via the relocated binding).
- Character tree head `manager+0xF8` and `CharacterNode` layout
  (`is_nil@0x19`, `vid@0x20`, `actor@0x28`): confirmed in real `GetActorByVid`
  (`0x5353B0`) and by the `static_assert`s passing at build time.
- `picked_actor@0xE0` and `mouse_down@0xFF` sit before those confirmed offsets,
  so they are unchanged (a field insertion would have shifted the later ones).
- `game_instance` viewport/cursor fields (`0x18/0x1c/0x20/0x24/0x30/0x34`)
  unchanged in `GAME_DOWN_DISPATCH`.

The ONE offset that changed is internal to `GET_ACTOR_POSITION` (actor position
sub-object `0x548 -> 0x558`); the loader calls that function and does not use
the offset directly.

## Rebuild

`python_loader.cpp` updated; `build.ps1 -FeatureOnly` succeeded.
`client_feature_loader.dll` = 151,552 bytes, SHA-256
`9AB8648749186C0A67608D90CF56779AF6CFCA19B78FFFD20C4B145B0AC9CC87`.

Re-inject with `run_client_feature.ps1` as usual. Verify `EXE build matched` in
the loader status before trusting queue behavior.
