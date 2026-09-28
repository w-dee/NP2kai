# Multiplierless audio waveform reference policy

Status: **bounded machine-time grid and continuous native FM/BEEP reference
architecture qualified for P4 port design**. This document specifies the
owner-selected rules and the executable SDL/Linux reference bounds.
It does not rename or extend N6-T, N6-C, N6-W0 or N6-W PASS propositions.

The profile identifiers are private to the native/reference code:
`LEGACY_NATIVE_W0_PROFILE` is the default OFF path;
`MACHINE_TIME_CONTINUOUS_WAVEFORM_PROFILE` is opt-in from the host reference
executors for FM and BEEP. No user-facing option, save format or P4 protocol is added.

## Time and ownership

| Coordinate | Contract |
| --- | --- |
| Machine time | Independent device-semantic clock, supplied by a qualified platform source. Deterministic fake time is the Linux authority for these tests. |
| Semantic history | Epoch, integer-nanosecond timestamp, sequence and operation. Acceptance and renderer application are distinct when old-prefix generation intervenes. |
| Output grid | Configured R=44100 or48000 observations per second. It does not depend on CPU progress, SDL credits or physical playback. |
| Generation plan | A finalized ordered action sequence and authorized output interval. Native FM continuous mode is partition invariant within the tested domain. |
| Producer frontier | Count of fully generated signed 32-bit stereo frames at R. It is progress, not permission to advance machine time. |
| Transport | Buffer/packet/consumer scheduling below the producer. Credit may delay computation or cause explicit resource failure. |
| Physical sink | Separate target deadline and continuity qualification. |

Linux wall-clock gaps do not define catch-up/freeze/clamp behavior. See the
[normative realtime policy](multiplierless-realtime-policy.md).

## Sample mapping and application

For a grid segment with machine-time origin `e` in integer nanoseconds, output
rate `R`, global first-sample index `N`, and event time `t >= e`:

```text
F(t) = N + ceil((t-e) * R / 1,000,000,000)
     = N + q + (remainder != 0),
       where (t-e)*R = q*1,000,000,000 + remainder.
```

The [checked C reference](../../tests/host/audio_waveform_policy/grid.c) uses
128-bit intermediate multiplication and rejects invalid rates, pre-origin
input and 64-bit frontier overflow. It never independently rounds time deltas.
A remainder accumulator is equivalent only if it retains its exact remainder
and origin. The [grid tests](../../tests/host/audio_waveform_policy/test_grid.c)
check partitioned and one-shot calculations, long timestamps, epoch offsets,
exact boundaries and adjacent nanoseconds at both rates.

Sample `n` observes the left edge of its interval. An event strictly after that
instant first applies at the next sample, while an exactly representable event
boundary can apply at `n`. Multiple operations at one frontier remain separate
and execute in semantic sequence order. Register snapshots, class priority,
CSM deduplication and transport order do not replace semantic sequence.

The [tracked reference executor](../../tests/host/audio_waveform_policy/fm_reference.c)
reads an explicit global-frame action plan from the
[history/grid harness](../../tools/test_audio_waveform_policy.py). The harness
accepts epoch, acceptance and application nanoseconds, sequence, operation and
rate; it emits frontiers, ordered actions and renderable spans. A `CSM_ENTRY`
marker in the plan is processed before the old prefix is generated to its
application frontier; ordered key-off/key-on then run at that frontier. This
exercises the distinction observed by the N6-W0 nested-sync fixture. It does
not add a fake `sound_sync` for direct reg27/extop assignment.

## Finalization and resources

Rendering `[S,E)` requires the current epoch, a committed ordered prefix
containing every operation with application frontier `< E`, a future-event
lower-bound watermark `L` for which `F(L) >= E`, and a committed plan through
`E`. Later same-time events mapping to `E` are legal and affect subsequent
samples. Timestamp alone or sequence count alone is insufficient. A partial
owner-service batch cannot publish a watermark past an uncommitted operation.

The harness has explicit finite record and output capacities. Exhaustion is
reported before publication; it does not drop events, shorten a logical span,
change frontiers, freeze machine time, or silently alter native calls. The
controlled credit model varies capacity, initially free blocks, return timing
and consumer pacing. It inserts demand-derived call cuts only after the
continuous FM invariant has been checked. A full materialized output interval
still requires work proportional to its sample count. Computing a far-away
frontier arithmetically is compact semantic planning, not O(1) synthesis.

## FM progression and compatibility

The actual native renderer has a private continuous entry in
[opngeng.c](../../sound/opngeng.c). It retains the same per-sample arithmetic as
`opngen_getpcm`, but does not return just because global `playing` is zero at
call entry. A long call that transitions to silence already traversed the
remaining samples; continuous mode makes later shorter calls do the same.
The reference also includes a parallel VR entry for code symmetry, but VR/
Speak Board is outside the qualified PC-9801-86 profile. The default native
callers retain the old entry guard and W0 semantics. The source contains no
new persistent renderer field, so experimental mode is selected by the private
entry point and does not alter save data layout.

