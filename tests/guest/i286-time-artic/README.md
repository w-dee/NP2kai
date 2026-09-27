# i286 ARTIC IPL fixture

Original DOS-free 16-bit fixture for the experimental ARTIC counter. This is
not N4. Guest assembly is BSD-2-Clause; host tools are MIT. The generated raw
floppy contains only this assembly and zero padding, with no DOS or proprietary
OS. Emulator boot qualification separately requires owner-local BIOS/font ROMs;
these are neither distributed nor copied into the image.

Read [ARTIC implementation](../../../docs/development/artic-machine-time.md),
[realtime policy](../../../docs/development/multiplierless-realtime-policy.md)
and [oracle semantics](../../../docs/development/guest-oracles.md).

## Build and run

Requires NASM, Python 3, GDB, Xvfb and the configured SDL2 interpreter binary.
The private runner currently uses the Linux x86_64 host calling convention;
the guest can run on both i286 and IA-32 backends. Qualification needs debug
symbols. Local ROM inputs are `.local/oracle/pristine/bios.rom` and `font.rom`.

```sh
python3 tools/guest/build_i286_time_artic.py --output .local/artic/artic.hdm --mode 2
python3 tools/guest/test_i286_time_artic.py
python3 tools/guest/run_i286_time_artic.py \
  --binary build_phase_c_i286_fake/sdlnp2kai_sdl2 \
  --output .local/artic/i286-fake --backend i286 --mode 2 \
  --multiple 4 --baseclock 2457600
```

For IA-32 use `--backend ia32` and its `sdlnp21kai_sdl2` binary. Use an
experimental build with both `NP2_ARTIC_MACHINE_TIME` and `NP2_ARTIC_FAKE_TIME`
ON for mode 2. Mode 1 requires an OFF build. The runner rejects a mismatched
source/mode; live binaries are not canonical fixture inputs. Output directories
hold the image, configuration, GDB script/log, per-read evidence, raw RAM and
JSON report. Use a separate output directory for each qualification run.

Modes:

| Value | Name | Completion interpretation |
| --- | --- | --- |
| 1 | `LEGACY_ARTIC_MODE` | `LEGACY_OBSERVATIONS_COMPLETE`: records legacy values without hardware-model comparison. |
| 2 | `MACHINE_TIME_ARTIC_EXPERIMENTAL_MODE` | `PASS`: every fake-time expected word matches and host checks pass. |

The deterministic image is 1,261,568 bytes (77 cylinders × 2 heads × 8 sectors
× 1,024 bytes). The single boot sector is 1,024 bytes, with 55 AA signatures
at offsets 510 and 1022; execution starts in its second half. No second-stage
BIOS loading is needed. NASM 2.16.01 mode-2 image SHA-256:
`d5fd909392b997898ec0755988cce7577639062441d92d426d882465aa9db1cf`.
The build test compares two independently generated complete images.

## Result format v1

Result address `0x29000`, length 544; all words little-endian. Guest initializes
the block, executes twenty observations, calculates checksum and writes terminal
state last. Each observation includes an 8,192-iteration CPU work loop followed
by an actual aligned word IN from 005Ch or 005Eh.

| Byte offset | Field |
| --- | --- |
| 0 | Four bytes `ARTC` |
| 4 | Version = 1 |
| 6 | Length = 544 |
| 8 | Mode = 1 or 2 |
| 10 | Record count = 20 |
| 12 | Target class = 1 (`SYNTHETIC_EMULATOR_ARTIC_MODEL`) |
| 14 | Observed BIOS byte at physical 045Bh, zero-extended; never modified |
| 16 | Failure count |
| 18–31 | Reserved zero |
| 32–511 | Twenty records, each 24 bytes |
| 512–537 | Reserved zero |
| 538 | Guard = A55Ah |
| 540 | Sum of the first 270 words modulo 65,536 |
| 542 | Terminal: 0 unfinished, 2 complete, 3 failed; written last |

Each record has twelve words: case ID, sequence/sample ID (1–20), word port,
raw observed slice, expected slice, CPU progress marker (=8192), verdict
(1=experimental match, 2=legacy observation, 0=failed), then five reserved zeros.
The sequence references the exact private schedule in `tools/guest/artic_contract.py`;
that module uses arbitrary-width absolute-time arithmetic as the reference.
`parameters.json` and `reads.json` preserve full ns/valid values, expected full
phase/fraction, accepted full state, rejection count and CPU progress evidence.
The result validator requires complete length, header, target class, guard,
checksum, ordered records, exact expectations, verdict and terminal success.
Tests reject truncation, checksum damage and wrong data even with a recomputed
checksum. Mode 1 cannot produce a hardware-model PASS.

