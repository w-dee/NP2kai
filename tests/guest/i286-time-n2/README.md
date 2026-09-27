# N2: long REP MOVSB restart IPL fixture

N2 is a standalone 16-bit i286 IPL test of interruptible REP memory progress.
It boots a raw 1232 KiB PC-98 floppy without DOS or a proprietary guest OS.
A PASS is the defined architectural and stock-backend regression result; it
is not a measurement of physical PIT frequency or emulator scheduler debt.
The earlier N1 fixture is unchanged.

## Build, verify, qualify

NASM 2.16.01 is the qualified assembler. Python 3 builds and validates the
image; the local stock qualification also uses Xvfb, xdotool, ImageMagick
`import`, GDB, and the established private BIOS/font ROM configuration.

```sh
make -C tests/guest/i286-time-n2 verify
make -C tests/guest/i286-time-n2 test
make -C tests/guest/i286-time-n2 qualify
```

The builder assembles `src/stage2.asm`, then the BSD2 1024-byte IPL with
compile-time payload size/sector count, and zero-pads a 77-cylinder, 2-head,
8-sector, 1024-byte/sector `.hdm` image. `reference.json` pins NASM, IPL,
stage2 and whole-image hashes. The stock runner builds a fresh image into
`.local/n2-fixture/qualification/`, verifies its hash and the stock i286
binary hash, then launches under private Xvfb and GDB. GDB reads the 256-byte
guest result and all 32,768 bytes of source and destination RAM without
changing emulator code or guest assertions. It also captures the window and
logs. GDB stopping can perturb host wall time; elapsed seconds are diagnostic
only. The original N1 runner and existing DOS oracle are untouched.

## Guest design and stable IDs

Stage2 runs at `2000:0008`, result RAM is physical `0x29000`, stack is
`2800:1000`. The source `3000:0100` and destination `4000:0100` are distinct
32,768-byte RAM ranges. Source bytes follow `(0x13 + 0x3d * index) & 0xff`;
destination starts at `a5h`, with `5ch` and `c5h` boundary canaries. Guest
computes a source checksum, performs `REP MOVSB` with CX=`8000h`, then
independently compares every byte and computes a destination checksum.

Only IRQ0 is unmasked. A one-shot PIT channel-0 reload of `1000h` is armed
immediately before `STI; REP MOVSB`; guest records that IRR bit 0 is clear
before the REP starts. The IRQ0 handler records the first acceptance phase,
CX, SI, DI, saved IP and FLAGS, plus PIC ISR before and after EOI. A value
between zero and `8000h` for first CX is mandatory. This is a virtual PIT
stimulus with a relational acceptance criterion, not an asserted physical
clock constant. A failure to receive a suitable interrupt fails the guest
assertion; the runner never infers success from wall time.

| ID | Name | Required proposition | Authority |
| --- | --- | --- | --- |
| 1 | `IRQ_DURING_REP` | IRR is clear before REP, IRQ0 enters PIC service, exactly one handler runs in phase 1 before the phase-2 completion marker, and EOI clears ISR bit 0. | `LEGACY_I286_BACKEND_REGRESSION` and `DEVICE_RELATIONAL_ASSERTION` |
| 2 | `RESTART_STATE` | First handler sees `0<CX<8000h`, SI=DI=`0100h+(8000h-CX)`, saved IP equals the REP prefix address, IF is set and DF is clear. | `CPU_ARCHITECTURAL_REQUIREMENT` |
| 3 | `FINAL_INTEGRITY` | After IRET and REP completion, CX=0, SI=DI=`8100h`, every destination byte matches its source, checksums match the pattern value `c000h`, and both canaries survive. | `CPU_ARCHITECTURAL_REQUIREMENT` |

Source programming, service/CPU acceptance, and completion have separate
fields and phases. The PIC IRR transition while the REP is running cannot be
sampled independently by the guest without itself interrupting REP; the ISR
bit and handler evidence establish publication by the time of acceptance.
The guest result is authoritative for the accepted propositions. GDB's
read-only byte comparison is an independent qualification cross-check.

