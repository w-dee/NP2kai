# GDC effective graphics-clock work ownership

This is a bounded `LEGACY_COMPATIBILITY_PROFILE` implementation repair. It
retains the existing normalization and DISPSYNC-selected pipeline frontier.
It does not assert physical GDC clock wiring, alter scan/status timing, drawing
busy duration, PIT/PIC, CPU scheduling, or presentation policy.

## Ownership inventory

| Producer / consumer | Classification and obligation |
| --- | --- |
| `gdc_o6a`, commands 82/83/84/85 | EMULATED_GDC_STATE: clear/set clock bits 0/1 immediately; PIPELINE_PENDING_WORK: mark normalization pending; RENDER_DIRTY_STATE: retain existing EXT |
| `bios0x18_30`, two clock writes | Same pending obligation for direct BIOS writes; existing direct or queued renderer dirt remains unchanged |
| `bios0x18_40`, two clock writes | Same pending obligation; existing SYNC, pitch and EXT writes remain unchanged |
| `gdc_biosreset` | Reset clock to zero, master/slave pitch to 80/40, discard previous pending clock work; existing render dirt remains |
| `gdc_reset` / `gdc_machine_reset` | Cold reset clears all GDC-machine state and pending work; initialization starts with normalized clock zero |
| GDC pipeline | EMULATED_GDC_STATE: normalize bit7 once when pending, using the unchanged predicate; clear only pending work and retain existing redraw request on a change |
| Experimental `drawscreen` | HOST_CACHE_STATE / RENDER_DIRTY_STATE / PRESENTATION_ONLY: consume EXT for vertical/horizontal/mode cache refresh; cannot touch pending clock work |
| Legacy OFF `drawscreen` | Original EXT-triggered clock normalization and rendering remain compiled unchanged |
| GDC analog-mode changes; BIOS slave-SYNC mode; command dirty table | EMULATED_GDC_STATE plus RENDER_DIRTY_STATE as before; no clock-register write, so no new clock pending obligation |
| Master SYNC/class configuration | Separate existing committed-SYNC/class comparison owns its timing commit; not renderer EXT or the clock-pending bit |
| Text-mode, cursor, display/plasma flags | Existing text renderer/cache dirt; no clock obligation |
| Save-load render refresh | Legacy render dirt only; experimental save/load remains rejected |
| Pitch registers: reset, BIOS, generic CMD_PITCH data write | EMULATED_GDC_STATE, existing immediate/FIFO assignment and dirty table; no clock normalization request |
| `makegrph`, `makegrphex`, `maketgrp`, `maketext` | Read pitch and effective clock to derive host framebuffer addressing; do not consume pending GDC work |
| Clock readback and `np2info` | Observation only; no pending mark |

There are eight actual clock-register mutation sites, plus the BIOS reset and
normalization consumers. Queued BIOS I/O is not an additional direct write;
the existing I/O handler marks work when the queued command is executed.
Comments, read expressions and pitch writes are not clock-write producers.

## Pending state and frontier

`GDC_MACHINE.clock_pending` is a bounded Boolean obligation, not an event
queue. Actual clock writes set it even when the same value is written. Several
writes before a frontier coalesce to the latest raw register value, matching
the existing flag-based contract. Renderer calls can consume EXT any number
of times without touching it.

The existing `pipeline(frames)` consumes pending work only when `frames != 0`,
after the existing configuration commit and before publication. DISPSYNC=1
selects V entry; DISPSYNC=0 selects display entry. Equal-time service,
pre-frontier reads and rendering cannot normalize early. Subsequent service
without a new write cannot repeat the work. A huge gap still uses the existing
bounded pipeline; no per-frame replay is added.

The normalization predicate is unchanged: toggle bit7 if it is set while the
clock is not 0x83, or if the clock is 0x03. Clearing bit7 is covered as well as
setting it. Bit7 is not forced permanently; Windows and pitch128 receive no
special handling. Rendering after consumption still sees its normal dirty
request. No serialized structure or public interface is added.

BIOS display reset first runs the inherited old-state service, then resets the
clock and clears the old pending obligation. Cold reset clears the entire
machine object before GDC initialization. A new write after either reset can
create new pending work. The full test and integration qualification is
recorded with the mission evidence; this document alone is not a PASS claim.

## Qualification assertions

`tools/test_gdc_binding.py` compiles the actual GDC/PIC/PIT binding and
mechanically extracts the actual clock I/O and BIOS/cold-reset handlers.
`tests/time_domains/test_gdc_clock_pending.c` adds ordering, repeated-service,
latest-write coalescing, set/clear, both DISPSYNC frontiers, all reachable raw
clock combinations, multiple pitch values and reset assertions. The renderer
fixture performs the exact EXT-consumption statement; renderer pixels,
palette conversion, bank mapping and vector-reset internals are peripheral
stubs in this host test. Actual guest integration remains a separate gate.

The host gate retains the prior 35,434 canonical checks and adds 2,556 pending
ownership checks across both fixed profile bases and standalone/combined PIT
configurations. Each configuration also rejects a mutated implementation that
restores renderer-EXT dependence. These are compatibility and isolation
assertions; passing them does not establish physical GDC timing or audio.

## Integration qualification

The repair retains all 72,948 arithmetic and 35,434 original binding checks,
adds the 2,556 ownership checks above, and passes the required 60-case N4
matrix, 40 additional schedules and 10 redraw cases. The 110 captures and 90
rejection controls retain their original assertions. IRQ0/IRQ2 composition,
save/load rejection and OFF N1/N2/N3/N4 regressions pass. Both OFF binaries'
whole `.text` sections match their prior OFF references.

Ordinary paced LIVE startup remains approximately 8.7 seconds to the i286 DOS
checkpoint and 7.4 seconds to the IA-32 menu. Instrumented completed frames
retain exact CPU debit conservation, one entry/setup/tail/exit and zero
CPU/NEVENT changes across host-only waits. Linux observations do not qualify
physical realtime deadlines.

Both LIVE DOS/FMP visual oracles pass, followed by approximately ten seconds
of observation. Two ordinary paced Windows runs pass all four distinct SCSI
alerts, one VSC55 alert, early-desktop rejection and six consecutive final
IntelliPoint matches. No NoWait or debugger is used for those acceptance runs.
Separate debugger tracing retains 24-to-31 kHz admission evidence only.

The mission evidence is retained locally under `.local/gdc-clock-pending-repair/`.
The owner subsequently confirmed normal「ピポッ」startup sound for all four
current i286/IA-32 OFF/LIVE conditions. Saved listening trials match the current
binary identities and use ordinary pacing. This completes
`PASS_GDC_EFFECTIVE_CLOCK_PENDING_REPAIR`. The audible classification is the
owner's bounded observation; automated visual or software timestamps do not
supply it. No general AUDIO PASS or expanded physical GDC claim follows.
