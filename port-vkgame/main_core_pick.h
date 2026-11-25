/* PS3_MAIN_CORE=1: which physical core the guest main thread gets (main.cpp main_core_setup). Pure, so the choice
 * can be tested without the hardware (tests/test_main_core_pick.c).
 *
 * The frame is bound by the guest main thread (generated/analysis/roadto60_next CURRENT_CRITICAL_PATH.md), so it
 * wants the fastest core. Windows' efficiency class says which cores are the big ones on hybrid CPUs, but a CPU may
 * report one class for all of them while its cores still differ in clock: the Ryzen AI 9 HX 370 has 4 Zen 5 cores
 * (up to 5.1 GHz) and 8 Zen 5c cores (up to 3.3 GHz). Order: the highest efficiency class, then the highest maximum
 * clock (0 = unknown), taken as the best of the core's logical processors, then the highest core index (the choice
 * before the clock was considered). The firmware's preferred-core rank (SchedulingClass) is logged, not used: on a
 * Ryzen 5 9600X the preferred core 2 was slower than core 5 in 5 of 6 race pairs, median -3.0 fps (Kmc2-Kmc7,
 * generated/analysis/handheld30). */
#ifndef MAIN_CORE_PICK_H
#define MAIN_CORE_PICK_H

typedef struct {
    int core;      /* CoreIndex of the CPU set */
    int eff;       /* EfficiencyClass */
    int sched;     /* SchedulingClass (preferred-core rank): logged only */
    unsigned mhz;  /* maximum clock of this logical processor, 0 if unknown */
} main_core_lp;

/* The core for the main thread among n logical processors, or -1 if n is 0. */
static inline int main_core_pick(const main_core_lp* lp, int n)
{
    int best = -1, best_eff = -1, best_sched = -1;
    unsigned best_mhz = 0;
    for (int i = 0; i < n; i++) {
        const int eff = lp[i].eff, core = lp[i].core;
        int sched = lp[i].sched;
        unsigned mhz = lp[i].mhz;
        for (int j = 0; j < n; j++) {   /* a core's rank and clock: the best of its logical processors */
            if (lp[j].core != core) continue;
            if (lp[j].sched > sched) sched = lp[j].sched;
            if (lp[j].mhz > mhz) mhz = lp[j].mhz;
        }
        (void)best_sched;
        int better = eff != best_eff ? eff > best_eff : mhz != best_mhz ? mhz > best_mhz : core > best;
        if (better) { best = core; best_eff = eff; best_sched = sched; best_mhz = mhz; }
    }
    return best;
}

#endif
