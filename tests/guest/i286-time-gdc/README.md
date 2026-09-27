# N4: standalone GDC scan, status and IRQ fixture

N4 is an original, DOS-free PC-98 IPL for SDL2 i286 and the SDL2 IA-32
interpreter. It programs GDC/PIC ports after its BIOS floppy bootstrap,
publishes 28 structured observations, computes CRC32 in the guest, and halts.
There is no OCR, keyboard driver, screenshot criterion or audio assertion.
No emulator product code or existing fixture is changed.

## What a current success proves

`LEGACY_COMPATIBILITY_PROFILE_CAPTURED` means all of these checks succeeded:

- The guest booted, completed its bounded sequence and published a valid,
  fresh 4096-byte result with terminal state written last.
- All 56 master/slave status bytes in guest RAM match returns from actual
  guest reads of ports `60h` and `A0h`, observed independently through GDB.
- The requested master/slave SYNC geometry was committed in the emulator.
  Its class and clock fields match the selected parent compatibility formula.
- Masked CRT IRQ2 became pending without acceptance, then expired at a later
  display interval. One unmasked IRQ2 was accepted; ISR2 remained active
  through at least two VSync callbacks, with no interrupt backlog.
- Guest specific EOI cleared ISR2. A second CRT IRQ woke `STI; HLT`; the
  handler recorded the expected return IP, CS and saved IF. Its EOI cleared
  ISR2. No host code delivered an interrupt or edited guest/device state.
- Guest CPU work advanced its progress counter by 32768 and advanced the
  actual CPU ledger. The functional FIFO drain check completed.

Boot/publication is an **INTEGRATION_ASSERTION** at the aggregate level.
Each RAM record explicitly carries its assertion category: cases 15–17 are
**ARCHITECTURAL_ASSERTION**, the remaining cases are
**LEGACY_COMPATIBILITY_ASSERTION**. Case 17's CPU-held timing assertion is
**deferred**, as is case 14's huge-gap timing assertion. Case 15/16 currently
proves CPU work only. No record is `HARDWARE_QUALIFIED_ASSERTION`.

Success does **not** prove exact legacy H/V boundary timing, machine-time
independence, rendering suppression, Linux realtime service, drawing duration,
physical Ne2/GD5428 behavior, or audio. `RASTER=1_TIMING_OUT_OF_SCOPE`.
The runner requires RASTER=0, DISPSYNC=1, no HAXM, and no async CPU.
The debugger changes host pacing; legacy observations are not realtime gates.

## Profiles and direct programming

The source authority is the bounded preflight for parent
`134af751728c0a2f85abcf29e45a93ebfb94b21b`, summarized by the development
realtime policy. All geometry below is compatibility profile data.
31 kHz's source constant is **not** a physical-clock claim.

| Class | Master SYNC, hex | Slave SYNC, hex | Cold selection |
|---|---|---|---|
| 15 | `10 4e 07 25 0d 0f c8 94` | `06 26 03 11 86 0f c8 94` | DIP first byte `3f`, port 9A8=0 |
| 24 | `10 4e 07 25 07 07 90 65` | `06 26 03 11 83 07 90 65` | DIP first byte `3e`, port 9A8=0 |
| 31 | `10 4e 4b 0c 03 0b db 95` | `02 4e 4b 0c 83 06 e0 95` | DIP first byte `3e`, port 9A8=1 |

The stock CMake i286 target omits `SUPPORT_CRT31KHZ`; only the IA-32 target
includes it (`CMakeLists.txt`, IA-32 definitions). The runner rejects a
31-class run without the private `gdc_o9a8` handler as
`UNSUPPORTED_GDC_SCAN_CLASS`. Qualification therefore covers 15/24 on both
backends and 31 on IA-32. The guest image itself is CPU-286-compatible.
There is no i286 31-class PASS and no product feature enablement in this slice.

15 kHz needs a cold boot: the parent's class latch comes from the BIOS DIP
setup, and ordinary port 6E changes only its other bit. N4 does not patch that
latch. After bootstrap, all three classes explicitly write SYNC command 0F
and eight parameters, followed by PITCH. No later BIOS display service is
used. Master pitch is 80, slave pitch 40 (15/24) or 80 (31).
Cases 27/28 increment master P4 by one and restore it, with two settling
frames each. The host checks both committed parameter arrays and clock fields.

