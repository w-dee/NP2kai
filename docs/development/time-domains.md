# Phase A: explicit legacy time domains

Phase A preserves the cycle-derived timing policy. It introduces an internal
adapter, not a new clock source. The baseline authority is parent
`084f9919fbc4f659b94c3ecffdcf25380691ead7` and the bounded time-dependency audit.

## Units and ownership

| Domain | Representation / interface | Owner and meaning |
| --- | --- | --- |
| CPU cycle ledger | Existing `CPU_CLOCK`, `CPU_BASECLOCK`, `CPU_REMCLOCK` | Backend instruction costs debit signed remaining budget; NEVENT commits and rebases slices |
| Device observation | `LEGACY_CYCLESTAMP`, `legacy_cpu_device_now()` | Unsigned 32-bit `committed + slice - remaining`; a read does not dispatch or advance devices |
| Committed CPU cycles | `legacy_cpu_committed_cycles()` | Accumulated slice boundaries only; intentionally different from the in-slice observation |
| Scheduler deadlines | `LEGACY_DEADLINE`, existing signed `NEVENTITEM.clock` | Offset from current slice origin in legacy CPU-cycle units; may be negative |
| Conversion settings | `pccore.baseclock`, `multiple`, `realclock`, `maxmultiple` | Configured base Hz, dimensionless multiplier, derived cycles/virtual-second and configured multiplier ceiling; not CPU slice budgets |
| Host pacing | Existing `timing_getcount` and frontend policy | Host milliseconds/fractional frame counts; not NEVENT units or authoritative device progress |
| Civil calendar / output | Existing calendar and audio code | Existing wall-calendar mode, frame-derived calendar, and host audio demand remain separate policies |

`legacytime.h` holds arithmetic contracts and unit aliases. `legacycpu.h`
binds those operations to the selected existing CPU ledger. There is no new
persistent state, allocation, lock, thread, public symbol, or save field.
Aliases document units; they are not C strong types and do not prevent every
incorrect conversion. The existing serialized structures retain their types.

## Exact accounting contracts

Write K=committed, B=slice budget, R=remaining. Device position is
`C = K + B - R`. The first addition is unsigned 32-bit; wrap occurs before a
caller widens to 64-bit (important for PCM86). Slice elapsed `B-R` remains
signed. Negative R carries instruction overshoot; no clamp or saturation is
introduced. Signed arithmetic keeps the original representability assumptions:
this refactor does not define new behavior for signed overflow.

- Rebase by d: `B -= d; R -= d`, preserving C.
- Progress: `K += B`; subtract the old B from event offsets; select the next B;
  `R += next_B`. This also preserves C, including overshoot, before callbacks.
- Begin/reset slice: set both B and R to the selected deadline.
- Force exit: only when R>0, subtract R from B and set R=0. No unexecuted work
  is charged. This is different from existing BIOS/backend `R=-1` yields.
- External `legacy_cpu_charge(cost)` preserves the original `R -= cost`
  operand promotions, including unsigned/size_t costs. It evaluates cost once
  and introduces no instruction boundary, interrupt check or DMA service.

NEVENT ABSOLUTE remains `eventclock + (B-R)` (from the current execution
position); RELATIVE adds to the previous stored event deadline. Neither is an
absolute host timestamp. One slot per ID, stable tie insertion, signed past
positions, SETEVENT/WAIT, periodic relative rearm and callback ordering remain
unchanged. `nevent_forceexecute` still calls directly without cancelling an
existing queued event. `nevent_getremain` still returns -1 for an absent ID.

The clock-change path retains its original positive-deadline rescaling,
rounding and INT_MAX clamp; nonpositive event offsets are not rescaled. At a
slice boundary it begins the newly selected slice; otherwise the existing
signed-64 intermediate rescale of B and R remains explicitly scheduler-owned.
This conversion changes the configured legacy rate, not the timing policy.

`legacy_configured_rate(base_hz, multiple)` retains the original product.
`legacy_deadline_from_ms(rate, ms)` retains **division before multiplication**,
UINT64 promotion of ms (including negative input), and the original unsigned
`INT_MAX-rate` bound. Device-specific formulas are not generalized: PIT count
multiplication, GDC geometry division then multiplication, OPNA timer constants,
PCM86 fixed-point/modulus arithmetic, serial/MIDI baud division, mouse/HRT
rates and ARTIC divisors keep their exact operand order, widths and rounding.

## Migration and retained dependencies

| Before | Phase A |
| --- | --- |
| Canonical `CPU_CLOCK + CPU_BASECLOCK - CPU_REMCLOCK` in device/audio/input code | `legacy_cpu_device_now()` |
| Deliberate `CPU_CLOCK` observations in PIT beep and sound initialization | `legacy_cpu_committed_cycles()` |
| `CPU_BASECLOCK - CPU_REMCLOCK` in NEVENT and GDC | `legacy_cpu_slice_elapsed()` |
| External `CPU_REMCLOCK -= cost` in BIOS/HLE, storage, I/O, ARTIC, memory/video and WAB | `legacy_cpu_charge(cost)` |
| NEVENT slice initialization/commit/rebase/continuation/forceexit | Named `legacy_cpu_*` ownership operations |
| `baseclock * multiple` when setting `realclock` | `legacy_configured_rate(...)` |
| NEVENT millisecond conversion | `legacy_deadline_from_ms(...)` |
| Core positive-budget execution guard | `legacy_cpu_remaining() > 0` |

