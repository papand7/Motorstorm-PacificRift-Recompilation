/* Screens (settings.ini "screens", PS3RECOMP_VK_SPAN): the settings.ini line (pc_settings.h pcs_screens,
 * pcs_screens_env) and the lens model the Hor+ hook relies on (main.cpp mspr_screens_film: the lens's
 * half-angle is atan(film * c / focal), so a film width times k is tan(half-angle) times k, the Hor+ view of
 * rsx_ms_hfov_deg with the vertical field unchanged). Host only. */
#include <math.h>
#include <stdio.h>
#include "pc_settings.h"
#include "rsx_multiscreen.h"

static int s_fail, s_n;
#define CHECK(c) do { s_n++; if (!(c)) { s_fail++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)

static void test_ini(void)
{
    CHECK(pcs_screens(NULL) == 1 && pcs_screens("") == 1);
    CHECK(pcs_screens("screens = Triple\n") == 3);
    CHECK(pcs_screens("screens=dual\r\n") == 2);
    CHECK(pcs_screens("  screens = SINGLE  \r\n") == 1);
    CHECK(pcs_screens("screens = 3\n") == 3 && pcs_screens("screens = 2\n") == 2 && pcs_screens("screens = 1\n") == 1);
    CHECK(pcs_screens("screens = Triple\nscreens = Dual\n") == 2);         /* the last line wins */
    CHECK(pcs_screens("screens = Triple\nscreens = Quad\n") == 3);         /* an unknown value is ignored */
    CHECK(pcs_screens("# screens = Triple\n; screens = Dual\n") == 1);     /* comments */
    CHECK(pcs_screens("screensaver = Triple\n") == 1);                    /* another key */
    CHECK(pcs_screens("display = Fullscreen\nresolution = 1080p\nscreens = Triple\nunlocktracks = On\n") == 3);
    CHECK(pcs_screens("screens = 33\n") == 1 && pcs_screens("screens =\n") == 1);
    CHECK(!pcs_screens_env(1) && !strcmp(pcs_screens_env(2), "2") && !strcmp(pcs_screens_env(3), "3"));
    CHECK(!pcs_screens_env(0) && !pcs_screens_env(4));
    /* the labels pcmenu_save writes read back */
    for (int n = 1; n <= 3; n++) {
        char line[64];
        snprintf(line, sizeof line, "screens = %s\n", k_pcs_screens[n - 1]);
        CHECK(pcs_screens(line) == n);
    }
    /* the variable is the one the backend reads */
    CHECK(rsx_ms_parse(pcs_screens_env(2)) == 2 && rsx_ms_parse(pcs_screens_env(3)) == 3 && !rsx_ms_parse(pcs_screens_env(1)));
    /* not a page row: the settings table has no "screens" key, so pcs_format / pcs_parse leave it alone */
    CHECK(pcs_find("screens") < 0);
}

static void test_lens_model(void)
{
    const double d2r = 3.14159265358979323846 / 180.0;
    /* film sizes and focal lengths of the camera-list kind (focal * 0.001), any constant c */
    const double films[][2] = { { 0.036, 0.02025 }, { 0.024, 0.0135 }, { 1.0, 0.5625 } };
    const double focals[] = { 0.018, 0.024, 0.035, 0.5 };
    const double c = 0.5;
    const float ks[] = { 2.0f, 3.0f, 2.7f, 1.0f };
    for (unsigned i = 0; i < sizeof films / sizeof films[0]; i++)
        for (unsigned j = 0; j < sizeof focals / sizeof focals[0]; j++)
            for (unsigned q = 0; q < sizeof ks / sizeof ks[0]; q++) {
                const double hx = atan(films[i][0] * c / focals[j]), hy = atan(films[i][1] * c / focals[j]);
                const double hx2 = atan(films[i][0] * ks[q] * c / focals[j]);   /* the hooked film width */
                CHECK(fabs(tan(hx2) / tan(hx) - ks[q]) < 1e-9);                  /* tan of the half-angle times k */
                CHECK(fabs(2.0 * hx2 / d2r - rsx_ms_hfov_deg(2.0 * hx / d2r, ks[q])) < 1e-9);
                /* the 16:9 films keep their shape: the widened view is the window's aspect at the same vertical field */
                if (i < 2) CHECK(fabs(tan(hx2) / tan(hy) - ks[q] * 16.0 / 9.0) < 1e-6);
            }
}

int main(void)
{
    test_ini();
    test_lens_model();
    if (s_fail) { printf("test_screens: %d of %d checks FAILED\n", s_fail, s_n); return 1; }
    printf("test_screens: all %d checks passed\n", s_n);
    return 0;
}
