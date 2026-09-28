# PC-9801-86 OPNA Timer A/B compatibility pilot (N6-T)

This experimental, default-OFF pilot is a `LEGACY_COMPATIBILITY_PROFILE`, with
`c05748f42ab75a80fc889fded1e6fb1f5b2cf2ea` as its parent. Read the
[realtime-target policy](multiplierless-realtime-policy.md) and
[guest-oracle contract](guest-oracles.md) before interpreting qualification.

## Admission and ownership

`NP2_OPNA_TIMER_MACHINE_TIME=ON` admits Linux SDL2, single-owner interpreters,
PC-9801-86 (`SOUNDID=0x04`, `board86_reset(config,FALSE)`), native OPNA, CSM off.
It is cold-boot only. `NP2_OPNA_TIMER_FAKE_TIME=ON` selects the private debugger
source; otherwise the source is a fresh `CLOCK_MONOTONIC` sample. There is no
INI switch, guest protocol, dependency, thread, or physical hardware claim.

The initial base/cpumode pair must be 1996800/8-MHz mode or 2457600/other mode.
That pair defines a fixed timer profile until reset; subsequent CPU throughput
or multiplier changes do not change it. No PIT-style reference multiplier is
used: **OPNA_TIMER_M_REF=NONE**.

PCM86 remains in the generic board. The admitted state requires `fifo & 0xa0`
to be zero, empty real/virtual buffers, clear `reqirq` and `irqflag`, and no
`NEVENT_86PCM` work. These are source-state assertions, not an acoustic test.
The existing shared-IRQ callback still invokes `pcm86gen_intrq(1)` when IRQs
match. With FIFO bit 5 clear that function returns before synchronization or
mutation. CSM, FMGEN, other boards, ADPCM capability and active PCM are rejected
explicitly, with an admission diagnostic and abort, following the GDC pilot's
bounded admission approach. They never silently fall back to CPU time or drop
waveform events. Code outside the experimental mode remains available.

Timer service never renders FM samples in the admitted profile. Existing
waveform register writes retain their ordinary synthesis path. Thus a later
P4 bridge can retain CPU/device/PIC ownership on one core and synthesis on
another. No SDL mixer, buffer-fill, renderer, or transport cadence is authority.

## Period and phase

The integer counts are exactly the legacy expressions, before time conversion:

```
A = (reg24 << 2) | (reg25 & 3)
C_A = floor(18 * (1024 - A) * K / 625)
C_B = floor(288 * (256 - reg26) * K / 625)
K = 1248 (8-MHz mode), 1536 (other mode)
period = C / fixed_profile_baseclock seconds
```

Legacy `C * multiple / realclock` cancels `multiple`. The pure state tracks
remaining base ticks and a fractional numerator over 78125 for each timer.
The source conversion numerator is 156 or 192 ticks per 78125 ns. A fresh
start resets that timer's fractional phase: it is a relative delay from the
accepted start time, not PIT's independently authorized absolute source grid.
Repeated starts preserve remaining ticks and fraction.

For delta `dt`, split division before multiplication:

```
part = (dt % 78125) * numerator + fraction
ticks = (dt / 78125) * numerator + part / 78125
fraction = part % 78125
```

If ticks reaches the old remaining count R, the first expiry retains its old
scheduled deadline. For the current register period P, subsequent expiries
number `1 + (ticks-R)/P`, and remaining becomes `P - (ticks-R)%P`.
The next observable nanosecond deadline is the anchor plus
`ceil((remaining*78125-fraction)/numerator)`. No repeated rounded period is
added. Deadline overflow is reported as unavailable, not wrapped.

The advancement has exactly two channel iterations regardless of elapsed
period count. Under CSM-off/quiescent PCM, each channel's first status
transition and PIC publication exhausts the observable effects until another
guest action. At most one original callback per channel is dispatched, with
relative NEVENT rearm suppressed in this mode. Later identical expiries are
represented arithmetically, not queued. Counts/diagnostics saturate on overflow;
phase arithmetic does not saturate or clamp elapsed time. Even UINT64_MAX ns
fits the split tick calculation. Invalid/backward samples leave the accepted
anchor and phase unchanged; equal samples are idempotent. Register operations
use the last accepted frontier if a source sample is rejected.

## Compatibility and linearization

The existing PIT/GDC rule is reused: settle old device state through T before
observing or changing it at T. Timer register writes settle before changing the
shadow register; board86 ordinary and extended status reads settle before
returning status. Existing PIC I/O and arbitration settle before IMR/IRR/ISR,
EOI or CPU IF decisions. CPU instruction wait charges retain their existing
meaning and are not converted into machine time.

| Operation | Preserved behavior / bound |
| --- | --- |
| Start | Inactive timer gets a relative delay using the current integer period. |
| Repeated start | Does not reload a running timer. |
| Stop | Removes active deadline, retains already-latched status. |
| Restart | New relative period and fractional phase. |
| A/B value rewrite | Current deadline survives; next expiry reload uses the new value. |
| Status enable | Running independently of status-enable; enabling does not invent an expiry. |
| Clear strobes | Clear associated status and self-clear stored bits 4/5. |
| PIC clear | Original shared-source quirk retained: a clear can reset the shared IRQ even with the other timer's flag latched. |
| Expiry / rearm | Original status/PIC callback; relative phase advanced analytically. |
| Read/write at deadline | Expiry using old registers precedes the observation/mutation. |
| A/B equal deadline | Independent sticky flags and the same PIC request commute in this profile. No arbitration occurs between them. |

NEVENT retains stable insertion order for tied events in OFF mode. The pilot
does not promise internal callback-trace order across channels: that order has
no guest-visible distinction under the admitted profile. CSM/active PCM would
invalidate this reduction and is explicitly excluded. It does not manufacture
CPU interrupt acceptances for historical expiries.