The RAM geometry bytes mean **requested** geometry, because the guest cannot
read back SYNC registers. `capture.json` supplies independent committed
geometry evidence at every sample. Case 27 has geometry ID `class+100`;
other cases use `class`. Backend, runtime base/multiplier, B_ref, M_ref,
RASTER and committed timing fields are host-owned manifest data.

The two fixed compatibility display identities are B_ref=1996800 and
B_ref=2457600. The reference multiplier M_ref=5 derives the frozen parent
integer conversions only. It is not a physical oscillator or a runtime CPU
multiplier selector. Current legacy runs retain their runtime clock coupling
and require runtime base=B_ref. Future runs cross each fixed display identity
with both runtime bases and M=1/4/20. Historical runtime-dependent observations
are not requirements for the future multiplier-independent implementation.

## HSync and VSync policy

HSync correctness means **known frozen scan phase → one direct status read →
expected bit6**. There is no requirement to observe every natural pulse.
Missing a naturally running pulse is not failure. Bit6 is the parent's
horizontal blank/HSYNC-compatible inequality, not a universally qualified
physical HSYNC waveform.

The legacy run takes finite H samples; their names reserve future positions
and do not assert those positions occurred in legacy execution. Its VSync
waits assist sequencing, while independent callback counts establish the
ISR-spanning-frames case. Status bit5 may include the parent's TURE_SYNC
correction. Exact future expectations do not apply TURE_SYNC a second time.
The polling instruction after IN is MOV, avoiding the recognized SEARCH_SYNC
IN/TEST/branch idiom. Forced CPU budget exit is not a correctness condition.

`future-cases.json` specifies all 28 observation points, the private control
checkpoints, exact rational reference grid, six cold display profiles and
selected expected bits. `gdc_contract.reference_phase` implements the audited
host expectation, not product advancement. For stable geometry, F=D+V:

```
p = Q % F
vsync = p >= D
remaining = F-p if vsync else D-p
bit6 = remaining % R < H
```

Service all deadlines at or before the frontier before observing. This is a
two-segment countdown; horizontal residue may jump at VSync. Selected H points
cover outside, threshold equality, first inside quantum, after exit, and both
sides of a line boundary. V points include D−1/D/D+1 and F; repeated schedules
cover F−1/F/F+1, one/several frames and a trillion-frame gap. The host model may
qualify every transition mathematically; the guest samples selected positions.

## Case inventory

| IDs | Purpose | Current qualification / future obligation |
|---|---|---|
| 1 | Direct setup | Committed SYNC/class/clock observation |
| 2–7 | H phase points | Raw samples now; selected exact phases later |
| 8–11 | V entry/interior/exit | Raw samples now; exact boundaries later |
| 12–13 | One/several frames | Legacy sequencing now; exact elapsed frames later |
| 14 | Huge gap | Timing deferred; later finite state without per-frame loop |
| 15–16 | CPU work | Actual 32768 iterations; later freeze GDC time throughout |
| 17 | CPU held | Timing deferred; later advance GDC time with CPU ledger held |
| 18–19 | Masked IRQ2 | Pending then expired, count stays zero |
| 20–21 | Acceptance/ISR | Count one; ISR spans repeated VSyncs after rearm |
| 22 | Specific EOI | ISR2 clears |
| 23–24 | HLT/EOI | Count two, architectural return evidence, ISR2 clears |
| 25–26 | Command FIFO | Queued PITCH observation then empty check |
| 27–28 | SYNC mutation/restore | Commit identity now; latched deadline/reanchor later |

Busy bit3 on the slave is recorded, with no drawing command or duration claim.
FIFO bits 0–2 are independent of scan bits 5/6. Master/slave raw bytes are
retained. No command engine is granted machine-time authority. PIC records
retain all eight IRR/ISR/IMR bits so a later host composition check can also
inspect IRQ0. N4 requires no PIT0 machine-time source; combined IRQ0/IRQ2
priority and other EOI variants remain separate host/model qualification.
Detailed memory-wait cycle charges also remain host/model follow-up. The
result and trace identify phase, geometry and CPU ledger for that work.

## Two explicit modes and future control seam

1. `LEGACY_GDC_OBSERVATION` (mode 1) runs now. Its positive result is
   `LEGACY_COMPATIBILITY_PROFILE_CAPTURED`.
