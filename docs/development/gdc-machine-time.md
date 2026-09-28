# Experimental GDC compatibility machine time

This cold-boot pilot uses `LEGACY_COMPATIBILITY_PROFILE` authority. It implements
an independent clock for the bounded GDC scan/display unit. It does not qualify
physical Ne2/GD5428 timing, an electrical HSYNC waveform, or a universal PC-98
oscillator. Read the [realtime policy](multiplierless-realtime-policy.md) and
[guest-oracle contract](guest-oracles.md) before interpreting its evidence.

## Selection and admission

The private CMake selections are:

| Option | Default | Meaning |
| --- | --- | --- |
| `NP2_GDC_MACHINE_TIME` | OFF | Compile the bounded GDC experiment |
| `NP2_GDC_FAKE_TIME` | OFF | Deterministic private qualification source; requires the experiment |
| `NP2_GDC_PROFILE_BASE` | 2457600 | Fixed display compatibility identity: 1996800 or 2457600 |

There is no runtime switch or guest protocol. Both providers require Linux SDL2,
interpreter execution, one emulator owner, no HAXM and no async CPU. Runtime
admission requires RASTER=0, accelerator relay=0 and the bounded normal master
SYNC mode (P0=0x10). An unadmitted configuration aborts with an admission code;
it is never silently converted to another display mode.

| Backend | Admitted scan classes |
| --- | --- |
| i286 | 15 and 24 kHz compatibility profiles |
| IA-32 | 15, 24 and 31 kHz compatibility profiles |

31 kHz is required by the observed Windows fixture. Its profile is compatibility
authority, not a physical oscillator claim. Stock i286 still excludes 31 kHz.
RASTER=1 palette-journal timing and accelerator relay operation require separate
authority. Immediate guest palette register semantics remain in their existing
I/O paths; palette conversion and texture upload remain renderer work.

## Profile and integer coordinate

`gdc_profile_make` preserves the audited parent clamps, rescaling and truncation.
`B_ref` is fixed at build time; `M_ref=5` is fixed in the formula. In particular,
the parent frame calculation remains:

```text
frame = floor(B_ref * clamped_lines / horizontal_frequency) * 5
R = floor(frame / clamped_lines)
H = floor(R * rescaled_columns / clamped_columns)
D = R * rescaled_display_lines
V = frame - D
F = D + V
```

Division before multiplication is intentional. `B_ref` and `M_ref` identify a
compatibility profile. Runtime `pccore.baseclock`, `pccore.multiple`, CPU ledger,
NEVENT remaining time and Phase-B shadow samples do not advance machine GDC.
The old runtime-dependent D/V calculation survives only as the legacy CPU-time
housekeeping heartbeat.

The reference quantum is `1/(5*B_ref)` seconds. Nanoseconds convert exactly with
`780/78125` or `960/78125` ticks/ns. Quotient/remainder arithmetic avoids
multiplying a full uint64 nanosecond delta by the numerator. State retains the
accepted source anchor, fractional numerator remainder, latched current segment
countdown, D/V segment, committed profile and diagnostic counters.

For a stable epoch at display entry, the independent committed N4 reference is:

```text
phase = Q % F
VSync = phase >= D
remaining = VSync ? F-phase : D-phase
status bit5 = VSync
status bit6 = remaining % R < H
```

Status is right-continuous after every deadline at or before the observation.
The bit6 proposition is selected scan phase, not a requirement that a CPU poller
observe every naturally running pulse. Exact transition arithmetic is host
qualified; N4 samples selected positions through real guest IN instructions.

## Source and service contract

`GDC_SAMPLE` supplies fresh nanoseconds and an explicit validity flag.
`gdc_time_source()` is the replaceable private provider seam. Fake time is
canonical on Linux; the live provider obtains a fresh checked CLOCK_MONOTONIC
sample on each request. The first valid observation anchors without inventing
elapsed time. Invalid/backward observations increment rejection diagnostics and
leave the accepted anchor, remainder and guest phase intact. Equal observations
are idempotent. Reset discards the anchor; there is no CPU-time fallback.

