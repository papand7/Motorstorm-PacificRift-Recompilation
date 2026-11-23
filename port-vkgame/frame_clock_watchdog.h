/* Frame-clock stall watchdog (diagnostic only; off unless PS3_FC_WATCHDOG_MS is set).
 *
 * The frame-clock thread presents, ticks vblank/flip and drains the GCM FIFO.
 * When it stops, everything that depends on it stops together -- RSX `get`, the
 * heartbeat, presents -- and nothing says where it stopped (the native-audio
 * run 20261023-100017-audio: guest GcKernel::Present() timeouts, no runtime
 * message). This names the stage the thread was in and its host stack as
 * module+offset, so the stall can be attributed to the drain, the D3D12
 * present path or the window pump.
 *
 * Cost: the frame clock stores a stage number and bumps a counter. A separate
 * thread checks every 250 ms; after PS3_FC_WATCHDOG_MS without progress it
 * suspends the frame clock once, unwinds its stack (RtlLookupFunctionEntry /
 * RtlVirtualUnwind, nothing that takes the loader lock), resumes it, and
 * prints. One report per stall, at most FCW_MAX_REPORTS per run. Guest state
 * is never read or written. */
#pragma once
#ifdef _WIN32
#include <windows.h>
#include <psapi.h>
#pragma comment(lib, "psapi.lib")
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum { FCW_IDLE = 0, FCW_SLEEP, FCW_BEAT, FCW_PRESENT, FCW_DRAIN, FCW_PUMP, FCW_NSTAGES };
static const char* const fcw_stage_names[FCW_NSTAGES] = { "idle", "sleep", "beat", "present", "drain", "pump" };
#define FCW_MAX_REPORTS 8
#define FCW_MAX_FRAMES  24
#define FCW_MAX_MODULES 512

typedef struct fcw_state {
    volatile LONG stage;
    volatile LONG progress;
    HANDLE thread;            /* the watched thread (a real handle, not the pseudo-handle) */
    DWORD threshold_ms;
    FILE* out;
    volatile LONG reports;
    volatile LONG stop;
} fcw_state;

static fcw_state g_fcw;

/* Called by the watched thread. A store and an interlocked increment. */
static inline void fcw_mark(LONG stage)
{
    g_fcw.stage = stage;
    InterlockedIncrement(&g_fcw.progress);
}

typedef struct { ULONG_PTR base, size; char name[64]; } fcw_mod;

static int fcw_modules(fcw_mod* mods, int max)
{
    HMODULE hm[FCW_MAX_MODULES]; DWORD need = 0; int n = 0;
    if (!EnumProcessModules(GetCurrentProcess(), hm, sizeof hm, &need)) return 0;
    for (DWORD i = 0; i < need / sizeof(HMODULE) && n < max; i++) {
        MODULEINFO mi; char path[MAX_PATH];
        if (!GetModuleInformation(GetCurrentProcess(), hm[i], &mi, sizeof mi)) continue;
        if (!GetModuleFileNameA(hm[i], path, sizeof path)) continue;
        const char* b = strrchr(path, '\\');
        mods[n].base = (ULONG_PTR)mi.lpBaseOfDll; mods[n].size = mi.SizeOfImage;
        strncpy(mods[n].name, b ? b + 1 : path, sizeof mods[n].name - 1);
        mods[n].name[sizeof mods[n].name - 1] = 0;
        n++;
    }
    return n;
}

/* Suspend, unwind, resume. Returns the number of return addresses captured. */
static int fcw_capture(HANDLE th, DWORD64* pcs, int max)
{
    if (SuspendThread(th) == (DWORD)-1) return 0;
    CONTEXT ctx; memset(&ctx, 0, sizeof ctx); ctx.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
    int n = 0;
    if (GetThreadContext(th, &ctx)) {
#if defined(_M_X64) || defined(__x86_64__)
        while (n < max && ctx.Rip) {
            pcs[n++] = ctx.Rip;
            DWORD64 image = 0;
            PRUNTIME_FUNCTION fn = RtlLookupFunctionEntry(ctx.Rip, &image, NULL);
            if (!fn) {                                   /* leaf: return address at [rsp] */
                ctx.Rip = *(DWORD64*)ctx.Rsp; ctx.Rsp += 8;
            } else {
                void* hd = NULL; DWORD64 frame = 0;
                RtlVirtualUnwind(UNW_FLAG_NHANDLER, image, ctx.Rip, fn, &ctx, &hd, &frame, NULL);
            }
            if (!ctx.Rsp) break;
        }
#else
        pcs[n++] = 0;
#endif
    }
    ResumeThread(th);
    return n;
}

static void fcw_report(DWORD stalled_ms, LONG stage)
{
    static fcw_mod mods[FCW_MAX_MODULES];
    const int nm = fcw_modules(mods, FCW_MAX_MODULES);   /* before suspending: takes the loader lock */
    DWORD64 pcs[FCW_MAX_FRAMES];
    const int n = fcw_capture(g_fcw.thread, pcs, FCW_MAX_FRAMES);
    FILE* f = g_fcw.out ? g_fcw.out : stderr;
    fprintf(f, "[fc-watchdog] frame clock no progress for %lu ms in stage=%s (report %ld/%d)\n",
            (unsigned long)stalled_ms, (stage >= 0 && stage < FCW_NSTAGES) ? fcw_stage_names[stage] : "?",
            (long)g_fcw.reports, FCW_MAX_REPORTS);
    for (int i = 0; i < n; i++) {
        const char* name = "?"; ULONG_PTR off = (ULONG_PTR)pcs[i];
        for (int m = 0; m < nm; m++)
            if (pcs[i] >= mods[m].base && pcs[i] < mods[m].base + mods[m].size) { name = mods[m].name; off = (ULONG_PTR)pcs[i] - mods[m].base; break; }
        fprintf(f, "[fc-watchdog]   #%02d %s+0x%llx\n", i, name, (unsigned long long)off);
    }
    fflush(f);
}

static DWORD WINAPI fcw_thread(LPVOID)
{
    LONG seen = g_fcw.progress; DWORD since = GetTickCount(); int reported = 0;
    while (!g_fcw.stop) {
        Sleep(250);
        const LONG now = g_fcw.progress;
        if (now != seen) { seen = now; since = GetTickCount(); reported = 0; continue; }
        const DWORD stalled = GetTickCount() - since;
        if (!reported && stalled >= g_fcw.threshold_ms && g_fcw.reports < FCW_MAX_REPORTS) {
            InterlockedIncrement(&g_fcw.reports);
            fcw_report(stalled, g_fcw.stage);
            reported = 1;          /* once per stall; a new stall needs progress first */
        }
    }
    return 0;
}

/* Call on the thread to be watched. Returns 1 when the watchdog runs. */
static int fcw_start_for_current_thread(FILE* out)
{
    const char* e = getenv("PS3_FC_WATCHDOG_MS");
    const long ms = e ? atol(e) : 0;
    if (ms <= 0) return 0;
    if (!DuplicateHandle(GetCurrentProcess(), GetCurrentThread(), GetCurrentProcess(), &g_fcw.thread,
                         THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION, FALSE, 0))
        return 0;
    g_fcw.threshold_ms = (DWORD)(ms < 500 ? 500 : ms);
    g_fcw.out = out;
    HANDLE h = CreateThread(NULL, 64 * 1024, fcw_thread, NULL, 0, NULL);
    if (!h) return 0;
    CloseHandle(h);
    fprintf(out ? out : stderr, "[fc-watchdog] watching the frame clock, report after %lu ms without progress\n",
            (unsigned long)g_fcw.threshold_ms);
    return 1;
}
#endif
