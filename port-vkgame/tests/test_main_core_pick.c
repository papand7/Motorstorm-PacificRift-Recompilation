/* main_core_pick.h: the main thread's core on uniform, hybrid-by-class and hybrid-by-clock CPUs.
 *
 * Build (from the repository root):
 *   clang -std=gnu17 -O2 -Wall -Wextra -Iport-vkgame port-vkgame/tests/test_main_core_pick.c -o test_main_core_pick.exe */
#include "main_core_pick.h"

#include <stdio.h>

static int s_checks, s_failed;
#define CHECK(c) do { s_checks++; if (!(c)) { s_failed++; fprintf(stderr, "FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

int main(void)
{
    main_core_lp lp[32];
    int n;

    /* Ryzen 5 9600X: 6 uniform cores, SMT, one class, one clock: the last core, as before */
    n = 0;
    for (int c = 0; c < 6; c++) for (int t = 0; t < 2; t++) lp[n++] = (main_core_lp){ c, 0, 0, 5400 };
    CHECK(main_core_pick(lp, n) == 5);
    /* no clock known (0): the same */
    for (int i = 0; i < n; i++) lp[i].mhz = 0;
    CHECK(main_core_pick(lp, n) == 5);

    /* Ryzen AI 9 HX 370 reported with one class: cores 0-3 Zen 5 (5100), 4-11 Zen 5c (3300); the last Zen 5 core */
    n = 0;
    for (int c = 0; c < 12; c++) for (int t = 0; t < 2; t++) lp[n++] = (main_core_lp){ c, 0, 0, c < 4 ? 5100u : 3300u };
    CHECK(main_core_pick(lp, n) == 3);
    /* the same with the classes reported (Zen 5 = 1): still core 3 */
    for (int i = 0; i < n; i++) lp[i].eff = lp[i].core < 4;
    CHECK(main_core_pick(lp, n) == 3);
    /* the class wins over the clock (an efficient core can never be preferred by a higher number) */
    lp[n - 1].mhz = 6000;
    CHECK(main_core_pick(lp, n) == 3);

    /* Intel hybrid: P cores 0-5 class 1, E cores 6-13 class 0; one P core boosts higher (favoured core 2) */
    n = 0;
    for (int c = 0; c < 6; c++) for (int t = 0; t < 2; t++) lp[n++] = (main_core_lp){ c, 1, 0, c == 2 ? 5600u : 5400u };
    for (int c = 6; c < 14; c++) lp[n++] = (main_core_lp){ c, 0, 0, 4300 };
    CHECK(main_core_pick(lp, n) == 2);
    /* only one logical processor of a core reports its clock: the core still counts with it */
    lp[4].mhz = 0;   /* core 2, thread 0 */
    CHECK(main_core_pick(lp, n) == 2);

    /* the preferred-core rank is not used (Kmc2-Kmc7: slower on the 9600X): the 9600X with core 2 ranked first keeps core 5 */
    n = 0;
    for (int c = 0; c < 6; c++) for (int t = 0; t < 2; t++) lp[n++] = (main_core_lp){ c, 0, c == 2 ? 4 : 1, 3900 };
    CHECK(main_core_pick(lp, n) == 5);

    CHECK(main_core_pick(lp, 0) == -1);
    printf("test_main_core_pick: %d checks, %d failed\n", s_checks, s_failed);
    return s_failed ? 1 : 0;
}
