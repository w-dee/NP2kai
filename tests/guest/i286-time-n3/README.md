# N3: direct PC-98 FDC/DMA known-data IPL fixture

N3 qualifies two direct uPD765A-model READ DATA commands through PC-98 DMA2,
PIC IRQ11 and CPU acceptance on the stock SDL2/i286 build. All 1024 bytes of
each sector are compared in the guest and independently in the host. A PASS
is a **legacy emulator regression** with device relational assertions. It is
not physical PC-98 timing qualification. N1 and N2 are unchanged.

## Build and run

Qualified assembler: NASM 2.16.01. Python 3 and the established local Xvfb,
xdotool, ImageMagick `import`, GDB and stock i286 environment are used.

```sh
make -C tests/guest/i286-time-n3 verify
make -C tests/guest/i286-time-n3 test
make -C tests/guest/i286-time-n3 reproducibility-check
make -C tests/guest/i286-time-n3 qualify
```

The source-only fixture builds without guest OS or proprietary blobs. The
unmodified N1 IPL is shared by path and uses BIOS INT 1Bh only to bootstrap
stage2 from sectors 2 onward. **No BIOS disk service is called by stage2 or
used for either N3 transfer verdict.** Stage2 uses INT 18h for initial text
setup, then takes ownership of FDC, DMA2, IRQ11 and its own RAM. Running stock
NP2kai uses the existing local BIOS/font ROM configuration; those ROMs are
not part of the published fixture. No DOS filesystem or utility is used.

The builder assembles in a fresh temporary directory, checks header, bounds
and non-overlap, and writes a raw image. `reference.json` pins the NASM
version and image/IPL/stage2/payload hashes. The reproducibility target
builds twice independently, checks both references and compares every byte.
The qualification runner builds a fresh image, verifies the stock executable
SHA-256 `a7e2e22ec3b2fede5885d1317d2c1cd754fd8139ac9794f0d6eeea1221af4fd6`,
starts private Xvfb, and runs GDB in asynchronous MI mode. Only read-only RAM
extraction is used; emulator product sources and the DOS oracle are untouched.

Evidence is stored at `.local/n3-fixture/qualification/`: `n3.hdm`,
`result.bin`, `report.json`, `buffer-s7.bin`, `buffer-s8.bin`, `screen.png`,
`emulator.log`, `xvfb.log`, `gdb-mi.log`. A runtime exception produces
`failure.json`; old result/report/screen files are removed before launching.
GDB polling is bounded to 25 samples, each GDB command also has a timeout,
and the owned processes are cleaned up. Completion is recognized from the
terminal record and validated assertions, never from a fixed sleep. Host
elapsed seconds and GDB pauses are diagnostic only.

## Image and memory layout

Geometry is 77 cylinders x 2 heads x 8 sectors x 1024 bytes = 1,261,568 bytes.
Both reads use drive 0, C=0, H=0, N=3, length 1024; R is 7 then 8.

| Disk region | Byte placement | Meaning |
| --- | --- | --- |
| IPL | 0..1023, C0/H0/S1 | Shared BSD2 1024-byte loader |
| Stage2 | starts 1024, currently four sectors S2..S5 | Guest code and embedded expected-data bytes |
| Spare/padding | after stage2 through byte 6143 | Zero; stage2 must fit S2..S6 |
| Data 7 | 6144..7167, C0/H0/S7 | First known sector |
| Data 8 | 7168..8191, C0/H0/S8 | Distinct follow-up sector |
| Remainder | 8192..end | Zero; no disk result/output area |

The builder rejects stage2 longer than 5120 bytes, so the direct-read targets
cannot overlap its loader sectors. It checks these RAM regions separately:
IPL `1FC00h..1FFFFh`, stage2 reserve `20000h..27FFFh`, stack
`28000h..28FFFh`, result `29000h..290FFh`, inherited loader status
`2A000h..2A01Fh`, DMA buffer/canaries `400FFh..40500h` and
`408FFh..40D00h`. The two destinations are `40100h` and `40900h`.

Payload generation is project-original: byte i is
`((i*73) ^ ((i>>8)*29) ^ (sector*17)) & 255`, then the first 12 bytes are
packed little-endian as `<4sBBBBHH`: `N3FD`, version 1, C=0, H=0,
R=sector, length 1024, and `sector ^ A55Ah`. Sector CRC32 values are
`B7F50855h` and `77EC1D36h`. The concatenated payload SHA-256 is
`4616f4298b080633a415352f5ce1374b35b74e176697e957c74e198946f2e8b4`.
The guest contains expected bytes generated from the same contract, computes
CRC over them independently, and exact-compares its DMA destination. The host
regenerates both patterns and exact-compares extracted buffers.

