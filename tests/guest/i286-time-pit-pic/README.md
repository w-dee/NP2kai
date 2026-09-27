# PIT0/PIC machine-time compatibility IPL, version 1

Original DOS-free 1024-byte IPL in a deterministic 1232 KiB raw floppy.
Guest source is BSD-2-Clause; host tooling is project-original MIT.
No DOS, proprietary binary, or code from N1/N2/N3 is included. This fixture is
separate from the numbered N1/N2/N3 fixtures and is not assigned N4.

Authority and service rules:
[Phase D1 contract](../../../docs/development/pit-pic-compat-machine-time.md).
Profile 1 is `PROFILE_I286`; profile 2 is `PROFILE_IA32_71054_SELECTED`.
Neither identifies physical silicon. Mode 2 is the canonical fake-time test.
Mode 1 captures legacy observations, using longer periodic/HLT counts so
uncontrolled legacy CPU time can reach HLT before expiry.

## Build and qualify

```sh
python3 tools/guest/build_i286_time_pit_pic.py \
  --output .local/pit-pic.hdm --mode 2 --profile 1
python3 tools/guest/run_i286_time_pit_pic.py \
  --binary build_phase_d1_i286_fake/sdlnp2kai_sdl2 \
  --output .local/pit-pic-guest --backend i286 --mode 2 \
  --multiple 4 --baseclock 2457600
```

The private runner needs existing local BIOS/font assets, NASM, GDB, Xvfb
and Linux x86_64 host ABI. It creates isolated config and artifacts. It changes
only the private host fake-source symbol at stopped guest progress markers;
no emulator guest command/port API exists. It verifies actual port accesses,
CPU progress, and an existing service call with CPU/unrelated state frozen.
Linux scheduling/debugger elapsed time is not a timer oracle.

## Canonical cases

All numeric counter/PIC results are **LEGACY_COMPATIBILITY_ASSERTION** from
the selected parent profile at M_ref=5.

| Case | Actual guest operation | Positive assertion |
| --- | --- | --- |
| 1 | Program mode 0, count 100; read ch0 | Initial current word is 100. |
| 2 | Execute 8192 loop iterations; read ch0 with fake time unchanged | Current word remains 100 despite CPU progress. |
| 3 | Latch after 25 source ticks; advance another 25 before read | Latched word remains 75. |
| 4 | Program mode 3, count 9, IRQ0 masked; advance to expiry; read IRR | IRR0 is set. |
| 5 | Advance exactly two more source ticks, read IRR, unmask/STI | IRR0 remains set and one IRQ is accepted through existing arbitration; ISR entry and EOI are observed. |
| 6 | Program mode 0, count 40; STI/HLT; advance fake time while CPU is stopped at service | Service materializes IRR0 without CPU/other device mutation; normal arbitration wakes HLT, handler saved IP is the post-HLT label, total accepted count is two. |

The HLT and service relationship is also a **DEVICE_RELATIONAL_ASSERTION**.
The existing CPU boundary is observed; this fixture does not independently
replace N1's STI/MOV-SS architectural assertions or N2's REP restart test.

Time schedule is 0, 0, 125, 250, 295, 305, 505 reference quanta, where a
quantum is 1/5 source tick. Each integer quantum is converted to the first
nanosecond reaching it under the selected clock class. The 12-condition matrix
is two backends × two configured clock classes × multipliers 1/4/20.
Legacy mode is observation-only; its periodic and HLT count encodings are zero
(parent 65536 fallback), and no exact fake count or interrupt-total verdict
is imposed.

## RAM contract

Result lives at physical `0x29000`, 128 bytes, little endian. Terminal value
2 means collection complete, written last. The host validator supplies the
PASS/observation verdict after checking the whole block. No guest failure
counter is substituted for host validation.

| Byte offset | Contents |
| --- | --- |
| 0 | Magic `PIPC` |
| 4, 6, 8, 10 | Version 1, size 128, mode, profile |
| 12 | Current/final case ID (6) |
| 14 | Reserved zero |
| 16, 18 | Initial control 0x30 and count 100 |
| 20, 24, 26 | Initial, CPU-work/frozen, and latched current words |
| 28 | IRR at count9 expiry + two source ticks (low byte) |
| 30 | Accepted IRQ handler count |
| 32, 34 | ISR on latest entry and after EOI (low bytes) |
| 36, 38 | Pre-HLT 0x1111 and post-HLT 0x2222 |
| 40 | CPU loop progress (8192) |
| 42, 44 | Latest handler saved IP and expected post-HLT IP |
| 46, 48, 50 | IRR at expiry, IRQ count before HLT, final IMR |
| 52, 54 | Periodic and HLT programmed count encodings |
| 122 | Guard 0xa55a |
| 124 | Sum of preceding 62 words modulo 65536 |
| 126 | Terminal marker, written last |
| Other bytes | Reserved zero |

The builder reports image SHA-256, mode/profile and NASM version.
The runner additionally records binary SHA-256, structured validation,
fake-source/CPU ledger samples, and CPU/other-state equality during HLT service.
Artifacts are local; licensed source, schema and tooling are reusable.

PASS proves only these compatibility and service relationships in the tested
backend/configuration. It does not prove VM/VX hardware identity, electrical
GATE/OUT/IR0 behavior, physical mode-3 waveform, Linux realtime deadlines,
audio quality, or other device migration. Existing integration oracle semantics
and the historical hardware-authority block remain unchanged.
