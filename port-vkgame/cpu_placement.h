/* CPU Thread Placement (settings.ini "threadplace = Auto|Off", PS3_CPU_PLACEMENT=auto|off; Off by default): on a CPU
 * with fast and slow cores (AMD Zen 5 + Zen 5c, Intel P + E cores) the guest main thread and the renderer keep the
 * fast cores and the threads nothing in the frame waits on stay on the slow ones. Pure, so the decisions can be tested
 * on made-up topologies (tests/test_cpu_placement.c); main.cpp main_core_setup reads the machine and applies the plan
 * with Windows CPU sets.
 *
 * Which cores are fast (cpl_classify), the first rule that tells cores apart:
 *   1. PS3_CPU_SLOW_CORES=<core list> (testing, or a CPU the rules below cannot read);
 *   2. Windows' EfficiencyClass (Intel hybrid; the higher class is fast);
 *   3. the core type CPUID reports on the core itself (AMD leaf 0x80000026 EBX[31:28]: 0 performance, 1 efficiency;
 *      Intel leaf 0x1A EAX[31:24]: 0x40 Core, 0x20 Atom);
 *   4. the maximum clock (CallNtPowerInformation), when the fastest core is at least 15 % above the slowest: fast
 *      is at or above the middle (HX 370: Zen 5 up to 5.1 GHz, Zen 5c up to 3.3 GHz).
 * None of them: a uniform CPU (Ryzen 5 9600X), and Auto changes nothing beyond PS3_MAIN_CORE.
 *
 * The plan (cpl_plan), by role, as sets of logical processors:
 *   main        the main core (main_core_pick.h, among the fast cores): the guest main thread alone (PS3_MAIN_CORE);
 *   render      the fast cores except the main core: the frame clock / FIFO walker thread and the backend thread;
 *   worker      the process default, every core except the main core: SPU threads, SPURS, the guest's JobBatch,
 *               Havok helper and render threads (the main thread waits on them: they may use any free core);
 *   background  the slow cores: audio mixing, background shader compiles, and the guest's file (fios), stream,
 *               movie (Bink), pad, network and voice threads (cpl_guest_role). They can never take a fast core.
 * A role with an empty set (no slow cores, one fast core) keeps the process default. */
#ifndef CPU_PLACEMENT_H
#define CPU_PLACEMENT_H

#include <string.h>
#include "main_core_pick.h"

#define CPL_MAX 256

typedef struct {
    int core;         /* CoreIndex of the CPU set */
    int eff;          /* EfficiencyClass */
    unsigned mhz;     /* maximum clock, 0 if unknown */
    int ctype;        /* CPUID core type: 0 unknown, 1 performance, 2 efficiency */
} cpl_lp;

enum { CPL_UNIFORM = 0, CPL_BY_LIST = 1, CPL_BY_CLASS = 2, CPL_BY_TYPE = 3, CPL_BY_CLOCK = 4 };
enum { CPL_ROLE_MAIN = 0, CPL_ROLE_RENDER = 1, CPL_ROLE_WORKER = 2, CPL_ROLE_BACKGROUND = 3, CPL_ROLES = 4 };

static inline const char* cpl_method_name(int m)
{
    return m == CPL_BY_LIST ? "PS3_CPU_SLOW_CORES" : m == CPL_BY_CLASS ? "efficiency class" :
           m == CPL_BY_TYPE ? "CPUID core type" : m == CPL_BY_CLOCK ? "maximum clock" : "uniform";
}

/* "4-11" or "4,5,8-11" -> slow[core] = 1; returns the number of cores named. */
static inline int cpl_parse_cores(const char* s, unsigned char* slow, int max)
{
    int n = 0;
    memset(slow, 0, (size_t)max);
    while (s && *s) {
        while (*s == ' ' || *s == ',') s++;
        if (*s < '0' || *s > '9') break;
        int a = 0, b;
        while (*s >= '0' && *s <= '9') a = a * 10 + (*s++ - '0');
        b = a;
        if (*s == '-') {
            s++;
            b = 0;
            while (*s >= '0' && *s <= '9') b = b * 10 + (*s++ - '0');
        }
        for (int c = a; c <= b && c < max; c++)
            if (!slow[c]) { slow[c] = 1; n++; }
    }
    return n;
}

