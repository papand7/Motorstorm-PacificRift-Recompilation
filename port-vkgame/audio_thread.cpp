/* MSPR_PATCH=audiothread (in the default patch list; settings.ini "audiothread = Off" or an MSPR_PATCH without it
 * turns it off): the audio update on its own guest thread.
 *
 * The frame function calls Ms2Audio's virtual update (vtable slot +0x20 of the object at +0x44) once a frame:
 *   1.00: func_00082358, call at 0x000829D4, return address 0x000829D8 (and 9 linear copies of the function's tail);
 *   1.03: func_00069C38, call at 0x0006A14C, return address 0x0006A150 (1475 calls in a 30 s race, that one site).
 * The profile puts it at about 5 % of the main thread, and the call site does not use its result: r3 and the volatile
 * registers are dead after it. With the switch on, the lifted call site (generated/analysis/vksync/tools/
 * mspr_patch_lifted.py and launcher/pipeline/mspr_patch_lifted.py, bit 64) calls mspr_audio_kick() instead: it hands
 * the call to a worker and returns at once. The worker is a real guest thread (sys_ppu_thread_create), so it has its
 * own thread id (the lightweight mutexes in the audio code see a valid owner) and its own guest stack.
 *
 * The join is the frame's flip (g_frame_join_hook, called by _cellGcmSetFlipCommand): the audio update has finished
 * before the next frame's world update starts, and before a second kick. Between the kick and the flip the main
 * thread runs the per-view updates, the GUI and the timer step (about 2-3 % of the frame), which is all that
 * overlaps; the audio update itself must not run beside the race update (it reads positions that update writes).
 * The join waits on the job state, not on the completion event alone: a job that finished before the flip leaves
 * the auto-reset event set, and the next join would otherwise return at once while its own job still ran.
 *
 * TLS (MSPR_AUDIO_TLS): the audio code reads function pointers from thread-local storage that the main thread filled
 * in at start-up (a worker with a fresh TLS block crashed on a NULL bctr, Kk2916).
 *   copy (default): at each kick the main thread's TLS block (r13 - 0x7000, the PT_TLS size) is copied into the
 *     worker's own block and the update runs on that copy. At the join, every byte the update changed is copied back
 *     into the main thread's block, unless the main thread changed the same byte meanwhile (a conflict: the main
 *     thread's value is kept, as its write came later in the original order; counted and logged). So the two threads
 *     never write one TLS word at the same time (the allocator's "inside an allocation" flag and context pointer,
 *     ppu_loader.cpp ppu_tls_new_block, were the known hazard), and the main thread still sees the update's TLS
 *     writes, at the flip rather than at the call.
 *   shared: the first version: the worker runs with the main thread's r13, one block for both threads.
 * MSPR_AUDIO_TLS_LOG=1 logs each TLS offset the update or the overlapping main thread writes (first 64). */
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
extern "C" uint32_t ppu_tls_memsz(void);   /* ppu_loader.cpp: the PT_TLS memsz (0 without PT_TLS) */

#define AUDIO_CODE      0x0FEE0000u      /* a code address no lifted function uses, registered to the worker body */
#define AUDIO_STACK     0x100000u        /* guest stack of the worker */
#define AUDIO_BIT       64u
#define AUDIO_OPD       0x2FF0F000u      /* the guest page pc_menu.cpp already uses (PCMENU_EA 0x2FF00000, 64 KB) */
#define AUDIO_TIDOUT    0x2FF0F100u
#define AUDIO_TLS_BIAS  0x7000u          /* TLS data at r13 - 0x7000 (PPU ABI) */
#define AUDIO_TLS_MAX   0x4000u          /* larger PT_TLS: shared mode */

static struct {
    volatile LONG state;                 /* 0 idle, 1 job pending, 2 running */
    HANDLE        job, done, ready;
    uint64_t      r2, r3, r4, r13, ctr, lr;
    int           started, failed;
    uint64_t      kicks, waits;
    /* TLS copy mode */
    int           tls_copy, tls_log, merge_pending;
    uint32_t      main_tp, worker_tp, tls_size;
    uint8_t       snap[AUDIO_TLS_MAX];
    uint64_t      tls_audio_bytes, tls_main_bytes, tls_conflicts, tls_audio_joins;
    uint8_t       seen_a[AUDIO_TLS_MAX], seen_m[AUDIO_TLS_MAX];
    int           logged;
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
    s_a.worker_tp = (uint32_t)ctx->gpr[13];   /* its own TLS block (ppu_tls_new_block), or the main one if none */
    SetEvent(s_a.ready);
    for (;;) {
        WaitForSingleObject(s_a.job, INFINITE);
        InterlockedExchange(&s_a.state, 2);
        ctx->gpr[2] = s_a.r2;
        ctx->gpr[3] = s_a.r3;
        ctx->gpr[4] = s_a.r4;
        ctx->gpr[13] = s_a.r13;      /* copy mode: the worker's block holding the main thread's values; shared: main's */
        ctx->ctr = s_a.ctr;
        ctx->lr = s_a.lr;
        ps3_indirect_call(ctx);
        audio_drain(ctx);
        InterlockedExchange(&s_a.state, 0);
        SetEvent(s_a.done);
    }
}

