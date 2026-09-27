/* SPDX-License-Identifier: MIT */
#include <compiler.h>
#include <cpucore.h>
#include <pccore.h>
#include <nevent.h>
#include <legacycpu.h>
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define DECL(prefix) \
extern _NEVENT prefix##g_nevent; \
void prefix##nevent_allreset(void); \
void prefix##nevent_get1stevent(void); \
void prefix##nevent_progress(void); \
void prefix##nevent_changeclock(UINT32,UINT32); \
void prefix##nevent_set(NEVENTID,SINT32,NEVENTCB,NEVENTPOSITION); \
void prefix##nevent_setbyms(NEVENTID,SINT32,NEVENTCB,NEVENTPOSITION); \
void prefix##nevent_reset(NEVENTID); \
void prefix##nevent_waitreset(NEVENTID); \
BOOL prefix##nevent_iswork(NEVENTID); \
void prefix##nevent_forceexecute(NEVENTID); \
SINT32 prefix##nevent_getremain(NEVENTID); \
void prefix##nevent_forceexit(void)
DECL(old_);
UINT32 test_committed;
SINT32 test_slice, test_remaining;
struct test_pccore pccore;
struct test_pcstat pcstat;

struct api {
    _NEVENT *events;
    void (*reset)(void),(*begin)(void),(*progress)(void);
    void (*scale)(UINT32,UINT32);
    void (*set)(NEVENTID,SINT32,NEVENTCB,NEVENTPOSITION);
    void (*ms)(NEVENTID,SINT32,NEVENTCB,NEVENTPOSITION);
    void (*remove)(NEVENTID),(*unwait)(NEVENTID);
    BOOL (*work)(NEVENTID);
    void (*execute)(NEVENTID);
    SINT32 (*remain)(NEVENTID);
    void (*exit)(void);
};
#define API(p) {&p##g_nevent,p##nevent_allreset,p##nevent_get1stevent,p##nevent_progress, \
 p##nevent_changeclock,p##nevent_set,p##nevent_setbyms,p##nevent_reset,p##nevent_waitreset, \
 p##nevent_iswork,p##nevent_forceexecute,p##nevent_getremain,p##nevent_forceexit}
static struct api apis[]={API(old_),API()};
static struct api *active;
static UINT32 callback_hash,callback_count;
static void callback(NEVENTITEM item)
{
    NEVENTID id=(NEVENTID)(item-active->events->item);
    callback_hash=callback_hash*33u+(UINT32)id+item->flag+test_committed;
    callback_count++;
    /* Both periodic relative rearm and WAIT, bounded without changing IDs. */
    if(id==NEVENT_ITIMER && (item->flag & NEVENT_SETEVENT))
        active->set(id,137,callback,NEVENT_RELATIVE);
    if(id==NEVENT_FMTIMERA) item->flag ^= NEVENT_WAIT;
}
struct snapshot {
    _NEVENT events;
    UINT32 committed,hash,count;
    SINT32 slice,remaining,query;
    UINT8 screen;
};
static struct snapshot traces[2][80];
static void capture(struct snapshot *s,SINT32 query)
{
    memset(s,0,sizeof(*s));s->events=*active->events;
    s->committed=test_committed;s->slice=test_slice;s->remaining=test_remaining;
    s->hash=callback_hash;s->count=callback_count;s->query=query;s->screen=pcstat.screendispflag;
}
static void scenario(int which,UINT32 seed)
{
    unsigned step;
    active=&apis[which];active->reset();callback_hash=callback_count=0;
    test_committed=0xffffff00u+seed;test_slice=500;test_remaining=-23;
    pcstat.screendispflag=1;pccore.realclock=2457600*8u;
    /* Stable tie order, past deadlines and replacement of a single ID. */
    active->set(NEVENT_FLAMES,100,callback,NEVENT_ABSOLUTE);
    active->set(NEVENT_ITIMER,100,callback,NEVENT_ABSOLUTE);
    active->set(NEVENT_FMTIMERA,-12,callback,NEVENT_ABSOLUTE);
    capture(&traces[which][0],0);
    for(step=1;step<80;step++) {
        NEVENTID id;UINT32 before;SINT32 query=0;
        seed=seed*1664525u+1013904223u;id=(NEVENTID)(seed%8);
        before=legacy_cpu_device_now();
        switch((seed>>8)%12) {
        case 0:active->set(id,(SINT32)(seed%600)-80,callback,NEVENT_ABSOLUTE);
               assert(legacy_cpu_device_now()==before);break;
        case 1:active->set(id,(SINT32)(seed%600)-80,callback,NEVENT_RELATIVE);
               assert(legacy_cpu_device_now()==before);break;
        case 2:active->progress();assert(legacy_cpu_device_now()==before);break;
        case 3:active->exit();assert(legacy_cpu_device_now()==before);break;
        case 4:active->remove(id);break;
        case 5:active->unwait(id);break;
        case 6:active->execute(id);break;
        case 7:test_remaining-=(SINT32)(seed%300);break;
        case 8:active->begin();break;
        case 9:active->scale(8,7);break;
        case 10:active->scale(0,8);break;
        case 11:active->ms(id,(SINT32)(seed%3),callback,NEVENT_ABSOLUTE);break;
        }
        query=active->remain(id);query^=active->work(id);
        capture(&traces[which][step],query);
    }
}
static double bench(int which)
{
    unsigned i;clock_t start;
    active=&apis[which];active->reset();callback_hash=callback_count=0;
    test_committed=0;test_slice=500;test_remaining=500;
    start=clock();
    for(i=0;i<20000000;i++) {
        active->set(NEVENT_FLAMES,100,callback,NEVENT_ABSOLUTE);
        active->set(NEVENT_ITIMER,107,callback,NEVENT_RELATIVE);
        test_remaining=-3;
        active->progress();
        active->exit();
    }
    return (double)(clock()-start)/CLOCKS_PER_SEC;
}
int main(void)
{
    UINT32 seed;unsigned step,trial;
    for(seed=0;seed<512;seed++) {
        scenario(0,seed);scenario(1,seed);
        for(step=0;step<80;step++) {
            if(memcmp(&traces[0][step],&traces[1][step],sizeof(struct snapshot))) {
                fprintf(stderr,"NEVENT mismatch seed=%u step=%u\n",seed,step);return 1;
            }
        }
    }
    puts("PASS NEVENT parent/current: 40960 exact state tuples, callback order/WAIT/rearm, rebasing, forceexit, rescale");
    for(trial=0;trial<7;trial++) {
        double old_time,new_time;
        if(trial%2) {new_time=bench(1);old_time=bench(0);}
        else {old_time=bench(0);new_time=bench(1);}
        printf("BENCH %.6f %.6f\n",old_time,new_time);
    }
    return 0;
}