Intentionally retained direct mutations/dependencies:

- `i286c/`, `i286x/`, `i386c/` backend timing state and instruction/memory
  macros (including V30 paths): WORKCLOCK, instruction overshoot, HLT, STI/MOV
  SS extension, REP restart, trap/fault reset/refund. They own instruction
  semantics and their existing external contract is preserved. No new yield
  reason or safe point is introduced. The i286x assembly and HAXM variants
  are inventoried, not runtime-qualified by the two SDL interpreter builds.
- `i386hax/`: accelerated timing/pacing and ledger resets remain accelerator
  owned; no unification with the interpreter or host time source is attempted.
- `bios/bios.c:biosfunc`, `bios/bios18.c:bios0x18`,
  `bios/bios1b.c:bios0x1b_wait`, `bios/sxsibios.c:sasibios_operate` and
  `io/gdc.c:gdc_i60/gdc_ia0`: existing `CPU_REMCLOCK=-1` busy/yield paths.
  These terminate the existing execution budget, not ordinary cycle charges.
  GDC SEARCH_SYNC guards and its instruction inspection are unchanged.
- `nevent.c:nevent_changeclock`: paired signed-64 rescaling assignments and
  the boundary test remain together in their owning function, with exact
  existing arithmetic. This is a conversion operation, not timestamp rebasing.
- `pccore_exec`, `i386c/ia32/instructions/system_inst.c`,
  `cbus/board118.c`, `cbus/boardsb16.c`: TSC and gameport mapping retain the
  original slice/remaining and maxmultiple/multiple expressions and ordering.
- `io/mouseif.c` without VAEG_FIX: the historical **plus** remaining-budget
  expression is deliberately not replaced by the canonical minus expression.
- Windows/wx/X speed displays still read committed CPU_CLOCK. Commented-out
  experiments are left intact. These are not device timestamp consumers.

Generic DMA still gets execution opportunities from the existing backend
loops; timed sound DMA stays event-driven. No new service call was inserted.
FDC frame-delay and IDE raw-cycle delay paths remain in their existing domains.
Calendar advancement, frontend NOWAIT/frame skipping/event pumping, audio
callback/queue scheduling, synthesis tail fill and latency policy are unchanged.
Existing optional asynchronous producers are not made safe by this adapter;
no new ownership thread or concurrency claim is introduced.

## Save/load and future seam

CPU_STATSAVE/PCCORE/NEVENT structures and `statsave.c`/`statsave.tbl` are not
restructured. Saved K/B/R and event offsets retain their units and layouts;
callback reconstruction and userData handling remain as before. No format bump,
new epoch or compatibility reinterpretation is made.

Phase B can compare a separate host-monotonic target against the legacy
observation/commit seam. Such a target must initially have **no guest-state
authority**. Switching device progression, TSC, pause/resume, saved epochs,
DMA service or output policy requires a later reviewed contract. Phase A adds
no host clock reader to this interface and no shadow accumulator.

## Verification

```sh
python3 tools/test_legacy_time.py
make -C tests/guest/i286-time-n1 verify test
make -C tests/guest/i286-time-n2 verify test
make -C tests/guest/i286-time-n3 verify test
```

The focused test compiles the actual parent NEVENT source from Git and the
current source against the same small ledger/config test bindings. 512
scenarios compare 80 exact state tuples each: full event slots/order/flags,
K/B/R, callback history and remain/work queries. They cover tied and past
deadlines, replacement, periodic rearm, WAIT, forceexecute, forceexit,
rescaling and unsigned timestamp wrap. Separate arithmetic tests exercise
signed overshoot, mixed-width charges, configured rate and millisecond bounds.
The harness uses actual NEVENT code, not a second idealized scheduler.

A repeatable host benchmark alternates parent/current order over seven trials
of 20 million scheduler iterations; CPU time is performance evidence only.
There is no production tracing or disabled-trace branch. External charges are
macros to avoid per-access calls; arithmetic helpers use the project's INLINE.

Both SDL2/i286 and SDL2/IA-32 builds, N1/N2/N3, DOS/FMP on both backends and
the complete Windows95 state machine are required integration gates. Local
qualification adapters may select the rebuilt binary and record its identity
and source diff; fixture images, validators, expected values and visual
thresholds must stay unchanged. FMP screens confirm guest integration, not
PCM/audio fidelity. Save compatibility evidence is unchanged layout and
serialization implementation, not a newly claimed exhaustive resume matrix.