`gdc_machine_service_at(sample)` reconciles the bounded state to one supplied
frontier. `gdc_machine_service()` samples the source and delegates. Service is
single-owner and guards recursion. It does not accept interrupts or execute/charge guest instructions. The N4
held-service checkpoints prove byte-identical CPU and excluded-device state for
their scheduled work. This is not a purity claim for arbitrary queued drawing
commands: draining such a command can still schedule its existing legacy
NEVENT_GDCSLAVE deadline and adjust scheduler bookkeeping.

| Service point | Obligation |
| --- | --- |
| GDC I/O and direct BIOS GDC entry | Reconcile old state before observing or programming it |
| Both GDC status ports | Return fresh scan bits with separately owned FIFO/ready/busy bits |
| Existing PIC I/O/arbitration and direct BIOS IRQ0 unmask | Reconcile admitted producers before existing arbitration/mutation |
| Existing TRAM/VRAM/EGC wait-charge sites | Select the current phase's existing wait value before charging CPU cycles |
| Existing `pccore_exec` frontier | Reconcile display state and offer one current generation to the renderer |

No CPU safe point was added. IF, STI/MOV SS shadow, HLT and REP acceptance/restart
remain in the existing CPU/PIC paths. GDC service can publish IRR2 while CPU
state is held; acceptance happens when normal architectural execution resumes.

### Bounded advancement and configuration commits

A service processes at most four initial segment edges. These drain the finite
master/slave FIFOs at their existing boundary, commit pending geometry at the
DISPSYNC-selected frontier, and finish any old latched interval. Remaining
stable elapsed time is divided by F. There is no per-frame, per-raster or
per-pixel catch-up loop.

Master work precedes the V-entry pipeline; slave work occurs at display entry.
V entry arms the old V duration before the DISPSYNC=1 geometry commit. A
DISPSYNC=0 commit occurs before arming the next D interval. Pending SYNC bytes
are compared against an independent committed copy; renderer consumption of
EXT flags cannot discard a pending timing commit. The current latched endpoint
is not retroactively recalculated when the last SYNC byte arrives. N4 cases
27/28 and host tests cover alternate/restored geometry and both DISPSYNC choices.

The skipped alternating IRQ sequence reduces to at most three finite transforms
after the four initial edges. At V entry, an armed source attempts `pic_setirq(2)`
and disarms; the existing PIC handles ISR suppression/rearm. Display entry
expires an unaccepted IRR2 request and rearms. ISR/EOI are ordinary PIC state.
Elapsed frames do not form an interrupt-token queue. No missed CPU acceptance
is invented.

When PIT machine time is also selected, `gdc_machine_pic_service()` samples once
and supplies the same frontier to PIT0 and GDC before arbitration. PIT's existing
service body was factored into `pit0_machine_service_at`; its old wrapper still
samples its own provider. Controlled fake composition must keep both private
providers on the same nondecreasing timeline. Other PIC inputs retain their
existing domains and are not backdated.

### Status, waits and legacy command duration

The master/slave status handlers compose machine scan bits with existing
FIFO/ready and drawing-busy meanings. `NEVENT_GDCSLAVE`, drawing execution and
busy duration remain CPU/NEVENT driven. Boundary FIFO work is finite existing
command execution; it does not grant all command-engine latency a new clock.

Machine time selects `np2cfg.wait[2*kind + vsync]`. The existing
`legacy_cpu_charge` sites and debit amounts remain unchanged. A memory access
is not assigned a new machine-time duration.

SEARCH_SYNC and TURE_SYNC are compiled out only in experimental GDC mode.
Fresh machine status needs neither the legacy polling-loop CPU budget mutation
nor the legacy overshoot bit flip. OFF retains both original implementations.
The host test extracts the actual status function and policy, supplies the
recognized polling bytes and proves no force-yield debit; N4 independently
qualifies exact boundaries without the optimization.

## Display state versus presentation

Blink timing/count/renewal, effective graphics clock bit7, configuration commits
and scan/IRQ state advance in machine service. Blink uses bounded arithmetic,
including the first UINT8 wrap under a changed threshold. Dirty obligations are
accumulated with a bounded full-invalidation union. Palette/font dirty flags are
retained for eventual rendering.

