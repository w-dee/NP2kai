# Multiplierless realtime-target policy

This is the owner-approved, normative architecture policy for future
multiplierless timing work. **ESP32-P4 is the normative realtime execution
target.** Linux SDL is a development, semantic-validation, integration and
stress laboratory. Linux scheduler behavior does not define final-product
guest machine-time semantics. This policy describes the intended architecture;
it does not claim that the current ESP32-P4 port implements it.

Read [time domains](time-domains.md) for the retained legacy cycle model,
[Phase B shadow accounting](time-shadow.md) for its diagnostic implementation,
and [guest-oracle rules](guest-oracles.md) for what a test PASS proves.

## Contract, source and service

Keep three concerns separate:

| Concern | Contract |
| --- | --- |
| Machine time | The time coordinate and progression rules granted to a specific guest-visible device by approved, bounded device semantics and a lifecycle contract. |
| Platform time source | The mechanism that supplies observations of that coordinate. Its behavior and qualification authority depend on the platform and test mode. |
| Service scheduler | The software that observes time and performs device work by its deadlines. Its latency does not redefine the clock. |

```text
                       machine-time contract
                                |
             +------------------+------------------+
             |                  |                  |
      deterministic fake    Linux live       ESP32-P4 hardware
        canonical for        diagnostic       monotonic timer
      Linux semantics        evidence        normative target
```

These sources do not have equal qualification authority. A future ESP32-P4
implementation may use an appropriate hardware monotonic timer as its
authoritative source, with realtime, deadline-oriented device service and
observable service latency. That service is expected to meet explicit deadlines
for its supported workload envelope. The contract remains conceptually portable
across source implementations. A source's measured elapsed time alone does not grant
any device authority to advance; that device needs its own approved semantic
authority and lifecycle rules.

## Linux qualification

**Deterministic fake machine time is canonical for timing-semantics
qualification on Linux.** Tests can advance it independently of guest CPU
work and assert exact, reproducible behavior across slow or fast CPU execution,
HLT/IF=0, stalls, fractional ticks and wraps. For example, a controlled
machine-time advance of 20 ms with zero CPU virtual progress can qualify an
autonomous counter's documented phase change. Conversely, CPU virtual progress
with frozen fake time can qualify unchanged autonomous phase. The 5 ms and
20 ms intervals used in tests are scenarios, not product limits.

Live Linux `CLOCK_MONOTONIC` runs provide supporting integration, implementation
sanity, performance/stress and service-gap evidence. They do not by themselves
define guest machine-time semantics. Preserve their measured timestamps and
service gaps. If a host service gap falls outside the admitted qualification
envelope, report **`INCONCLUSIVE_REALTIME_SEMANTICS`** for that run's realtime
semantic qualification. Do not turn the gap into a PASS or a product rule. The
numeric envelope and its admission procedure require separate approval; this
document selects neither.

In particular, Linux descheduling, host thrash, a debugger stop or another
host-service interruption establishes neither mandatory full catch-up nor
mandatory freeze or clamp for the product. A live run inside its admitted
envelope remains supporting evidence; fake-time tests establish canonical
Linux timing semantics. Phase B's shadow target is diagnostic only and grants
no guest-state authority.

## Distinct forms of stalled progress

| Situation | Meaning for qualification |
| --- | --- |
| Guest CPU executes slowly, HLT, IF=0, or a workload-limited sequence | Guest CPU progress may slow or stop while independently clocked hardware time can continue under that device's hardware contract. Fake time can test this relationship directly. |
| Emulator CPU task is delayed while a realtime service path continues | The target architecture can observe machine time and service devices independently of CPU throughput. Qualify the actual service deadlines and device state transitions. |
| Entire Linux process is descheduled or stopped | Linux supplies no emulator service while stopped. This is chiefly an experimental-platform limitation; its duration is evidence, not an automatic product catch-up, freeze or clamp rule. |

These situations cannot substitute for one another in a test. A stopped process
cannot claim to have serviced devices during the stop. Any subsequent state
transition requires the device's approved catch-up and state semantics.

## ESP32-P4 realtime service

