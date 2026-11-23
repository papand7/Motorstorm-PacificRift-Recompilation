"""overlap60 step 2, on top of patch_samp_exact.py (ISOLATED copy only).
With PS3_SAMPLE_EXACT=1:
  - main-thread samples outside guest code are credited by an exact unwind (RtlVirtualUnwind over the exe's own
    .pdata, no loader lock) to the first lifted frame; RIPs outside the exe (ntdll sleeps) fall back to the old
    stack scan. Each sample is tagged direct / unwind / scan.
  - PS3_SAMPLE_DUMP=<file>: every report appends the FULL per-function histogram of that interval
    ("T <ms> total <n> guest <n>" then "<g hex> <direct> <unwind> <scan>"), then all counts restart.
usage: py -3 patch_samp_exact2.py <ppu_loader.cpp>"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)


rep("static uint32_t   s_pd_n;\n", "static uint32_t   s_pd_n;\nstatic const RUNTIME_FUNCTION* s_pd_rf;   /* the image's own table, for RtlVirtualUnwind */\n")
rep("    s_pd_n = n; s_pd_base = (uintptr_t)b;\n", "    s_pd_n = n; s_pd_base = (uintptr_t)b; s_pd_rf = rf;\n")

# per-slot counters by attribution kind; samp_hit returns the slot
rep("static void samp_hit(uint32_t g)\n{", """static uint64_t s_samp_kd[SAMP_SLOTS], s_samp_ku[SAMP_SLOTS], s_samp_ks[SAMP_SLOTS];   /* direct, unwind, scan */
static int samp_hit_slot(uint32_t g);
static void samp_hit(uint32_t g) { (void)samp_hit_slot(g); }
static void samp_hit_kind(uint32_t g, int kind)
{
    int k = samp_hit_slot(g);
    if (k < 0) return;
    if (kind == 0) s_samp_kd[k]++; else if (kind == 1) s_samp_ku[k]++; else s_samp_ks[k]++;
}
static int samp_hit_slot(uint32_t g)
{""")
rep("""        if (s_samp_ct[k] == 0) { s_samp_fn[k] = g; s_samp_ct[k] = 1; return; }
        if (s_samp_fn[k] == g) { s_samp_ct[k]++; return; }
    }
}""", """        if (s_samp_ct[k] == 0 && s_samp_kd[k] + s_samp_ku[k] + s_samp_ks[k] == 0) { s_samp_fn[k] = g; s_samp_ct[k] = 1; return (int)k; }
        if (s_samp_fn[k] == g) { s_samp_ct[k]++; return (int)k; }
    }
    return -1;
}""")

# exact unwind walk
rep("static uint32_t samp_stack_guest(HANDLE h, const CONTEXT* c)\n{", r"""/* first lifted frame above c by exact unwinding, 0 if none; *outside = 1 when the
 * walk left the exe (ntdll etc.), where the caller falls back to the scan */
static uint32_t samp_unwind_guest(const CONTEXT* c0, int* outside)
{
    CONTEXT c = *c0;
    *outside = 0;
    __try {
        for (int d = 0; d < 64; d++) {
            uintptr_t rip = (uintptr_t)c.Rip;
            if (rip < s_pd_lo || rip >= s_pd_hi) { if (d == 0) *outside = 1; return 0; }
            uintptr_t at = d ? rip - 1 : rip;   /* a return address may sit just past its call */
            if (d) { uint32_t g = samp_lookup(at); if (g) return g; }
            int64_t pi = samp_pd_find(at);
            if (pi < 0) {                        /* leaf: return address on top of the stack */
                c.Rip = *(const DWORD64*)c.Rsp; c.Rsp += 8;
            } else {
                PVOID hd = 0; DWORD64 est = 0;
                RtlVirtualUnwind(UNW_FLAG_NHANDLER, (DWORD64)s_pd_base, (DWORD64)rip,
                                 (PRUNTIME_FUNCTION)&s_pd_rf[pi], &c, &hd, &est, NULL);
            }
            if (!c.Rip) return 0;
        }
    } __except (1) { return 0; }
    return 0;
}

static uint32_t samp_stack_guest(HANDLE h, const CONTEXT* c)
{""")

rep("                    CONTEXT c; c.ContextFlags = CONTEXT_CONTROL;",
    "                    CONTEXT c; c.ContextFlags = s_samp_exact ? (CONTEXT_CONTROL | CONTEXT_INTEGER) : CONTEXT_CONTROL;")
rep("""                        if (!g && s_samp_main > 0) g = samp_stack_guest(h, &c);
                        if (g) { s_samp_guest++; samp_hit(g); samp_tid_hit(te.th32ThreadID);""",
"""                        int kind = 0;
                        if (!g && s_samp_main > 0) {
                            int outside = 1;
                            if (s_samp_exact && s_pd_n) { g = samp_unwind_guest(&c, &outside); kind = 1; }
                            if (!g && outside) { g = samp_stack_guest(h, &c); kind = 2; }
                        }
                        if (g) { s_samp_guest++; if (s_samp_exact) samp_hit_kind(g, kind); else samp_hit(g); samp_tid_hit(te.th32ThreadID);""")

# full dump at each report
rep("static void samp_report(void)\n{", r"""static void samp_dump(unsigned long long t_ms)
{
    static FILE* f = (FILE*)-1;
    if (f == (FILE*)-1) { const char* e = getenv("PS3_SAMPLE_DUMP"); f = (e && *e) ? fopen(e, "a") : NULL; }
    if (!f) return;
    fprintf(f, "T %llu total %llu guest %llu\n", t_ms, (unsigned long long)s_samp_total, (unsigned long long)s_samp_guest);
    for (int k = 0; k < SAMP_SLOTS; k++)
        if (s_samp_kd[k] + s_samp_ku[k] + s_samp_ks[k])
            fprintf(f, "%08X %llu %llu %llu\n", s_samp_fn[k], (unsigned long long)s_samp_kd[k],
                    (unsigned long long)s_samp_ku[k], (unsigned long long)s_samp_ks[k]);
    fflush(f);
    memset(s_samp_kd, 0, sizeof s_samp_kd); memset(s_samp_ku, 0, sizeof s_samp_ku); memset(s_samp_ks, 0, sizeof s_samp_ks);
}

static void samp_report(void)
{""")
rep("""            samp_report();""", """            if (s_samp_exact) samp_dump(GetTickCount64() - t0);
            samp_report();""")
open(p, 'w', encoding='utf-8').write(s)
print('patched', p)
