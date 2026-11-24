/* rsx_shadow_off.h: MSPR_NO_SHADOWS applies only with the original lighting, and the caster test picks depth-only
 * draws into the shadow atlas (1024x2048 or 2048x1024) and nothing else.
 *   generated\analysis\pcmenu\tools\build_tests.cmd */
#include <stdio.h>
#include "rsx_shadow_off.h"

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

int main(void)
{
    /* the switch: "1" only, and never with Enhanced lighting */
    CHECK(rsx_shadow_off_wanted("1", 0) == 1);
    CHECK(rsx_shadow_off_wanted("1", 1) == 0);
    CHECK(rsx_shadow_off_wanted("0", 0) == 0);
    CHECK(rsx_shadow_off_wanted("", 0) == 0);
    CHECK(rsx_shadow_off_wanted(NULL, 0) == 0);
    CHECK(rsx_shadow_off_wanted("10", 0) == 1);   /* a leading 1, as the other switches read */
    CHECK(rsx_shadow_off_wanted("on", 0) == 0);

    /* a caster: depth only (no colour, no MRT colour), depth test and write, the atlas size */
    CHECK(rsx_shadow_off_is_caster(0, 0, 1, 1, 1024, 2048) == 1);
    CHECK(rsx_shadow_off_is_caster(0, 0, 1, 1, 2048, 1024) == 1);
    CHECK(rsx_shadow_off_is_caster(0, 0, 1, 1, 1280, 720) == 0);   /* the scene */
    CHECK(rsx_shadow_off_is_caster(0, 0, 1, 1, 640, 360) == 0);    /* the dust layer */
    CHECK(rsx_shadow_off_is_caster(0, 0, 1, 1, 1024, 1024) == 0);  /* a square target: not the atlas */
    CHECK(rsx_shadow_off_is_caster(0xF, 0, 1, 1, 1024, 2048) == 0);   /* writes colour: not a depth-only caster */
    CHECK(rsx_shadow_off_is_caster(0, 0x2, 1, 1, 1024, 2048) == 0);   /* MRT colour */
    CHECK(rsx_shadow_off_is_caster(0, 0, 0, 1, 1024, 2048) == 0);     /* no depth test */
    CHECK(rsx_shadow_off_is_caster(0, 0, 1, 0, 1024, 2048) == 0);     /* no depth write */
    CHECK(rsx_shadow_off_is_caster(0, 0, 0, 0, 1024, 2048) == 0);

    printf("test_shadow_off: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
