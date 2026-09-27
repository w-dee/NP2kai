# Phase B: shadow host-monotonic accounting

Phase B observes a host-monotonic target alongside the Phase A legacy cycle
domain. **No shadow value has guest-state authority.** All guest/device time
continues to use the existing legacy model. No device consumes this target;
Phase B creates no committed device frontier. See [time domains](time-domains.md)
and the mandatory [guest-oracle contract](guest-oracles.md). Future machine-time
semantics and platform qualification follow the [normative realtime-target
policy](multiplierless-realtime-policy.md).

## Terms and units

| Term | Representation and meaning |
| --- | --- |
| Host monotonic sample | Unsigned 64-bit nanoseconds plus validity; a raw host observation |
| Shadow machine target | Accepted host sample minus the paired epoch's host sample, in ns |
| Legacy device position | Existing modulo-2^32 `LEGACY_CYCLESTAMP` from `legacy_cpu_device_now()` |
| Legacy rate | Existing `pccore.realclock`, derived from configured baseclock and multiple, in cycles per virtual second |
| Legacy elapsed duration | Diagnostic conversion of observed cycle progress, piecewise by legacy rate |
| Shadow divergence | Host target minus legacy-equivalent ns; positive means legacy progress is behind the target |
| Committed device frontier | A future architectural concept, not implemented by this observer |

## Clock contract and enabled platforms

The private `timeshadow_posix.c` adapter calls `clock_gettime(CLOCK_MONOTONIC)`.
It converts seconds and nanoseconds explicitly into uint64 nanoseconds, with
range/error checks. Its frequency is **1,000,000,000 units per second**,
independent of `clock_getres`. Resolution is separately queryable. There is no
wall-calendar source or floating point in the accounting.

The selected Linux SDL2 build path was verified by preprocessing and object
inspection. The existing `NP2_TickCount_GetCount` path selects `SDL_GetTicks`
while its frequency function returns 100000000: it tests `USE_SDL_VERSION`,
where these builds define `USE_SDL=2`. The generic POSIX tickcount branch also
derives frequency from resolution. Phase B therefore uses the private adapter;
it does not change tickcount or frontend pacing. The host adapter test checks
100,000 ordered reads and reports actual resolution (1 ns on the qualification
host). That resolution is not an accuracy or service-latency guarantee.

Linux `CLOCK_MONOTONIC` permits equal consecutive values, excludes system
suspend time, and can be frequency-adjusted. An emulator pause, debugger stop,
SIGSTOP or scheduling stall is included when this clock continues running.
The observer records the resulting raw gap; it neither clamps nor discards
elapsed time as a product policy. It cannot reconstruct suspend duration this
source does not measure. Final pause/suspend treatment is deferred. The 5 ms
and 20 ms test inputs are diagnostic scenarios, not product thresholds.

## Enablement and ownership

The private CMake option `NP2_TIME_SHADOW` defaults to OFF. Enable it only in a
local Linux SDL2 interpreter diagnostic build, using the established Phase A
configuration with `BUILD_WX=OFF`, `BUILD_X=OFF`, `BUILD_LIBRETRO=OFF`,
`USE_HAXM=OFF` and `USE_ASYNCCPU=OFF`. Other combinations are rejected; the
runtime also rejects multithreaded guest owners at compile time. Both i286 and
IA-32 are qualified. This does not establish support for other frontends.

When OFF, hook macros discard their arguments, and the three diagnostic C
sources are absent from the target. No clock read, ledger counter, branch,
allocation or shadow symbol remains. Parent versus OFF `.text` comparisons
under identical flags cover `pccore.c`, `nevent.c` and `statsave.c` on both CPUs.
There is no public runtime command, protocol, worker thread or serialized API.

When ON, fixed-size state belongs solely to the emulation thread. A stopped
debugger may inspect `np2_time_shadow` and `np2_time_shadow_epochs`. The observer
does no file/console output on its sampling path. External diagnostic capture
may stop the process; resulting service intervals are observations, not
unperturbed realtime guarantees.

## Internal interfaces and sampling points

`timeshadow_account.h` defines `SHADOW_HOST_SAMPLE`, the replaceable
`SHADOW_CLOCK` callback, `TIME_SHADOW`, `shadow_reset`, `shadow_observe` and
`shadow_rate_anchor`. Accounting consumes values, with no guest-state pointers.
The production adapter supplies the clock and reads the legacy ledger.

| Production hook | Purpose |
| --- | --- |
| `pccore_exec` entry | Paired host/legacy observation before existing audio/input/frame work; sees gaps since the previous exit |
| `pccore_exec` exit | Observation after existing frame work and reset handling; sees blocking work inside the call |
| `nevent_progress`, before existing slice commit | Add the same signed slice budget to a diagnostic wide commit witness; **no host clock read** |
| `nevent_changeclock`, before existing rescaling | Observe the preceding interval at the explicitly supplied old rate |
| `nevent_changeclock`, after existing rescaling | Anchor the next interval to the new rate and new legacy coordinates; no host read |
| `pccore_reset` and entry to `statsave_load_d` | Clear diagnostics only; next observation captures a fresh epoch |

These hooks add no CPU instruction safe point, REP check, interrupt check,
DMA opportunity or scheduler dispatch. Service-interval metrics describe the
clock sampling points above; they do not measure internal REP yield counts or
guarantee a scheduler-latency bound. The reset at load entry also applies to a
failed load attempt; this is diagnostic lifecycle handling only.

