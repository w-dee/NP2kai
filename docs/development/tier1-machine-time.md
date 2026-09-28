# Remaining Tier1 timing-policy qualification

The owner decisions D1–D3 select an explicit, default-OFF normalized reference
profile. `NP2_TIER1_MACHINE_TIME=ON` builds the private fake-time/fake-input
binding on Linux SDL2 single-owner i286 or IA32 interpreters. It has no live
clock/input adapter, user-facing runtime switch, guest control port, worker,
DMA clock or P4 implementation. The normative realtime policy remains
[multiplierless-realtime-policy.md](multiplierless-realtime-policy.md).

## Authority and admitted domain

D1 retains **CPU_BUS_SYNCHRONOUS_COMPATIBILITY**. The actual generic DMA loop
is unchanged: one transfer per working channel per semantic CPU/bus opportunity,
in channel order. Its TC/END callback precedes the final byte; count, memory and
address updates keep their old order. Without an opportunity, DMA does not
progress, regardless of elapsed machine time. HLT and an externally held owner
are different cases. Batching would require observational equivalence across
all intervening CPU/memory actions; this profile implements no batching.

D2 selects **SOURCE_SPECIFIC_NORMALIZED_MACHINE_TIME**, with no universal M_ref:

| Source | Exact duration |
| --- | --- |
| FDC IRQ, source constant512 | `512 / B` seconds |
| FDC seek/recalibrate countdown | Per-command epoch plus `frames * 5/282` seconds; six frames = `5/47` seconds |
| GDC drawing busy | `dots*K/(15625*B) + 30/B` seconds, K=22464 in8MHz mode, otherwise27648 |
| LIO raw drawing-wait argument | `cycles/B` seconds, retaining the source's raw work constants |
| Keyboard transfer | `1/1920` second |

B is the configured base clock, admitted at1,996,800 or2,457,600. Runtime M does
not enter these deadlines. FDC seek completion retains per-drive status and
then arms the separate IRQ delay; rearming replaces the corresponding pending
slot. GDC adds work to the later of now and its pending busy deadline. Existing
GDC scan/VSync rules are unchanged. The exec-pass FDC hook retains output-only
seek-sound housekeeping but no longer decrements semantic seek timers.

`TIER1_HZ=23,462,400,000,000` is an **integer representation denominator**, not a
hardware frequency. It is the LCM needed to represent the admitted durations
exactly, so their fractional phase is retained in absolute coordinates without
rounding each service interval. Fake timestamps use this lattice. A future
platform adapter must perform checked conversion/residue handling; no physical
source or resolution is chosen here. The pilot admits0..24hours per epoch,
fixed base/mode configuration, drawing-busy debt bounded by that horizon,8 input
sources,128 queued input records, and ordinary one-byte PC-98 key identities
00h..70h after frontend mapping. Other key mapping/LED/special-key paths and
live producer timestamp conversion are later source-specific integration.
Pending periodic/seek deadlines can extend beyond the final admitted observation;
all their bounded arithmetic still fits uint64. These are qualification/resource
bounds, not physical hardware claims.

## Keyboard admission, ordering and ownership

D3 selects **PRODUCER_TIMESTAMPED_MACHINE_TIME**, ordered edge history and no
edge collapse. `tier1_admit` accepts `{q, sequence, source, key, down}` records
in nondecreasing time and strictly increasing sequence. Timestamp/sequence are
assigned at the producer-to-emulator admission boundary, never delayed-owner
service time. Records at or before a finalized frontier, invalid identities,
backward sequence/time, and capacity exhaustion return failure without mutation.
Every admitted edge remains distinct until applied, including duplicate levels.

Before calling `tier1_settle(T)` or advancing the private provider to T, the
single-owner test driver supplies the **complete ordered input prefix through
T**. That call asserts prefix completeness and finalizes it; it is not a
live concurrent queue or a speculative watermark. An unstamped SDL keydown/up
is rejected in this profile. No live adapter may bypass that contract.

At each event coordinate, input edges run before the keyboard transfer due at
that coordinate. Transfers retain actual control-byte priority, output-register
full retention, queue order, command responses and IRQ1 publication. An edge
at a deadline is eligible for that transfer if the timer is already armed;
an idle device still starts the existing one-period transfer wait. Guest I/O
first settles through T. A keyboard reset signal at T settles the old epoch,
then applies the actual reset/control/resend operation and increments its epoch.
Held ownership and future admitted edges retain their identity/time.

