"""T193: patch ps3recomp-t193/runtime/spu/spu_channels.c (telemetry). Run from the motorstorm root."""
p = 'ps3recomp-t193/runtime/spu/spu_channels.c'
s = open(p, encoding='utf-8', newline='').read()
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')


def rep(old, new, cnt=1):
    global s
    assert s.count(old) == cnt, (s.count(old), old[:90])
    s = s.replace(old, new)


# 1. enum: sub-counters
rep('IBR_O_TASKRES, IBR_O_TASKREG, IBR_O_TASKPC,\n       IBR_N };',
    'IBR_O_TASKRES, IBR_O_TASKREG, IBR_O_TASKPC,\n'
    '       IBR_S_HIT_RELOC, IBR_S_HIT_SLOT, IBR_S_FILL_RELOC,   /* T193: subsets of HIT / FILL (relocatable slot, plain slot owner) */\n'
    '       IBR_N };')

# 2. storage + macros
rep('''#ifdef SPU_IB_FAST_STATS
static SPU_TLS unsigned long long t_ibr[IBR_N], t_ibr_sent[IBR_N];   /* per host thread: cumulative / already added to the totals */
static SPU_TLS unsigned t_ibr_tick;
static unsigned long long g_ibr_tot[IBR_N];                          /* process totals, filled at flush points only */
#  define SPU_IBF_COUNT(r) (t_ibr[r]++)
#else
#  define SPU_IBF_COUNT(r) ((void)0)
#endif''', '''#ifdef SPU_IB_FAST_STATS
/* T193: each host thread counts into its own shard (one writer, plain increments). Other threads never read a shard:
 * the owner adds its new counts to the process totals at flush points (every 4096 of its branches, at a checkpoint, and
 * from the thread-exit callback), and reporters read only the totals. */
typedef struct { unsigned long long n[IBR_N], sent[IBR_N]; unsigned tick; } spu_ibr_shard;
static SPU_TLS spu_ibr_shard* t_ibr_sh;          /* NULL until the thread's first counted branch */
static SPU_TLS spu_ibr_shard t_ibr_fallback;     /* if the heap shard or the exit callback cannot be had */
static unsigned long long g_ibr_tot[IBR_N];      /* process totals: relaxed atomic adds at flush points */
#  define SPU_IBF_COUNT(r) (t_ibr_sh->n[r]++)
#  define SPU_IBF_SUB_HIT(o) (t_ibr_sh->n[IBR_S_HIT_RELOC] += (o) == -3, t_ibr_sh->n[IBR_S_HIT_SLOT] += (o) == -2)
#  define SPU_IBF_SUB_FILL(o) (t_ibr_sh->n[IBR_S_FILL_RELOC] += (o) == -3)
#else
#  define SPU_IBF_COUNT(r) ((void)0)
#  define SPU_IBF_SUB_HIT(o) ((void)0)
#  define SPU_IBF_SUB_FILL(o) ((void)0)
#endif''')

# 3. init: environment for the interval reporter
rep('''#ifdef SPU_IB_FAST_STATS
    if (on) atexit(spu_ib_fast_report_atexit);
#endif''', '''#ifdef SPU_IB_FAST_STATS
    if (on) {
        extern int spu_ib_fast_telemetry_configure(unsigned, const char*);
        const char* iv = getenv("PS3_SPU_IB_STATS_INTERVAL_MS");
        const char* fp = getenv("PS3_SPU_IB_STATS_FILE");
        spu_ib_fast_telemetry_configure(iv ? (unsigned)strtoul(iv, NULL, 10) : 0u, fp && *fp ? fp : NULL);
        atexit(spu_ib_fast_report_atexit);
    }
#endif''')

