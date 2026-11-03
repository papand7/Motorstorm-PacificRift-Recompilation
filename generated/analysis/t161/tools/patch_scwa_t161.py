"""T161: one-off patch of include/ps3emu/sc_wait_acct.h (adds the HLE table)."""
import sys
from pathlib import Path
p = Path(sys.argv[1]) / 'include/ps3emu/sc_wait_acct.h'
s = p.read_text(encoding='utf-8')
assert '\r\n' not in s

def rep(old, new):
    global s
    assert s.count(old) == 1, old[:60]
    s = s.replace(old, new)

rep(""" * platform-neutral; tested without a guest. Off (one cached getenv) unless
 * the variable is set to a positive number. */""",
""" * platform-neutral; tested without a guest. Off (one cached getenv) unless
 * the variable is set to a positive number.
 *
 * PS3_HLE_WAIT_MS=<window ms> (T161) keeps a second table of the same shape
 * for HLE imports (ps3_hle_call), keyed by NID: sys_lwmutex_*, sys_lwcond_*,
 * cellFs*, cellSpurs* and the rest never pass through lv2_syscall, so a
 * thread blocked in them showed ~0 ms in [sc-wait]. Calls shorter than
 * PS3_HLE_WAIT_MIN_US (default 20) are not counted, which keeps the 12 slots
 * for the calls that wait. Lines read
 *   [hle-wait] window_ms=W tid=T total_ms=X nid1573DC3F=a.ams/n ... */""")
rep("""static inline void scwa_report(scwa_table* t, FILE* f, uint64_t window_ms)
{
""", """static inline void scwa_report_ex(scwa_table* t, FILE* f, uint64_t window_ms, int hle)
{
    const char* tag = hle ? "[hle-wait]" : "[sc-wait]";
""")
rep("""            const int w = snprintf(line + o, sizeof line - (size_t)o, " sc%u=%.2fms/%llu",
                                   k - 1u, (double)ns / 1e6, (unsigned long long)c);""",
"""            const int w = snprintf(line + o, sizeof line - (size_t)o,
                                   hle ? " nid%08X=%.2fms/%llu" : " sc%u=%.2fms/%llu",
                                   k - 1u, (double)ns / 1e6, (unsigned long long)c);""")
rep("""        if (o) fprintf(f, "[sc-wait] window_ms=%llu tid=%u total_ms=%.2f%s\\n",
                       (unsigned long long)window_ms, tid, (double)tot / 1e6, line);""",
"""        if (o) fprintf(f, "%s window_ms=%llu tid=%u total_ms=%.2f%s\\n",
                       tag, (unsigned long long)window_ms, tid, (double)tot / 1e6, line);""")
rep("""    if (d) fprintf(f, "[sc-wait] window_ms=%llu dropped=%llu\\n",
                   (unsigned long long)window_ms, (unsigned long long)d);
    fflush(f);
}
""", """    if (d) fprintf(f, "%s window_ms=%llu dropped=%llu\\n",
                   tag, (unsigned long long)window_ms, (unsigned long long)d);
    fflush(f);
}
static inline void scwa_report(scwa_table* t, FILE* f, uint64_t window_ms)
{
    scwa_report_ex(t, f, window_ms, 0);
}

/* HLE key: the NID. NID 0xFFFFFFFF would wrap the slot's "+ 1" to free, so
 * it shares a key with 0xFFFFFFFE (no such import exists in practice). */
static inline uint32_t scwa_hle_key(uint32_t nid) { return nid == 0xFFFFFFFFu ? 0xFFFFFFFEu : nid; }
""")
rep("""    return (uint64_t)v;
}

#ifdef __cplusplus""", """    return (uint64_t)v;
}

/* PS3_HLE_WAIT_MS, read once. 0 = off. */
static inline uint64_t scwa_hle_window_ms(void)
{
    static int64_t v = -1;
    if (v < 0) { const char* e = getenv("PS3_HLE_WAIT_MS"); v = (e && atoi(e) > 0) ? atoi(e) : 0; }
    return (uint64_t)v;
}

/* PS3_HLE_WAIT_MIN_US (default 20; 0 counts every call), read once, in ns. */
static inline uint64_t scwa_hle_min_ns(void)
{
    static int64_t v = -1;
    if (v < 0) { const char* e = getenv("PS3_HLE_WAIT_MIN_US"); v = (e && *e && atoi(e) >= 0) ? atoi(e) : 20; }
    return (uint64_t)v * 1000u;
}

#ifdef __cplusplus""")
p.write_text(s, encoding='utf-8', newline='\n')
print('patched', p)