One uint64 generation and one consumed generation describe the latest state.
There is no allocation or frame-history queue. Analytical skipping publishes a
coalesced obligation and advances blink without rendering skipped frames.
The single owner builds the latest image from current registers, palette and
guest VRAM/TRAM/font. Decoded geometry, pixel caches, cursor invalidation and
palette conversion remain in the renderer. The renderer consumes their dirty
flags only when it runs.

The old frame callbacks are retained solely as a CPU-time loop/housekeeping
heartbeat. They do not publish machine GDC IRQs, execute GDC boundary work or
advance blink. The unrelated `pccore_exec` tail retains its old CPU-time cadence;
a trillion machine frames do not cause a trillion audio/disk/RTC callbacks.
Host sleeps, draw skipping and display uploads have no fake-time authority.
Default-OFF presentation policy is unchanged.

The private fake adapter may suppress host presentation. At terminal capture it
lifts suppression and temporarily requests one existing host draw, then restores
the host request. It never writes guest result RAM, GDC/PIC state or CPU state.
The ordinary presentation call must preserve raw GDC and CPU bytes and consume
the current generation in one call. Rendering is not an audio assertion.

## Save/load and rollback

The seven existing queued/direct save, load, check and HDD snapshot entry points
reject before mutation when GDC machine time is compiled in. Guards compose with
ARTIC and PIT guards. No state-save format/version or timestamp serialization
was added. Cold boot is required; pause/suspend semantics are not defined here.

With GDC OFF the new source/state objects are absent from authority, and the
legacy scan, SEARCH_SYNC, TURE_SYNC, frame and renderer paths remain active.
`test_gdc_off.py` compares parent versus OFF `.text` under identical flags for
nine materially changed legacy translation units on both backends.

## Qualification tools and exact claims

The committed [N4 IPL](../../tests/guest/i286-time-gdc/README.md), its guest
sources, build IDs, RAM parser and mode-1 assertions are unchanged. Mode 2 uses a
separate private adapter. CMake embeds a SHA-256 identity over the material
product sources, checked in the inferior alongside the binding version; symbol
names alone are insufficient. Reports retain binary, image, RAM, capture and
ROM identities. Only fake-source and host presentation controls are written.

A temporary source-call-driven fake step gets through firmware bootstrap; it is
disabled before the canonical programmed epoch. Its boot progression is not
semantic evidence. All canonical samples then use explicit reference-derived
time. GDB inferior service calls run outside breakpoint stop callbacks.

| Tool | Evidence |
| --- | --- |
| `tools/test_gdc_time.py` | Actual integer model against independent committed N4 equations; invalid/backward/equal/huge samples, reset, fractional partitions, deadline overflow |
| `tools/test_gdc_binding.py` | Actual GDC/PIC/PIT with extracted production clocks/blink/status/TRAM debit; finite IRQ table, DISPSYNC reanchor, SEARCH_SYNC, mixed busy/FIFO, RASTER rejection and composition. Renderer and command execution are explicit stubs here |
| `tools/guest/run_gdc_machine.py` | Actual i286/IA-32 N4 mode-2 guest execution and ordinary production service |
| `tools/test_gdc_evidence.py` | Raw artifact revalidation, runtime/presentation/partition equality and malformed-evidence rejection |
| `tools/test_gdc_save.py` | Actual production seven-entry rejection with no file/device dependencies linked |
| `tools/test_gdc_off.py` | Exact default-OFF parent codegen comparison |

The 60 canonical runs cross five admitted backend/classes, two fixed B_ref,
two runtime CPU bases and M=1/4/20. Every run requires all 28 N4 records and
56 actual status returns. Forty additional runs cover suppression, fractional
partitioning, frozen repeat and boundary variants across all fixed profiles.
Memory-wait context is qualified by the actual host binding/charge test.