/* Copy mode, on the main thread after the job has finished: the update's TLS writes into the main block. */
static void audio_tls_merge(void)
{
    if (!s_a.merge_pending) return;
    s_a.merge_pending = 0;
    uint8_t* m = vm_base + (s_a.main_tp - AUDIO_TLS_BIAS);
    const uint8_t* w = vm_base + (s_a.worker_tp - AUDIO_TLS_BIAS);
    int any = 0;
    for (uint32_t i = 0; i < s_a.tls_size; i++) {
        const uint8_t o = s_a.snap[i];
        const int aw = w[i] != o, mw = m[i] != o;
        if (mw) {
            s_a.tls_main_bytes++;
            if (s_a.tls_log && !s_a.seen_m[i] && s_a.logged < 64) {
                s_a.seen_m[i] = 1; s_a.logged++;
                fprintf(stderr, "[audio-thread] TLS +0x%X changed by the main thread during the update\n", i);
            }
        }
        if (!aw) continue;
        any = 1;
        s_a.tls_audio_bytes++;
        if (s_a.tls_log && !s_a.seen_a[i] && s_a.logged < 64) {
            s_a.seen_a[i] = 1; s_a.logged++;
            fprintf(stderr, "[audio-thread] TLS +0x%X written by the audio update (0x%02X -> 0x%02X)\n", i, o, w[i]);
        }
        if (mw) {
            if (s_a.tls_conflicts++ < 16)
                fprintf(stderr, "[audio-thread] TLS conflict at +0x%X: both threads wrote it; main's value kept\n", i);
            continue;
        }
        m[i] = w[i];
    }
    s_a.tls_audio_joins += any;
}

static void audio_join(void)
{
    if (!s_a.started) return;
    if (InterlockedCompareExchange(&s_a.state, 0, 0) != 0) {
        s_a.waits++;
        while (InterlockedCompareExchange(&s_a.state, 0, 0) != 0)
            WaitForSingleObject(s_a.done, INFINITE);   /* a stale signal from an earlier job only loops once */
    }
    audio_tls_merge();
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
    {   /* TLS mode */
        const char* e = getenv("MSPR_AUDIO_TLS");
        const char* l = getenv("MSPR_AUDIO_TLS_LOG");
        s_a.tls_log = l && *l && strcmp(l, "0") != 0;
        s_a.main_tp = (uint32_t)ctx->gpr[13];
        s_a.tls_size = ppu_tls_memsz();
        const int want_copy = !(e && !strcmp(e, "shared"));
        const char* why = NULL;
        if (!want_copy) why = "MSPR_AUDIO_TLS=shared";
        else if (!s_a.tls_size) why = "no PT_TLS";
        else if (s_a.tls_size > AUDIO_TLS_MAX) why = "PT_TLS larger than the copy buffer";
        else if (s_a.main_tp < AUDIO_TLS_BIAS || s_a.worker_tp < AUDIO_TLS_BIAS) why = "no TLS pointer";
        else if (s_a.worker_tp == s_a.main_tp) why = "the worker has no TLS block of its own";
        s_a.tls_copy = why == NULL;
        fprintf(stderr, "[audio-thread] TLS %s (main r13 0x%08X, worker r13 0x%08X, 0x%X bytes)%s%s\n",
                s_a.tls_copy ? "copy" : "shared", s_a.main_tp, s_a.worker_tp, s_a.tls_size,
                why ? ": " : "", why ? why : "");
    }
    g_frame_join_hook = audio_join;
    s_a.started = 1;
    fprintf(stderr, "[audio-thread] worker started (stack 0x%X), update at 0x%08X (object 0x%08X)\n", AUDIO_STACK,
            (uint32_t)ctx->ctr, (uint32_t)ctx->gpr[3]);
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
    s_a.ctr = ctx->ctr;
    s_a.lr = ctx->lr;
    if (s_a.tls_copy && (uint32_t)ctx->gpr[13] == s_a.main_tp) {
        const uint8_t* m = vm_base + (s_a.main_tp - AUDIO_TLS_BIAS);
        memcpy(s_a.snap, m, s_a.tls_size);
        memcpy(vm_base + (s_a.worker_tp - AUDIO_TLS_BIAS), m, s_a.tls_size);
        s_a.r13 = s_a.worker_tp;
        s_a.merge_pending = 1;
    } else {
        s_a.r13 = ctx->gpr[13];
    }
    InterlockedExchange(&s_a.state, 1);
    s_a.kicks++;
    SetEvent(s_a.job);
    if ((s_a.kicks & (s_a.kicks - 1u)) == 0)
        fprintf(stderr, "[audio-thread] %llu kicks, %llu joins that had to wait; TLS: %llu bytes written by the "
                "update (%llu updates), %llu by the main thread meanwhile, %llu conflicts\n",
                (unsigned long long)s_a.kicks, (unsigned long long)s_a.waits,
                (unsigned long long)s_a.tls_audio_bytes, (unsigned long long)s_a.tls_audio_joins,
                (unsigned long long)s_a.tls_main_bytes, (unsigned long long)s_a.tls_conflicts);
    return 1;
}
