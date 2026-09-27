/**
 * @file	nevent.c
 * @brief	Implementation of the event
 */

#include <compiler.h>
#include <nevent.h>
#include <cpucore.h>
#include <pccore.h>
#include <legacycpu.h>
#include <timeshadow.h>

	_NEVENT g_nevent;
#if 0
#undef	TRACEOUT
#define	TRACEOUT(s)	(void)(s)
static void trace_fmt_ex(const char* fmt, ...)
{
	char stmp[2048];
	va_list ap;
	va_start(ap, fmt);
	vsprintf(stmp, fmt, ap);
	strcat(stmp, "¥n");
	va_end(ap);
	OutputDebugStringA(stmp);
}
#define	TRACEOUT(s)	trace_fmt_ex s
#endif	/* 1 */

	_NEVENT g_nevent;

#if defined(SUPPORT_MULTITHREAD)

#if defined(NP2_WIN)

static int nevent_cs_initialized = 0;
static CRITICAL_SECTION nevent_cs;

static BOOL nevent_tryenter_criticalsection(void){
	if(!nevent_cs_initialized) return TRUE;
	return TryEnterCriticalSection(&nevent_cs);
}
static void nevent_enter_criticalsection(void){
	if(!nevent_cs_initialized) return;
	EnterCriticalSection(&nevent_cs);
}
static void nevent_leave_criticalsection(void){
	if(!nevent_cs_initialized) return;
	LeaveCriticalSection(&nevent_cs);
}

void nevent_initialize(void)
{
	if(!nevent_cs_initialized){
		memset(&nevent_cs, 0, sizeof(nevent_cs));
		InitializeCriticalSection(&nevent_cs);
		nevent_cs_initialized = 1;
	}
}
void nevent_shutdown(void)
{
	if(nevent_cs_initialized){
		DeleteCriticalSection(&nevent_cs);
		memset(&nevent_cs, 0, sizeof(nevent_cs));
		nevent_cs_initialized = 0;
	}
}

#elif defined(USE_SDL) && USE_SDL >= 3

static SDL_Mutex *nevent_cs = NULL;
static int nevent_cs_initialized = 0;

static BOOL nevent_tryenter_criticalsection(void){
	if(!nevent_cs_initialized || !nevent_cs) return TRUE;
	return SDL_TryLockMutex(nevent_cs) == 0;
}
static void nevent_enter_criticalsection(void){
	if(!nevent_cs_initialized || !nevent_cs) return;
	SDL_LockMutex(nevent_cs);
}
static void nevent_leave_criticalsection(void){
	if(!nevent_cs_initialized || !nevent_cs) return;
	SDL_UnlockMutex(nevent_cs);
}

void nevent_initialize(void)
{
	if(!nevent_cs_initialized){
		nevent_cs = SDL_CreateMutex();
		nevent_cs_initialized = 1;
	}
}
void nevent_shutdown(void)
{
	if(nevent_cs_initialized && nevent_cs){
		SDL_DestroyMutex(nevent_cs);
		nevent_cs = NULL;
		nevent_cs_initialized = 0;
	}
}

#elif defined(SUPPORT_PTHREAD)

#include <pthread.h>
static pthread_mutex_t nevent_cs = PTHREAD_MUTEX_INITIALIZER;
static int nevent_cs_initialized = 1;

static BOOL nevent_tryenter_criticalsection(void){
	return pthread_mutex_trylock(&nevent_cs) == 0;
}
static void nevent_enter_criticalsection(void){
	pthread_mutex_lock(&nevent_cs);
}
static void nevent_leave_criticalsection(void){
	pthread_mutex_unlock(&nevent_cs);
}

void nevent_initialize(void) { (void)nevent_cs_initialized; }
void nevent_shutdown(void) { }

#endif /* NP2_WIN / USE_SDL / SUPPORT_PTHREAD */

#endif /* SUPPORT_MULTITHREAD */

void nevent_allreset(void)
{
	/* すべてをリセット */
	memset(&g_nevent, 0, sizeof(g_nevent));
}

void nevent_get1stevent(void)
{
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	/* 最短のイベントのクロック数をセット */
	if (g_nevent.readyevents)
	{
		legacy_cpu_begin_slice(g_nevent.item[g_nevent.level[0]].clock);
	}
	else
	{
		/* イベントがない場合のクロック数をセット */
		legacy_cpu_begin_slice(NEVENT_MAXCLOCK);
	}

	
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
}