2. `MACHINE_TIME_GDC_EXPERIMENTAL` (mode 2) is buildable now. The runner always
   fails closed as `NOT_EXECUTABLE_UNTIL_MACHINE_TIME_GDC` until a product fake
   source and qualified adapter exist. It records absence of the proposed
   private symbols `gdc_fake_sample` and `gdc_machine_service`; their presence
   alone is insufficient. There is no fallback to legacy execution.

Both use the same source/protocol; the two modes are compile-time selections.
The mode-2 image is already built by this mission. Its waits emit private RAM
checkpoints instead of natural CPU-derived polling. No guest rewrite is
needed to attach the future time source: extend the **host adapter** only,
then qualify its authority before enabling exact verification.

| RAM token at offset 24 | Future adapter obligation |
|---|---|
| `1001` | Program writes finished; observe commit sequence, retain latched old end |
| `1100` / `1120` | Service the next requested display/VSync phase; frozen CPU wait replacement |
| `1200` / `1204` | Service until pending IRQ2 clears/sets without accepting it |
| `2000+case` | Position/freeze selected time immediately before actual status INs |
| `3002` | Guest masked and armed IRQ2 |
| `3003` | Guest unmasked and armed; normal STI acceptance follows |
| `3004` | Guest rearmed while ISR2 remains active |
| `3005` | Guest is about to STI/HLT; verify actual halt before wake advancement |
| `3010` | Hold CPU, advance only approved fake GDC service, verify ledger unchanged |

An emulator 16-bit RAM write may use separate byte stores. The adapter must
reject transient token values using the expected protocol step and case ID.
Current capture accepts a sample only when token=`2000+current_case`.
Never write result RAM, CPU, GDC or PIC state to make a case pass. Future
controlled time must use a qualified private source and normal device service.
Both ports must see the same frozen time. The existing runner is read-only.

The future inventory includes frozen repeated reads, fractional/partitioned
advances, CPU work with time frozen, CPU held while time advances, exact IRQ2
mask/IRR/ISR/EOI/HLT cases, SYNC latched-deadline checks and a paired run with
presentation entirely suppressed over multiple frames. Drawing suppression
is **not executed now**. None of these deferred rows becomes PASS merely
because legacy observations or the reference model match.

## RAM schema v1

Physical address `30000h`; 4096 bytes; little endian. Stage2 runs at `2000:0`,
stack at `2800:1000`; the result is outside both. Bootstrap reads sectors
using BIOS only, then jumps to original stage2 code.

| Header offset | Type / meaning |
|---|---|
| 0 | four bytes `N4GD` |
| 4, 6, 8, 10 | u16 version=1, size=4096, record_size=80, published_count=28 |
| 12, 14 | u16 mode, class (15/24/31) |
| 16 | 8-byte deterministic fixture build ID |
| 24, 26, 28 | u16 checkpoint, current case, requested geometry ID |
| 30 | u16 guest backend=0 (unknown; host manifest owns identity) |
| 32 | u32 guest CPU progress |
| 36, 38 | u16 IRQ acceptance count, failure code |
| 40 | guard bytes `3c c3 a5 5a` |
| 44 | u16 expected record count=28 |
| 46–127 | reserved zero |

28 records begin at offset 128, stride 80:

| Record offset | Type / meaning |
|---|---|
| 0, 2, 4 | u16 case, sequence, geometry ID |
| 6, 7 | u8 category, observation verdict |
| 8, 10 | u16 flags=7 (master/slave/PIC), sample token |
| 12, 13 | u8 raw master/slave status |
| 14, 15 | u8 expected V/H = FF (host-owned, unknown to guest) |
| 16–19 | u8 decoded master V/H and slave V/H |
| 20–22 | u8 master PIC IRR/ISR/IMR |
| 23–25 | u8 slave busy, master/slave FIFO bits |
| 26, 28, 30 | u16 IRQ count, HLT entry/wake |
| 32 | u32 CPU progress |
| 36, 37 | u8 handler ISR, post-EOI ISR |
| 38, 40, 42, 44 | u16 saved IP, expected wake IP, saved CS, saved FLAGS |
| 46 | u16 wrapping poll count, diagnostic only |
| 48–55, 56–63 | requested master/slave SYNC bytes |
| 64–67 | u8 master/slave command, port9A8 class selector, reserved=0 |
| 68 | u16 specific EOI count |
| 70–71 | reserved zero |
| 72–75 | guard bytes `3c c3 a5 5a` |
| 76–79 | reserved zero |

