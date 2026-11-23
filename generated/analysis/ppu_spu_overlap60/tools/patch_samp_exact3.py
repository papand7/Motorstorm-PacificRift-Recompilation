"""overlap60 step 3, on top of patch_samp_exact.py + patch_samp_exact2.py + the PS3_SAMPLE_REPORT_MS edit (ISOLATED copy).
With PS3_SAMPLE_EXACT=1 and PS3_SAMPLE_MAIN set:
  - the main thread is sampled through one cached handle (no process-wide thread snapshot per sample), and the
    period is kept with a high-resolution waitable timer (Sleep(2) is ~15.6 ms on the default timer): Kksr114 got
    ~20-40 samples/s instead of ~500.
  - every PS3_SAMPLE_DUMP interval line carries the critical-path trace's clock ("ft_us <us>", -1 when no trace runs),
    so 1 s intervals line up with trace seconds.
usage: py -3 patch_samp_exact3.py <ppu_loader.cpp>"""
import sys

p = sys.argv[1]
s = open(p, encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a[:80]
    s = s.replace(a, b)


body_old = """                if (SuspendThread(h) != (DWORD)-1) {
                    CONTEXT c; c.ContextFlags = s_samp_exact ? (CONTEXT_CONTROL | CONTEXT_INTEGER) : CONTEXT_CONTROL;
                    if (GetThreadContext(h, &c)) {
                        s_samp_total++;
                        uint32_t g = samp_lookup((uintptr_t)c.Rip);
                        int kind = 0;
                        if (!g && s_samp_main > 0) {
                            int outside = 1;
                            if (s_samp_exact && s_pd_n) { g = samp_unwind_guest(&c, &outside); kind = 1; }
                            if (!g && outside) { g = samp_stack_guest(h, &c); kind = 2; }
                        }
                        if (g) { s_samp_guest++; if (s_samp_exact) samp_hit_kind(g, kind); else samp_hit(g); samp_tid_hit(te.th32ThreadID);
                                 samp_tid2(te.th32ThreadID, 1, 0); }
                        else { int nt = samp_mod_hit((uintptr_t)c.Rip);
                               if (!nt) samp_rva_hit((uintptr_t)c.Rip);
                               samp_tid2(te.th32ThreadID, 0, nt); }
                    }
                    ResumeThread(h);
                }"""
rep(body_old, "                samp_one(h, te.th32ThreadID);")

fn = """/* One sample of thread h (tid): suspend, read the context, attribute, resume. */
static void samp_one(HANDLE h, DWORD tid)
{
    if (SuspendThread(h) == (DWORD)-1) return;
    CONTEXT c; c.ContextFlags = s_samp_exact ? (CONTEXT_CONTROL | CONTEXT_INTEGER) : CONTEXT_CONTROL;
    if (GetThreadContext(h, &c)) {
        s_samp_total++;
        uint32_t g = samp_lookup((uintptr_t)c.Rip);
        int kind = 0;
        if (!g && s_samp_main > 0) {
            int outside = 1;
            if (s_samp_exact && s_pd_n) { g = samp_unwind_guest(&c, &outside); kind = 1; }
            if (!g && outside) { g = samp_stack_guest(h, &c); kind = 2; }
        }
        if (g) { s_samp_guest++; if (s_samp_exact) samp_hit_kind(g, kind); else samp_hit(g); samp_tid_hit(tid);
                 samp_tid2(tid, 1, 0); }
        else { int nt = samp_mod_hit((uintptr_t)c.Rip);
               if (!nt) samp_rva_hit((uintptr_t)c.Rip);
               samp_tid2(tid, 0, nt); }
    }
    ResumeThread(h);
}

/* The sampling period: a high-resolution waitable timer with PS3_SAMPLE_EXACT (Sleep rounds up to the 15.6 ms tick). */
static void samp_wait(unsigned period)
{
    static HANDLE t = (HANDLE)-1;
    if (t == (HANDLE)-1) t = s_samp_exact ? CreateWaitableTimerExW(NULL, NULL, 0x00000002u /* HIGH_RESOLUTION */, TIMER_ALL_ACCESS) : NULL;
    if (t) {
        LARGE_INTEGER due; due.QuadPart = -(LONGLONG)period * 10000;
        if (SetWaitableTimer(t, &due, 0, NULL, NULL, FALSE)) { WaitForSingleObject(t, INFINITE); return; }
    }
    Sleep(period);
}

static DWORD WINAPI samp_thread(LPVOID p)
{"""
rep("static DWORD WINAPI samp_thread(LPVOID p)\n{", fn)

rep("""    for (;;) {
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        if (snap != INVALID_HANDLE_VALUE) {""", """    for (;;) {
        static HANDLE s_main_h;
        if (s_samp_exact && s_samp_main > 0) {   /* main thread only: one cached handle, no snapshot */
            if (!s_main_h) s_main_h = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, s_samp_boot_tid);
            if (s_main_h) samp_one(s_main_h, s_samp_boot_tid);
        }
        HANDLE snap = (s_samp_exact && s_samp_main > 0) ? INVALID_HANDLE_VALUE : CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        if (snap != INVALID_HANDLE_VALUE) {""")
rep("        Sleep(period);\n        if (GetTickCount64() >= next_report) {", "        samp_wait(period);\n        if (GetTickCount64() >= next_report) {")

rep("""    fprintf(f, "T %llu total %llu guest %llu\\n", t_ms, (unsigned long long)s_samp_total, (unsigned long long)s_samp_guest);""",
    """    const double ft_us = g_ps3_ft.base ? (double)(ps3_ft_now() - g_ps3_ft.base) / 1e3 : -1.0;
    fprintf(f, "T %llu total %llu guest %llu ft_us %.0f\\n", t_ms, (unsigned long long)s_samp_total, (unsigned long long)s_samp_guest, ft_us);""")
open(p, 'w', encoding='utf-8').write(s)
print('patched', p)
