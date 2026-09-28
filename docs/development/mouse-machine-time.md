# N5 normalized mouse machine-time pilot

The owner explicitly approved a **normalized multiplierless mouse profile**
following the N5 preflight. It intentionally changes legacy movement timing;
it is not a legacy-equivalence or physical PC-98 profile. The default/OFF path
remains legacy. This is a bounded Linux SDL2, single-owner, fake-time/input
qualification pilot. It does not implement SDL, USB, BLE, touch or P4 input
admission and does not establish realtime deadlines.

## Authority and build

Owner policy: timestamped ordered host input; autonomous capture every `5/282`
seconds (56.4 Hz); continuous movement over that same duration; exact IRQ rates
120/60/30/15 Hz; settle through T before guest I/O. Same-T order is input,
capture, IRQ expiry, guest I/O. These are `OWNER_APPROVED_NORMALIZED_PROFILE`
assertions, not physical hardware claims. The general
[realtime policy](multiplierless-realtime-policy.md) still applies.

```sh
cmake -S . -B .local/n5-build -DBUILD_I286=ON -DBUILD_WX=OFF \
  -DBUILD_SDL=ON -DUSE_SDL=2 -DCMAKE_BUILD_TYPE=Debug \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DNP2_MOUSE_MACHINE_TIME=ON -DNP2_MOUSE_FAKE_TIME=ON
cmake --build .local/n5-build --target sdlnp2kai_sdl2 -j4
```

Both options default OFF. Enabling the profile without its fake source fails
configuration. No INI, guest command, public input API or runtime switch is
added. The private `mouse_fake_now` coordinate and `mouse_time_admit` fixture
entry are host qualification interfaces. Normal SDL input is not consumed by
this fake-input profile; it remains outside the admitted input stream. Selecting
this test build does not provide a usable live mouse adapter.

## Exact coordinate and admission

One private quantum is `1/(141*10^9)` seconds. An integer nanosecond timestamp
converts by checked multiplication by 141. The fixture can represent rational
boundaries exactly: capture period is 2,500,000,000 quanta; IRQ period is
1,175,000,000 quanta shifted by the rate selector. Neither CPU multiple nor the
legacy cycle ledger participates. No floating point or rounded period is used.

Input records contain timestamp, strictly increasing sequence, relative X/Y and
latest active-low button level (bits7/5). Timestamps are nondecreasing. Admit the
complete input prefix through T **before** settling T. A finalized frontier is
sealed: later insertion at or before it fails. Thus records at T are included
in capture at T, and an event cannot retroactively alter a finalized capture.
Equal-time records use their sequence order. This is a single-owner prefix
contract, not a concurrency or platform-arrival mapping implementation.

The first capture is one period after cold-boot origin. Captures include all
queued records with timestamp <= their boundary. Their X/Y sums and final
button level determine the next batch. Unobserved button edges are not queued
as guest-visible interrupts. IRQ deadlines never sample input.

Initial admitted domain:

- Nonnegative monotonic private coordinate through 24 hours from coordinate
  zero; all arithmetic stays within uint64. This is a qualification bound,
  not a product freeze, catch-up or maximum uptime policy.
- Each input, sum within a capture, and settled live axis lies in
  `[-32767,32767]`. No invented signed wrap or saturation exists. Guest latch
  retains its established `[-128,127]` clamp/drop behavior.
- At most 256 queued input records in the pilot. Full capacity rejects; no
  event is dropped and this is not a permanent backlog design.
- Plain relative mouse path, no KEY_MODE=3, MOUSERAPID, absolute suppression,
  or np2sysp getmpos/direct-manager protocol. Those need later source-specific
  integration under this architecture. Existing OFF implementations remain.
- Cold boot only: save/load APIs reject before file/device effects. A second
  full pccore reset is rejected at function entry before CPU/device mutation;
  direct mouse reset also rejects before clearing the device. Runtime reset
  epochs and retained external input/button restoration are not qualified by
  this initial pilot. CPU-only reset leaves the independent mouse clock alone.

Invalid admission leaves the core unchanged. Service runs on a complete scratch
state, checks movement/time bounds at all relevant captures, and commits only
on success; PIC publication follows commit. Therefore a failed service cannot
partially consume input, advance phase/movement, or publish IRQ. Production
binding rejects unsupported requests by an explicit diagnostic and abort;
core qualification functions return failure for exact before/after checks.

