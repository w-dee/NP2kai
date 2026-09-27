# Phase D1 PIT0/PIC compatibility machine time

This private, default-OFF pilot replaces the time parent of PIT channel 0 and
its IR0 publication/PICMASK effects. The authority is the owner-approved
**LEGACY_COMPATIBILITY_PROFILE**, pinned to parent
`1dbcac20adfa4aba5fe979fbf5ef371deed41686` and reference multiplier **M_ref=5**.
It follows the [normative realtime policy](multiplierless-realtime-policy.md)
and preserves the [guest-oracle contract](guest-oracles.md).

The historical audit remains `BLOCKED_PHASE_D1_PIT_PIC_HARDWARE_AUTHORITY`.
H01A (VM/VX physical timer/controller identity), H02A (GATE0 and OUT0-to-IR0
board transfer, polarity and request storage), and NEC71054 mode-3 mid-half
replacement remain **INCONCLUSIVE_NEEDS_HARDWARE_AUTHORITY**. No physical OUT
waveform or electrical INTA model is added.

## Profiles and the owner-selected reference

| Profile | Identity |
| --- | --- |
| `PROFILE_I286` (fixture 1) | Parent i286 PIT/PIC port, flag, count and finite-state behavior, normalized at M_ref=5. |
| `PROFILE_IA32_71054_SELECTED` (fixture 2) | Parent IA-32's currently selected `uPD71054` code path, including status/readback byte behavior, normalized at M_ref=5. |

These names identify emulator backends, not physical timer silicon. Both use
the same PIT0 advancement calculation; existing conditional PIT handlers retain
their profile differences. No primary hardware proposition is changed.

The owner selected M=5 after a parent-code probe showed that runtime integer
rounding makes simultaneous preservation of parent M=1/4/20 observations
impossible. The owner's cited np2_espresso M=5 operating experience is
engineering precedent for this choice, not PC-98 hardware authority. Historical
parent M=1/4/20 observations remain evidence, not experimental requirements.

### Exact normalization rules

One internal reference quantum is **1/5 PIT source tick**. Let
`P(N) = 5 * (N > 8 ? N : 65536)`. The reference does not read the runtime
CPU multiplier.

| Conversion | Frozen M=5 compatibility calculation |
| --- | --- |
| Timer reload/deadline | `P(N)` reference quanta |
| PICMASK after masked periodic IRQ0 | `floor(P(N)/4)` reference quanta |
| Current count | `floor(remaining_reference_quanta/5)`, then existing 16-bit/byte encoding |
| Fractional phase | Absolute source grid at 5 times the selected legacy PIT source frequency; writes preserve the fractional grid phase. |

For N>8, PICMASK is `floor(5*N/4)/5` source ticks. N=9 gives
`11/5 = 2.2`, **not** exact N/4. At two source ticks after publication IRR0 is
still set; immediate unmask and normal eligible arbitration accept one IRQ.
At 2.2 ticks, if still masked, the workaround clears it. N<=8 retains
16384 source ticks for PICMASK and 65536 for the timer.

Current reads also contain a legacy clock-quantization artifact. For a reload
N>8 before expiry, at elapsed source time x, the frozen result is
`floor((5*N - floor(5*x))/5)`. For example N=9 at x=0.1 yields 9 under
M=5, while parent M=20 yields 8; at x=0.2 M=5 yields 8 while parent M=1
still yields 9. Executable parent probes record these differences. They are
pure integer conversion artifacts of the same owner-authorized class.
They are **LEGACY_COMPATIBILITY_ASSERTION**s, not physical counter edges.

The source rates are the existing configured clock classes: 1996800 Hz for
`CPUMODE_8MHZ`, otherwise 2457600 Hz, selected at cold reset. Equivalent
source-clock programming and normalized observation times match in both
families. Identical nanosecond intervals naturally give different counts
between these two device clock classes. Runtime CPU throughput multiples
1/4/20 do not select the experimental result.

## Build, rollback, ownership

CMake options:

- `NP2_PIT_PIC_MACHINE_TIME=OFF` (default): parent scheduling and reads.
- `NP2_PIT_PIC_MACHINE_TIME=ON`: private PIT0/IR0 machine-time ownership.
- `NP2_PIT_PIC_FAKE_TIME=ON`: deterministic private debugger/host-test source;
  requires the pilot. Otherwise the pilot uses fresh Linux CLOCK_MONOTONIC.

The qualified build is Linux SDL2, i286 or IA-32 interpreter, single owner,
with async CPU and HAXM disabled. No runtime switch, product INI option,
guest control port, worker thread, or dependency change is introduced.
ARTIC machine time can remain OFF to isolate this migration.

Seven production save/load/check entry points reject before queue/file/device
mutation whenever either ARTIC or PIT/PIC machine time is enabled. The combined
guard preserves ARTIC's restriction. No save format, version, legacy chunk,
or host timestamp serialization changes. Cold boot is mandatory.

## State and time provider

`pit0_time.h` exposes a platform-neutral observation and next-deadline seam.
`PIT0_TIME` holds the accepted nanosecond anchor, fractional reference quantum,
remaining timer and mask deadlines, equal-deadline insertion order, and
saturating diagnostics. The programmed value, access mode, interrupt arm bit,
latch and byte phases remain in the existing `pit.ch[0]`. PIC IRR/ISR/IMR
remain the finite controller state; no missed-IRQ counter drives acceptance.

For accepted delta d, the exact conversion is:

```text
numerator = 780 (1996800 Hz) or 960 (2457600 Hz)
part = (d % 78125) * numerator + fraction
quanta = (d / 78125) * numerator + part / 78125
fraction = part % 78125
```

The split prevents uint64 multiplication overflow even at the largest delta.
First valid observation anchors the epoch. Invalid or backwards samples leave
guest state and the accepted anchor unchanged and increment a saturating
rejection diagnostic. No clamp/freeze/catch-up product pause policy is chosen.
`services`, `max_gap_ns` and `collapsed` are diagnostic only.

`pit0_time_source()` returns a fresh `{ns, valid}`. The fake symbol
`pit0_fake_sample` is controlled only by private host qualification machinery.
Neither provider reads CPU progress, the multiplier, cached Phase-B shadow
time, ARTIC state, or another device clock.

## Service and existing CPU acceptance

`pit0_machine_service()` samples the source and advances only PIT0 plus IRR0.
It cannot execute guest instructions or accept an interrupt.

| Service point | Purpose |
| --- | --- |
| Existing `pic_irq()`, before its IF gate | Materialize elapsed IR0 effects at the existing scheduler/arbitration boundary, including IF=0 and HLT. |
| PIT ch0 `pit_setflag`, `pit_setcount`, `pit_getstat` | Settle old state before observing/programming the channel. Pointer guard excludes other channels. |
| IA-32 readback selecting ch0 | Settle before the direct latch path that bypasses `pit_setflag`. |
| PIC command/mask/read handlers | Settle before observable IRR/ISR/IMR changes and EOI/init operations. |
| BIOS INT 1Ch direct IRQ0 unmask | Settle before the HLE mask write, including the IA-32 queued-I/O path. |
| Cold PIT reset | Select clock class and anchor the new private epoch. |
| Future platform deadline callback | Call the same single-owner service without guest execution. |

The existing `CPU_INTERRUPT` call sites, IF/shadow semantics, HLT resume, REP
restart and CPU scheduler safe points are unchanged. No service call is added
inside an instruction or REP iteration. PIC operations for other IRQs retain
the original controller code; serving PIT0 before a PIC I/O does not give
those IRQ sources a machine-time clock.

## Analytical advancement

Between guest/controller operations the control/value, arm flag and mask
are stable. If elapsed quanta cross the current timer deadline, compute
the number of expiries by division and the final residual by modulo.
The first expiry publishes only if the parent's arm bit was set; the
periodic branch rearms it. Subsequent periodic expiries coalesce to the
last distinguishable IRR0 state. Nonperiodic expiry clears the arm and
reschedules the parent's 65536 fallback counter without periodic publication.

