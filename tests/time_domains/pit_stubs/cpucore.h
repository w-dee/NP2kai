/* SPDX-License-Identifier: MIT */
#pragma once
extern UINT32 test_committed;
extern SINT32 test_slice,test_remaining;
extern int test_ei;
extern unsigned test_accepted;
#define CPU_CLOCK test_committed
#define CPU_BASECLOCK test_slice
#define CPU_REMCLOCK test_remaining
#define CPU_isEI (test_ei)
#define CPU_isDI (!test_ei)
#define CPU_INTERRUPT(v,s) ((void)(v),(void)(s),++test_accepted)
