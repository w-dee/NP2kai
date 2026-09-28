/* SPDX-License-Identifier: MIT */
#include "gdc_time.h"
/* Private deterministic test source. Boot stepping is disabled before N4's
 * canonical epoch. Neither this provider nor its step counter reads a CPU. */
GDC_SAMPLE gdc_fake_sample={0,1};
uint64_t gdc_fake_step_ns;
int gdc_fake_suppress_presentation;
const unsigned gdc_fake_binding_version=1;
GDC_SAMPLE gdc_time_source(void)
{
    GDC_SAMPLE result=gdc_fake_sample;
    if (gdc_fake_step_ns<=UINT64_MAX-gdc_fake_sample.ns)
        gdc_fake_sample.ns+=gdc_fake_step_ns;
    else gdc_fake_sample.valid=0;
    return result;
}
