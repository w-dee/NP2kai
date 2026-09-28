# N5 normalized mouse IRQ IPL

Original DOS-free 1024-byte IPL in a 1232 KiB raw floppy. This fixture exercises
real mouse I/O, real PIC, real guest IRQ13 handler/IRET and HLT continuation on
i286 and IA32. It is separate from N1/N2/N3 and does not widen their PASS claims.
See the [normalized owner contract](../../../docs/development/mouse-machine-time.md).

Run with `tools/guest/run_i286_time_mouse.py --binary <fake SDL2 binary>
--output <excluded directory> --backend i286` (or ia32). It requires Linux x86_64,
NASM, GDB, Xvfb and existing local BIOS/font assets under `.local/oracle/pristine`.
The private GDB runner advances only `mouse_fake_now` at guest markers or a
CPU-held service entry. It adds no guest control port. Each run uses isolated
configuration and retains image, binary hash, GDB log, RAM block and service
snapshots. Default multiple=4/base=2457600; both have explicit runner options.

Positive assertions:

- With fake time frozen, the guest executes 8192 loop iterations and no mouse
  IRQ appears. CPU work is not a mouse clock.
- Seven logical IRQ periods with IF=0/masks set produce one pending slave
  IRR bit5 and no guest handler execution.
- After unmask/STI, real CPU acceptance executes one IRQ13 handler. It records
  slave ISR bit5 on entry and its clearing after slave/master EOI.
- While halted, a real owner-service call advances to the eighth deadline and
  publishes the request without changing CPU, ARTIC, GDC, DMA or NEVENT state.
  Normal arbitration then wakes HLT and executes the second handler.
- The guest resumes after HLT and terminates with exactly two handlers for
  eight logical publications.

RAM is 128 bytes at physical 0x29000. Words: +0/+2 signature `N5TM`; +12 step;
+16 loop count; +18/+20 initial/pending slave IRR bytes; +22 pre-accept count;
+24 ISR count; +26/+28 slave ISR before/after EOI bytes; +32 mouse read byte;
+34 HLT continuation marker; +36 final handler count; +126 completion=2.
Completion alone is not PASS: host assertions validate the preceding records
and frozen-state snapshots. Byte fields are stored into a zero-initialized block.

Authority is `OWNER_APPROVED_NORMALIZED_PROFILE` and
`DEVICE_RELATIONAL_ASSERTION`. The fixture does not measure physical interrupt
latency, Linux/P4 service latency, host input admission latency or physical
mouse timing. Its byte at +32 is diagnostic, not a standalone movement oracle;
rational movement and input history are qualified by the host real-I/O tests.