A N4 machine-time PASS proves selected reference H/V phases, finite IRQ2
mask/expiry/ISR/EOI/rearm, architectural HLT wake, positive CPU work under frozen
GDC time, held-CPU independent advancement, FIFO coherence and SYNC commits.
It does not prove every naturally occurring HSync pulse was observed. Record
14/17 guest verdicts retain their original deferred labels; the separate host
qualification supplies the added timing/isolation assertions.

Cross-run equality projects PIC observations to IRQ2 and IF; unrelated IRQ bits,
CPU instruction flags and polling counts are outside that comparison. It
compares committed geometry, phase/remainder, blink count/phase, guest progress,
HLT results and finite IRQ2 observations. Normal and suppressed runs must match;
zero suppressed presentations followed by one latest draw are checked separately.

N1/N2/N3 retain their documented CPU shadow/HLT, REP integrity and FDC/DMA
propositions. DOS/FMP and Windows remain visual/integration oracles. Both FMP
backends must continue for approximately ten seconds after the checkpoint;
prompt return is command completion. No AUDIO PASS is supplied.

## Linux live limitations and performance

Live Linux evidence is supporting only, especially under GDB. Service counters
report maximum accepted sample gap, maximum deadline lateness in reference ticks,
collapsed transitions, rejected samples and presentation coalescing. These do
not define a Linux or ESP32 service envelope. Live elapsed time is not authority
for a clamp/freeze/pause policy.

The current frontend can run CPU work in bursts and sleep through part of a
machine-time VSync interval. A guest polling loop can consequently make slow
progress even though the analytical scan is correct. The live boot diagnostics
retain actual PC/status and timeout evidence; the existing NoWait frontend
option can be used as an explicitly labelled diagnostic configuration. It does
not change the default product presentation policy. Successful live visual
integration is still realtime-semantic INCONCLUSIVE.

Host performance measurements include actual model/status/binding service for
zero, one, five and approximately one trillion frames. The binding benchmark
includes a constant state-reset cost and stubs command/render work; the model
benchmark includes Python FFI overhead. Compare operation counts as well as
elapsed time. Default-OFF `.text` equality is the strong codegen/overhead gate.
There is no new hard performance budget, worker thread or unbounded log in the
product.

## ESP32-P4 provider and service seam

ESP32-P4 remains the normative realtime target. A future hardware timer provider
implements the same fresh monotonic source contract, with platform lifecycle
semantics separately qualified. `gdc_time_deadline` returns the next finite
segment deadline using exact remainder/ceiling arithmetic, or failure if the
anchor/deadline is unavailable or overflows.

Required service frontiers are V/display transitions (IRQ publication/expiry and
display obligations), pending configuration commits, and each affected status,
PIC or memory-wait observation. A hardware alarm may notify the emulator owner;
it must not concurrently mutate PIC/GDC/render state. No per-raster timer IRQ is
required. Status can be derived analytically on demand.

Late service reconstructs only the approved finite state, collapses
indistinguishable historical frames and preserves the latest dirty generation.
It cannot reconstruct missed CPU acceptance or render an old-frame backlog.
Deadline publication latency and CPU acceptance latency are separate measures.
Target qualification must cover alarm delivery, owner handoff, critical sections
and competing work; no numeric latency/resource budget is selected here.

## Qualification snapshot (2026-09-27)

Parent and unchanged final HEAD: `04535e4f8de2dfbaa2382cc98165e44e24c73e9d`.
Work branch: `feature/multiplierless-gdc-machine-time-pilot`.
The uncommitted implementation was qualified as
**PASS_GDC_COMPATIBILITY_FAKE_TIME_PILOT_LIVE_LINUX_INCONCLUSIVE**.