Intel's [System Programming Guide, volume 3A, section 8.2.4.1](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-3a-part-1-manual.pdf)
states the precise REP interruption rule: indices address the next element,
the saved instruction pointer denotes the string instruction, and the count
reflects completed iterations. The historical [Intel 80286 programmer
reference, printed page 8-93](https://bitsavers.org/components/intel/80286/210498-005_80286_and_80287_Programmers_Reference_Manual_1987.pdf)
is identified in the source audit. N2 applies only those register/restart
requirements to this real-mode i286 test. It does not assert an exact
interrupt iteration or PIT tick count.

## Machine-readable result

The `N2RP` v1 block is 256 bytes at physical `0x29000`. Header offsets are:
magic 0..3, version 4, size 6, record count 8, completed 10, passed 12,
failed 14, first failed ID 16, record size 18. Three 32-byte records begin
at 32, 64 and 96. Each begins with ID, authority class (1 CPU, 2 backend/
device), status (1 pass, 2 fail), then little-endian 16-bit observations at
offsets 4, 6, and so on. Their ordered fields are:

- ID1: PIT reload, pre-REP IRR, IRQ count, ISR entry, ISR after EOI,
  first-handler phase, final phase.
- ID2: initial CX, first-handler CX/SI/DI, saved IP, REP IP, saved FLAGS,
  IRQ count, initial SI/DI.
- ID3: final CX/SI/DI, source/destination sums, first mismatch offset
  (`ffffh` if none), before/after canaries, IRQ count.

CRC32/ISO-HDLC of bytes 0..247 is at 248..251. State at 252 is written
last: 1 running, 2 pass, 3 fail. The validator checks the full contract,
per-record propositions, aggregates and terminal consistency. Negative tests
modify valid synthetic records and recompute CRC to prove the semantic checks
also reject impossible progress, data mismatch and wrong restart IP.

## Scope and authority limits

Source `i286c/i286c_rp.c` has a budget/rewind boundary in REP MOVSB; the local
IA-32 `i386c/ia32/cpu.c` uses a distinct continuation path. The historical
source audit `1a228cf01713ac4608a1fe512bc89546759bca8d` covers 576
host-only REP cases and shows that atomic INS/OUTS and conditional-string
handlers can overrun a CPU budget. Neither that audit nor NP2TEST's short
four-byte/two-word MOVS test establishes a safe repeated-I/O endpoint.
The audit's coverage matrix explicitly leaves the safe port model open.
Actual IDE data ports involve media/controller state and are not a harmless
loopback. **REP INS/OUTS is deferred** (`SAFE_IO_AUTHORITY_REQUIRED`); N2
issues no arbitrary or synthetic I/O port transaction.

The guest cannot observe `CPU_REMCLOCK`, the number of internal yields, or
scheduler overshoot. These are `HOST_DIAGNOSTIC_ONLY` / future Phase A/B
instrumentation questions. N2 records architectural progress, not a numeric
internal budget claim. No exact physical PC-98 PIT timing or masked-request
persistence is claimed. The selected PIT reload is accepted only if the
result actually shows a mid-REP interrupt.

## Provenance and licenses

| N2 material | Provenance | License |
| --- | --- | --- |
| `src/ipl.asm` | Byte-identical to `esp-np2kai` commit `3944218b948d94b426aaebb93e0401739a0f9aab`, `tests/guest/np2video-gdc/src/ipl.asm`; carried through N1 | BSD-2-Clause, adjacent notice |
| CRC32 routine in `src/stage2.asm` | `esp-np2kai` same commit, `tests/guest/np2kbdtest/src/ipl.asm:crc32`; adapted through N1 | BSD-2-Clause, adjacent notice |
| Other N2 guest/host logic, metadata, documentation | New project-original content | MIT under repository `LICENSE` |

The BSD2 IPL retains its old `NP2V` loader-state block at `0x2A000`; N2's
separate `N2RP` block is authoritative. No source-knowledge repository files,
proprietary guest data or emulator product source are included.