## Assertions and exact coverage

Hardware-derived aligned-word assertions qualify the implementation against
the bounded NEC model (`HARDWARE_QUALIFIED_ASSERTION` for the model only).
They do not establish physical-machine capability. Arithmetic/isolation tests
also establish the explicitly stated internal implementation properties.

| ID | Assertion and evidence |
| --- | --- |
| F01 | 1 s = 307,200 ticks: host rational reference and guest samples 6–7. |
| F02 | Unchanged source preserves phase/fraction: host tests; guest repeated 1 s reads. |
| F03 | +5 ms = +1,536 ticks: host and guest sample 4. |
| F04 | +20 ms = +6,144 ticks: host and guest sample 5 after sample 4. |
| F05 | 3,255 ns → 0 tick; 3,256 ns → 1 tick, exact remainder: host and guest samples 2–3 with private state evidence. |
| F06 | Modulo-24 single wrap: samples 13–14 at 54,613,333,334 ns. |
| F07 | Multiple wraps: samples 15–16 at 200 s; host also covers UINT64_MAX ns. |
| F08 | CPU ledger advances with frozen fake time: samples 6–8, guest work markers and host CPU-ledger comparison; phase remains fixed. |
| F09 | +20 ms with frozen CPU ledger: sample 9, handler-entry/exit CPU/PIT/PIC/GDC/DMA snapshots; +6,144 ticks. Also actual-handler host test with frozen entire CPU ledger. |
| F10 | Multiplier independence: both backend guest matrices at 1/4/20; host binding tests change multiplier while retaining state. Record 10 alone does not establish a transition. |
| F11 | Base/mode independence: guest matrix at 1,996,800/2,457,600 base clocks; host binding transitions paired legacy mode. No separate record is required. |
| F12 | Low aligned word is bits 0–15: all 005Ch reads and actual binding test. |
| F13 | Upper aligned word is bits 8–23: 005Eh reads. |
| F14 | Rollover-adjacent independent reads: samples 11–14. No atomic snapshot claim. |
| F15 | Partition invariance including fraction: host compares 10,000 irregular partitions with one interval. Guest sample 20 checks retained fractional progress only. |
| F16 | Invalid/backward rejection without CPU fallback: samples 17–18, unchanged phase/fraction and two rejections; host additionally checks anchor and saturation. |
| F17 | `LEGACY_REGRESSION_ASSERTION`: actual-handler tests preserve byte/odd aliases and OUT005F extra 20-cycle debit. Guest sample 19 adds OUT005F before a frozen-source read. |

F17 mappings and reset-to-zero are compatibility policies, not physical
hardware claims. The save/load rejection tests are separate host tests of the
production APIs. The IPL does not redefine save format or final lifecycle rules.

The private runner starts the executable before setting address breakpoints
(to account for PIE relocation), waits for the guest magic, and stops at actual
`artic_r16` entry. It changes only the private fake source, then executes the
real handler. A finish breakpoint checks the actual returned word and full
phase/fraction and captures state before/after. After twenty reads, a hardware
watchpoint waits for the guest's final RAM store, preventing a BIOS memory test
from being mistaken for completion. The runner never injects expected results
into guest RAM. The guest independently compares its actual reads with the
expected table and publishes its checksum and terminal state.

## Qualification boundary

Initial matrix: both guest backends × both base clocks × multipliers 1/4/20,
twelve experimental semantic PASS runs; one legacy observation run per backend.
All twenty reads in each experimental run must match. No instruction timing,
Linux scheduling interval or screenshot is the canonical timer reference.

`SYNTHETIC_EMULATOR_ARTIC_MODEL` is distinct from
`PHYSICAL_ARTIC_CAPABILITY_CONFIRMED`. The fixture does not manufacture BIOS
flags or assert that this emulator's VM/VX configuration proves physical ARTIC
availability. It does not assert byte/odd-word physical semantics, cross-port
atomicity, hidden latch behavior, physical reset phase, power-state oscillator
behavior, other-device timing, audio, or live realtime deadlines.

Fake-time debugger control is canonical for these deterministic assertions.
It cannot qualify live Linux timing. Live integration, especially debugger-
stopped runs, remains supporting/`INCONCLUSIVE_REALTIME_SEMANTICS`; no numeric
Linux service envelope or catch-up/freeze/clamp policy is selected here.