For masked periodic operation, the last publication starts the frozen
PICMASK interval. Its final expiry either leaves IRR0 pending or clears it.
An already scheduled mask can coexist with a rewritten timer; the state
retains parent insertion ordering for coincident deadlines. Publication
replaces an older mask just as the parent's `nevent_set` clears that item's
old callback flag. Arbitration cancels the mask on accepted IRQ0.

There is no loop in either advancement or service, no per-tick/per-period
replay, and no queue of expirations. This analytical result reconstructs
finite state when no intervening guest programming or acknowledgement occurred.
It cannot reconstruct hypothetical CPU acceptances or external operations
that were never executed.

| Legacy mechanism | Experimental equivalent |
| --- | --- |
| `NEVENT_ITIMER`, `systimer`, relative rearm | Reference-quantum timer residual and analytical arm/publication transitions |
| ch0 `nevent_getremain / multiple` | Frozen reference-quantum current count |
| `NEVENT_PICMASK`, `picmask` | Finite mask residual, owner M=5 timeout, conditional IRR0 clear |
| IRQ0 acceptance `nevent_reset(PICMASK)` | Cancel private mask residual |
| Other NEVENT IDs and device callbacks | Existing legacy paths unchanged |

Experimental reset does not enqueue either PIT0 event. The two old callback
bodies are disabled in experimental builds so forced legacy execution cannot
duplicate publication. General NEVENT code and scheduling are untouched.

## Intentionally preserved quirks

All items here are **LEGACY_COMPATIBILITY_ASSERTION**:

- N<=8 and zero use the parent large-count fallback.
- Mode 0 continues a silent fallback counter after its first armed expiry.
- The parent periodic predicate `(ctrl & 0x0c)==4` includes the selected
  mode-2/mode-3 behavior; no physical half-wave correction is added.
- A control write changes flags/mode but does not immediately reschedule the
  active deadline. Completed reload does; a first word byte already changes
  the stored value and can affect a subsequent periodic reload.
- Parent mode-1 armed-write early return remains.
- Ordinary channel-0 control/latch writes clear IRR0. Repeated latch overwrites
  an unread latch and preserves the existing byte sequencing behavior.
- IA-32 selected readback/status behavior and stored status/OUT representation
  remain in the original handler; i286 does not gain an IA-32 readback feature.
- Reset's final channel-0 control value remains the parent's 0x16.
- PIC initialization, ISR, masks, EOI, priority/cascade and SFNM limitations
  remain in shared parent code. The unrelated CRT suppression path is untouched.

## Qualification and claim boundaries

Canonical semantics use deterministic fake time. The reusable tests execute
the actual pinned parent PIT/PIC/NEVENT source at M=5, with isolated stubs only
for CPU acceptance counting and unrelated peripherals:

```sh
python3 tools/test_pit_pic_time.py --output .local/pit-pic-profile
cc -std=c99 -O2 -Wall -Wextra -Werror -fsanitize=undefined \
  -fno-sanitize-recover=all -I. tests/time_domains/test_pit_math.c \
  pit0_time.c -o /tmp/np2-pit-math
/tmp/np2-pit-math
python3 tools/test_pit_pic_save.py --build build_phase_d1_i286_fake
```

The profile differential covers reset, modes 0/1/2/3, LSB/MSB/word writes,
partial and active rewrite, zero/small/large counts, current/latch/repeated
latch/readback/status, exact and multiple-period advances, IF/mask/ISR/EOI,
PIC init, and a controlled legacy IRQ1. Each observation includes PIT fields,
current count, PIC IRR/ISR/IMR/priority/OCW3 and acceptance count. Parent
per-event replay is test-only. Runtime arithmetic has bounded work.

The pure arithmetic test checks fractional/exact deadlines, N=9 mask edges,
invalid/backwards samples, UINT64_MAX handling, and huge-jump partition
invariance. The separate [PIT/PIC IPL](../../tests/guest/i286-time-pit-pic/README.md)
uses actual guest I/O, structured RAM, substantial CPU work with frozen time,
and controlled HLT. Its debugger observes service with CPU and unrelated state
unchanged before normal CPU acceptance resumes.