GDC/PIT's existing PIC service composition is unchanged and precedes OPNA
service. When composing fake pilots, their private providers must use the same
nondecreasing timeline. No other device's time domain is migrated. Live calls
observe fresh samples in that existing owner context; Linux service gaps do
not establish P4 deadline or recovery policy.

## CPU observation opportunities and Linux pacing

Timer service and CPU acceptance remain different operations. Removing the old
NEVENT timer also removes its incidental CPU-slice boundary. Merely publishing
an analytically correct timer flag can therefore leave an FMP handler waiting
until a display-sized CPU slice completes. The initial live implementation
reproduced that slowdown in producer-side PCM and register timestamps.

The pilot bounds CPU execution before the **existing** pccore PIC arbitration
site to the established 0.5 ms CPU-throughput quantum. A paired scheduler rebase
keeps `CPU_CLOCK + CPU_BASECLOCK - CPU_REMCLOCK` unchanged; NEVENT item deadlines
are unchanged, and the ordinary `nevent_progress` commits only the consumed
slice. This also bounds an HLT slice. It neither creates timer expiries from
CPU cycles nor calls PIC from inside an instruction. The full frame continues
on its original stack, with setup and tail each executed once.

Live OPNA builds also reuse existing SDL CPU pacing, including its final partial
quantum and idle accounting. The pacing function itself is unchanged. GDC-only,
OFF and fake pacing behavior is retained. Fake OPNA builds exercise the same
CPU slice bound without host-clock sleeps, so deterministic N1/N2/N3 and N6
can qualify ledger, instruction, interrupt and device separation. The selected
CPU multiplier controls CPU opportunity density, never OPNA period or phase.
The 0.5 ms choice is an existing soft SDL scheduling quantum, not a new resource
gate, physical device period or P4 deadline guarantee.

Temporary local diagnostics capture guest OPNA register events and the mixed
signed-32-bit stereo producer buffer immediately after synthesis, before SDL
transport. Generation by CPU synchronization and demand top-up is tagged
separately. Generated frame counts and register-to-frame boundaries are measured;
SDL callback output is never semantic authority. Raw event identity is compared
before interpreting time-scale or PCM-duration ratios. No diagnostic public
API/UI or waveform-clock migration is introduced.

## Lifecycle and persistence

`pccore_reset` discards private state before resetting devices; sound-board
reset also discards it. Board86 initialization admits the profile and starts a
new epoch with inactive timers. A debugger/platform epoch reset must perform
the device reset too; merely moving the source backward is rejected.
The seven production save/load/check entry points reject before queue, file or
device mutation when this pilot is enabled. No partial timing serialization is
introduced. OFF retains all original scheduling, PCM, synthesis and save paths.

## Reproducible qualification

Example configure (replace BUILD_I286=ON with OFF for IA-32):

```
cmake -S . -B build_n6_i286_fake -DBUILD_SDL=ON -DBUILD_WX=OFF \
  -DUSE_SDL=2 -DBUILD_I286=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DNP2_OPNA_TIMER_MACHINE_TIME=ON -DNP2_OPNA_TIMER_FAKE_TIME=ON
cmake --build build_n6_i286_fake --target sdlnp2kai_sdl2
python3 tools/test_opna_timer_time.py --output .local/n6/math
python3 tools/test_opna_timer_binding.py \
  --binary build_n6_i286_fake/sdlnp2kai_sdl2 --backend i286 \
  --baseclock 2457600 --multiple 4 --output .local/n6/binding
python3 tools/guest/run_opna_timer_n6.py \
  --binary build_n6_i286_fake/sdlnp2kai_sdl2 --backend i286 \
  --baseclock 2457600 --multiple 4 --output .local/n6/guest
python3 tools/test_opna_timer_save.py --build build_n6_i286_fake
python3 tools/test_opna_timer_off.py --build <OFF-build> --output .local/n6/off
```

Binding qualification invokes actual production board86 bound handlers in the
complete SDL binary while holding CPU execution. Unrelated NEVENT work is
reset explicitly. This isolates the timer proposition without replacing OPNA,
PCM86, PIC, board reset or NEVENT. `--mode legacy` executes the parent NEVENT
path and emits comparable `observations.json`. Differential starts use exactly
representable source grid points; separate fake cases start at arbitrary ns
and exercise D-1 ns/D directly through I/O without preceding service.

The [N6 IPL](../../tests/guest/opna-timer-n6/README.md) executes actual dispatcher
IN/OUT, guest arithmetic, IF, HLT, ISR and EOI. It separately proves publication
versus acceptance. Both fixtures record binary/image identity; bulky evidence
belongs in excluded `.local/` directories.

These assertions do not prove physical YM2608/PC-9801-86 timing, waveform or
acoustic correctness, PCM86/ADPCM/Speak support, CSM machine time, general AUDIO
PASS, Linux realtime, P4 deadline/physical audio continuity, or experimental
save-state compatibility. PCM86 is deferred, not an automatic next milestone.

## Bounded qualification outcome

The N6 mission passed 20 production-binding runs (83 observations each),
12 real-guest CPU-observation runs, both OFF code-generation comparisons,
the existing time-domain regressions, and the complete stock guest oracles.
The live FMP slowdown was reproduced before the CPU-opportunity repair.
With temporary producer instrumentation, the repaired i286/IA-32 candidates
matched all 7063/7059 available register events against OFF. Matched producer
PCM duration ratios were 1.000027/1.000043 at 44100 stereo frames per second.
These are bounded rate measurements, not bit-identical PCM or AUDIO PASS.
The local mission record and raw traces reside under `.local/n6-opna-timer/`;
the committed fixtures above reproduce the canonical timer assertions.