| Gate | Result |
| --- | --- |
| Required N4 matrix | 60/60, all 28 records and 56 direct reads per run |
| Additional host schedules | 40/40; ten paired suppression comparisons and ten partition comparisons |
| Latest actual host draw | Ten further suppressed runs: zero intervening draws, then exactly one draw consuming latest generation |
| Model / binding | 72,948 arithmetic checks; 35,434 actual-binding checks under UBSan |
| Capture rejection | 90 corrupted/missing/stale evidence controls rejected |
| PIT regression | 606,240 observations against frozen parent M=5, both backends |
| Save guards | All seven APIs reject in i286, IA-32 and combined PIT/GDC builds |
| Default OFF | Nine parent-identical `.text` objects per backend; new source symbols absent |
| OFF guest regression | N1/N2/N3 exact assertions; N4 mode 1 on all five admitted backend/classes |
| Experimental guest guards | N1/N2/N3 exact assertions with private fake bootstrap, frozen GDC after IPL entry |
| OFF integration | Both DOS/FMP and complete Windows state machine |
| Live integration | Both DOS/FMP; complete Windows state machine with the firmware-only NoWait diagnostic described below |

Both final OFF FMP observation windows were about 10.03 seconds. The live i286
and IA-32 windows were 10.030 and 10.032 seconds. These are observation allowances;
there is no AUDIO PASS. Windows passed four distinct SCSI alerts, one VSC55 alert,
rejected the early desktop and matched the final IntelliPoint state six times.
The live trace observed the admitted 24-to-31 kHz programming transition.

**Live limitation:** ordinary paced Windows attempts hit the unchanged 35-second
menu timeout, including an attempt without GDB. Read-only diagnostics repeatedly
found the firmware VSync wait at F800:11B6/11B8. Continuous NoWait reached Windows
but its accelerated input handling skipped required modal observations. The
successful diagnostic used the existing NoWait option only during firmware boot,
then restored ordinary pacing at the menu, before the Windows selection. All
visual thresholds, modal stability waits and six-match final assertions remained
unchanged. This is a bounded integration result, not an ordinary-paced live boot
PASS, nor authority to change target scheduling semantics. Initial live N1/N2/N3
attempts likewise exceeded their short capture windows before IPL entry; their
fake-source regression runs passed the original guest assertions.

At the last bounded trace checkpoints, the largest observed live service gaps
were 25.483 ms (i286 FMP), 40.875 ms (IA-32 FMP), and 139.558 ms (Windows).
Rejected samples were zero; these debugger-contaminated observations establish
no realtime envelope. The host binding measured roughly 41–54 ns for one frame,
77–103 ns for five, and 76–102 ns for one trillion, including constant reset cost
and stubbed command/render execution. Five and one trillion frames both required
at most seven finite transforms. No numeric product budget follows from these
measurements.

Machine-readable evidence and the full changed-file/provenance report are in the
ignored local `.local/gdc-machine-pilot/` directory. It contains the starting
manifest, per-build identities, `n4-final/`, `n4-extra/`, `n4-render/`, model/binding
reports, final OFF codegen and fixture reports, workload inventories and preserved
failed live diagnostics. `tools/test_gdc_evidence.py` revalidates the 110 captures
against raw RAM, committed reference assertions, current source identity and
binary hashes. Established fixture/oracle files were mechanically unchanged.

Example commands for an already configured private build:

```sh
python3 tools/test_gdc_time.py
python3 tools/test_gdc_binding.py
python3 tools/guest/run_gdc_machine.py \
  --binary build_gdc_i286_fake_2457600/sdlnp2kai_sdl2 \
  --output .local/gdc-example --backend i286 --scan-class 24 \
  --profile-base 2457600 --baseclock 1996800 --multiple 4 --suppress
python3 tools/test_gdc_save.py --build build_gdc_i286_fake_2457600
python3 tools/test_gdc_evidence.py --output .local/gdc-machine-pilot
```

The runner rejects a nonempty output directory. `--schedule` also accepts
`frozen_repeat`, `boundary_variants` and `fractional_and_partitioned`. Repeat
across the admitted matrix; i286 31 kHz is an explicit unsupported combination.

### Effective graphics-clock pending ownership

Clock-register writes retain their immediate raw-bit semantics and mark a
separate bounded `clock_pending` obligation. The existing DISPSYNC-selected
pipeline consumes it, independently of renderer EXT consumption. BIOS display
reset and cold reset discard stale work. See the
[ownership review and regression contract](gdc-clock-pending.md) for all eight
producers, timing/reset rules and ordering assertions. The normalization rule,
scan/status profile, command-busy domain and presentation sites are unchanged.
