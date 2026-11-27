/* cpu_placement.h: fast/slow cores, the main core, the role sets and the guest thread roles on made-up topologies:
 * Ryzen AI 9 HX 370 (4 Zen 5 + 8 Zen 5c, SMT), Intel 8P + 16E (P cores with Hyper-Threading), a uniform 8-core.
 *
 * Build (from the repository root):
 *   clang -std=gnu17 -O2 -Wall -Wextra -Iport-vkgame port-vkgame/tests/test_cpu_placement.c -o test_cpu_placement.exe */
#include "cpu_placement.h"

#include <stdio.h>

static int s_checks, s_failed;
#define CHECK(c) do { s_checks++; if (!(c)) { s_failed++; fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

static cpl_lp lp[CPL_MAX];
static unsigned char fast[CPL_MAX];
static cpl_plan_t plan;

/* HX 370: cores 0-3 Zen 5, 4-11 Zen 5c, two logical processors each (24) */
static int hx370(int eff_differs, int ctype, unsigned mhz_fast, unsigned mhz_slow)
{
    int n = 0;
    for (int c = 0; c < 12; c++)
        for (int t = 0; t < 2; t++)
            lp[n++] = (cpl_lp){ c, eff_differs ? (c < 4) : 0, c < 4 ? mhz_fast : mhz_slow, ctype ? (c < 4 ? 1 : 2) : 0 };
    return n;
}

static int count_core(int role, int core, int n)
{
    int k = 0;
    for (int i = 0; i < n; i++) k += plan.in[role][i] && lp[i].core == core;
    return k;
}

