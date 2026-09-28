# Linux SDL execution pacing with autonomous GDC

This is a Linux frontend implementation contract. It grants no device new
machine-time authority and selects no ESP32-P4 deadline. Read the
[realtime policy](multiplierless-realtime-policy.md),
[GDC contract](gdc-machine-time.md), and [oracle contract](guest-oracles.md).

## Problem and execution ownership

A frame-sized burst of guest instructions followed by a frontend wait can miss
whole autonomous VSync intervals. Correct status reconstruction and timely
service do not guarantee that a polling guest executes while status is high.
The startup audit demonstrated this on both interpreter backends.

The repair retains the existing `pccore_exec` call stack. Completed interpreter
iterations can yield the host thread and then resume at the original next
instruction. There is no new frame entry, CPU_EXEC restart, event frontier,
interrupt arbitration point, or serializable execution state at a host yield.
The ordinary CPU instruction, shadow, HLT, exception and REP boundaries remain
unchanged. A long instruction or existing REP segment can exceed the scheduling
quantum; this is not a hard realtime guarantee.

| Work | Ownership across a host yield |
| --- | --- |
| SDL draw/frame-skip/adaptive counters and selected frame | Existing frontend frame loop |
| `pccore_exec` draw intent, sound/input sync, palette journal | Entry once; live stack retained |
| GDC service/presentation offer and NEVENT_FLAMES setup | Entry once; no repeat on yield |
| Key-repeat processing | Existing frame entry |
| Instruction execution, trap/DMA work, CPU clock ledger | Existing interpreter; no pacing writes |
| PIC arbitration, CPU reset, TSC and RTC observations | Existing pccore/CPU frontiers |
| NEVENT commit/rebase/dispatch and heartbeat callbacks | Existing scheduler; never called by pacing |
| ARTIC/MPU/SMPU/disk/calendar/S98/sound/FDC tail | Existing frame end once |
| Hardware-reset completion and final shadow accounting | Existing frame end once |
| GDC phase/status/IRQ/display generations | Existing autonomous source and approved service paths |

The retained stack is the resumable state. In particular, CPU_BASECLOCK,
CPU_REMCLOCK, current NEVENT frontier, interpreter locals, draw intent and
frame-tail obligations remain in place. Frontend event callbacks are not
invoked inside the interpreter: reset/menu callbacks are not reentrant.
Existing frontend event processing resumes at its ordinary frame boundary.

## Private pacing rule

For ordinary live-GDC SDL execution, `paced_exec` establishes a monotonic host
origin and the current modulo-32-bit CPU cycle position before its single
`pccore_exec` call. The selected rate is `pccore.realclock` scaled by the existing
emulation-speed setting. `sdl/cpupacing.h` checks accumulated existing CPU debits
at completed dispatch iterations; IA-32 checks at the loop head so its
completed-opcode `continue` paths are covered too.

After approximately 0.5 ms of selected CPU work, `sdl/cpupacing.c` performs an
absolute CLOCK_MONOTONIC wait until the corresponding consumed-cycle target.
The final fractional quantum is paced at frame end. Absolute deadlines avoid
adding a fresh full delay after every scheduling overrun. Already-late work is
not delayed again. There is no extra frame, global CPU credit, CPU debit,
GDC service call, rendering call, or event dispatch in the pacing function.
A discontinuous backward ledger/reset cancels that frame's pacing epoch.
The next ordinary frame establishes its own epoch.

The quantum is a Linux scheduling choice, not a guest timing constant or an
ESP32 requirement. GDC still gets its own fresh source samples; pacing neither
writes that clock nor widens, latches, freezes or stretches a status interval.
Existing service/deadline publication is independent of host sleep.

Ordinary SDL outer waits use SDL_Delay in this live configuration so a build
without SUPPORT_NP2_THREAD does not busy-spin in `taskmng_sleep`. NoWait retains
its existing diagnostic meaning. The adaptive draw decision subtracts accumulated voluntary in-frame waits
from its work-time observation; its real pacing counter is left untouched.
Otherwise moving idle time inside pccore_exec would falsely classify it as
slow CPU work and raise frame skipping. The wait accumulator resets with the
existing frontend frame-count reset. Drawing remains at the original frame call
sites and keeps the existing generation/coalescing policy; a slice does not
trigger rendering. Audio synthesis, buffers, sample rate, configured latency
and frame audio hooks are unchanged.

