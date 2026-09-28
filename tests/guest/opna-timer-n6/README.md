# N6-T PC-9801-86 timer CPU-observation fixture

Original DOS-free 1232 KiB IPL, assembled with existing NASM. See the
[timer contract](../../../docs/development/opna-timer-machine-time.md) for
admission, mathematical and binding qualification.

`run_opna_timer_n6.py` launches the complete SDL emulator with native PC-9801-86,
IRQ12, CSM off and source-asserted quiescent PCM86. Both i286 and IA-32 are
supported. The debugger writes only the private fake-time source and observes
RAM/device state. Guest code performs real IN/OUT through the dispatcher,
including unchanged CPU wait charges.

The result at physical RAM 0x29000 is 128 bytes. Its signature is `N6OT`, step
is word at +12 and completion is word +126=2. The runner asserts:

* 8192 guest loop iterations complete at frozen time with status unchanged.
* A deadline publishes status and slave IRR bit4 while masked and IF=0;
  ISR count remains zero. Unmasking alone with IF=0 still does not accept it.
* STI permits the first ISR. The handler observes slave ISR bit4 and clears it
  with the existing slave/master EOI path; it also clears the timer flag.
* At HLT, the next fake deadline advances timer/PIC state while the CPU record,
  NEVENT, PCM86, ARTIC, GDC and DMA bytes remain unchanged within timer service.
* Only subsequent CPU opportunity executes the second handler and wakes HLT.

This is a `LEGACY_COMPATIBILITY_ASSERTION` plus CPU-observation separation,
not physical timing or AUDIO PASS. It does not qualify other boards, FMGEN,
CSM, active PCM, synthesis/transport timing or a realtime platform deadline.