## Epoch, wraps and discontinuities

The first valid host observation pairs host ns, legacy stamp and configured
rate. The epoch is runtime diagnostics only. Reset/load clears it without
altering or adding save fields. Subsequent host targets are relative to this
epoch. Backward or failed host samples increment an invalid counter and retain
raw evidence; they do not replace the last accepted host anchor. Legacy work
can still be counted during a rejected host sample.

A modulo stamp alone cannot prove how many wraps occurred: host elapsed time
times the configured rate is not an upper bound on progress, especially with
NOWAIT. The diagnostic witness instead sums the **existing signed NEVENT
commits** into int64 and adds the current wide `slice - remaining` offset.
Paired budget rebase/commit operations preserve this coordinate, including
overshoot. Its delta must be nonnegative and agree with the modulo stamp delta.
This independent evidence resolves ordinary and multiple wraps without
guessing. The wrap counter counts forward modulo crossings on accepted
intervals; rate-coordinate re-anchoring is excluded.

Missing/invalid witness evidence, a negative delta, modulo disagreement,
unobserved rate change, zero rate or numeric overflow marks a discontinuity.
The raw host/stamp/witness inputs remain available, and the first discontinuity's
input and duration snapshot is retained even after further samples. Legacy totals then freeze
as a known prefix and comparison validity remains false until a new epoch;
they must not be interpreted as current duration. Raw host targets and maximum
accepted host gaps continue to update. No guest state is repaired. Large gaps
with a valid wide witness can remain unambiguous, irrespective of wrap count.
Representational overflow is reported, not used to define a stall policy.

## Rate and fraction accounting

Each accepted cycle delta is converted at its interval's rate using integer
arithmetic with a 128-bit intermediate. Duration is accumulated as uint64 ns
plus a uint32 fractional ns (Q32); division remainder is carried between
samples. At a rate boundary, the previous segment is first accounted at the
old rate, then the shadow coordinate is re-anchored after existing rescaling.
Previously accumulated cycles/duration are never converted again at the new
rate. Remainder is mapped to the new denominator; the truncation error is less
than one 2^-32 ns unit per rate change. Repeated same-rate samples introduce no
avoidable division drift. Reported integer divergence uses floor legacy ns.

The adapter does not write `pccore.baseclock`, `multiple`, `realclock`, CPU
budget, NEVENT deadlines, or their rescaling. Unannounced rate changes are
flagged rather than assigned an invented history.

## Metrics

`TIME_SHADOW` exposes a bounded snapshot, not an event log:

- `samples`, `anchored`; paired `epoch_host_ns`, `epoch_stamp`, `epoch_ledger`.
- `raw_host_ns`, `raw_stamp`, `raw_ledger`; accepted `last_host_ns` and last
  legacy sample/witness coordinates.
- `raw_rate` and retained `first_bad_host_ns`, `first_bad_stamp`,
  `first_bad_ledger`, `first_bad_rate`, `first_bad_target_ns`, `first_bad_legacy_ns`.
- `host_target_ns`, `max_host_interval_ns`.
- `legacy_cycles`, `legacy_ns`, `legacy_fraction`, `remainder`, `rate`.
- Signed `divergence_ns`, `max_positive_ns`, `max_negative_ns` (zero if that
  sign has not occurred), and unsigned `max_absolute_ns`.
- `observed_wraps`, `invalid_host_samples`, `discontinuities`, `rate_changes`.
- `discontinuity_reasons` bitset (`SHADOW_BAD_LEDGER`, `SHADOW_RATE_UNKNOWN`,
  `SHADOW_OVERFLOW`), `legacy_valid`, `comparison_valid`.

Extrema include valid comparisons only. Numeric limits are 64-bit ns/cycles,
signed 64-bit witness/divergence, and 32-bit configured rate. A snapshot with
`comparison_valid=0` must not be presented as a valid current divergence.
`np2_time_shadow_epochs` counts diagnostic resets outside the reset snapshot.

## Validation and future boundary

Run `python3 tools/test_time_shadow.py` for deterministic fake-clock accounting,
the actual host adapter, and one-way source-dependency checks. Tests cover
steady progress, 5/20 ms jumps, seeded irregular jumps, equal/backward/invalid
samples, huge deltas, single/multiple wraps and missing wrap evidence, rate
changes with fractional remainder, unknown rate changes, overflow, and new
epochs. Runtime binding tests exercise commit invariance, overshoot, rescaling
and reset with the production adapter and a fake source. These are arithmetic
and binding tests, not device or hardware assertions.

Live integration qualification requires N1/N2/N3 exact structured OFF/ON
equality, both DOS/FMP integrations, and the complete Windows 95 state machine
with existing
thresholds. At least one FMP diagnostic observation must continue for about
10 seconds after the normal prompt checkpoint to include background playback.
That run provides no audio PASS; visual success never proves playback
completion or audio continuity. Performance measurements distinguish disabled
code generation from enabled observation cost.

Save layouts/units, TSC, DMA service, frontend pacing, audio production and
consumption, and device progression retain their existing semantics. Phase C
would require separate approval before any autonomous counter/device consumes
machine time; no PIT, OPNA, GDC, DMA or RTC host-time advancement is authorized
by this diagnostic implementation.