`TL_BITS=FREQ_BITS+2`, so four old `<< (FREQ_BITS-(TL_BITS-2))` expressions
were always zero-bit shifts. Removing them avoids UBSan's negative-left-shift
failure without changing the value. Legacy W0 tests and sealed old PCM
comparison protect the OFF path; this arithmetic cleanup is not a YM2608
hardware claim.

In the [bounded FM matrix](../../tools/test_audio_waveform_policy.py), 50
project-owned fixtures at each rate include six simultaneous channels, all
algorithms with representative feedback, key/envelope transitions, frequency
writes, same-frontier CSM/key/high-low/extop, explicit legacy single/repeated CSM,
active and quiet large/split plans, frequency changes, reset and five
fixed-seed generated histories. Original demand cuts, one-frame, max17,
max137, max240, max511, event-boundary and large-interval plans produce exact
producer PCM and the W0 scalar final renderer fingerprint for a given fixture
and rate. Event projection is identical by construction and hashed in evidence.
This is bounded qualification, not a proof over all possible native states.

The selected continuous policy deliberately changes some old results.
The new harness records per-fixture current OFF-versus-continuous first
PCM difference, changed-frame count and final-state equality. In the new
controlled corpus, quiet-split first differs at frame 10000 (991/11000 frames
at 44100, 163/11000 at 48000; final state differs). Active large/split,
single/repeated CSM, CSM plus key, frequency, reset, same-frontier CSM and
the project-owned sequence have no OFF-to-continuous difference under their
original call plans. These values do not imply all old call plans agree. No profile can
preserve two mutually inconsistent old call partitions for the same history.

The unchanged W0 oracle means: same initial state, exact ordered history,
frontiers, call partition and epochs imply exact native PCM and fingerprint.
The new continuous profile has a separate result namespace; it does not widen
W0. The existing [oracle contract](guest-oracles.md) still applies.

## Epochs, reset and rate segments

A guest reset closes the old semantic epoch at global frontier `F`, applies
RESET there, and starts the new semantic epoch at **the same global sample
index**. Output coordinate and physical sink lifetime continue. Every included
source in a mixed profile must close at `F`; an FM/BEEP mismatch is invalid.
The reference reset fixture retains global producer position and changes the
history epoch from1 to2 at the reset action. Save/load serialization is outside
this experimental profile; existing legacy guards remain.

A sample-rate change is an explicit fully finalized segment fence. The C grid
reference accepts a new segment only when the old segment maps the fence time
to the already finalized global frontier. The new segment has a new origin and
rate, with `first_sample` equal to that frontier; old generated samples are
never reinterpreted. The reference checks 44100→48000 and the reverse.
Arbitrary hot mid-span renderer remapping is outside the initial profile.

## BEEP, PSG, rhythm and PCM86 scope

FM and BEEP have independent ordered histories but share the machine-time-derived
sample grid, finalized mix frontier and reset coordinate. The owner selected
`CONTINUOUS_LOGICAL_SOURCE_PROGRESSION` for BEEP as well as FM. The new private
[BEEP state machine](../../sound/beep_waveform_policy.h) in
[beepg.c](../../sound/beepg.c) is default OFF; the old `beep_getpcm` entry and
its state remain available. The new entry consumes mode/data/phase-increment/
edge events at their checked `ceil` frontiers. Mode 0 holds the last 8- or 16-bit PIT data
value and advances its optional 500-sample adaptive offset per sample. Mode 1
uses the source's four phase steps per steady sample; an edge at a sample
boundary emits the new duty value for that sample and resets phase, matching
native exact-boundary behavior. This avoids both old call-local time
interpolation and event-queue exhaustion. The new state is per source, and
reset clears it at the same global F at which FM and the mix close.

The old BEEP modes were diagnosed separately. In mode 0, `oneshot` derives
`bound=(last_loaded_time-first_time)/count`, so changing `count` changes which
held PIT value each sample sees. In mode 1, `rategenerator` consumes pending
`BPEVENT` clocks, resets phase at events and clears the queue at the end of a
call. Splitting a call can consume a future event early and change subsequent
phase/state. The [legacy diagnostic](../../tools/test_audio_waveform_beep.py)
finds both modes partition sensitive at both rates. Its mode-0 timestamps
stand in for legacy CPU-cycle PIT timestamps; this is not a machine-time
conversion. All 16 old diagnostic PCM hashes still equal the pre-change
baseline.