The intended ESP32-P4 design combines a suitable hardware monotonic timer,
realtime or deadline-oriented device service, and measurements of service
latency and deadline compliance. **Machine-time correctness and deadline
compliance are separate qualification dimensions.** An observed deadline miss
does not stop machine time, automatically replay every missed event, or make
stale state acceptable. It is a qualification or quality-of-service violation
for the supported workload envelope that must be detected and reported.
Recovery, event coalescing, lost events and state advancement must follow each
device's hardware-qualified model or approved compatibility profile and its
separately reviewed implementation contract.

Realtime suitability does not mean deadline misses are impossible. Future
qualification must define deadlines and measure their compliance, including
critical sections, interrupt masking, flash/cache/PSRAM activity and scheduling
contention where applicable. This document does not set numeric deadlines,
latency budgets or a universal device recovery algorithm.

## Hardware authority and compatibility profiles

Name the semantic authority for each bounded guest-visible proposition:

- `HARDWARE_QUALIFIED_SEMANTICS` requires authoritative hardware evidence or
  controlled measurement for the target class. Use
  `HARDWARE_QUALIFIED_ASSERTION` only for the behavior that evidence supports.
- An owner-approved `LEGACY_COMPATIBILITY_PROFILE` may use existing np2kai
  guest-visible behavior as the baseline for an **experimental** machine-time
  migration when physical authority is incomplete. This supports a labeled
  compatibility claim, not physical PC-98 equivalence.

A compatibility profile is admissible only when the missing evidence would
otherwise block clock-source decoupling without establishing a contradiction;
the existing behavior can be stated precisely, inspected and regression-tested;
and changing the time parent can preserve that behavior. Document the unresolved
hardware details and exact profile scope. Retain default legacy behavior as a
rollback and reference path. Where neither hardware authority nor a stable,
testable existing profile is sufficient, the migration remains blocked.

The first compatibility migration preserves the specified guest-visible
behavior while changing its authoritative time parent. Preserve, label and
test necessary legacy quirks; defer their correction. Do not invent hardware
behavior, silently choose among contradictory sources, or call a compatibility
quirk hardware-correct. Hardware-qualified behavior takes precedence for its
bounded proposition and must not be overwritten by a legacy quirk. A later
hardware correction is a separately reviewed semantic change with its own
authority, regression tests and qualification. Do not combine it with
clock-source decoupling unless the owner explicitly authorizes that scope.
Existing oracle assertions must not be relaxed to fit a migration, and other
device families receive no time authority merely for convenience.

Future implementation and test reports must distinguish
`LEGACY_COMPATIBILITY_ASSERTION` from `HARDWARE_QUALIFIED_ASSERTION`. Use
`ARCHITECTURAL_ASSERTION`, `DEVICE_RELATIONAL_ASSERTION` and
`INCONCLUSIVE_NEEDS_HARDWARE_AUTHORITY` where they fit. This vocabulary does not
rename or widen any established [guest oracle](guest-oracles.md) PASS.

### First PIT/PIC pilot

The historical Phase D1 audit remains
`BLOCKED_PHASE_D1_PIT_PIC_HARDWARE_AUTHORITY` against its hardware-authority
success condition. This owner decision does not turn it into a hardware PASS.
It permits a **separately labeled compatibility-profile pilot** under a later
implementation mission, subject to preservation and regression qualification
of its explicit profile.

For that pilot, current i286 PIT behavior and current IA-32 behavior with its
71054-selected path may define separate backend-specific compatibility profiles.
The current observable mode-3 rewrite, PIT-to-PIC request publication and PIC
finite-state behavior, including documented quirks, may be retained where
physical authority is incomplete. Small-count fallback, PICMASK timeout,
latch/request interactions, status/OUT representation, PIC initialization,
SFNM/cascade limitations and CRT suppression are examples to preserve, label,
test and correct separately if needed. No profile is automatically qualified
merely because this policy allows it.

The unresolved H01A controller identity, H02A GATE0/OUT0-to-IR0 transfer
function, and NEC71054 mid-half mode-3 rewrite details remain unresolved
hardware questions. This permission establishes neither VM/VX timer silicon
identity nor wiring, pulse/latch conditioning, exact electrical INTA timing,
hardware-correct mode-3 replacement, or equivalence across PC-98 models. A
future clock-source-decoupling PASS may use a name such as
`PASS_PHASE_D1_PIT_PIC_COMPATIBILITY_PILOT`; it must state the tested
compatibility propositions and must not imply hardware-qualified VM/VX timing.
The ESP32-P4 service and deadline requirements, Linux fake-time qualification,
and separate CPU interrupt acceptance rules still apply.

