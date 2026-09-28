/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <io/iocore.h>
#include <pccore.h>
#include "mouse_machine.h"
#include <stdio.h>
#include <stdlib.h>
MOUSE_TIME mouse_machine;
uint64_t mouse_fake_now;
int mouse_machine_ready;
extern int mouseif_absflag;
void mouse_machine_reject(void)
{
    fprintf(stderr, "N5 normalized mouse: input/time/configuration outside admitted fake-source profile\n");
    abort();
}
static void scope(void)
{
    if (np2cfg.KEY_MODE == 3 || np2cfg.MOUSERAPID || mouseif_absflag)
        mouse_machine_reject();
}
void mouse_machine_reset(void)
{
    scope();
    /* Runtime reset integration is excluded from the initial cold-boot pilot.
     * The pccore guard rejects it before any CPU/device reset mutation. */
    if (mouse_machine_ready || !mouse_time_reset(&mouse_machine, mouse_fake_now))
        mouse_machine_reject();
    mouse_machine_ready = 1;
}
void mouse_machine_service(void)
{
    uint64_t before;
    if (!mouse_machine_ready) return;
    scope();
    before = mouse_machine.publications;
    if (!mouse_time_settle(&mouse_machine, mouse_fake_now)) mouse_machine_reject();
    mouseif.x = (SINT16)mouse_machine.live[0]; mouseif.y = (SINT16)mouse_machine.live[1];
    mouseif.sx = (SINT16)mouse_machine.batch[0]; mouseif.sy = (SINT16)mouse_machine.batch[1];
    mouseif.rx = (SINT16)(mouse_machine.batch[0] - mouse_machine.emitted[0]);
    mouseif.ry = (SINT16)(mouse_machine.batch[1] - mouse_machine.emitted[1]);
    mouseif.b = mouse_machine.buttons;
    if (mouse_machine.publications != before) pic_setirq(13);
}
void mouse_machine_control(unsigned portc)
{
    if (!mouse_time_enable(&mouse_machine, !(portc & 0x10))) mouse_machine_reject();
}
void mouse_machine_import_live(void)
{
    mouse_machine.live[0] = mouseif.x; mouse_machine.live[1] = mouseif.y;
}
