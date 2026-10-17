# Hunter audit evidence (bounded investigations)

Date: 2026-10-17. Status of each task: `VERIFIED`, `PARTIAL`, or `UNRESOLVED`, kept
separate from the mutation-safety contracts in `HUNTER_NATIVE_API_CONTRACT.md`. Completing
each attempt is required; fully resolving the recorder protocol is an evidence enhancement,
not a gate on local Hunter implementation.

Binary identity: `C:\Program Files (x86)\Lirin\app\Lirin.exe`, SHA-256
`8B6F5EA90AE62F4FB54752B187897D60962AD80FF71BFC0A7BF277D5A52A75A0`.
Decompilation sources: recovery `native_traces\recorder\`, and this worktree's
`native_contracts\` for anything re-derived.

## A. Incoming audit configuration / trigger — PARTIAL

Entry points inspected:

- Adapter export `FUN_1403c1000` (`1403c1000.c`) reads its payload as: enabled byte at
  `+0`, 16-bit sample value at `+2`, 16-bit flush value at `+4`, and calls
  `FUN_140498eb0(recorder, enabled, sample, flush)`. These are **adapter input offsets**,
  not verified wire offsets/padding/endianness/packet length.
- Config routine `FUN_140498eb0` (`140498eb0.c`) VERIFIED: frees the buffered sample
  vectors (`+0x18/+0x20` at stride `0x50`, `+0x30/+0x38`, `+0x48/+0x50`), clears a
  coordinate-store vector (`+0x78/+0x80`), zeroes stored coordinates (`+0x9C/+0xA0`) and the
  dirty flag (`+0x90`), then writes effective settings: `+8 = enabled`, `+0xA = sample_ms`
  (zero → 100), `+0xC = flush_ms` (zero → 200), and resets timers `+0x10/+0x14/+0x60/+0x94`
  from the current monotonic time. It does not itself emit a record or send.

Findings: the config substitution (100/200 ms for zero) and the buffer/coordinate resets are
verified. Who invokes `FUN_1403c1000`, the receive dispatch/deserializer that fills its
payload, the registration-table index, and any numeric packet/message opcode are
**UNRESOLVED** — a registration-table index is not assumed to be a network opcode, and this
callback is not assumed to be reached directly by one packet. Startup/local-setting paths
were not excluded. Next step: trace data references to `FUN_1403c1000`'s registration slot
and the receive dispatch to a verified opcode; until then no incoming trigger is named.

## B. Outgoing record / flush serialization — PARTIAL

Entry points inspected (`native_traces\recorder\`):

- Sample construction `FUN_1404939e0` (`1404939e0.c`): builds one in-memory sample with
  normalized 16-bit coordinates `(x*10000/screen_w)`, `(y*10000/screen_h)`, a byte of
  button/state flags at `+3`, a code byte at `+7`, and later fields holding cursor/state
  counters and the picked VID. Button flags come from `player+0xFF/+0x100` held state when
  `app+0x20 == 0`, else `GetAsyncKeyState`; a queue-enabled/empty bit is OR-ed into the
  flags. This confirms the held-state branch and that background code-0 samples read stored
  coordinates, but not a complete field map.
- Click append `FUN_140497840` (`140497840.c`): if enabled, builds a sample (code = arg,
  coords) and appends via `FUN_1404978b0`.
- Periodic sampling `FUN_140499340` (`140499340.c`): on the sample timer, appends a code-0
  sample (stored coords when background, else live cursor) and checks the flush timer.
- Dirty queue-list snapshot `FUN_140499480` (`140499480.c`): when the dirty flag is set,
  copies the queue vector `player+0x4588..0x4590` and, on change, sends it via
  `FUN_1403816d0`; resets the flag after 200 ms. This is the separate recorder queue-list
  snapshot, distinct from the ordinary state/count path.
- Flush `FUN_140494610` (`140494610.c`): walks the buffered samples (stride `0x50`), applies
  delta encoding (code-0 timestamps compressed against `sample_ms`), and serializes into an
  output vector before calling `FUN_140381720`.
- Sender `FUN_140381720` (`140381720.c`): builds a small header (screen width/height as two
  16-bit values), copies the 0x50-byte element vector, and calls the serializer
  `FUN_14033e2e0(game, &header, 0)`.

Findings: the **in-memory** 0x50-byte element stride is established, but that stride is not
a demonstrated wire-record length. The actual wire framing/opcode, field order/width,
encoding, byte order, variable-length fields, compression/delta format, batching/dedupe and
the reachability of a final send through `FUN_14033e2e0` and its helpers are **UNRESOLVED**.
Local dirty state is not transmission or server receipt. Next step: decompile
`FUN_14033e2e0` and its serializer helpers to establish framing; until then no exact
opcode/wire-byte/audit-window claim is made, and any fixture is labeled "constructed from
verified layout", never captured server traffic.

## C. Read-only audit-status query

`audit_status()` reads only verified singletons/fields already exercised by the loader:
`recorder` (`RVA 0x07CCB198`) `+8` enabled, `+0xA` sample_ms (16-bit), `+0xC` flush_ms
(16-bit); `app` (`RVA 0x07CD3168`) `+0x20` app-active byte. It returns
`{valid, error, observed_tick_ms, recorder_enabled, sample_ms, flush_ms, app_active}`.
It does not call record/config/tick/flush/sender routines, reset buffers, read unbounded
sample buffers, or change scheduling/input state. `valid=False` means unknown state, never
"recorder-disabled". No additional unbounded counters are exposed (their exact meaning is
not independently proven). Missing capability permits local Hunter work but blocks any
claim of live audit coverage.

## Evidence rules applied

- Stock add generates no accompanying click record itself; independent periodic recorder
  samples can still occur. Dirtying does not prove immediate transmission or server receipt.
- The recorder-comparison explanation (H-AUDIT) remains a hypothesis, not an established
  disconnect cause; its mechanism and priority over other causes are unestablished.
- The distinction between local correctness, live behavior, audit exposure and server
  acceptance is preserved; no fabricated input, recorder manipulation, size-based
  acknowledgement, silent fallback, or blind retry is introduced.
