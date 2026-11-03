"""T161 V5 one-off patch of ps3recomp-t161 include/ps3emu/lwcond_wake.h: once-only state
init (lwcw_get_once), race-free lwcw_now_us, opt-in fb=1 fallback attribution."""
import sys
from pathlib import Path
CR, LF = chr(13), chr(10)


def load(q):
    global crlf
    raw = q.read_bytes().decode('utf-8')
    crlf = CR + LF in raw
    return raw.replace(CR + LF, LF)


def save(q, t):
    q.write_bytes((t.replace(LF, CR + LF) if crlf else t).encode('utf-8'))


p = Path(sys.argv[1]) / 'include/ps3emu/lwcond_wake.h'
s = load(p)


def sub(a, b):
    global s
    assert s.count(a) == 1, a[:70]
    s = s.replace(a, b)


sub(""" * PS3_LWCOND_WAKE=1[:poll_ms=100][:stats_ms=0]   (unset or 0 = off: old poll path)
 * Fixed tables; a full table falls back to the poll path for that lwcond (nofit=).
""", """ * PS3_LWCOND_WAKE=1[:poll_ms=100][:stats_ms=0][:fb=0]   (unset or 0 = off: old poll path)
 * Fixed tables; a full table falls back to the poll path for that lwcond (nofit=).
 * fb=1 (with stats_ms) also attributes every fallback to (thread, lwcond, call site)
 * and to whether any signal reached that lwcond during the wait ([lwc-wake-fb]).
 * The process-wide state is configured once (lwcw_get_once): concurrent first
 * callers wait for the one that parses the variable; it is never reconfigured,
 * and after lwcw_shutdown every later wait takes the poll path.
""")
sub("""static inline uint64_t lwcw_now_us(void)
{
    static LARGE_INTEGER f;
    LARGE_INTEGER c;
    if (!f.QuadPart) QueryPerformanceFrequency(&f);
    QueryPerformanceCounter(&c);""", """static inline uint64_t lwcw_now_us(void)
{
    LARGE_INTEGER f, c;
    QueryPerformanceFrequency(&f);     /* per call: a lazily cached static was a racy first write */
    QueryPerformanceCounter(&c);""")
sub("""#define LWCW_SPIN_PAUSE() YieldProcessor()
#define LWCW_XCHG(p, v) InterlockedExchange((volatile LONG*)(p), (v))
""", """#define LWCW_SPIN_PAUSE() YieldProcessor()
#define LWCW_YIELD() SwitchToThread()
#define LWCW_XCHG(p, v) InterlockedExchange((volatile LONG*)(p), (v))
#define LWCW_CAS32(p, o, n) (InterlockedCompareExchange((volatile LONG*)(p), (n), (o)) == (o))
""")
sub("""#define LWCW_SPIN_PAUSE() sched_yield()
#define LWCW_XCHG(p, v) __atomic_exchange_n((p), (v), __ATOMIC_ACQ_REL)
""", """#define LWCW_SPIN_PAUSE() sched_yield()
#define LWCW_YIELD() sched_yield()
#define LWCW_XCHG(p, v) __atomic_exchange_n((p), (v), __ATOMIC_ACQ_REL)
#define LWCW_CAS32(p, o, n) __sync_bool_compare_and_swap((p), (o), (n))
""")
sub("""#define LWCW_CVS 4096u                 /* lwconds with a host record (open addressing) */
""", """#if defined(__GNUC__) || defined(__clang__)
#define LWCW_LOAD_ACQ(p) __atomic_load_n((p), __ATOMIC_ACQUIRE)
#else   /* MSVC x86/x64 (/volatile:ms): a volatile read is an acquire */
#define LWCW_LOAD_ACQ(p) (*(p))
#endif

#define LWCW_CVS 4096u                 /* lwconds with a host record (open addressing) */
#define LWCW_FBS 256u                  /* fb=1 attribution rows per stats window */
#define LWCW_FB_BT 3                   /* guest call-site words kept per row */
""")
sub("""    uint32_t tid;
    int state;                         /* -1 waiting, else an LWCW_* result; under cv->lock */
} lwcw_waiter;""", """    uint32_t tid;
    int state;                         /* -1 waiting, else an LWCW_* result; under cv->lock */
    uint32_t seq0, sig_seen;           /* cv->sig_seq at registration; signals on the cv until return */
} lwcw_waiter;""")
sub("""    lwcw_waiter *head, *tail;          /* FIFO */
} lwcw_cv;""", """    lwcw_waiter *head, *tail;          /* FIFO */
    uint32_t sig_seq;                  /* signal calls on this lwcond (under lock) */
} lwcw_cv;

/* fb=1: fallbacks per (thread, lwcond, call site) in the current stats window. */
typedef struct lwcw_fb {
    uint32_t tid, cv, lr, site[LWCW_FB_BT];
    uint32_t n, nosig, sig_other;      /* fallbacks; no signal on the cv during the wait; signals woke others */
} lwcw_fb;""")
sub("""    int on;
    uint32_t poll_ms, stats_ms;
    volatile long tab_lock;""", """    int on, fb_attr;
    uint32_t poll_ms, stats_ms;
    volatile long tab_lock;""")