The original N1/N2/N3 sources, images, assertions and validators are unchanged.
Their OFF gates remain exact. DOS/FMP and complete Windows 95 results support
only their established integration checkpoints. FMP prompt return is command
completion; background observation is separate. No AUDIO PASS or physical
timer equivalence follows.

Linux live is **NON-NORMATIVE**. Debugger-controlled timing is
**INCONCLUSIVE**. In particular, the unchanged N2's fixed reload can outlast
the host's execution of its REP under live time; a missing IRQ during REP is
not by itself a CPU restart failure. Preserve the failed live result and
requalify with deterministic fake expiry at an existing acceptance boundary.
Never lower N2's exact assertions or claim the live run passed.

## ESP32-P4 seam and late service

`pit0_time_deadline` returns the earliest timer or mask transition as an
absolute nanosecond deadline, rounded up to the first representable source
sample reaching the reference quantum. It returns false if unanchored or if
the future timestamp would overflow. The future provider must supply the
authoritative monotonic source and arrange single-owner service at/near the
deadline without changing CPU interrupt acceptance boundaries.

Late service can analytically reconstruct current count, arm state and finite
IRR0/mask state over an interval with stable programming/mask and no CPU ACK.
It cannot invent missed guest observations, intermediate acknowledgements or
the timing/order of other IRQs and guest writes. Service must be ordered before
those distinguishable operations; a cross-thread timer ISR must hand work to
the emulator owner instead of mutating these structs concurrently.

Future ESP qualification must measure scheduled-versus-serviced deadline
lateness, maximum accepted sample gap, backlog/collapsed transitions, provider
failures, IRR publication-to-existing-CPU-acceptance latency, HLT response, and
ordering relative to legacy IRQs and programming. No numeric latency budget,
Linux-derived envelope, suspend policy, or ESP hardware code is selected here.


## Initial qualification results

The parent differential matched 50,520 observations per configuration across
all 12 combinations (606,240 comparisons total), executing both profiles.
The new IPL passed the 12 fake configurations and completed both legacy M=5
observation runs. The owner count9 boundary retained IRR0 at two source clocks;
unmask admitted one IRQ. Huge analytical jumps retained finite state and
matched partitioned advancement.

Default-OFF PIT, PIC, save and BIOS INT 1Ch objects have byte-identical `.text`
to the parent under the same compiler flags on both backends. The isolated
read-plus-arbitration benchmark measured median parent/OFF/fake/huge-jump/live
costs of approximately 5.77/5.68/22.34/21.12/60.91 ns. These are local Linux
CPU-time measurements, with no product performance threshold.

OFF passed exact N1 6/6, N2 3/3 plus 32 KiB identity, N3 2/2 plus DMA identity,
both DOS/FMP oracles and complete Windows 95. Experimental live passed N1,
N3, both DOS/FMP and complete Windows 95. Live N2 completed its copy before
IRQ0 expiry: its record had zero accepted IRQs, with correct final pointers,
checksum and guards. That run remains a failed N2 regression observation.
The unchanged N2 then passed exact 3/3 and full 32 KiB identity with fake expiry
in an existing `pic_irq` boundary during REP. This bounds the live mismatch;
it does not revise N2's criteria.

Bounded diagnostic traces observed PIT controls 0x30/0x36 in DOS and
0x00/0x30/0x34/0x36 in the Windows workload, plus existing PIC initialization,
mask and EOI operations. They introduce no newly admitted semantic family.
The initial trace limits were 48 observations per handler; recorded maximum
service gaps were about 19.2 ms (DOS) and 27.0 ms (Windows), under debugger
control. Those measurements establish neither a Linux service envelope nor
an ESP32 timing limit.

The appropriate closure is
`PASS_PHASE_D1_PIT_PIC_COMPATIBILITY_FAKE_TIME_PILOT_LIVE_LINUX_INCONCLUSIVE`.
Detailed local evidence resides under `.local/phase-d1-pit-pic-compat/`;
`closure-final.json` and `FINAL-EVIDENCE.md` distinguish the completed migration
from the preserved earlier owner-decision stop. No VM/VX hardware equivalence,
save-format change, other-device time migration, or remote publication follows.
