/* SPDX-License-Identifier: MIT */
#include "artic_time.h"
#include <assert.h>
#include <stdio.h>
int main(void)
{
    ARTIC_SAMPLE a=artic_time_source();
    assert(a.valid);
    for(unsigned i=0;i<100000;i++) {
        ARTIC_SAMPLE b=artic_time_source();assert(b.valid && b.ns>=a.ns);a=b;
    }
    artic_machine_reset();
    uint32_t before=artic_machine_time.phase;
    (void)artic_machine_read();
    assert(artic_machine_time.anchored && !artic_machine_time.rejected);
    assert(artic_machine_time.phase>=before);
    puts("PASS live adapter monotonic sanity only; no realtime-semantic qualification");
}