# 4. the counter / reporting functions
i = s.index("/* This thread's counters (nonzero only in -DSPU_IB_FAST_STATS builds): cache hits and fills")
j = s.index('/* Returns the lifted function the full resolver would dispatch to for this')
NEW = r'''/* This thread's counters (nonzero only in -DSPU_IB_FAST_STATS builds): cache hits and fills (misses that resolved). */
void spu_ib_fast_stats(unsigned long long out[2])
{
#ifdef SPU_IB_FAST_STATS
    const spu_ibr_shard* sh = t_ibr_sh;
    out[0] = sh ? sh->n[IBR_HIT] : 0; out[1] = sh ? sh->n[IBR_FILL] : 0;
#else
    out[0] = out[1] = 0;
#endif
}
void spu_ib_fast_reset_stats(void)
{
#ifdef SPU_IB_FAST_STATS
    spu_ibr_shard* sh = t_ibr_sh;
    if (sh) { memset(sh->n, 0, sizeof sh->n); memset(sh->sent, 0, sizeof sh->sent); sh->tick = 0; }
#endif
}
/* This thread's IBR_N reason counters (see the enum); zeros in builds without -DSPU_IB_FAST_STATS. */
void spu_ib_fast_reasons(unsigned long long out[IBR_N])
{
#ifdef SPU_IB_FAST_STATS
    if (t_ibr_sh) memcpy(out, t_ibr_sh->n, sizeof t_ibr_sh->n); else memset(out, 0, sizeof(unsigned long long) * IBR_N);
#else
    memset(out, 0, sizeof(unsigned long long) * IBR_N);
#endif
}
int spu_ib_fast_nreasons(void) { return IBR_N; }
#ifdef SPU_IB_FAST_STATS
static const char* const s_ibr_nm[IBR_N] = { "hit", "fill", "d_policy", "d_irq", "d_trace", "d_service", "d_image23", "d_task",
    "d_reloc_off", "d_unrecognized", "d_unresolved", "d_other", "p_cold", "p_conflict", "p_image", "p_owner", "p_epoch",
    "o_policy", "o_irq", "o_slot", "o_slot_reloc", "o_overlay", "o_task_resident", "o_task_registered", "o_task_pc",
    "s_hit_reloc", "s_hit_slot", "s_fill_reloc" };

/* ---- T193: flush protocol (seqlock-like, writers never wait) ----
 * A flusher bumps g_ibr_fbeg, fences, adds its deltas (relaxed), then bumps g_ibr_fend (release). A reader accepts a
 * snapshot only if fbeg == fend before it read the totals and fbeg is unchanged after (acquire fence), i.e. no flush
 * was in progress or started meanwhile; it retries a bounded number of times and otherwise reports consistent=0. */
static unsigned long long g_ibr_fbeg, g_ibr_fend;
static unsigned g_ibr_live, g_ibr_seen, g_ibr_exited;     /* registered host threads: alive / ever / exited */

static void spu_ibr_flush_shard(spu_ibr_shard* sh)
{
    __atomic_fetch_add(&g_ibr_fbeg, 1, __ATOMIC_RELAXED);
    __atomic_thread_fence(__ATOMIC_RELEASE);
    for (int i = 0; i < IBR_N; i++) {
        const unsigned long long d = sh->n[i] - sh->sent[i];
        if (d) __atomic_fetch_add(&g_ibr_tot[i], d, __ATOMIC_RELAXED);
        sh->sent[i] = sh->n[i];
    }
    __atomic_fetch_add(&g_ibr_fend, 1, __ATOMIC_RELEASE);
}
static int spu_ibr_snapshot(unsigned long long out[IBR_N])
{
    for (int tries = 0; tries < 4096; tries++) {
        const unsigned long long e1 = __atomic_load_n(&g_ibr_fend, __ATOMIC_ACQUIRE);
        const unsigned long long b1 = __atomic_load_n(&g_ibr_fbeg, __ATOMIC_ACQUIRE);
        if (b1 != e1) continue;
        for (int i = 0; i < IBR_N; i++) out[i] = __atomic_load_n(&g_ibr_tot[i], __ATOMIC_RELAXED);
        __atomic_thread_fence(__ATOMIC_ACQUIRE);
        if (__atomic_load_n(&g_ibr_fbeg, __ATOMIC_RELAXED) == b1) return 1;
    }
    for (int i = 0; i < IBR_N; i++) out[i] = __atomic_load_n(&g_ibr_tot[i], __ATOMIC_RELAXED);
    return 0;
}

/* ---- thread registration: the exit callback flushes the shard, so counts survive thread exit ---- */
#ifdef _WIN32
static DWORD s_ibr_fls = FLS_OUT_OF_INDEXES;
static void WINAPI spu_ibr_thread_exit(void* p)
#else
static pthread_key_t s_ibr_key;
static void spu_ibr_thread_exit(void* p)
#endif
{
    spu_ibr_shard* sh = (spu_ibr_shard*)p;
    if (!sh) return;
    spu_ibr_flush_shard(sh);
    __atomic_fetch_sub(&g_ibr_live, 1u, __ATOMIC_RELAXED);
    __atomic_fetch_add(&g_ibr_exited, 1u, __ATOMIC_RELAXED);
    free(sh);
}
static int s_ibr_key_state;   /* 0 none, 1 being made, 2 ready, 3 unavailable */
static int spu_ibr_key_ready(void)
{
    int st = __atomic_load_n(&s_ibr_key_state, __ATOMIC_ACQUIRE);
    if (st >= 2) return st == 2;
    int z = 0;
    if (__atomic_compare_exchange_n(&s_ibr_key_state, &z, 1, 0, __ATOMIC_ACQ_REL, __ATOMIC_ACQUIRE)) {
#ifdef _WIN32
        s_ibr_fls = FlsAlloc(spu_ibr_thread_exit);
        st = s_ibr_fls != FLS_OUT_OF_INDEXES ? 2 : 3;
#else
        st = pthread_key_create(&s_ibr_key, spu_ibr_thread_exit) == 0 ? 2 : 3;
#endif
        __atomic_store_n(&s_ibr_key_state, st, __ATOMIC_RELEASE);
        return st == 2;
    }
    while ((st = __atomic_load_n(&s_ibr_key_state, __ATOMIC_ACQUIRE)) == 1) {}
    return st == 2;
}
static void spu_ibr_register(void)
{
    spu_ibr_shard* sh = spu_ibr_key_ready() ? (spu_ibr_shard*)calloc(1, sizeof *sh) : NULL;
    int ok = 0;
#ifdef _WIN32
    if (sh) ok = FlsSetValue(s_ibr_fls, sh) != 0;
#else
    if (sh) ok = pthread_setspecific(s_ibr_key, sh) == 0;
#endif
    if (!ok) { free(sh); t_ibr_sh = &t_ibr_fallback; return; }   /* counted, flushed at ticks only */
    t_ibr_sh = sh;
    __atomic_fetch_add(&g_ibr_live, 1u, __ATOMIC_RELAXED);
    __atomic_fetch_add(&g_ibr_seen, 1u, __ATOMIC_RELAXED);
}

/* ---- interval / checkpoint reporter: no thread of its own; runs on whichever thread reaches a due flush point ---- */
static int g_ibr_rep_busy;                                   /* try-lock; never taken on the branch path */
static unsigned long long g_ibr_iv_ns, g_ibr_next_ns, g_ibr_t0_ns, g_ibr_last_ns, g_ibr_seq;
static unsigned long long g_ibr_last[IBR_N];
static FILE* g_ibr_out;                                      /* NULL: stderr */

static int spu_ibr_lock(unsigned long long wait_ns)
{
    if (!__atomic_exchange_n(&g_ibr_rep_busy, 1, __ATOMIC_ACQUIRE)) return 1;
    if (!wait_ns) return 0;
    const unsigned long long t_end = spu_host_ns() + wait_ns;
    while (spu_host_ns() < t_end) {
        sched_yield();
        if (!__atomic_exchange_n(&g_ibr_rep_busy, 1, __ATOMIC_ACQUIRE)) return 1;
    }
    return 0;
}
static void spu_ibr_unlock(void) { __atomic_store_n(&g_ibr_rep_busy, 0, __ATOMIC_RELEASE); }

/* One line, written with one fputs and flushed before returning. Caller holds the lock. */
static void spu_ibr_emit(const char* kind)
{
    unsigned long long t[IBR_N], d[IBR_N];
    const int ok = spu_ibr_snapshot(t);
    const unsigned long long now = spu_host_ns();
    if (!g_ibr_t0_ns) g_ibr_t0_ns = now;
    if (!g_ibr_last_ns) g_ibr_last_ns = g_ibr_t0_ns;
    for (int i = 0; i < IBR_N; i++) d[i] = t[i] - g_ibr_last[i];        /* modulo 2^64: wrap-safe */
    char buf[6144];
    int p = snprintf(buf, sizeof buf, "[spu-ib-stats] v=1 kind=%s seq=%llu mono_ns=%llu t_ms=%.3f dt_ms=%.3f"
                     " thr_live=%u thr_seen=%u thr_exited=%u consistent=%d",
                     kind, g_ibr_seq, now, (double)(now - g_ibr_t0_ns) / 1e6, (double)(now - g_ibr_last_ns) / 1e6,
                     __atomic_load_n(&g_ibr_live, __ATOMIC_RELAXED), __atomic_load_n(&g_ibr_seen, __ATOMIC_RELAXED),
                     __atomic_load_n(&g_ibr_exited, __ATOMIC_RELAXED), ok);
    for (int pass = 0; pass < 2; pass++) {
        const unsigned long long* v = pass ? d : t;
        const char* pre = pass ? "dlt" : "cum";
        unsigned long long br = 0;
        for (int i = 0; i <= IBR_D_OTHER; i++) br += v[i];
        p += snprintf(buf + p, sizeof buf - (size_t)p, " %s.branches=%llu %s.miss=%llu %s.hit_plain=%llu", pre, br,
                      pre, v[IBR_FILL] + v[IBR_D_UNRESOLVED], pre, v[IBR_HIT] - v[IBR_S_HIT_RELOC] - v[IBR_S_HIT_SLOT]);
        for (int i = 0; i < IBR_N; i++) p += snprintf(buf + p, sizeof buf - (size_t)p, " %s.%s=%llu", pre, s_ibr_nm[i], v[i]);
    }
    snprintf(buf + p, sizeof buf - (size_t)p, " end=1\n");
    FILE* f = g_ibr_out ? g_ibr_out : stderr;
    fputs(buf, f);
    fflush(f);
    memcpy(g_ibr_last, t, sizeof t);
    g_ibr_last_ns = now;
    g_ibr_seq++;
}

/* Flush point: every 4096 counted branches of a thread. Emits an interval line when one is due and nobody else is
 * reporting (never waits). */
static void spu_ibr_flush_point(void)
{
    spu_ibr_flush_shard(t_ibr_sh);
    const unsigned long long iv = __atomic_load_n(&g_ibr_iv_ns, __ATOMIC_RELAXED);
    if (!iv) return;
    const unsigned long long now = spu_host_ns();
    if (now < __atomic_load_n(&g_ibr_next_ns, __ATOMIC_RELAXED) || !spu_ibr_lock(0)) return;
    if (g_ibr_iv_ns && now >= g_ibr_next_ns) {
        __atomic_store_n(&g_ibr_next_ns, now + g_ibr_iv_ns, __ATOMIC_RELAXED);
        spu_ibr_emit("interval");
    }
    spu_ibr_unlock();
}

/* Add this thread's new counts to the process totals (also run every 4096 branches and at thread exit). */
void spu_ib_fast_thread_flush(void) { if (t_ibr_sh) spu_ibr_flush_shard(t_ibr_sh); }
void spu_ib_fast_totals(unsigned long long out[IBR_N]) { spu_ibr_snapshot(out); }

/* Explicit checkpoint (host stats interval, test, shutdown): flushes the caller's shard and writes one line of the
 * given kind. Waits at most 200 ms for a reporter on another thread. 0 written, -1 not. */
int spu_ib_fast_report_now(const char* kind)
{
    spu_ib_fast_thread_flush();
    if (!spu_ibr_lock(200000000ull)) return -1;
    spu_ibr_emit(kind && *kind ? kind : "checkpoint");
    spu_ibr_unlock();
    return 0;
}
/* (Re)configure the reporter: interval in ms (0: checkpoints and exit only), output file (appended; NULL: stderr).
 * May be called repeatedly; closes the previous file. 0 ok, -1 file not opened (stderr used), -2 reporter busy. */
int spu_ib_fast_telemetry_configure(unsigned interval_ms, const char* path)
{
    if (!spu_ibr_lock(200000000ull)) return -2;
    int rc = 0;
    if (g_ibr_out) { fclose(g_ibr_out); g_ibr_out = NULL; }
    if (path) {
        g_ibr_out = fopen(path, "a");
        if (g_ibr_out) setvbuf(g_ibr_out, NULL, _IOFBF, 1 << 16); else rc = -1;
    }
    const unsigned long long now = spu_host_ns();
    if (!g_ibr_t0_ns) { g_ibr_t0_ns = now; g_ibr_last_ns = now; }
    __atomic_store_n(&g_ibr_iv_ns, (unsigned long long)interval_ms * 1000000ull, __ATOMIC_RELAXED);
    __atomic_store_n(&g_ibr_next_ns, now + (unsigned long long)interval_ms * 1000000ull, __ATOMIC_RELAXED);
    spu_ibr_unlock();
    return rc;
}
/* Test hook: move the totals (and the last-reported snapshot, so deltas are unchanged) by b, to exercise 2^64 wrap. */
void spu_ib_fast_test_bias(unsigned long long b)
{
    if (!spu_ibr_lock(200000000ull)) return;
    for (int i = 0; i < IBR_N; i++) { __atomic_fetch_add(&g_ibr_tot[i], b, __ATOMIC_RELAXED); g_ibr_last[i] += b; }
    spu_ibr_unlock();
}
void spu_ib_fast_threads(unsigned out[3])
{
    out[0] = __atomic_load_n(&g_ibr_live, __ATOMIC_RELAXED); out[1] = __atomic_load_n(&g_ibr_seen, __ATOMIC_RELAXED);
    out[2] = __atomic_load_n(&g_ibr_exited, __ATOMIC_RELAXED);
}
/* The T192 one-line summary (unchanged format). */
void spu_ib_fast_report(FILE* f)
{
    unsigned long long t[IBR_N], all = 0;
    spu_ib_fast_thread_flush(); spu_ibr_snapshot(t);
    for (int i = 0; i <= IBR_D_OTHER; i++) all += t[i];
    fprintf(f, "[spu-ib-fast-stats] branches=%llu", all);
    for (int i = 0; i < IBR_N; i++) if (t[i]) fprintf(f, " %s=%llu", s_ibr_nm[i], t[i]);
    fprintf(f, "\n");
    fflush(f);
}
static void spu_ib_fast_report_atexit(void)
{
    spu_ib_fast_report_now("exit");
    spu_ib_fast_report(stderr);
    if (spu_ibr_lock(200000000ull)) { if (g_ibr_out) { fclose(g_ibr_out); g_ibr_out = NULL; } spu_ibr_unlock(); }
}
/* Test hook: pretend PS3_FTRACE_SPUJOB is recording with this job-return address (0 = tracing off). */
void spu_ib_fast_test_trace(uint32_t jr) { g_ps3_ft.spujob = jr; __atomic_store_n(&g_ps3_ft.on, jr ? 2 : 1, __ATOMIC_RELEASE); }
/* Overlapping observations of the context (independent of the primary reason) and the policy / irq reasons. */
static inline void spu_ibf_pre(const spu_context* ctx)
{
    if (__builtin_expect(!t_ibr_sh, 0)) spu_ibr_register();
    unsigned long long* n = t_ibr_sh->n;
    if (__builtin_expect((++t_ibr_sh->tick & 0xFFFu) == 0, 0)) spu_ibr_flush_point();
    n[IBR_O_POLICY] += ctx->policy_mode != 0;
    n[IBR_O_IRQ] += ctx->irq_saved != 0;
    n[IBR_O_OVL] += ctx->resident_ovl != 0;
    n[IBR_O_TASKRES] += ctx->resident_task != 0;
    n[IBR_O_TASKREG] += (s_task_elf_count | s_task_entry_count) != 0;
    n[IBR_O_TASKPC] += ctx->pc >= SPU_TASKSET_TASK_LO;
    for (unsigned slot = 0; slot < 4; ++slot) {
        const uint32_t lsa = ctx->resident_code[slot].lsa;
        if (ctx->resident_code[slot].image_id && ctx->pc >= lsa && ctx->pc - lsa < ctx->resident_code[slot].size) {
            n[IBR_O_SLOT]++; n[IBR_O_SLOT_RELOC] += ctx->resident_code[slot].link_base != 0; break;
        }
    }
    if (ctx->policy_mode) n[IBR_D_POLICY]++; else if (ctx->irq_saved) n[IBR_D_IRQ]++;
}
#else
void spu_ib_fast_thread_flush(void) {}
void spu_ib_fast_totals(unsigned long long out[IBR_N]) { memset(out, 0, sizeof(unsigned long long) * IBR_N); }
void spu_ib_fast_report(FILE* f) { (void)f; }
int spu_ib_fast_report_now(const char* kind) { (void)kind; return -1; }
int spu_ib_fast_telemetry_configure(unsigned interval_ms, const char* path) { (void)interval_ms; (void)path; return -1; }
void spu_ib_fast_test_bias(unsigned long long b) { (void)b; }
void spu_ib_fast_threads(unsigned out[3]) { out[0] = out[1] = out[2] = 0; }
void spu_ib_fast_test_trace(uint32_t jr) { (void)jr; }
#endif

'''
s = s[:i] + NEW + s[j:]

# 5. hit / fill sub-counters
rep('        SPU_IBF_COUNT(IBR_HIT);\n', '        SPU_IBF_COUNT(IBR_HIT);\n        SPU_IBF_SUB_HIT(ovl);\n')
rep('    SPU_IBF_COUNT(IBR_FILL);\n', '    SPU_IBF_COUNT(IBR_FILL);\n    SPU_IBF_SUB_FILL(ovl);\n')
open(p, 'w', encoding='utf-8', newline='').write(s.replace('\n', nl))
print('patched')