int main(void)
{
    int n, m, main_core;

    /* ---- HX 370, told apart by the clock only (one efficiency class, no core type) */
    n = hx370(0, 0, 5100, 3300);
    m = cpl_classify(lp, n, NULL, fast);
    CHECK(m == CPL_BY_CLOCK);
    for (int i = 0; i < n; i++) CHECK(fast[i] == (lp[i].core < 4));
    main_core = cpl_pick_main(lp, n, fast);
    CHECK(main_core == 3);
    CHECK(cpl_plan(lp, n, fast, m, main_core, &plan) == 4);
    CHECK(plan.count[CPL_ROLE_MAIN] == 2 && count_core(CPL_ROLE_MAIN, 3, n) == 2);
    CHECK(plan.count[CPL_ROLE_RENDER] == 6);                     /* Zen 5 cores 0-2 */
    for (int c = 0; c < 3; c++) CHECK(count_core(CPL_ROLE_RENDER, c, n) == 2);
    CHECK(count_core(CPL_ROLE_RENDER, 3, n) == 0);
    CHECK(plan.count[CPL_ROLE_WORKER] == 22);                    /* everything but the main core */
    CHECK(count_core(CPL_ROLE_WORKER, 3, n) == 0);
    CHECK(plan.count[CPL_ROLE_BACKGROUND] == 16);                /* the Zen 5c cores only */
    for (int c = 0; c < 4; c++) CHECK(count_core(CPL_ROLE_BACKGROUND, c, n) == 0);
    /* nothing of the main core is in any other set */
    for (int i = 0; i < n; i++)
        if (lp[i].core == 3) CHECK(!plan.in[CPL_ROLE_RENDER][i] && !plan.in[CPL_ROLE_WORKER][i] && !plan.in[CPL_ROLE_BACKGROUND][i]);

    /* ---- HX 370 with the same clock reported for every core (base clock) but the CPUID core type */
    n = hx370(0, 1, 2000, 2000);
    CHECK(cpl_classify(lp, n, NULL, fast) == CPL_BY_TYPE);
    for (int i = 0; i < n; i++) CHECK(fast[i] == (lp[i].core < 4));
    CHECK(cpl_pick_main(lp, n, fast) == 3);
    /* ... and with nothing but the clock at base: uniform (the HX 370 log must say which rule applied) */
    n = hx370(0, 0, 2000, 2000);
    CHECK(cpl_classify(lp, n, NULL, fast) == CPL_UNIFORM);
    /* ... where PS3_CPU_SLOW_CORES names the Zen 5c cores */
    unsigned char slow[CPL_MAX];
    CHECK(cpl_parse_cores("4-11", slow, CPL_MAX) == 8);
    CHECK(cpl_classify(lp, n, slow, fast) == CPL_BY_LIST);
    for (int i = 0; i < n; i++) CHECK(fast[i] == (lp[i].core < 4));
    CHECK(cpl_parse_cores("4,5, 8-11", slow, CPL_MAX) == 6 && slow[4] && slow[5] && !slow[6] && slow[11]);
    /* a list naming every core, or none, does not apply */
    CHECK(cpl_parse_cores("0-11", slow, CPL_MAX) == 12);
    CHECK(cpl_classify(lp, n, slow, fast) == CPL_UNIFORM);
    /* the class wins over the clock and the type */
    n = hx370(1, 1, 5100, 3300);
    CHECK(cpl_classify(lp, n, NULL, fast) == CPL_BY_CLASS);
    /* small clock differences (preferred-core boost on a uniform part) are not a slow core */
    n = hx370(0, 0, 5100, 4800);
    CHECK(cpl_classify(lp, n, NULL, fast) == CPL_UNIFORM);

    /* ---- Intel 8P + 16E: P cores 0-7 with Hyper-Threading (16 logical), E cores 8-23 (16 logical), class 1 / 0 */
    n = 0;
    for (int c = 0; c < 8; c++) for (int t = 0; t < 2; t++) lp[n++] = (cpl_lp){ c, 1, c == 5 ? 5800u : 5400u, 1 };
    for (int c = 8; c < 24; c++) lp[n++] = (cpl_lp){ c, 0, 4300, 2 };
    m = cpl_classify(lp, n, NULL, fast);
    CHECK(m == CPL_BY_CLASS);
    main_core = cpl_pick_main(lp, n, fast);
    CHECK(main_core == 5);                                       /* the P core that boosts highest */
    CHECK(cpl_plan(lp, n, fast, m, main_core, &plan) == 4);
    CHECK(plan.count[CPL_ROLE_MAIN] == 2);
    CHECK(plan.count[CPL_ROLE_RENDER] == 14);                    /* the other 7 P cores */
    CHECK(plan.count[CPL_ROLE_WORKER] == 30);
    CHECK(plan.count[CPL_ROLE_BACKGROUND] == 16);                /* the E cores */
    for (int i = 0; i < n; i++) CHECK(plan.in[CPL_ROLE_BACKGROUND][i] == (lp[i].core >= 8));
    /* PS3_MAIN_CORE off: the main thread shares the P cores, the workers keep the default */
    CHECK(cpl_plan(lp, n, fast, m, -1, &plan) == 3);
    CHECK(plan.count[CPL_ROLE_MAIN] == 16 && plan.count[CPL_ROLE_WORKER] == 0 && plan.count[CPL_ROLE_RENDER] == 16);
    CHECK(plan.count[CPL_ROLE_BACKGROUND] == 16);

    /* ---- uniform 8-core with SMT: only the main core's reservation, as PS3_MAIN_CORE alone */
    n = 0;
    for (int c = 0; c < 8; c++) for (int t = 0; t < 2; t++) lp[n++] = (cpl_lp){ c, 0, 5000, 1 };
    m = cpl_classify(lp, n, NULL, fast);
    CHECK(m == CPL_UNIFORM);
    main_core = cpl_pick_main(lp, n, fast);
    CHECK(main_core == 7);                                       /* main_core_pick's choice */
    CHECK(cpl_plan(lp, n, fast, m, main_core, &plan) == 2);
    CHECK(plan.count[CPL_ROLE_MAIN] == 2 && plan.count[CPL_ROLE_WORKER] == 14);
    CHECK(plan.count[CPL_ROLE_RENDER] == 0 && plan.count[CPL_ROLE_BACKGROUND] == 0);
    CHECK(cpl_plan(lp, n, fast, m, -1, &plan) == 0);             /* nothing at all without a main core */

    /* ---- one fast core (a made-up 1 + 7): render shares the workers' set */
    n = 0;
    for (int c = 0; c < 8; c++) lp[n++] = (cpl_lp){ c, c == 0, 0, 0 };
    m = cpl_classify(lp, n, NULL, fast);
    main_core = cpl_pick_main(lp, n, fast);
    CHECK(main_core == 0);
    cpl_plan(lp, n, fast, m, main_core, &plan);
    CHECK(plan.count[CPL_ROLE_RENDER] == 7 && plan.count[CPL_ROLE_BACKGROUND] == 7);

    /* ---- guest thread names (MotorStorm 1.00 run Kmed38) */
    CHECK(cpl_guest_role("fios mediathread") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("fios scheduler") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("avStream::StreamCodecMP3::ProcessThread") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("Multistream PPU Update Thread") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("Bink Audio Thread") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("Bink IO Thread") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("OpenMovieAsyncTask") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("FpPadThread") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("VoiceChat") == CPL_ROLE_BACKGROUND);
    CHECK(cpl_guest_role("JobBatchHandler") == CPL_ROLE_WORKER);
    CHECK(cpl_guest_role("AsyncRenderThread") == CPL_ROLE_WORKER);
    CHECK(cpl_guest_role("hkSpuUtil Helper") == CPL_ROLE_WORKER);
    CHECK(cpl_guest_role("workerThread") == CPL_ROLE_WORKER);
    CHECK(cpl_guest_role("16f41d80") == CPL_ROLE_WORKER);
    CHECK(cpl_guest_role("") == CPL_ROLE_WORKER && cpl_guest_role(NULL) == CPL_ROLE_WORKER);

    /* ---- the setting's values */
    CHECK(cpl_mode_on("Auto") && cpl_mode_on("auto") && cpl_mode_on("1") && cpl_mode_on("ON"));
    CHECK(!cpl_mode_on("Off") && !cpl_mode_on("0") && !cpl_mode_on("") && !cpl_mode_on(NULL) && !cpl_mode_on("autox"));

    /* ---- CPUID core type */
    unsigned z[4] = { 0, 0, 0, 0 }, a26[4] = { 0, 0, 0, 0 }, i1a[4] = { 0, 0, 0, 0 };
    a26[1] = 0x00010000u;                                        /* AMD EBX[31:28] = 0: performance */
    CHECK(cpl_core_type(1, 0x10, 0x80000026u, z, a26, 0) == 1);
    a26[1] = 0x10010000u;                                        /* 1: efficiency (Zen 5c) */
    CHECK(cpl_core_type(1, 0x10, 0x80000026u, z, a26, 0) == 2);
    CHECK(cpl_core_type(1, 0x10, 0x80000021u, z, a26, 0) == 0);  /* no leaf 0x80000026 */
    i1a[0] = 0x40000001u;
    CHECK(cpl_core_type(0, 0x20, 0x80000008u, i1a, z, 1u << 15) == 1);
    i1a[0] = 0x20000001u;
    CHECK(cpl_core_type(0, 0x20, 0x80000008u, i1a, z, 1u << 15) == 2);
    CHECK(cpl_core_type(0, 0x20, 0x80000008u, i1a, z, 0) == 0);  /* not hybrid */
    CHECK(cpl_core_type(0, 0x16, 0x80000008u, i1a, z, 1u << 15) == 0);

    printf("test_cpu_placement: %d checks, %d failed\n", s_checks, s_failed);
    return s_failed ? 1 : 0;
}
