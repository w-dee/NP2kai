# Tier1 normalized deadlines and DMA opportunity fixtures

This is a new qualification namespace. Read the
[guest-oracle contract](../../../docs/development/guest-oracles.md) and
[Tier1 profile](../../../docs/development/tier1-machine-time.md).

`tools/guest/run_tier1_qualification.py` runs actual Linux SDL2 i286 or IA32
executables under private GDB/Xvfb, with isolated configuration and existing
local ROM assets. It accepts `--case n3` or `--case dma-hlt`. `--off` is for
N3 legacy regression only. It retains binary hashes, guest RAM, debugger logs
and result JSON. A watchdog timeout or an incomplete assertion sequence is
failure, not evidence about device timing. Debugger time has no realtime claim.

## N3 assertion reuse

The N3 case builds the unchanged image and uses the unchanged reference hashes,
`verify_i286_time_n3.verify_result`, and independent known-sector payloads. Its
positive assertions remain two direct READ DATA transfers, both1024-byte exact
buffers/CRC, address/count/TC/read-clear, legacy result bytes, pending IRQ11,
real guest handler/PIC ISR/EOI and reuse. The ordinary legacy N3 runner and its
pinned binary are unchanged. New IA32 runs are an explicit reuse of that same
data/assertion contract, not a retrospective extension of historical i286 PASS.

ON runs advance only the private fake source to each newly armed FDC IRQ
deadline at a debugger boundary. The CPU subsequently executes the real owner
service. This supplies deterministic time; it does not measure disk speed,
rotational latency or DMA throughput. Actual512/B boundary correctness is
independently checked in the host real-body suite. OFF runs use normal legacy
scheduling without fake-time injection.

## DMA CPU-work / held-owner / HLT distinction

The original `dma-hlt.asm` IPL masks interrupts and supplies three phases:

1. At the first guest marker, the debugger makes actual DMA channel2 ready for
   a64-byte transfer to42000h, using the existing `dma_dummyin/out/proc` endpoints.
   It requests the same CPU-budget yield as real `dmac_check` readiness. The
   guest executes128 loop iterations, reading the first and last destination
   bytes. At least one read must observe a **partially transferred interval**;
   final address/count must show64 bytes. This rules out whole-sector/whole-
   buffer instantaneous substitution in the tested CPU-memory interleaving.
2. Once the guest reaches CLI/HLT, the debugger supplies a fresh four-byte DMA
   readiness state and advances fake time during an actual `tier1_service`
   invocation. CPU core and DMA snapshots before/after that service must be
   identical. No CPU/bus opportunity means no DMA progress.
3. The backend resumes its normal owner loop while the guest remains halted.
   Actual `dmax86` entries are counted; each must advance one byte/address and
   four opportunities must complete four bytes with FFFF count and TC. Both
   inspected interpreters provide these HLT opportunities. This is a bounded
   backend compatibility property, not an assumed universal meaning of HLT.

The endpoint readiness injection is a fixture setup, not a guest hardware port
or a device timer. The host suite separately exercises actual channel order,
END/TC-before-final-byte callback ordering, decrement mode and memory effects.
This fixture does not claim physical DMA arbitration/bus timing, independent
DMA pacing, CPU interrupt latency or physical HLT behavior. DMA/CPU product
implementations are not altered for the fixture.

The keyboard's real register/control/PIC ordering, per-source edge history and
reset-signal semantics are qualified by the host suite on both compile profiles;
this IPL is not an IRQ1 handler oracle or a complete keyboard-mapping test.