## Movement and guest I/O

For batch axis d captured at C, let e=clamp(T-C,0,P), P=5/282 seconds.
Cumulative delivered displacement is `sign(d)*floor(abs(d)*e/P)` and the exact
nonnegative remainder is retained. The signed fractional remainder belongs to
the sign of the batch. Service applies the difference from the preceding
cumulative result. At the next capture the previous batch is complete. This
reference defines integer movement observation of a continuous linear batch;
small calls never discard fractions. Product multiplication is bounded by
32767 times the integer capture period.

Guest reads merely settle to the observation coordinate. They neither stamp a
new movement origin nor change the movement fraction. C7 rising first settles,
then uses the real existing latch/counter-clear/clamp operation; only already
delivered live counts are cleared. The batch's unspent portion survives. The
binding imports the cleared live counters without clearing delivered progress.
Other existing port decode, button bits and four-read clamp modifier remain;
that modifier still changes on reads, but does not quantize movement itself.

Legacy deliberately retained as OFF: pccore_exec-entry captures; 2000/1000-cycle
query buckets; floor(realclock/56400); discarded per-read motion fractions;
legacy signed16 narrowing and extreme-gap undefined arithmetic. The normalized
profile does not reproduce those timing artifacts. OFF qualification executes
the pinned pre-N5 parent and current source on the same real-device corpus.

## IRQ and owner service

The real mouse handlers settle first. A C4 falling edge arms now+P only if no
pending deadline exists; no immediate IRQ is published. Disable leaves the
outstanding deadline, which retires without publication/rearm if still disabled.
Re-enable before it is due preserves it. Rate writes leave the pending deadline
unchanged; subsequent rearm uses the new period. At exact expiry T, an I/O write
runs after the old enable/rate state's expiry and rearm.

`pic_irq` and PIC mask/read/EOI handlers settle the mouse before observation or
mutation. This segments analytical expiry collapse at PIC observations and
acceptance. Within one service, no CPU/PIC observer runs concurrently, so any
positive number of publications can OR the real slave IRR bit once while the
logical publication/expiry counts and phase advance exactly. Acceptance still
runs through real PIC arbitration and the real CPU interrupt implementation.
No NEVENT_MOUSE deadline is armed in the new profile. The legacy callback is
an explicit rejection if reached accidentally.

Empty captures and IRQ periods advance analytically. Work is bounded by queued
input capture groups plus a constant number of batch completions, not the
number of empty ticks. Captures and IRQ transitions commute internally because
captures do not mutate IRQ state; the final publication occurs before guest I/O
and only after all checks succeed. Input/capture ordering is retained exactly.

`mouseif_sync` is a service opportunity only in this profile. It no longer
captures, flushes residuals or stamps CPU time. Fake time can advance while CPU
state is held, and CPU work with frozen fake time cannot advance the mouse.

## Qualification and limits

```sh
python3 tools/test_mouse_time.py --output .local/n5-tests
python3 tools/test_mouse_off.py --build-root .local/n5-tests
python3 tools/test_mouse_save.py --build .local/n5-tests/build-i286
python3 tools/test_mouse_save.py --build .local/n5-tests/build-ia32
python3 tools/guest/run_i286_time_mouse.py --binary .local/n5-build/sdlnp2kai_sdl2 \
  --output .local/n5-guest --backend i286 --multiple 4 --baseclock 2457600
```

The math corpus uses an independent absolute rational displacement oracle,
50 deterministic mixed-axis histories, fine and randomized service partitions,
exact-T capture, latch residual, all rates, million-tick gaps and transactional
rejection. Real mouse/PIC binding tests cover both backends, both base clocks,
and M1/4/5/20 under normal and ASan/UBSan builds. The dispatch hook in that
fixture is not a guest ISR; the separate [IPL fixture](../../tests/guest/i286-time-mouse/README.md)
executes the actual handler/IRET and validates HLT wake.

A bounded PASS covers this normalized external-input/capture/movement/IRQ
architecture. Live timestamp mapping, input watermarks across producers, runtime
reset epochs, alternate input paths, broader numerical domains and P4 deadlines
remain separate integration work. No physical PC-98 timing or input latency is
proved; Linux debugger elapsed time is not semantic authority.