Bytes 2368–4083 are zero. End guard at 4084. CRC32 at 4088 covers bytes
0–4087 (standard reflected polynomial EDB88320, initial/final XOR FFFFFFFF).
Reserved u16 at 4092 is zero. Terminal u16 at 4094 is written **last**:
1=running, 2=complete, 3=guest failure, 4=bootstrap failure. Failure codes are
1=V wait timeout, 2=IRR wait timeout, 3=acceptance timeout. HLT has a host
90-second timeout, with no extra PIT watchdog. The runner kills its dedicated
process group on failure. Only complete+CRC+positive assertions can qualify.

Category codes: 1 integration, 2 legacy compatibility, 3 architectural,
4 device relational, 5 hardware qualified, 6 inconclusive hardware authority.
Verdict 1 means observed, **not a hardware PASS**; 3 reserves deferred timing
observations (cases 14/17). Even in mode 2 the guest publishes raw evidence;
the future host must separately supply phase expectations and qualification.

## Build, run, verify

Use existing NASM, Python 3, GDB with Python, Xvfb, Linux x86_64 and the existing
debuggable SDL2 interpreter builds. No new dependency installation is needed.
Commands below run from the repository root. Output directories must be new
or empty; stale captures are rejected. ROMs are copied read-only in provenance
from `.local/oracle/pristine/{bios,font}.rom`; only those two files are used.

```sh
python3 tools/guest/build_i286_time_gdc.py --scan-class 24 --mode 1 --output .local/n4-gdc/build/n4-24.hdm
python3 tools/guest/test_gdc_contract.py
python3 -O tools/guest/test_gdc_contract.py

python3 tools/guest/run_i286_time_gdc.py --binary build_phase_d1_i286_off/sdlnp2kai_sdl2 --backend i286 --scan-class 15 --output .local/n4-gdc/example-i286-15
python3 tools/guest/verify_i286_time_gdc.py --backend i286 --scan-class 15 --output .local/n4-gdc/example-i286-15

python3 tools/guest/run_i286_time_gdc.py --binary build_phase_d1_ia32_off/sdlnp21kai_sdl2 --backend ia32 --scan-class 31 --output .local/n4-gdc/example-ia32-31
python3 tools/guest/verify_i286_time_gdc.py --backend ia32 --scan-class 31 --output .local/n4-gdc/example-ia32-31
```

Repeat with `--scan-class 15`, `24`, `31` and `--baseclock 1996800` or
`2457600`; `--multiple 5` is the default normative compatibility capture.
The same class image is used by supported backends and both base families. To prove
reproducibility, build identical options into two paths and compare image
bytes and JSON manifests with `cmp`. All images are 1,261,568 bytes (77×2×8×1024).
No user ROM or other guest content is embedded in generated images.

The deliberate negative command exits nonzero and writes a blocked report:

```sh
python3 tools/guest/build_i286_time_gdc.py --scan-class 24 --mode 2 --output .local/n4-gdc/build/n4-future.hdm
python3 tools/guest/run_i286_time_gdc.py --binary build_phase_d1_i286_off/sdlnp2kai_sdl2 --backend i286 --mode 2 --output .local/n4-gdc/example-future-refused
```

Each successful run writes `report.json`, `result.bin`, `capture.json`, image
and build manifest, source manifest, GDB/Xvfb logs, and isolated configuration.
Hashes cover source, binary, build cache, image, ROM, result and capture.
The offline verifier rebuilds current fixture identity, checks explicit
backend/class/mode, artifact hashes, current source identity, parser semantics
and independent host evidence. Old captures fail after relevant source edits.
Unit-test synthetic blocks are parser inputs only and are never guest evidence.

## License and provenance

`src/ipl.asm` and `src/stage2.asm` are original project-authored N4 code under
[BSD-2-Clause](LICENSE.BSD-2-Clause). Generated fixture image content has the
same source provenance. The bootstrap, CRC routine and port sequence were
written for this fixture; no NEC sample listing, third-party guest binary or
DOS program was imported. Existing project N1/N2/N3 conventions informed the
layout only. Host tools and this Makefile use the project's MIT policy and
carry SPDX identifiers. The parent's existing GDC formulas/port implementation
are the explicit compatibility reference, not physical hardware authority.