sub("""    volatile long long last_report_us;
    FILE* out;
} lwcw_state;""", """    volatile long long last_report_us;
    FILE* out;
    volatile long fb_lock;
    uint32_t fb_rows;
    long long fb_dropped;
    lwcw_fb fb[LWCW_FBS];
} lwcw_state;""")
sub("""    s->stats_ms = 0;
    s->on = spec && atoi(spec) > 0;""", """    s->stats_ms = 0;
    s->fb_attr = 0;
    s->on = spec && atoi(spec) > 0;""")
sub("""        else if (!strncmp(p + 1, "stats_ms=", 9)) s->stats_ms = (uint32_t)strtoul(p + 10, NULL, 10);
    }
    s->last_report_us = (long long)lwcw_now_us();
    if (out) fprintf(out, "[lwc-wake] on poll_ms=%u stats_ms=%u\\n", s->poll_ms, s->stats_ms);
    return 1;
}
""", """        else if (!strncmp(p + 1, "stats_ms=", 9)) s->stats_ms = (uint32_t)strtoul(p + 10, NULL, 10);
        else if (!strncmp(p + 1, "fb=", 3)) s->fb_attr = atoi(p + 4) > 0;
    }
    s->last_report_us = (long long)lwcw_now_us();
    if (out) fprintf(out, "[lwc-wake] on poll_ms=%u stats_ms=%u fb=%d\\n", s->poll_ms, s->stats_ms, s->fb_attr);
    return 1;
}

/* Thread-safe one-time configure of a process-wide state (s and *once zeroed, static
 * storage) from getenv(env). *once: 0 = not yet, 1 = being configured, 2 = done. The
 * first caller configures; concurrent first callers wait until it publishes, so none
 * sees a half-configured state. Returns s if on, else NULL (never reconfigured). */
static inline lwcw_state* lwcw_get_once(lwcw_state* s, volatile long* once, const char* env, FILE* out)
{
    if (LWCW_LOAD_ACQ(once) != 2) {
        if (LWCW_CAS32(once, 0, 1)) {
#ifdef LWCW_TEST_INIT_HOOK
            LWCW_TEST_INIT_HOOK();
#endif
            lwcw_configure(s, getenv(env), out);
            LWCW_XCHG(once, 2);                 /* full barrier: publishes the configured state */
        } else {
            for (int i = 0; LWCW_LOAD_ACQ(once) != 2; i++) {
                if (i < 64) LWCW_SPIN_PAUSE(); else LWCW_YIELD();
            }
        }
    }
    return s->on ? s : NULL;
}
""")
sub("""    w->cv = c; w->tid = tid; w->state = -1;
    lwcw_lock(&c->lock);
    w->prev = c->tail;""", """    w->cv = c; w->tid = tid; w->state = -1;
    lwcw_lock(&c->lock);
    w->seq0 = c->sig_seq;
    w->prev = c->tail;""")
sub("""    int r = w->state;
    lwcw_unlock(&c->lock);""", """    int r = w->state;
    w->sig_seen = c->sig_seq - w->seq0;
    lwcw_unlock(&c->lock);""")
sub("""        lwcw_lock(&c->lock);
        if (kind == LWCW_ALL) {""", """        lwcw_lock(&c->lock);
        c->sig_seq++;
        if (kind == LWCW_ALL) {""")