## Controller and DMA contract

The authoritative local implementation is target commit
`9e7d61bfbbf23398672120c21cf4be176ccf5449`, principally `io/fdc.c`,
`io/dmac.c`, `io/pic.c`, `mem/dmax86.c`, and `i286c/i286c.c`.

| Interface | Programming and observation |
| --- | --- |
| FDC type | `io/fdc.c` identifies a uPD765A model |
| PC-98 mode | `BEh=03h`: 2HD and 90h port group; DMA2 and IRQ11 |
| FDC ports | status 90h, command/result 92h, control 94h |
| Setup | 94h gets 80h then 18h: reset with bit3 clear, then DMA/motor setup; avoids the model's reset-IRQ scheduling path |
| SPECIFY | `03 DF 02`, ND=0; timing fields are configuration, not latency assertions |
| Drive check | `04 00` SENSE DRIVE STATUS; ready bit checked, track0 inherited from ordinary boot/loader |
| Read command | `46 00 00 00 R 03 08 1B FF`: MFM READ DATA, drive0/head0, EOT8 |
| Handshake | RQM/DIO=80h before every command byte; C0h before each result byte |
| DMA channel | 2, peripheral-to-memory incrementing single transfer, mode 46h at 17h |
| DMA registers | mask 15h (06h/02h), byte flip-flop clear 19h, address 09h, count 0Bh, page 23h=04h |
| Count | initial 03FFh (1024-1), final FFFFh; final address initial+0400h |
| TC | status 11h bit2, read clears TC low bits; recorded before/after read |
| PIC | master ports 00h/02h; slave 08h/0Ah; masks 7Fh/F7h; cascade master IRQ7 |
| CPU vector | slave base10h+3 = 13h; only IRQ11 vector installed |
| EOI | slave then master, command20h; ISR bit3/bit7 observed then cleared |

