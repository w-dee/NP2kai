# N1: standalone i286 PIT/PIC/interrupt IPL fixture

N1 is the canonical IPL timing semantics fixture. It boots a raw PC-98 2HD
floppy with no DOS or proprietary guest operating system. A passing run means
the current stock SDL2/i286 emulator accepted the stated N1 regression
assertions. It **does not** establish numerical PIT/PIC equivalence with
physical PC-98 hardware.

## Build and qualify

Requires NASM 2.16.01 (the qualified version), Python 3, and, for the stock
headless run, Xvfb, xdotool, ImageMagick `import`, and GDB. The guest source is
16-bit NASM. No binary floppy image is tracked.

```sh
make -C tests/guest/i286-time-n1 verify
python3 -m unittest tools/guest/test_i286_time_n1.py -v
make -C tests/guest/i286-time-n1 qualify
```

The builder writes `.local/n1-fixture/n1.hdm`. The runner builds a fresh image
at `.local/n1-fixture/qualification/n1.hdm`, checks the stock emulator SHA-256,
starts a private Xvfb, launches that emulator under GDB, pauses only to read
256 bytes of guest RAM, captures the screen, and stores a JSON report plus
Xvfb/emulator/GDB logs. Guest RAM extraction is a diagnostic transport; it
makes no emulator product change. GDB may briefly perturb wall-clock timing,
so `elapsed_s` is diagnostic only. It does not participate in guest assertions.
The runner needs the already established local BIOS/font ROM configuration at
`.local/oracle/xdg/sdlnp2kai/`; those local ROMs are not published with N1.
The existing DOS oracle and its pristine floppy are not used or changed.

The image uses 77 cylinders, 2 heads, 8 sectors/track, 1024 bytes/sector
(1,261,568 bytes). The BSD2 IPL occupies the first 1024 bytes and reads a
versioned `ST2V` payload from sector 2 into `2000:0000`, then enters
`2000:0008`. The stage2 runs with a private stack at `2800:1000`, installs
IRQ0 vector 08h, and publishes the N1 result at physical `0x29000`.
`reference.json` pins the exact image and stage hashes for the qualified
NASM version. Rebuilding in two independent directories must produce equal
bytes and that reference SHA-256.

## Result protocol

`N1TM` version 1 occupies 256 bytes at physical `0x29000`. Header fields are
little-endian: magic 0..3, version 4, size 6, six-record count 8, completed
10, passed 12, failed 14, first failed ID 16, record size 18. Six records
start at 32, each 24 bytes. Within a record: ID 0, authority class 1
(1 CPU architectural, 2 device relational/legacy regression), status 2
(1 pass, 2 fail), phase 3, count before 4, count after 6, observation/handler
count 8, post marker 10, saved return IP 14, handler marker 16, entry SP 18,
IRR 20, ISR on handler entry 21, ISR after EOI 22, PIC mask 23.
CRC32/ISO-HDLC over bytes 0..247 is at 248..251. Terminal state at 252 is
written last: 2 pass, 3 fail. The validator rejects malformed headers, CRC,
aggregate counts, case identity, sequence markers, or terminal state.

| ID | Name | Accepted proposition and classification |
| --- | --- | --- |
| 1 | `PIT_COUNT_LATCH` | Mode-0 channel-0 live and latched counts are nonzero and the later latch is lower. `DEVICE_RELATIONAL_ASSERTION`; exact count/frequency is measured only. |
| 2 | `PIC_MASK` | With IRQ0 masked, PIC IRR bit 0 is observed while the handler count remains zero. `LEGACY_EMULATOR_REGRESSION`; masked-request persistence on hardware remains open. |
| 3 | `PIT_IRQ_EOI` | After unmask/rearm, IRQ0 is pending with IF=0, a handler runs after STI, ISR bit 0 is set on entry and clear after EOI. `DEVICE_RELATIONAL_ASSERTION` on this emulator. |
| 4 | `HLT_WAKE` | No IRQ0 request is pending before `STI; HLT`; the handler saved IP is immediately after HLT; the pre-HLT marker is seen in the handler and post-HLT code runs. `LEGACY_EMULATOR_REGRESSION`. |
| 5 | `STI_SHADOW` | A pre-pending IRQ is accepted only after the instruction following STI; handler sees the changed marker and the saved IP points after that instruction. `ARCHITECTURAL_CPU_ASSERTION`. |
| 6 | `MOV_SS_SHADOW` | A pre-pending IRQ is accepted after `STI; MOV SS,AX; MOV SP,1800h`, at the instruction after MOV SP and with the new stack (`entry SP=17F8h`). `ARCHITECTURAL_CPU_ASSERTION`. |

The fixture uses PIT data/control ports `71h/77h`, master PIC command/mask
ports `00h/02h`, OCW3 `0Ah/0Bh` for IRR/ISR, and EOI `20h`. Those interfaces
are verified against the local stock NP2kai `io/pit.c` and `io/pic.c`. The
second service after case 3 also exercises the EOI path. Cases 2, 3, 5, and 6
poll IRR with IF=0 before CPU acceptance, separating request publication from
handler execution. Case 4 relies on PIT expiry while HLT executes; a failure
to wake is a host timeout, not a guest PASS. Polls have fixed iteration limits.

Intel's [System Programming Guide, volume 3A](https://cdrdv2-public.intel.com/835754/253668-sdm-vol-3a.pdf)
describes interrupt inhibition after STI and MOV SS. The precise PC-98 PIT
input frequency, fractional count behavior, PIC edge/level wiring, masked
request lifetime, and retrigger/lost-tick behavior remain
`HARDWARE_AUTHORITY_REQUIRED`. No numeric timing constant is asserted as a
physical truth.

## Provenance and licenses

| Target material | Source at `esp-np2kai` commit `3944218b948d94b426aaebb93e0401739a0f9aab` | License |
| --- | --- | --- |
| `src/ipl.asm` | `tests/guest/np2video-gdc/src/ipl.asm`, copied unchanged | BSD-2-Clause; see `LICENSE.BSD-2-Clause` |
| CRC32 routine in `src/stage2.asm` | `tests/guest/np2kbdtest/src/ipl.asm:crc32`, adapted to N1 result layout | BSD-2-Clause; see `LICENSE.BSD-2-Clause` |
| Other N1 guest logic, builder, validator, runner, tests, docs | New project-original material | MIT under the repository `LICENSE` |

The IPL's legacy `NP2V` loader-state block at physical `0x2A000` is retained
unchanged for source fidelity. It is not N1's authoritative result. No
excluded source media, guest OS image, or external payload is copied.