sub("""/* Print and reset the counters if stats_ms elapsed (any thread; one wins). */""",
    """/* fb=1: record a fallback return of w (lwcw_sleep returned LWCW_FALLBACK) at guest
 * call site lr / site[0..n) (guest code words from the waiter's stack). */
static inline void lwcw_note_fallback(lwcw_state* s, const lwcw_waiter* w, uint32_t lr, const uint32_t* site, int n)
{
    uint32_t st[LWCW_FB_BT] = { 0 };
    for (int i = 0; i < n && i < LWCW_FB_BT; i++) st[i] = site[i];
    const uint32_t cv = (uint32_t)w->cv->addr;
    while (LWCW_XCHG(&s->fb_lock, 1)) LWCW_SPIN_PAUSE();
    lwcw_fb* f = NULL;
    for (uint32_t i = 0; i < s->fb_rows && !f; i++) {
        lwcw_fb* e = &s->fb[i];
        if (e->tid == w->tid && e->cv == cv && e->lr == lr && !memcmp(e->site, st, sizeof st)) f = e;
    }
    if (!f && s->fb_rows < LWCW_FBS) {
        f = &s->fb[s->fb_rows++];
        memset(f, 0, sizeof *f);
        f->tid = w->tid; f->cv = cv; f->lr = lr; memcpy(f->site, st, sizeof st);
    }
    if (f) { f->n++; if (w->sig_seen) f->sig_other++; else f->nosig++; }
    else s->fb_dropped++;
    LWCW_XCHG(&s->fb_lock, 0);
}

/* Print and reset the counters if stats_ms elapsed (any thread; one wins). */""")
sub("""            (long long)LWCW_TAKE(&s->to_miss));
}""", """            (long long)LWCW_TAKE(&s->to_miss));
    if (!s->fb_attr) return;
    while (LWCW_XCHG(&s->fb_lock, 1)) LWCW_SPIN_PAUSE();
    for (uint32_t i = 0; i < s->fb_rows; i++) {
        const lwcw_fb* f = &s->fb[i];
        fprintf(s->out, "[lwc-wake-fb] window_ms=%u tid=%u cv=0x%08X lr=0x%08X site=%X+%X+%X n=%u nosig=%u sig_other=%u\\n",
                s->stats_ms, f->tid, f->cv, f->lr, f->site[0], f->site[1], f->site[2], f->n, f->nosig, f->sig_other);
    }
    if (s->fb_dropped) fprintf(s->out, "[lwc-wake-fb] window_ms=%u dropped=%lld\\n", s->stats_ms, s->fb_dropped);
    s->fb_rows = 0; s->fb_dropped = 0;
    LWCW_XCHG(&s->fb_lock, 0);
}""")
save(p, s)

# runtime/ppu/ppu_sysprx.cpp: once-only lwcw_get, fb=1 hook after a fallback return.
p = Path(sys.argv[1]) / 'runtime/ppu/ppu_sysprx.cpp'
s = load(p)
sub("""static lwcw_state* lwcw_get(void)
{
    static lwcw_state s;
    static int on = -1;
    if (on < 0) on = lwcw_configure(&s, getenv("PS3_LWCOND_WAKE"), stderr);
    return on ? &s : nullptr;
}""", """static lwcw_state* lwcw_get(void)
{
    static lwcw_state s;
    static volatile long once;   /* configured once, also when the first waits race */
    return lwcw_get_once(&s, &once, "PS3_LWCOND_WAKE", stderr);
}""")
sub("""        if (reg) wr = lwcw_sleep(wk, &wt, ctx->gpr[4]);
        else Sleep(1);
""", """        if (reg) wr = lwcw_sleep(wk, &wt, ctx->gpr[4]);
        else Sleep(1);
        if (wr == LWCW_FALLBACK && wk->fb_attr) {   /* fb=1: read-only stack scan, fallbacks only */
            uint32_t bt[LWCT_BT];
            lwct_stack_bt(ctx, bt);
            lwcw_note_fallback(wk, &wt, (uint32_t)ctx->lr, bt, LWCT_BT);
        }
""")
save(p, s)
print('patched')