## Budget proof and boundaries

Let C_i be the existing legacy cycle position at each pacing observation.
Unsigned debits C_i-C_(i-1) telescope to the frame's actual ledger advance,
including existing instruction overshoot. The pacing layer only reads these
positions. CPU execution, device charges, NEVENT rebases/commits, HLT and REP
retain sole ownership of the ledger and the original frame frontier.

For a continuous frame with selected rate R, its final pacing target is
host_origin + floor((C_end-C_begin)*1e9/R). Thus distributing work adds no
CPU budget. Transient lead is the checkpoint quantum plus the existing
instruction/REP/event work until the next checkpoint. No new architectural
preemption is inserted to enforce a hard bound. Host lateness can reduce
throughput; no extra work is authorized to compensate across frames.

The unit gate `tools/test_sdl_cpupacing.py` uses the actual pacing source with
controlled host-clock wrappers. It checks unchanged ledger bytes, paired
rebases, instruction overshoot, final fractional work, clock wrap, interruption,
late host and reset. Startup diagnostics additionally check raw CPU and NEVENT
bytes across actual waits and reconcile frame begin/end, per-yield debits and
presentation/callback counts. Qualification results are kept with the mission
report; passing a synthetic pacing test alone is insufficient for integration.

## Selection, rollback and claims

The hooks and private pacing state are compiled out with GDC OFF and with the
canonical fake provider. The pilot already restricts selection to Linux SDL2
single-owner interpreters without HAXM or asynchronous CPU adjustment. No
public runtime switch, protocol, save-state field, worker thread or dependency
is added. Save/load remains rejected by the existing GDC pilot guards.

Default-OFF `.text` comparisons include the touched frontend and selected CPU
objects as well as the original GDC migration objects. Canonical N4, PIT/GDC
composition, N1/N2/N3/N4 OFF and complete integration oracles retain their
existing assertions. DOS/FMP observations continue approximately ten seconds
after the visual checkpoint; neither those observations nor startup-beep
onset timestamps establish AUDIO PASS. A human beep-duration observation is
recorded separately.

The target lesson is that device service and guest observation opportunities
both need qualification. ESP32-P4 requires its own task/service/deadline
analysis; it does not inherit this Linux quantum or frontend structure.

## Qualification capture precondition

The N4 host presentation probe requests a host repaint through the existing
`pcstat.screenupdate` flag before capturing its before-state. Ordinary schedules
can already have consumed every dirty region at that point. A presentation
offer without a pending repaint does not require a surface draw. The probe
continues to require exactly one actual draw, one presentation accounting
increment, latest-generation consumption, and byte-identical GDC/CPU state.
Guest fixture source, fake-time schedule and assertion thresholds are unchanged.

## Qualification status at owner stop

The pacing repair is partially qualified. Both interpreter startups and the
canonical regressions pass, but ordinary live Windows completion is still a
failed gate. Investigation exposed a separate inherited dependency: the GDC
pipeline uses `GDCSCRN_EXT` to trigger effective graphics-clock normalization,
while the renderer consumes the same flag. The deterministic host reproduction
can produce clock `0x03` and zero graphics pitch when presentation consumes it
first. Existing N4 passing cases do not cover this ordering.

The owner chose to stop within the pacing mission's scope. No GDC clock-pending
fix has been applied. Do not promote this work to complete live qualification,
reuse debugger-assisted Windows completion as ordinary-paced acceptance, or
infer startup-beep duration correctness. The new human beep comparison remains
unperformed. See the local mission report under `.local/gdc-pacing-repair/` for
preserved failures, exact measurements and the unapplied repair proposal.


## Subsequent effective-clock ownership repair

The separately authorized [GDC pending-work repair](gdc-clock-pending.md)
closes the renderer-EXT dependency that prevented the earlier ordinary LIVE
Windows acceptance. It preserves this pacing implementation byte for byte.
Two ordinary paced complete Windows oracles now pass with that GDC repair;
startup and CPU-budget conservation are requalified. The earlier partial
mission report remains the historical record of its owner stop. The owner
subsequently confirmed normal「ピポッ」startup sound for all four current
i286/IA-32 OFF/LIVE conditions, completing the separate pending-work repair
mission. This bounded human observation is not inferred from a Windows or
DOS/FMP visual result and does not establish general AUDIO PASS.