The [continuous BEEP harness](../../tools/test_audio_waveform_beep_continuous.py)
uses the same checked grid/history/finalization contract as FM. At 44100 and
48000, seven partitions over both modes, adaptive/fixed mode-0 offset, edges,
period changes, same-frontier groups and nonzero-tail reset produce 126 exact
PCM and qualified-state results. Owner-service batches, delayed worker copies
and transport-credit cuts also match. Same-frontier order reversal changes
PCM and state, as required. Mixed FM+BEEP cases include active FM with BEEP
edge, BEEP silence with FM, FM silence with BEEP, and a nonzero old tail
closed at F=1237 for both sources and the mix. Immediate, delayed and credit
plans produce the same 4000-frame signed-32-bit producer mix at each rate.

The 16-bit mode-0 fixture also verifies the actual PIT data width. Old
adaptive-offset comparison is bounded to 8-bit data because the old static
32-bit offset sum can overflow for a sustained high 16-bit value. The new
per-source sum is 64-bit.

The [compatibility matrix](../../tools/test_audio_waveform_beep_compat.py)
compares the same ordered control events against old native large, 1-frame,
137-frame, 240-frame and event-boundary calls in 180 controlled cases. Its
synthetic legacy clock values are sample-index proxies: actual mode-0 PIT
records CPU cycles and actual mode-1 event clocks are CPU deltas scaled to
16.16 sample delays. This isolates call-boundary behavior; it does not claim
hardware BEEP timing. In these fixtures the continuous result equals the old
large-call PCM except for adaptive-offset mode-0 reset: the old static offset
persists across guest reset, while the new per-epoch source offset resets at
F=1237, causing 2763 changed frames. Old split calls can also diverge. For example, at 44100 mode-0 transition differs from the new profile
in 1499 frames under old one-frame calls (first difference at frame 1); old
mode-1 edge-start differs in 2517 frames (first difference at frame 1). Both
old state and new source state are recorded per case. Equality with one old
partition is evidence, not the new policy authority: continuous progression
on the common grid is the authority. No guest-visible PIT/port semantics are
changed.

PSG register/control history is ordered by `psggen_setreg` and shares the
producer sample coordinate; tone/noise/envelope counters advance inside
`psggen_getpcm`. A bounded native test at 44100/48000 with tone/noise/envelope
and register changes found exact PCM/state across six partitions. The PSG
phase counter intentionally wraps; the sanitizer probe compiles that one
translation unit with `-fwrapv` to define the established wrap behavior.
This is source-specific qualification work under the same architecture, not
physical PSG accuracy.

OPNA rhythm uses ordered trigger/volume/pan writes and the shared
`pcmmix_getpcm` producer callback. A bounded test uses project-owned synthetic
PCM asset data and found exact PCM/state across six partitions at both rates,
including trigger, retrigger and stop. External `2608_*.wav` asset loading and
all asset variants are not covered; source integration remains later work.
Neither PSG nor rhythm evidence resolves BEEP's separate semantic choice.

PCM86 playback remains **deferred but architecturally covered**. A future
playback profile can reuse a machine-time owner, ordered byte/control history,
finite FIFO state, this common output grid, delayed decode/resampling, and
transport separation. It still needs decisions for legacy versus nominal
source period, guest-visible `virbuf`/`realbuf` compensation and IRQ, and
underflow/refill renderer partition semantics. No PCM86 guest behavior or
product support is changed here.

## Qualification and limits

Reproduce grid/FM with `python3 tools/test_audio_waveform_policy.py --output
.local/audit/audio-waveform-policy-20260928/full`; use `--sanitizer` for the
ASan/UBSan variant. BEEP and other-source diagnostics have separate scripts.
Canonical PCM is signed 32-bit stereo before SDL transport conversion. Within
a configured rate, exact bytes and final scalar state are compared; cross-rate
PCM equality is not expected. Immediate and worker-owned copied plans, owner
service batches, CPU-coordinate/multiple changes and controlled transport
credits are distinct deterministic checks. SDL callback output is never a
semantic oracle.

Architecture closure verdict: **`AUDIO_MULTIPLIERLESS_ARCHITECTURE_CLOSED_FOR_P4_PORT=YES`**
for the bounded reference architecture. FM and BEEP partition dependence is
removed in separately named default-OFF reference entries; PSG and rhythm fit
the same history/grid/producer architecture within the tested source scope.
Their remaining source-specific integration, external rhythm assets and PCM86
compatibility choices are implementation or feature work under this
architecture. No P4 source, deadline model, protocol or hardware is modified.
The private reference entries are not wired as a live SDL product option;
closure is architectural and bounded, not a finished P4 audio port.

This profile does not prove physical YM2608/PCM86 accuracy, FMGEN or ADPCM
support, Speak Board semantics, all possible FM states, Linux realtime
behavior, ESP32-P4 compute/deadline feasibility, hardware clock calibration or
physical audio continuity.
