// Frame-clock watchdog: reports a blocked thread's stage and host stack, stays
// quiet for a thread that keeps progressing, and leaves the thread runnable.
// Build: clang-cl /nologo /O1 /EHsc test_frame_clock_watchdog.cpp psapi.lib
#include "../frame_clock_watchdog.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static HANDLE g_release;
static volatile LONG g_mode;          // 0 = progress forever, 1 = block in "drain"
static volatile LONG g_done;
static FILE* g_out;

static DWORD WINAPI worker(LPVOID)
{
    fcw_start_for_current_thread(g_out);
    for (int i = 0; i < 300 && !g_mode; i++) { fcw_mark(FCW_SLEEP); Sleep(5); fcw_mark(FCW_DRAIN); }
    fcw_mark(FCW_DRAIN);
    WaitForSingleObject(g_release, INFINITE);   // the stall
    fcw_mark(FCW_PUMP);
    g_done = 1;
    return 0;
}

static long read_all(char* buf, long cap)
{
    fflush(g_out);
    long n = ftell(g_out);
    rewind(g_out);
    n = (long)fread(buf, 1, n < cap - 1 ? n : cap - 1, g_out);
    buf[n] = 0;
    fseek(g_out, 0, SEEK_END);
    return n;
}

int main()
{
    static char buf[1 << 16];
    _putenv("PS3_FC_WATCHDOG_MS=500");
    g_out = tmpfile();
    g_release = CreateEventA(NULL, TRUE, FALSE, NULL);
    HANDLE th = CreateThread(NULL, 0, worker, NULL, 0, NULL);

    Sleep(1200);                                       // progressing: no report
    read_all(buf, sizeof buf);
    assert(strstr(buf, "watching the frame clock"));
    assert(!strstr(buf, "no progress"));

    g_mode = 1;                                        // now block
    Sleep(1500);
    read_all(buf, sizeof buf);
    assert(strstr(buf, "no progress for"));
    assert(strstr(buf, "stage=drain"));
    assert(strstr(buf, "ntdll.dll") || strstr(buf, "KernelBase.dll"));
    assert(strstr(buf, "#01 "));                       // unwound beyond the top frame

    Sleep(1000);                                       // one report per stall
    read_all(buf, sizeof buf);
    const char* first = strstr(buf, "no progress for");
    assert(first && !strstr(first + 1, "no progress for"));

    SetEvent(g_release);                               // the thread was resumed and still runs
    assert(WaitForSingleObject(th, 2000) == WAIT_OBJECT_0);
    assert(g_done == 1);
    g_fcw.stop = 1;

    _putenv("PS3_FC_WATCHDOG_MS=");                     // off by default
    assert(fcw_start_for_current_thread(NULL) == 0);

    puts(buf);
    puts("frame clock watchdog: all checks passed");
    return 0;
}