The NEC [uPD765A/uPD765B datasheet](https://hxc2001.com/download/datasheet/floppy/thirdparty/FDC/NEC/UPD765_Datasheet_OCRed.pdf)
provides the READ DATA command/result structure and DMA DRQ/DACK/TC signal
meaning (pin functions and instruction-set tables). PC-98 port wiring and
this model's completion behavior are checked against local source rather
than inferred from PC/AT register addresses.

In the stock generic path, FDC sets channel `ready`; `dmac_check` selects
work; `i286c` calls `dmax86` after CPU instruction opportunities. At count
zero the latter publishes TC before consuming the final byte, decrements
to FFFFh, and completes the byte/address update. FDC consumes TC and enters
its seven-byte result phase; an event then publishes IRQ11. There is no
guest-readable DRQ/DACK pin trace: their operation is inferred from this
source chain plus register/data/completion observations, not measured as
physical bus signals. N3 deliberately polls while IF=0 to provide legacy DMA
opportunities; it does not claim DMA can progress autonomously during HLT.

## Cases and causal evidence

| Stable ID | Name | Required evidence |
| --- | --- | --- |
| 1 | `DIRECT_READ_S7` | Direct command, DMA setup/progression, TC/read-clear, result phase, pending IRQ11, handler/PIC/EOI, sector7 CRC and exact data |
| 2 | `FOLLOWUP_READ_S8` | Same chain on a different destination and distinct sector after first result drain/EOI; verifies path reuse |

Both records carry authority class 2 (`LEGACY_EMULATOR_REGRESSION`), with
`DEVICE_RELATIONAL_ASSERTION` comparisons for count/address/data and IRQ.
Each buffer starts as the bitwise complement of the expected sector: no byte
can accidentally match before DMA. Canaries surround it. The guest records
initial address/count/status/IRR, issues nine command bytes, and polls TC and
IRQ with IF=0. An IRQ observed during the TC poll triggers an immediate DMA
snapshot; it is accepted only if TC and the coherent completed address/count
are observable. This is a sampled ordering check, not per-cycle pin tracing.
The regular path also captures address/count at TC and again in the handler.

While the IRQ is pending, exact comparison and CRC run before STI allows CPU
acceptance. The handler must see phase3, slave ISR08h, master ISR80h and
completed DMA registers. EOI clears the service bits, then seven FDC result
bytes are drained and status must return to 80h. The second transfer repeats
without a controller reset, and handler count must progress 0->1->2.

FDC result bytes are expected to be `00 00 00 00 00 01 03`. In particular,
R=1 is pinned **legacy model behavior** from `fdc_dataread`'s TC path, not a
claim about real-controller CHRN at a sector boundary. The fixture checks
initialization/reset and reuse but does not qualify recovery from arbitrary
controller errors. Any failure records its last phase and ends in a permanent
result screen with CLI/HLT; DMA2 is masked. Full machine-state restoration is
not needed in this exclusive IPL context.

Every command/result-byte poll has at most 65535 iterations. TC and pending
IRQ polls each have at most 16*65535 iterations. A watchdog expiry records
FAIL. Exact motor spin-up/head timing, rotational latency, transfer cadence,
DMA arbitration, TC edge positioning, interrupt edge/level wiring and
real-hardware reset handling remain `HARDWARE_AUTHORITY_REQUIRED`. No physical
microsecond constant, hardware equivalence or internal scheduler debt is a
PASS condition.

## Result and negative validation

`N3FD` result v1 occupies 256 bytes at physical 29000h. It shares N1's header
shape: magic 0..3; u16 version/size/count/completed/passed/failed/first-failed/
record-size at offsets 4/6/8/10/12/14/16/18. Two 96-byte records start at
32 and 128. `tools/guest/n3_contract.py:FIELDS` maps every field and size;
raw ST0/ST1/ST2/C/H/R/N occupy record offsets32..38. The unused bytes are zero.
CRC32/ISO-HDLC covers bytes0..247 and is stored at248..251. Terminal state at
252 is written last (2 PASS, 3 FAIL); 1 denotes running.

Record phases: 1 setup/poison, 2 command/DMA wait, 3 data checked/pending IRQ
acceptance, 4 drained result and final validation. The validator checks
requested CHS/length, both CRCs against regenerated data, exact comparison,
poison, DMA progress, TC, pending/accepted IRQ, PIC/EOI, FDC result, canaries,
record status, aggregates and terminal consistency. Synthetic negative tests
recompute CRC when altering semantics; a separate test corrupts the CRC.
Builder tests reject overlap, malformed image and corrupted known data.

## Reuse research and provenance

Source knowledge checkout remains at
`3944218b948d94b426aaebb93e0401739a0f9aab`. Current and all-ref history
inspection found the following useful evidence; hardware qualification is
not inferred from the earlier host-only smoke result.

| Material | Exact source commit/path | Use/license |
| --- | --- | --- |
| Shared IPL | source `3944218b948d94b426aaebb93e0401739a0f9aab:tests/guest/np2video-gdc/src/ipl.asm`; target N1 copy at parent `9e7d61bfbbf23398672120c21cf4be176ccf5449` | Shared unchanged; BSD-2-Clause notice included |
| CRC32 | source same commit `tests/guest/np2kbdtest/src/ipl.asm:crc32`, via target N1 | Adapted to return CRC for arbitrary ES:SI range; BSD-2-Clause |
| N1/N2 host tools | target parent `9e7d61bfbbf23398672120c21cf4be176ccf5449:tools/guest/{build,run}_i286_time_n1.py` and `run_i286_time_n2.py` | Import stable helpers; adapt runner; MIT |
| A86P pattern/build/validator | source HEAD `tools/guest/build_a86smoke.py:make_probe`, `verify_a86smoke.py`; introduced at `3de334a54a693cef9baab40848c8afd5c251a1ff` | Design reference only; N3 data is newly generated |
| Audio86 probe | same source HEAD `tests/guest/a86smoke/src/stage2.asm:disk_probe`, `host/tests/run_a86smoke.py` | BIOS INT1Bh probe, not direct FDC qualification; host reports physical_claims=none |
| Historical storage audit | `daf86ebba9088b0fb86b04bbbaff7a00a15fdf7a:docs/development/cross-project-bios/storage.md` | Describes direct FDC/IRQ11/DMA2 and BIOS/PIO differences; no external BIOS code copied |

N3 guest logic, sector algorithm, build/validation/tests/docs are new MIT
project material under the repository LICENSE. Preserve the BSD2 notice for
shared loader and CRC when redistributing generated images. No external BIOS
code, proprietary media, or third-party-local-only payload is copied.