The owner-selected Phase D1 normalization freezes legacy cycle quantization at
**M_ref=5**, independently of runtime CPU multiplier. The
[implementation contract](pit-pic-compat-machine-time.md) records the exact
PICMASK and current-count conversions, executable parent differential, and
backend profile boundaries. This is compatibility authority only; the
historical hardware-authority block remains unchanged.

## Device migrations and the ARTIC preflight

This policy governs ARTIC and later PIT, GDC, OPNA, PCM, DMA and other device
migrations. A future mission must identify hardware-qualified semantics or an
approved legacy compatibility profile, its platform-time contract, service
ownership, deadline requirements and device-specific response to missed service
before granting machine-time authority. The existing
[guest-oracle contract](guest-oracles.md) continues to limit what each test PASS
can establish.

The ARTIC preflight's primary hardware findings on counter width, nominal rate,
CPU-clock independence, documented word ports and rollover remain valid for
the bounded ARTIC-equipped target class. Its fake-time-first test plan is the
canonical Phase C semantic qualification path on Linux. Linux live ARTIC runs
provide supporting integration, sanity, stress and service-gap evidence. A
large Linux scheduling gap does not decide ARTIC product catch-up behavior.
The final ESP32-P4 implementation may use its hardware monotonic timer under
the machine-time contract and its separately qualified service model.

This document supersedes the ARTIC audit's unresolved platform-policy question
without rewriting that historical audit. ARTIC-specific availability,
read/latch limits, reset and save/load decisions remain subject to the audit's
bounds. No Phase C device behavior is implemented by this policy document.

## Required review boundary

Stop and escalate before a future change:

- treats Linux scheduler elapsed time as normative guest machine time;
- derives catch-up, freeze or clamp policy from Linux behavior alone;
- grants a new device machine-time authority without identifying the intended
  platform-time contract and bounded device-semantic authority;
- invents a compatibility profile without stable, testable existing behavior,
  presents it as hardware truth, bundles an unrelated hardware correction into
  clock-source decoupling, or overrides hardware-qualified behavior with a
  legacy quirk; or
- changes the ESP32-P4 deadline/service model without explicit review.

## Owner-approved N5 normalized mouse exception

The owner separately authorized the [N5 normalized mouse profile](mouse-machine-time.md):
autonomous 56.4 Hz input capture, continuous rational movement, exact normal-domain
mouse IRQ rates, and input/capture/expiry/I/O ordering at equal time. This explicit
normalization removes legacy CPU/read-cadence dependence; it is not covered by a
claim of unchanged legacy semantics or hardware qualification. Default OFF keeps
the existing path. The bounded fake-time pilot grants no time authority to other
devices and no Linux/P4 deadline or host-arrival mapping policy.

## Owner-approved remaining Tier1 decisions

The [bounded Tier1 qualification profile](tier1-machine-time.md) implements
three additional owner decisions, default OFF:

- **D1:** generic DMA is CPU/bus-synchronous compatibility. A transfer opportunity
  is an ordering/arbitration event, with no machine-time pacing. No opportunity
  means no transfer. Guest HLT behavior is qualified per backend rather than
  equated with a completely held CPU/bus owner.
- **D2:** residual Tier1 durations use source-specific normalized machine time.
  Raw C-cycle constants become C/B seconds; expressions
  `floor(X*M/Q)+Y*M` in B*M cycles become exact `X/(Q*B)+Y/B`.
  Audited exec-pass countdowns use semantic frames of5/282 second. Source
  epochs, rational phase and cancellation/rearm remain explicit. Neither PIT
  M_ref=5 nor P4 M15 is universal. Tier2 devices receive no grant from this rule.
- **D3:** keyboard edges are timestamped at producer-to-emulator admission,
  sequenced and source-identified, with no edge collapse. A complete prefix
  through T precedes autonomous transfer through T, then guest I/O, then reset
  semantics. Late insertion at/before the finalized frontier and resource
  exhaustion fail explicitly. Source ownership/duplicate suppression remains;
  transfer period is1/1920 second and key repeat remains outside the profile.

These intentional normalizations are not hardware qualification or changes to
legacy/default-OFF semantics. They grant no Linux-derived deadline/recovery
policy, live serial semantics, floppy rotational model or new P4 time source.