/* fast[i] = 1 for logical processor i on a fast core; returns the rule used (CPL_*). slow_cores: per core index, the
 * PS3_CPU_SLOW_CORES list, or NULL. A rule that would leave no fast core or no slow core does not apply. */
static inline int cpl_classify(const cpl_lp* lp, int n, const unsigned char* slow_cores, unsigned char* fast)
{
    for (int i = 0; i < n; i++) fast[i] = 1;
    if (n <= 0) return CPL_UNIFORM;
    int nf, ns;
#define CPL_COUNT() do { nf = ns = 0; for (int i_ = 0; i_ < n; i_++) { if (fast[i_]) nf++; else ns++; } } while (0)
    if (slow_cores) {
        for (int i = 0; i < n; i++) fast[i] = !(lp[i].core >= 0 && lp[i].core < CPL_MAX && slow_cores[lp[i].core]);
        CPL_COUNT();
        if (nf && ns) return CPL_BY_LIST;
    }
    int emin = lp[0].eff, emax = lp[0].eff;
    for (int i = 1; i < n; i++) { if (lp[i].eff < emin) emin = lp[i].eff; if (lp[i].eff > emax) emax = lp[i].eff; }
    if (emin != emax) {
        for (int i = 0; i < n; i++) fast[i] = lp[i].eff == emax;
        return CPL_BY_CLASS;
    }
    int perf = 0, effc = 0;
    for (int i = 0; i < n; i++) { perf += lp[i].ctype == 1; effc += lp[i].ctype == 2; }
    if (perf && effc) {
        for (int i = 0; i < n; i++) fast[i] = lp[i].ctype != 2;
        return CPL_BY_TYPE;
    }
    /* the clock: a core's clock is the best of its logical processors; every core must report one */
    unsigned cmin = ~0u, cmax = 0;
    for (int i = 0; i < n; i++) {
        unsigned m = 0;
        for (int j = 0; j < n; j++) if (lp[j].core == lp[i].core && lp[j].mhz > m) m = lp[j].mhz;
        if (!m) { cmax = 0; break; }
        if (m < cmin) cmin = m;
        if (m > cmax) cmax = m;
    }
    if (cmax && (unsigned long long)cmax * 100u >= (unsigned long long)cmin * 115u) {
        const unsigned mid = cmin + (cmax - cmin) / 2u;
        for (int i = 0; i < n; i++) {
            unsigned m = 0;
            for (int j = 0; j < n; j++) if (lp[j].core == lp[i].core && lp[j].mhz > m) m = lp[j].mhz;
            fast[i] = m >= mid;
        }
        return CPL_BY_CLOCK;
    }
    for (int i = 0; i < n; i++) fast[i] = 1;
    return CPL_UNIFORM;
#undef CPL_COUNT
}

/* The main thread's core: main_core_pick among the fast cores only. */
static inline int cpl_pick_main(const cpl_lp* lp, int n, const unsigned char* fast)
{
    main_core_lp m[CPL_MAX];
    int k = 0;
    for (int i = 0; i < n && k < CPL_MAX; i++)
        if (fast[i]) m[k++] = (main_core_lp){ lp[i].core, lp[i].eff, 0, lp[i].mhz };
    return main_core_pick(m, k);
}

typedef struct {
    int method;                         /* CPL_* (cpl_classify) */
    int main_core;                      /* -1: none reserved */
    unsigned char in[CPL_ROLES][CPL_MAX];   /* in[role][i]: logical processor i belongs to the role's set */
    int count[CPL_ROLES];               /* 0: the role keeps the process default */
} cpl_plan_t;

/* The plan for n logical processors (fast from cpl_classify), the main core main_core (-1: PS3_MAIN_CORE off).
 * Uniform CPUs: only the main core's reservation (as PS3_MAIN_CORE alone). Returns the number of roles with a set. */