Per-source duplicate suppression and first-owner press/last-owner release
preserve the existing P4 ownership policy. The bridge invokes actual
`keystat_down/up`; actual `keyboard_callback`, register handlers and PIC are
used, not a replacement keyboard device. Repeat remains disabled. The legacy
`xferclock` field is retained for layout/OFF compatibility but is not consumed
as the normalized transfer authority.

The finite settlement envelope conservatively requires pending edges through T
plus existing device data bytes to fit128 slots even before considering byte
consumption or duplicate suppression. Exceeding it returns explicit failure
before any device/PIC/ownership mutation; no edge is silently dropped or
retimestamped. This may reject a batch that a more elaborate transactional
planner could accept. Public device wrappers fail-stop on rejection. Control
FIFO behavior remains the existing command protocol, distinct from external
edge admission capacity. Repeated full-register timer callbacks can collapse
only when they make the same finite PIC publication and no guest observation
intervenes; phase and expiry count still advance exactly.

## Integration and lifecycle

The binding settles at relevant real keyboard/FDC/GDC/PIC observation and
arbitration entries. Private provider reads never derive from CPU work,
`pccore_exec`, SDL credits or Linux elapsed time. Device callbacks may arm
successor deadlines at their logical event coordinate, not the late target T.
The DMA functions and CPU interpreter arbitration paths are unchanged.

The first pilot is cold-boot-only for whole-machine lifecycle. A subsequent
`pccore_reset` is rejected before machine mutation. Keyboard reset-signal I/O is
separately qualified as above; this is not whole-machine reset composition.
All existing experimental save/load rejection entry points also reject this
profile. No save format changed. RTC/calendar and other exec-pass consumers
are not migrated here: the owner-approved semantic frame coordinate makes
their audited frame-domain integration possible later without a new authority.
No Tier2 delay is normalized by this option.

## Qualification and compatibility delta

Run:

```sh
python3 tools/test_tier1_time.py --output .local/audit/tier1-qualification-20260928
python3 tools/test_tier1_time.py --output .local/audit/tier1-qualification-20260928 --build-only
python3 tools/test_tier1_save.py --build <configured Tier1 build>
python3 tools/guest/run_tier1_qualification.py --binary <SDL2 binary> --backend i286 --case n3 --output <excluded path>
python3 tools/guest/run_tier1_qualification.py --binary <SDL2 binary> --backend ia32 --case dma-hlt --output <excluded path>
```

The host suite extracts whole actual production functions without body changes,
links actual keystat/NEVENT and the new binding, and substitutes only CPU
interrupt dispatch and memory/media/output endpoints. It covers both bases,
M=1/4/5/20, exact deadline-minus-one/equality, real seek/recalibrate command
bodies, rearm/busy accumulation, actual keyboard I/O/control/reset, ownership,
full-register retention, one-shot versus137-part service, input exhaustion and
invalid-domain rejection before mutation. ASan/UBSan runs use both CPU compile
profiles. Python `Fraction` produces an independent exact duration reference
and compatibility deltas. Undefined signed-overflow domains of the old GDC
expression are labeled as such, not assigned fabricated legacy values.

For example, at B=2,457,600, normalized FDC IRQ delay is1/4800 second. Old M=4
used1/19200 second; this intentional4x duration difference is owner-approved.
GDC's old `floor(dots*K*M/15625)` loses a multiplier-dependent fraction; the new
rational expression retains it. These changes are never claims of physical
accuracy or unchanged ON behavior. OFF executable text of every changed
production C file is compared against parent75b080b2 under identical compiler
flags, on both backends.

The [guest fixture contract](../../tests/guest/tier1-timing/README.md) distinguishes
unchanged N3 data assertions from new timing/HLT propositions. Existing PIT/PIC,
GDC scan/busy separation and N5 assertions remain unchanged. Full ON/OFF builds
and real N3/HLT runs are separate from host-body tests and save rejection.

The architectural conclusion is bounded: these policies remove the three
remaining owner decisions without adding a fifth information class. They do
not finish every source port, provide a live SDL product, establish P4 deadlines,
qualify physical floppy/audio timing, or select a P4 landing-zone branch.
