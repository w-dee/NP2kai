/* SPDX-License-Identifier: MIT */
/* Link the production statsave.c object built with function sections. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
extern uint8_t g_u8ControlState;
int statsave_save(const char *);
int statsave_load(const char *);
int statsave_save_d(void);
int statsave_load_d(void);
int statsave_save_hdd(const char *);
int statsave_load_hdd(const char *);
int statsave_check(const char *, char *, int);
/* Only the diagnostic string copy may remain reachable in this test link. */
void milutf8_ncpy(char *dst, const char *src, unsigned count)
{
    if (count) { strncpy(dst,src,count-1);dst[count-1]=0; }
}
int main(void)
{
    char message[96]="untouched";
    g_u8ControlState=0;
    assert(statsave_save("must-not-create.sav")==-1);
    assert(statsave_load("must-not-open.sav")==-1);
    assert(g_u8ControlState==0);
    assert(statsave_save_d()==-1 && statsave_load_d()==-1);
    assert(statsave_check("must-not-open.sav",message,sizeof(message))==-1);
    assert(strstr(message,"cold-boot only"));
    assert(statsave_check(0,0,0)==-1);
    assert(statsave_save(0)==-1 && statsave_load(0)==-1);
    assert(statsave_save_hdd("artic-test")==-1 && statsave_load_hdd("artic-test")==-1);
    puts("PASS production statsave queue/check/direct save+load rejection; no file/device dependencies linked");
}
