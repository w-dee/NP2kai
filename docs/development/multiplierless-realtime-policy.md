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
| Machine time | The time coordinate and progression rules granted to a specific guest-visible device by an approved hardware and lifecycle contract. |
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
any device authority to advance; that device needs its own hardware semantics
and approved lifecycle rules.

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
device's hardware model and separately approved implementation contract.

Realtime suitability does not mean deadline misses are impossible. Future
qualification must define deadlines and measure their compliance, including
critical sections, interrupt masking, flash/cache/PSRAM activity and scheduling
contention where applicable. This document does not set numeric deadlines,
latency budgets or a universal device recovery algorithm.

## Device migrations and the ARTIC preflight

This policy governs ARTIC and later PIT, GDC, OPNA, PCM, DMA and other device
migrations. A future mission must identify its device hardware authority,
platform-time contract, service ownership, deadline requirements and
device-specific response to missed service before granting machine-time
authority. The existing [guest-oracle contract](guest-oracles.md) continues to
limit what each test PASS can establish.

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
  platform-time contract and device hardware semantics; or
- changes the ESP32-P4 deadline/service model without explicit review.
