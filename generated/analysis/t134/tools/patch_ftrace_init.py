"""T134: PS3_CRITICAL_PATH_TRACE init / span / arm routing in include/ps3emu/ps3_ftrace.h (one-shot patch)."""
from pathlib import Path
import sys

p = Path(sys.argv[1]) / 'include/ps3emu/ps3_ftrace.h'
t = p.read_text(encoding='utf-8')
NL = '\\n'


def rep(old, new):
    global t
    assert t.count(old) == 1, old[:90]
    t = t.replace(old, new)


rep('''    int on = 3;
    const char* e = getenv("PS3_FTRACE");
    double start = 0, secs = 0;
    int used = 0;
    if (e && *e) {
        if (sscanf(e, "%lf:%lf:%n", &start, &secs, &used) < 2 || !used || secs <= 0) {
            fprintf(stderr, "[ftrace] PS3_FTRACE=<start s>:<seconds>:<path>, got '%s'NL", e);
        } else {
            snprintf(s->path, sizeof s->path, "%s", e + used);
'''.replace('NL', NL), '''    int on = 3;
    const char* e = getenv("PS3_FTRACE");
    double start = 0, secs = 0;
    int used = 0, ok = 0;
    /* T134: PS3_CRITICAL_PATH_TRACE=1 | <start s>:<seconds>[:<path>] streams the
     * same spans (plus host-thread CPU samples) while recording, so a run that is
     * killed keeps them; PS3_FTRACE, when set, wins. */
    const char* cp = getenv("PS3_CRITICAL_PATH_TRACE");
    if (e && *e) {
        if (sscanf(e, "%lf:%lf:%n", &start, &secs, &used) < 2 || !used || secs <= 0)
            fprintf(stderr, "[ftrace] PS3_FTRACE=<start s>:<seconds>:<path>, got '%s'NL", e);
        else { snprintf(s->path, sizeof s->path, "%s", e + used); ok = 1; }
    } else if (cp && *cp && strcmp(cp, "0") != 0) {
        const char* path = "ps3_critical_path.txt";
        if (strcmp(cp, "1") == 0) { start = 0; secs = 86400; ok = 1; }
        else if (sscanf(cp, "%lf:%lf%n", &start, &secs, &used) >= 2 && secs > 0 && start >= 0) {
            if (cp[used] == ':' && cp[used + 1]) path = cp + used + 1;
            ok = 1;
        } else {
            fprintf(stderr, "[ftrace] PS3_CRITICAL_PATH_TRACE=1|<start s>:<seconds>[:<path>], got '%s'NL", cp);
        }
        if (ok) { snprintf(s->path, sizeof s->path, "%s", path); s->stream = 1; }
    }
    if (ok) {
        {
'''.replace('NL', NL))

rep('''            const char* c = getenv("PS3_FTRACE_CAP");
            s->cap = c ? (uint32_t)strtoul(c, 0, 10) : 4u << 20;
            s->buf = (ps3_ft_rec*)calloc(s->cap, sizeof(ps3_ft_rec));
            if (!s->buf) {
                fprintf(stderr, "[ftrace] no memory for %u spansNL", s->cap);
            } else {'''.replace('NL', NL), '''            const char* c = getenv("PS3_FTRACE_CAP");
            s->cap = c ? (uint32_t)strtoul(c, 0, 10) : 4u << 20;
            if (s->stream) {   /* the queue: a power of two, default 1M cells (48 MB) */
                uint64_t qn = 1;
                while (qn < (c ? (uint64_t)s->cap : (1ull << 20)) && qn < (1ull << 26)) qn <<= 1;
                s->q = (ps3_ft_cell*)malloc(qn * sizeof(ps3_ft_cell));
                if (s->q) for (uint64_t i = 0; i < qn; i++) s->q[i].seq = i;
                s->qmask = qn - 1;
                s->out = s->q ? fopen(s->path, "w") : NULL;
                const char* sm = getenv("PS3_CRITICAL_PATH_SAMPLE_MS");
                s->sample_ms = sm ? (uint32_t)strtoul(sm, 0, 10) : 250u;
                if (!s->sample_ms) s->sample_ms = 250u;
                s->cap = 0;
            } else {
                s->buf = (ps3_ft_rec*)calloc(s->cap, sizeof(ps3_ft_rec));
            }
            if (s->stream ? !s->out : !s->buf) {
                fprintf(stderr, "[ftrace] cannot record: %sNL", s->stream ? s->path : "no memory");
                s->stream = 0;
            } else {'''.replace('NL', NL))

