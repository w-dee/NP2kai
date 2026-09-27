# Phase C: experimental ARTIC machine time

**Default OFF; cold-boot qualification only. Save/load is rejected in the
experimental build.** Only ARTIC elapsed phase receives machine-time authority.
ESP32-P4 remains the [normative realtime target](multiplierless-realtime-policy.md).
Deterministic fake time is canonical for Linux semantics; live Linux runs are
supporting integration evidence. Read the [guest-oracle contract](guest-oracles.md)
before interpreting any integration PASS.

## Bounded hardware authority

The NEC *PC-9800 Series Technical Data Book, HARDWARE*, revised edition dated
1993-10-25, chapter 9, printed pages 89–92, supplies the bounded ARTIC contract
([primary scan](https://vtda.org/docs/computing/NEC/PC-9800TechnicalDataBookHARDWARE%2BOCR_1993.pdf)):
read-only, free-running 24-bit binary phase; nominal 307,200 ticks/second
independent of CPU clock; aligned word IN 005Ch gives bits 0–15 and aligned
word IN 005Eh gives bits 8–23; wrap is modulo 2^24. Availability is a separate
capability condition, including the documented PC-H98 exception to the ROM
capability indication. These assertions apply to the bounded ARTIC-equipped
class, not every PC-98 family.

The IPL qualifies `SYNTHETIC_EMULATOR_ARTIC_MODEL` against that model. It records
the BIOS capability byte without modifying it. This is not
`PHYSICAL_ARTIC_CAPABILITY_CONFIRMED`, nor physical VM/VX qualification.
Byte access, odd-word aliases, cross-port atomic snapshots, latches, physical
reset phase and power-saving oscillator behavior remain unqualified.

## Selection and ownership

CMake options, both default OFF:

| Option | Meaning |
| --- | --- |
| `NP2_ARTIC_MACHINE_TIME=ON` | Compile the experimental binding and arithmetic; reject save/load. |
| `NP2_ARTIC_FAKE_TIME=ON` | Select the private deterministic provider; requires machine-time mode. |

With machine-time ON and fake OFF, select the Linux `CLOCK_MONOTONIC` provider.
The pilot configuration accepts Linux SDL2 interpreter builds, i286 or IA-32,
and rejects asynchronous CPU, HAXM and other frontends. There is no runtime
switch, public command option, guest protocol, thread or periodic ARTIC event.
Build directories must be configured with the repository's existing SDL2
options in addition to these options.

OFF compiles the existing ARTIC callback/lazy CPU-ledger implementation. Its
known signed-overflow hazards remain outside this change; legacy tests keep
inputs in its established safe range. The new sources are absent from OFF.
The [legacy time-domain adapters](time-domains.md) retain their meaning.

ON retains the existing I/O dispatch and makes `artic_getcnt()` call
`artic_machine_read()`. The old periodic callback does no work in this mode.
Only the ARTIC reader consumes the new phase. CPU budgeting, NEVENT, PIT, PIC,
GDC/VSync, OPNA/PCM, DMA, RTC, mouse, serial/MIDI, TSC, audio and presentation
retain their existing authorities. [Phase B](time-shadow.md) remains diagnostic;
ARTIC never reads its state or cached target.

## Private provider and exact representation

`artic_time.h` depends only on integer types. `ARTIC_SAMPLE` supplies
`{ ns: uint64_t, valid: int }`. `ARTIC_TIME` holds a 24-bit phase, fractional
remainder, accepted machine-time anchor, anchored flag and saturating rejection
counter. None is serialized.

- `artic_time_reset(state)` clears the arithmetic state.
- `artic_time_observe(state, sample)` accepts a valid nondecreasing observation,
  advances exactly, and returns 1. Invalid/backward input returns 0, retaining
  phase, fraction and anchor; only the diagnostic rejection count changes.
- `artic_time_source()` supplies a fresh observation at each read and reset.
- `artic_machine_reset()` clears phase/fraction and samples a new anchor.
- `artic_machine_read()` observes the provider and returns phase.

The first valid observation anchors without advancing. If reset sampling
fails, the next accepted sample establishes the epoch; there is no CPU fallback.
Repeated timestamps preserve phase and fraction exactly.

The rate is `307200 / 1000000000 = 24 / 78125` ticks/ns. For accepted elapsed
nanoseconds `delta`, the production calculation is:

```text
q, r = divmod(delta, 78125)
z = r * 24 + remainder
ticks = q * 24 + z / 78125       # integer division
remainder = z % 78125
phase = (phase + ticks) & 0x00ffffff
```

`0 <= remainder < 78125`; therefore `z <= 1,953,100`. Even for
`delta = UINT64_MAX`, `q * 24` is less than 2^53. Adding `z / 78125` and a
24-bit phase still fits uint64. Subtraction follows the backward check; no
signed arithmetic, floating point, CPU cycles, multiplier or base clock enter
this path. Integer remainder retention makes interval partitioning exact.

`artic_time_fake.c` exposes only a private host symbol `artic_fake_sample`.
Host tests or a stopped debugger set it; guest software cannot control it.
`artic_time_posix.c` makes a fresh checked `clock_gettime(CLOCK_MONOTONIC)` call,
validates its range and converts to ns with an overflow check. It has independent
ownership and freshness from Phase B.

A future ESP32-P4 provider can implement `artic_time_source()` using authoritative
monotonic ns and explicit validity without changing arithmetic or port semantics.
It must preserve single-owner access, fresh observations, nondecreasing accepted
time, and separately qualify source resolution/range and service deadlines.
The current CMake frontend restriction would need a reviewed platform extension.
No ESP32-P4 implementation or final pause/suspend/recovery policy is supplied here.

## Compatibility and lifecycle

Existing byte mappings remain 005Ch=bits 0–7, 005Dh/005Eh=bits 8–15,
005Fh=bits 16–23. Odd word aliases remain 005Dh→005Ch and 005Fh→005Eh.
They are **legacy compatibility**, not new physical hardware assertions.
Each read independently observes time; no cross-port atomicity is asserted.

OUT 005Fh still debits exactly 20 legacy CPU cycles in either mode. It does
not advance frozen fake machine time. This is not a physical 600 ns wait claim.
Reset-to-zero is `LEGACY_COMPATIBILITY_POLICY`: clear phase/fraction and recreate
the runtime anchor, without claiming physical power-on/reset phase.

Experimental builds return `STATFLAG_FAILURE` at the entry to
`statsave_save`, `statsave_load`, `statsave_save_d`, `statsave_load_d`,
`statsave_check`, `statsave_save_hdd` and `statsave_load_hdd`, before queue,
file or device mutation. The check API also supplies a cold-boot-only diagnostic
when a buffer is provided. This prevents loading legacy ARTIC state or writing
experimental state under the legacy eight-byte chunk. The state format,
version, table and legacy struct are unchanged; OFF retains its save behavior.

## Qualification and PASS boundary

See [the ARTIC IPL README](../../tests/guest/i286-time-artic/README.md) for its
versioned RAM block, exact F01–F17 evidence mapping and private GDB runner.
The Linux x86_64 runner exercises actual guest word IN instructions on both
emulator backends. It sets fake source samples before each real handler,
checks the returned phase/fraction, and compares CPU/PIT/PIC/GDC/DMA state
before and after that handler. A CPU work loop establishes progress while
fake time is frozen. The +20 ms read executes with unchanged CPU ledger and
adds exactly 6,144 ticks. This proves bounded read isolation, supplemented by
the source/dependency scan for all excluded consumers.

Focused commands from the repository root:

```sh
python3 tools/test_artic_time.py
python3 tools/test_artic_save.py --build build_phase_c_i286_fake
python3 tools/test_artic_save.py --build build_phase_c_ia32_fake
python3 tools/guest/test_i286_time_artic.py
```

Arithmetic/binding tests use strict warnings and UBSan, including UINT64-scale
intervals, 10,000 irregular partitions, transitions of multiplier/base mode,
rejection, reset, aliases and OUT005F. Save tests compile the actual configured
production save object; no file/device dependencies remain reachable when the
rejection functions are linked into the test.

Initial qualification ran both backends at base clocks 1,996,800 and 2,457,600,
with multipliers 1, 4 and 20: twelve fake-time semantic PASS runs, plus two
legacy observation runs. OFF ARTIC and save `.text` matched the parent under
identical compiler flags on both backends. An access microbenchmark measured
parent/OFF/fake/live separately; its Linux measurements are not a realtime
resource gate or an ESP32-P4 prediction.

The existing OFF and live integration matrices cover N1, N2, N3, i286 DOS/FMP,
IA-32 DOS/VEM486/FMP and the complete Windows 95 state machine. Their PASS
claims remain exactly those in the oracle contract. In particular, FMP prompt
return is command completion; the i286 runs also observed approximately ten
seconds after return. No AUDIO PASS is claimed. Windows 95 completion requires
the final IntelliPoint state, not the early desktop.

A canonical fake-time PASS establishes implementation of the bounded ARTIC
model, CPU/machine-time independence, exact rational phase/fraction and preserved
compatibility surfaces. It does not establish physical target identity, audio,
other-device timing, service deadlines or final lifecycle policy. Linux live
integration is supporting only. Debugger-stopped live runs are
`INCONCLUSIVE_REALTIME_SEMANTICS`; no numeric Linux envelope is selected, and
successful boot cannot promote live timing to canonical authority. The pilot
may close as `PASS_PHASE_C_ARTIC_FAKE_TIME_PILOT_LIVE_LINUX_INCONCLUSIVE` while
all integration checkpoints pass. Promotion to default is not authorized.
