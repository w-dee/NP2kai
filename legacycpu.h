/* SPDX-License-Identifier: MIT */
#ifndef NP2_LEGACYCPU_H
#define NP2_LEGACYCPU_H
#include <legacytime.h>

/* Bind to the selected cpucore.h ledger; no extra state or ownership thread.
 * Backend instruction charging/HLT/REP remains backend-owned. NEVENT owns
 * slice commit/rebase. Device reads observe only; they do not dispatch events.
 * This adapter is the seam for a later NON-authoritative shadow observer. */
#define legacy_cpu_device_now() \
    legacy_cycles_now(CPU_CLOCK, CPU_BASECLOCK, CPU_REMCLOCK)
#define legacy_cpu_committed_cycles() (CPU_CLOCK)
#define legacy_cpu_slice_elapsed() \
    legacy_slice_elapsed(CPU_BASECLOCK, CPU_REMCLOCK)
#define legacy_cpu_slice_budget() (CPU_BASECLOCK)
#define legacy_cpu_remaining() (CPU_REMCLOCK)
#define legacy_cpu_begin_slice(deadline) \
    legacy_budget_begin(&CPU_BASECLOCK, &CPU_REMCLOCK, (deadline))
#define legacy_cpu_continue_slice(deadline) \
    legacy_budget_continue(&CPU_BASECLOCK, &CPU_REMCLOCK, (deadline))
/* Keep paired lvalue debits visible to the optimizer; evaluate reduction once. */
#define legacy_cpu_rebase_slice(reduction) \
    do { \
        SINT32 legacy_reduction_ = (reduction); \
        CPU_BASECLOCK -= legacy_reduction_; \
        CPU_REMCLOCK -= legacy_reduction_; \
    } while (0)
#define legacy_cpu_forceexit() \
    legacy_budget_forceexit(&CPU_BASECLOCK, &CPU_REMCLOCK)
#define legacy_cpu_commit_slice() (CPU_CLOCK += CPU_BASECLOCK)

/* External storage/HLE/I/O/memory costs in legacy CPU cycles. A macro keeps
 * the ORIGINAL operand promotions (including UINT and size_t), evaluates the
 * charge once, permits negative remaining budgets, and adds no hot-path call.
 * This is neither an instruction boundary nor a device advancement request. */
#define legacy_cpu_charge(cycles) (CPU_REMCLOCK -= (cycles))

#endif