static void nevent_execute(void)
{
	UINT nEvents;
	UINT i;
	NEVENTID id;
	NEVENTITEM item;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	nEvents = 0;
	for (i = 0; i < g_nevent.waitevents; i++)
	{
		id = g_nevent.waitevent[i];
		item = &g_nevent.item[id];

		/* コールバックの実行 */
		if (item->proc != NULL)
		{
			item->proc(item);

			/* 次回に持ち越しのイベントのチェック */
			if (item->flag & NEVENT_WAIT)
			{
				g_nevent.waitevent[nEvents++] = id;
			}
		}
		else {
			item->flag &= ~(NEVENT_WAIT);
		}
		item->flag &= ~(NEVENT_SETEVENT);
	}
	g_nevent.waitevents = nEvents;
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
}

void nevent_progress(void)
{
	UINT nEvents;
	LEGACY_DEADLINE nextbase;
	UINT i;
	NEVENTID id;
	NEVENTITEM item;
	UINT8 fevtchk = 0;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	time_shadow_commit(legacy_cpu_slice_budget());
	legacy_cpu_commit_slice();
	nEvents = 0;
	nextbase = NEVENT_MAXCLOCK;
	for (i = 0; i < g_nevent.readyevents; i++)
	{
		id = g_nevent.level[i];
		item = &g_nevent.item[id];
		item->clock -= legacy_cpu_slice_budget();
		if (item->clock > 0)
		{
			/* イベント待ち中 */
			g_nevent.level[nEvents++] = id;
			if (nextbase >= item->clock)
			{
				nextbase = item->clock;
			}
		}
		else
		{
			/* イベント発生 */
			if (!(item->flag & (NEVENT_SETEVENT | NEVENT_WAIT)))
			{
				g_nevent.waitevent[g_nevent.waitevents++] = id;
			}
			item->flag |= NEVENT_SETEVENT;
			item->flag &= ~(NEVENT_ENABLE);
//			TRACEOUT(("event = %x", id));
#if defined(SUPPORT_ASYNC_CPU)
			pccore_asynccpustat.screendisp = (id == NEVENT_FLAMES && g_nevent.item[NEVENT_FLAMES].proc == screendisp);
#endif
		}
		fevtchk |= (id==NEVENT_FLAMES ? 1 : 0);
	}
	g_nevent.readyevents = nEvents;
	legacy_cpu_continue_slice(nextbase);
	nevent_execute();

	// NEVENT_FLAMESが消える問題に暫定対処
	if(!fevtchk){
		//printf("NEVENT_FLAMES is missing!!¥n");
		pcstat.screendispflag = 0;
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
//	TRACEOUT(("nextbase = %d (%d)", nextbase, CPU_REMCLOCK));
}

void nevent_changeclock(UINT32 oldclock, UINT32 newclock)
{
	UINT i;
	NEVENTID id;
	NEVENTITEM item;
	SINT32 baseClock;
	SINT32 remClock;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif

	time_shadow_rate_before(oldclock);
	if (oldclock > 0)
	{
		if (g_nevent.readyevents)
		{
			// イベントのクロック数を修正
			for (i = 0; i < g_nevent.readyevents; i++)
			{
				id = g_nevent.level[i];
				item = &g_nevent.item[id];
				if (item->clock > 0)
				{
					SINT64 newClock = ((SINT64)item->clock * newclock + oldclock / 2) / oldclock;
					if (item->clock > 0 && newClock <= 0) newClock = 1;
					if (newClock > INT_MAX) newClock = INT_MAX;
					item->clock = (SINT32)newClock;
				}
			}

			// 自動調整のクロック変更のタイミングは CPU_BASECLOCK==CPU_REMCLOCK のタイミングになるように調整済み
			if (CPU_BASECLOCK == CPU_REMCLOCK) {
				legacy_cpu_begin_slice(g_nevent.item[g_nevent.level[0]].clock);
			}
			else {
				// I/O経由の場合はずれている場合あり。この場合はスケール
				/* Scheduler-owned rate conversion, not invariant-preserving rebase. */
				CPU_BASECLOCK = ((SINT64)CPU_BASECLOCK * newclock + oldclock / 2) / oldclock;
				CPU_REMCLOCK = ((SINT64)CPU_REMCLOCK * newclock + oldclock / 2) / oldclock;
			}
		}
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif

	time_shadow_rate_after(newclock);
}

void nevent_reset(NEVENTID id)
{
	UINT i;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	/* 現在進行してるイベントを検索 */
	for (i = 0; i < g_nevent.readyevents; i++)
	{
		if (g_nevent.level[i] == id)
		{
			break;
		}
	}
	/* イベントは存在した？ */
	if (i < g_nevent.readyevents)
	{
		/* 存在していたら削る */
		g_nevent.readyevents--;
		for (; i < g_nevent.readyevents; i++)
		{
			g_nevent.level[i] = g_nevent.level[i + 1];
		}
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
}

void nevent_waitreset(NEVENTID id)
{
	UINT i;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	/* 現在進行してるイベントを検索 */
	for (i = 0; i < g_nevent.waitevents; i++)
	{
		if (g_nevent.waitevent[i] == id)
		{
			break;
		}
	}
	/* イベントは存在した？ */
	if (i < g_nevent.waitevents)
	{
		/* 存在していたら削る */
		g_nevent.waitevents--;
		for (; i < g_nevent.waitevents; i++)
		{
			g_nevent.waitevent[i] = g_nevent.waitevent[i + 1];
		}
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
}

void nevent_set(NEVENTID id, SINT32 eventclock, NEVENTCB proc, NEVENTPOSITION absolute)
{
	LEGACY_DEADLINE clk;
	NEVENTITEM item;
	UINT eventId;
	UINT i;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
//	TRACEOUT(("event %d - %xclocks", id, eventclock));

	clk = legacy_cpu_slice_elapsed();
	item = &g_nevent.item[id];
	item->proc = proc;
	item->flag = 0;
	if (absolute)
	{
		item->clock = eventclock + clk;
	}
	else
	{
		item->clock += eventclock;
	}
#if 0
	if (item->clock < clk)
	{
		item->clock = clk;
	}
#endif
	/* イベントの削除 */
	nevent_reset(id);

	/* イベントの挿入位置の検索 */
	for (eventId = 0; eventId < g_nevent.readyevents; eventId++)
	{
		if (item->clock < g_nevent.item[g_nevent.level[eventId]].clock)
		{
			break;
		}
	}

	/* イベントの挿入 */
	for (i = g_nevent.readyevents; i > eventId; i--)
	{
		g_nevent.level[i] = g_nevent.level[i - 1];
	}
	g_nevent.level[eventId] = id;
	g_nevent.readyevents++;

	/* もし最短イベントだったら... */
	if (eventId == 0)
	{
		clk = legacy_cpu_slice_budget() - item->clock;
		legacy_cpu_rebase_slice(clk);
//		TRACEOUT(("reset nextbase -%d (%d)", clock, CPU_REMCLOCK));
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
}

void nevent_setbyms(NEVENTID id, SINT32 ms, NEVENTCB proc, NEVENTPOSITION absolute)
{
	nevent_set(id, legacy_deadline_from_ms(pccore.realclock, ms), proc, absolute);
}

BOOL nevent_iswork(NEVENTID id)
{
	UINT i;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	/* 現在進行してるイベントを検索 */
	for (i = 0; i < g_nevent.readyevents; i++)
	{
		if (g_nevent.level[i] == id)
		{
#if defined(SUPPORT_MULTITHREAD)
			nevent_leave_criticalsection();
#endif
			return TRUE;
		}
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
	return FALSE;
}

void nevent_forceexecute(NEVENTID id)
{
	NEVENTITEM item;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	item = &g_nevent.item[id];

	/* コールバックの実行 */
	if (item->proc != NULL)
	{
		item->proc(item);
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
}

SINT32 nevent_getremain(NEVENTID id)
{
	UINT i;
	
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	/* 現在進行してるイベントを検索 */
	for (i = 0; i < g_nevent.readyevents; i++)
	{
		if (g_nevent.level[i] == id)
		{
			SINT32 result = (g_nevent.item[id].clock - (legacy_cpu_slice_elapsed()));
#if defined(SUPPORT_MULTITHREAD)
			nevent_leave_criticalsection();
#endif
			return result;
		}
	}
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
	return -1;
}

void nevent_forceexit(void)
{
#if defined(SUPPORT_MULTITHREAD)
	nevent_enter_criticalsection();
#endif
	legacy_cpu_forceexit();
#if defined(SUPPORT_MULTITHREAD)
	nevent_leave_criticalsection();
#endif
}
