/* MSPR_PATCH=audiothread (opt-in, off by default): the audio update on its own guest thread.
 *
 * MotorStorm 1.03 calls Ms2Audio's virtual update from the frame function func_00069C38 (call at 0x0006A14C, return
 * address 0x0006A150, vtable slot +0x20; 1475 calls in a 30 s race, all from that one site). The profile puts it at
 * about 5 % of the main thread, and the call site does not use its result: r3 and the volatile registers are dead
 * after it. With the switch on, the lifted call site (generated/analysis/vksync/tools/mspr_patch_lifted.py, bit 64)
 * calls mspr_audio_kick() instead: it hands the call to a worker and returns at once. The worker is a real guest
 * thread (sys_ppu_thread_create), so it has its own thread id (the lightweight mutexes in the audio code see a valid
 * owner), its own guest stack and its own TLS block.
 *
 * The join is the frame's flip (g_frame_join_hook, called by _cellGcmSetFlipCommand): the audio update has finished
 * before the next frame's world update starts, and before a second kick. Between the kick and the flip the main
 * thread runs the per-view updates, the GUI and the timer step (about 2-3 % of the frame), which is all that
 * overlaps; the audio update itself must not run beside the race update (it reads positions that update writes).
 *
 * TLS: the audio code reads function pointers from thread-local storage that the main thread filled in at start-up
 * (a worker with a fresh TLS block crashed on a NULL bctr, Kk2916). So the worker runs with the MAIN thread's r13.
 * Eight functions in the call tree use r13. The two threads then share one TLS block: a thread-local word that both
 * write at the same time would race. That is the remaining risk, and why this is opt-in. */
#include "ppu_recomp.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif

typedef void (*audio_fn)(ppu_context*);
extern "C" void ppu_register_function(uint64_t addr, audio_fn fn);
extern "C" int64_t sys_ppu_thread_create(ppu_context* ctx);
extern "C" void ps3_indirect_call(ppu_context* ctx);
extern "C" PPU_THREAD_LOCAL void (*g_trampoline_fn)(void*);
extern "C" void (*g_frame_join_hook)(void);
extern "C" int mspr_patch_on(uint32_t bit);

#define AUDIO_CODE      0x0FEE0000u      /* a code address no lifted function uses, registered to the worker body */
#define AUDIO_STACK     0x100000u        /* guest stack of the worker */
#define AUDIO_BIT       64u
#define AUDIO_OPD       0x2FF0F000u      /* the guest page pc_menu.cpp already uses (PCMENU_EA 0x2FF00000, 64 KB) */
#define AUDIO_TIDOUT    0x2FF0F100u

static struct {
    volatile LONG state;                 /* 0 idle, 1 job pending, 2 running */
    HANDLE        job, done, ready;
    uint64_t      r2, r3, r4, r13, ctr, lr;
    int           started, failed;
    uint64_t      kicks, waits;
} s_a;

static void audio_drain(ppu_context* ctx)
{
    while (g_trampoline_fn) {
        void (*f)(void*) = g_trampoline_fn;
        g_trampoline_fn = 0;
        f(ctx);
    }
}

/* The worker thread's body: wait for a job, run the virtual call it was handed, signal completion. */
static void audio_worker(ppu_context* ctx)
{
    SetEvent(s_a.ready);
    for (;;) {
        WaitForSingleObject(s_a.job, INFINITE);
        ctx->gpr[2] = s_a.r2;
        ctx->gpr[3] = s_a.r3;
        ctx->gpr[4] = s_a.r4;
        ctx->gpr[13] = s_a.r13;      /* the main thread's TLS block: its startup values are what the audio code expects */
        ctx->ctr = s_a.ctr;
        ctx->lr = s_a.lr;
        ps3_indirect_call(ctx);
        audio_drain(ctx);
        InterlockedExchange(&s_a.state, 0);
        SetEvent(s_a.done);
    }
}

static void audio_join(void)
{
    if (!s_a.started || s_a.state == 0) return;
    s_a.waits++;
    WaitForSingleObject(s_a.done, INFINITE);
}

static int audio_start(ppu_context* ctx)
{
    s_a.job = CreateEventA(NULL, FALSE, FALSE, NULL);
    s_a.done = CreateEventA(NULL, FALSE, FALSE, NULL);
    s_a.ready = CreateEventA(NULL, TRUE, FALSE, NULL);
    const uint32_t opd = AUDIO_OPD, tid_out = AUDIO_TIDOUT;
    if (!s_a.job || !s_a.done || !s_a.ready) return -1;
    ppu_register_function(AUDIO_CODE, audio_worker);
    vm_write32(opd, AUDIO_CODE);
    vm_write32(opd + 4u, (uint32_t)ctx->gpr[2]);
    ppu_context tmp;
    memset(&tmp, 0, sizeof tmp);
    tmp.gpr[2] = ctx->gpr[2];
    tmp.thread_id = ctx->thread_id;
    tmp.gpr[3] = tid_out;            /* u64* thread id out */
    tmp.gpr[4] = opd;                /* entry OPD */
    tmp.gpr[5] = 0;                  /* arg */
    tmp.gpr[6] = 1000;               /* priority */
    tmp.gpr[7] = AUDIO_STACK;        /* guest stack size */
    tmp.gpr[8] = 0;                  /* flags: not joinable */
    tmp.gpr[9] = 0;
    const int64_t rc = sys_ppu_thread_create(&tmp);
    if (rc != 0) { fprintf(stderr, "[audio-thread] sys_ppu_thread_create failed 0x%llX\n", (unsigned long long)rc); return -1; }
    if (WaitForSingleObject(s_a.ready, 5000) != WAIT_OBJECT_0) { fprintf(stderr, "[audio-thread] worker did not start\n"); return -1; }
    g_frame_join_hook = audio_join;
    s_a.started = 1;
    fprintf(stderr, "[audio-thread] worker started (stack 0x%X)\n", AUDIO_STACK);
    return 0;
}

/* Called in place of the audio update's virtual call. ctx is the caller's context at the call: ctr holds the code
 * address, r2 the callee's TOC, r3 the object, r4 the argument. Returns 1 when the call was handed over, 0 when the
 * caller should make the call itself (the worker could not be started). */
extern "C" int mspr_audio_kick(ppu_context* ctx)
{
    if (s_a.failed) return 0;
    if (!s_a.started && audio_start(ctx)) { s_a.failed = 1; return 0; }
    audio_join();                        /* a second kick before the flip: wait for the first */
    s_a.r2 = ctx->gpr[2];
    s_a.r3 = ctx->gpr[3];
    s_a.r4 = ctx->gpr[4];
    s_a.r13 = ctx->gpr[13];
    s_a.ctr = ctx->ctr;
    s_a.lr = ctx->lr;
    InterlockedExchange(&s_a.state, 1);
    s_a.kicks++;
    SetEvent(s_a.job);
    if ((s_a.kicks & (s_a.kicks - 1u)) == 0)
        fprintf(stderr, "[audio-thread] %llu kicks, %llu joins that had to wait\n",
                (unsigned long long)s_a.kicks, (unsigned long long)s_a.waits);
    return 1;
}
