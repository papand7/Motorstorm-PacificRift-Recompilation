MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T69: build the isolated race-perf instrumentation patch from copies of
ps3recomp-t62 files. Never writes into the worktree. Logging/timing only:
no guest-visible state changes."""
import os, shutil, subprocess, sys
SRC = (MS_ROOT + r"\ps3recomp-t62")
OUT = (MS_ROOT + r"\generated\analysis\t69\patch")
FILES = ["libs/spurs/cellSpurs.c", "runtime/spu/spu_channels.c"]

def sub(text, old, new, path):
    # the files mix CRLF and LF lines; match the anchor's own line ending
    if text.count(old.replace("\n", "\r\n")) == 1:
        old = old.replace("\n", "\r\n"); new = new.replace("\n", "\r\n")
    if text.count(old) != 1:
        sys.exit(f"anchor not unique in {path}: {old[:60]!r}")
    return text.replace(old, new)

work = os.path.join(OUT, "work")
shutil.rmtree(work, ignore_errors=True)
for f in FILES:
    for side in ("a", "b"):
        d = os.path.join(work, side, os.path.dirname(f)); os.makedirs(d, exist_ok=True)
        shutil.copyfile(os.path.join(SRC, f), os.path.join(work, side, f))

p = os.path.join(work, "b", FILES[0]); t = open(p, "rb").read().decode("utf-8")
t = sub(t, r"""static DWORD WINAPI spurs_pm_worker(LPVOID p)
{
    struct SpursPmSlot* slot = (struct SpursPmSlot*)p;
    struct SpursInst* si = slot->instance;
#ifdef _WIN32
    { ULONG g = 256 * 1024; SetThreadStackGuarantee(&g); }
#endif
""", r"""/* SPURS_BUSY_MS=<ms> (T69, diagnostic): per-workload host busy time of the
 * policy-module runs, printed by the coordinator every <ms>. Host timing only;
 * no guest state is read or written. */
static int spurs_busy_ms(void)
{ static int v = -1; if (v < 0) { const char* e = getenv("SPURS_BUSY_MS"); v = e ? atoi(e) : 0; } return v; }
#include <time.h>   /* timespec_get */
static long long s_busy_us[16], s_busy_runs[16], s_busy_polled[16];
static u64 spurs_busy_now_us(void)
{ struct timespec ts; timespec_get(&ts, TIME_UTC);
  return (u64)ts.tv_sec * 1000000u + (u64)ts.tv_nsec / 1000u; }

static DWORD WINAPI spurs_pm_worker(LPVOID p)
{
    struct SpursPmSlot* slot = (struct SpursPmSlot*)p;
    struct SpursInst* si = slot->instance;
#ifdef _WIN32
    { ULONG g = 256 * 1024; SetThreadStackGuarantee(&g); }
#endif
    if (spurs_busy_ms())
        fprintf(stderr, "[thread-role] hosttid=%lu role=spurs-pm spurs=0x%08X sn=%u\n",
                (unsigned long)GetCurrentThreadId(), si->ea, slot->spu_num);
""", p)
t = sub(t, r"""        ReleaseSRWLockExclusive(&si->lock);
        spu_run_policy_module(slot->fn, slot->image_id, slot->pm, slot->pm_size,
                              slot->data, slot->wid, slot->ea, slot->spu_num);
        extern SPU_THREAD_LOCAL volatile unsigned g_spurs_pm_polls;
        unsigned polls = g_spurs_pm_polls;
""", r"""        ReleaseSRWLockExclusive(&si->lock);
        u64 busy_t0 = spurs_busy_ms() ? spurs_busy_now_us() : 0;
        spu_run_policy_module(slot->fn, slot->image_id, slot->pm, slot->pm_size,
                              slot->data, slot->wid, slot->ea, slot->spu_num);
        extern SPU_THREAD_LOCAL volatile unsigned g_spurs_pm_polls;
        unsigned polls = g_spurs_pm_polls;
        if (busy_t0 && slot->wid < 16) {
            __atomic_add_fetch(&s_busy_us[slot->wid], (long long)(spurs_busy_now_us() - busy_t0), __ATOMIC_RELAXED);
            __atomic_add_fetch(&s_busy_runs[slot->wid], 1, __ATOMIC_RELAXED);
            if (polls) __atomic_add_fetch(&s_busy_polled[slot->wid], 1, __ATOMIC_RELAXED);
        }
""", p)
t = sub(t, r"""    int disabled = getenv("PS3_NO_SPURS_PM") != NULL;
    AcquireSRWLockExclusive(&si->lock);
    while (!si->stopping) {
        SleepConditionVariableSRW(&si->wake, &si->lock, 1, 0);
        if (si->stopping) break;
""", r"""    int disabled = getenv("PS3_NO_SPURS_PM") != NULL;
    const int busy_ms = spurs_busy_ms();
    u64 busy_last = busy_ms ? spurs_busy_now_us() : 0;
    if (busy_ms)
        fprintf(stderr, "[thread-role] hosttid=%lu role=spurs-kernel spurs=0x%08X\n",
                (unsigned long)GetCurrentThreadId(), si->ea);
    AcquireSRWLockExclusive(&si->lock);
    while (!si->stopping) {
        SleepConditionVariableSRW(&si->wake, &si->lock, 1, 0);
        if (si->stopping) break;
        if (busy_ms && si == &s_inst[0]) {
            u64 now = spurs_busy_now_us();
            if (now - busy_last >= (u64)busy_ms * 1000u) {
                for (u32 w = 0; w < 16; w++) {
                    long long us = __atomic_exchange_n(&s_busy_us[w], 0, __ATOMIC_RELAXED);
                    long long runs = __atomic_exchange_n(&s_busy_runs[w], 0, __ATOMIC_RELAXED);
                    long long pr = __atomic_exchange_n(&s_busy_polled[w], 0, __ATOMIC_RELAXED);
                    if (runs)
                        fprintf(stderr, "[spurs-busy] wid=%u window_ms=%llu runs=%lld polled=%lld busy_ms=%.1f pass=%u\n",
                                w, (unsigned long long)((now - busy_last) / 1000u), runs, pr,
                                us / 1000.0, si->pass_no);
                }
                busy_last = now;
            }
        }
""", p)
open(p, "wb").write(t.encode("utf-8"))

p = os.path.join(work, "b", FILES[1]); t = open(p, "rb").read().decode("utf-8")
t = sub(t, r"""            unsigned n = ++g_spurs_pm_polls;
            if (n <= 4 || (n % 4096) == 0)
                fprintf(stderr, "[spurs-pm] poll #%u (r3=0x%08X) -> continue\n",
                        n, ctx->gpr[3]._u32[0]);
""", r"""            unsigned n = ++g_spurs_pm_polls;
            /* g_spurs_pm_polls restarts at 0 every policy run, so gating on it
             * printed the first poll of EVERY run (~1000 lines/s in a race).
             * Gate the log on a process-wide count; n is still returned as before. */
            static unsigned long s_poll_log = 0;
            unsigned long pl = __atomic_add_fetch(&s_poll_log, 1, __ATOMIC_RELAXED);
            if (pl <= 16 || (pl % 65536) == 0)
                fprintf(stderr, "[spurs-pm] poll #%u (r3=0x%08X, total %lu) -> continue\n",
                        n, ctx->gpr[3]._u32[0], pl);
""", p)
open(p, "wb").write(t.encode("utf-8"))

r = subprocess.run(["git", "diff", "--no-index", "--src-prefix=", "--dst-prefix=", "a", "b"],
                   cwd=work, capture_output=True)
diff = r.stdout.replace(b"--- a/", b"--- a/").replace(b"a/libs", b"a/libs")
# rewrite paths a/X b/X relative to repo root
diff = diff.replace(b"diff --git a/", b"diff --git a/").replace(b" b/", b" b/")
open(os.path.join(OUT, "t69_race_perf_instrumentation.patch"), "wb").write(diff)
print("patch bytes", len(diff))