rep('''                atexit(ps3_ft_dump_atexit);
                on = 2;
            }''', '''                atexit(ps3_ft_dump_atexit);
                on = 2;
                if (s->stream) {
                    fprintf(s->out, "# ps3_ftrace start_us=%.3f end_us=%.3f spans=0 dropped=0 stream=1 sample_ms=%uNL",
                            (double)(s->start0 - s->base) / 1e3, (double)(s->end - s->base) / 1e3, s->sample_ms);
                    fflush(s->out);
#ifdef _WIN32
                    s->writer = CreateThread(NULL, 0, ps3_ft_writer_main, s, 0, NULL);
#else
                    static pthread_t wt;
                    s->writer = pthread_create(&wt, NULL, ps3_ft_writer_main, s) == 0 ? (void*)&wt : NULL;
#endif
                    if (!s->writer) { fprintf(stderr, "[ftrace] no writer threadNL"); on = 3; }
                }
            }'''.replace('NL', NL))

rep('''    if (t0 > s->end) { ps3_ft_dump(); return; }
    const uint32_t i = __atomic_fetch_add(&s->n, 1, __ATOMIC_RELAXED);
    if (i >= s->cap) { __atomic_fetch_add(&s->dropped, 1, __ATOMIC_RELAXED); return; }''',
    '''    if (s->stream) {   /* the writer ends the window itself; never block a hook */
        ps3_ft_rec r = { t0, t1, a, b, who, (uint32_t)kind };
        if (t0 <= s->end && !ps3_ft_q_push(s, &r)) __atomic_fetch_add(&s->dropped, 1, __ATOMIC_RELAXED);
        return;
    }
    if (t0 > s->end) { ps3_ft_dump(); return; }
    const uint32_t i = __atomic_fetch_add(&s->n, 1, __ATOMIC_RELAXED);
    if (i >= s->cap) { __atomic_fetch_add(&s->dropped, 1, __ATOMIC_RELAXED); return; }''')

rep('''    const uint32_t i = __atomic_fetch_add(&s->n, 1, __ATOMIC_RELAXED);   /* kept: it precedes the window */
    if (i < s->cap) { ps3_ft_rec r = { now, now, fn, lr, 0, (uint32_t)PS3_FT_ARM }; s->buf[i] = r; }
    else __atomic_fetch_add(&s->dropped, 1, __ATOMIC_RELAXED);''',
    '''    if (s->stream) {   /* kept: it precedes the window */
        ps3_ft_rec r = { now, now, fn, lr, 0, (uint32_t)PS3_FT_ARM };
        if (!ps3_ft_q_push(s, &r)) __atomic_fetch_add(&s->dropped, 1, __ATOMIC_RELAXED);
    } else {
        const uint32_t i = __atomic_fetch_add(&s->n, 1, __ATOMIC_RELAXED);   /* kept: it precedes the window */
        if (i < s->cap) { ps3_ft_rec r = { now, now, fn, lr, 0, (uint32_t)PS3_FT_ARM }; s->buf[i] = r; }
        else __atomic_fetch_add(&s->dropped, 1, __ATOMIC_RELAXED);
    }''')

rep('''#ifdef _WIN32
#  include <windows.h>
#else
#  include <time.h>
#endif''', '''#ifdef _WIN32
#  include <windows.h>
#  if !defined(__clang__) && !defined(__GNUC__)
#    include <intrin.h>   /* __rdtsc */
#  endif
#else
#  include <time.h>
#  include <pthread.h>
#endif''')

p.write_text(t, encoding='utf-8')
print('patched', p)
