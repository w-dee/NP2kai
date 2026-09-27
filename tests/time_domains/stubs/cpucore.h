/* SPDX-License-Identifier: MIT */
extern UINT32 test_committed;
extern SINT32 test_slice, test_remaining;
#define CPU_CLOCK test_committed
#define CPU_BASECLOCK test_slice
#define CPU_REMCLOCK test_remaining