static inline int cpl_plan(const cpl_lp* lp, int n, const unsigned char* fast, int method, int main_core, cpl_plan_t* p)
{
    memset(p, 0, sizeof *p);
    p->method = method;
    p->main_core = main_core;
    if (n > CPL_MAX) n = CPL_MAX;
    const int hybrid = method != CPL_UNIFORM;
    for (int i = 0; i < n; i++) {
        const int on_main = main_core >= 0 && lp[i].core == main_core;
        p->in[CPL_ROLE_MAIN][i] = (unsigned char)on_main;
        p->in[CPL_ROLE_WORKER][i] = (unsigned char)!on_main;
        p->in[CPL_ROLE_RENDER][i] = (unsigned char)(hybrid && fast[i] && !on_main);
        p->in[CPL_ROLE_BACKGROUND][i] = (unsigned char)(hybrid && !fast[i] && !on_main);
    }
    if (main_core < 0 && hybrid)   /* no reserved core: the main thread on the fast cores, shared */
        for (int i = 0; i < n; i++) p->in[CPL_ROLE_MAIN][i] = fast[i];
    for (int r = 0; r < CPL_ROLES; r++)
        for (int i = 0; i < n; i++) p->count[r] += p->in[r][i];
    /* a set that is every processor, or none, keeps the default */
    if (main_core < 0) p->count[CPL_ROLE_WORKER] = 0;
    for (int r = 0; r < CPL_ROLES; r++) if (p->count[r] == n) p->count[r] = 0;
    if (!p->count[CPL_ROLE_RENDER] && hybrid && p->count[CPL_ROLE_WORKER]) {   /* one fast core: render with the workers */
        memcpy(p->in[CPL_ROLE_RENDER], p->in[CPL_ROLE_WORKER], (size_t)n);
        p->count[CPL_ROLE_RENDER] = p->count[CPL_ROLE_WORKER];
    }
    int roles = 0;
    for (int r = 0; r < CPL_ROLES; r++) roles += p->count[r] > 0;
    return roles;
}

/* A guest PPU thread's role by its name (sys_ppu_thread_create): BACKGROUND for the file, stream, movie, pad, network
 * and voice threads; WORKER (the process default) for everything else, among them JobBatchHandler, AsyncRenderThread,
 * workerThread, "hkSpuUtil Helper" and unnamed threads, which the main thread waits on. */
static inline int cpl_guest_role(const char* name)
{
    static const char* const k_bg[] = {
        "fios ", "avStream::", "Multistream", "Bink ", "OpenMovieAsyncTask", "PS Button Handler", "FpPadThread",
        "Monitor Network", "Rumble", "VoiceChat", "UpInterface",
    };
    if (!name || !*name) return CPL_ROLE_WORKER;
    for (size_t i = 0; i < sizeof k_bg / sizeof k_bg[0]; i++)
        if (!strncmp(name, k_bg[i], strlen(k_bg[i]))) return CPL_ROLE_BACKGROUND;
    return CPL_ROLE_WORKER;
}

/* settings.ini / PS3_CPU_PLACEMENT value: 1 for Auto (auto, on, 1), 0 for anything else. */
static inline int cpl_mode_on(const char* v)
{
    if (!v || !*v) return 0;
    char t[8];
    size_t k = 0;
    for (; v[k] && k < sizeof t - 1; k++) t[k] = (char)(v[k] >= 'A' && v[k] <= 'Z' ? v[k] + 32 : v[k]);
    t[k] = 0;
    return !strcmp(t, "auto") || !strcmp(t, "on") || !strcmp(t, "1");
}

/* CPUID core type of the processor this runs on: 1 performance, 2 efficiency, 0 unknown. vendor_amd: the vendor
 * string; max_ext / max_std: the highest extended / standard leaf; r: the leaf's registers (EAX..EDX). Pure: the
 * caller runs CPUID (pinned to the processor) and passes the values. */
static inline int cpl_core_type(int vendor_amd, unsigned max_std, unsigned max_ext,
                                const unsigned leaf1a[4], const unsigned leaf80000026[4], unsigned leaf7_edx)
{
    if (vendor_amd) {
        if (max_ext < 0x80000026u) return 0;
        const unsigned t = leaf80000026[1] >> 28;   /* EBX[31:28] */
        return t == 0 ? 1 : t == 1 ? 2 : 0;
    }
    if (max_std < 0x1Au || !(leaf7_edx & (1u << 15))) return 0;   /* not a hybrid part */
    const unsigned t = leaf1a[0] >> 24;   /* EAX[31:24] */
    return t == 0x40 ? 1 : t == 0x20 ? 2 : 0;
}

#endif
