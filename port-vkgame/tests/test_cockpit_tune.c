/* cockpit_tune.h: names, free-flight motion, readout, cockpit_positions.json read/write round trip. */
#include "cockpit_tune.h"
#include <assert.h>
#include <math.h>

static int near(float a, float b) { return fabsf(a - b) < 1e-3f; }

int main(void)
{
    static ct_table t;
    char nm[CT_NAME];
    assert(ct_norm_name("atv22", nm, sizeof nm) && !strcmp(nm, "atv22"));
    assert(ct_norm_name("Buggy20_LV01", nm, sizeof nm) && !strcmp(nm, "buggy20"));
    assert(!ct_norm_name("", nm, sizeof nm));
    assert(!ct_norm_name("bad name", nm, sizeof nm));
    assert(!ct_norm_name("\x01\x02", nm, sizeof nm));

    ct_entry* e = ct_find(&t, "atv22", 1);
    assert(e && t.n == 1 && ct_find(&t, "atv22", 0) == e && !ct_find(&t, "bike03", 0));
    e->dy = 0.1f; e->dz = -1.8f; e->pitch = 4.0f; e->focal = 7.0f;

    /* nothing held: no change */
    ct_input in = {0};
    assert(!ct_fly(e, &in, 0, 0.016f, 1));
    /* facing forward (yaw 0): I moves -z at 1 unit/s (the stored z points back), J strafes +x (left), T raises y */
    in.fwd = 1;
    for (int i = 0; i < 50; i++) assert(ct_fly(e, &in, 0, 0.02f, 1));   /* 1 s */
    assert(near(e->dz, -2.8f) && near(e->x, 0));
    in.fwd = 0; in.left = 1;
    ct_fly(e, &in, 0, 0.5f, 1);   /* clamped to 0.1 s of motion */
    assert(near(e->x, 0.1f));
    in.left = -1; in.up = 1;
    ct_fly(e, &in, 0, 0.1f, CT_FAST);   /* strafe right and up, 5x */
    assert(near(e->x, -0.4f) && near(e->dy, 0.6f));
    /* facing left (yaw -90): forward is +x, strafe left is +z; facing the rear (180): forward is +z */
    e->x = 0; e->dz = 0; in = (ct_input){0};
    in.fwd = 1; ct_fly(e, &in, -90, 0.1f, 1);
    assert(near(e->x, 0.1f) && near(e->dz, 0));
    in.fwd = 0; in.left = 1; ct_fly(e, &in, -90, 0.1f, 1);
    assert(near(e->x, 0.1f) && near(e->dz, 0.1f));
    in.left = 0; in.fwd = 1; ct_fly(e, &in, 180, 0.1f, 1);
    assert(near(e->dz, 0.2f));
    /* pitch, yaw and focal at their speeds; Num0 slows */
    in = (ct_input){0}; in.pitch = -1; in.yaw = 1; in.focal = 1;
    ct_fly(e, &in, 0, 0.1f, 1);
    assert(near(e->pitch, 1.0f) && near(e->yaw, 3.0f) && near(e->focal, 7.4f));
    ct_fly(e, &in, 0, 0.1f, CT_FINE);
    assert(near(e->pitch, 0.4f) && near(e->yaw, 3.6f));
    /* back far behind is not stopped short; the limits are far out */
    e->dz = 0; in = (ct_input){0}; in.fwd = -1;
    for (int i = 0; i < 20; i++) ct_fly(e, &in, 0, 0.1f, CT_FAST);   /* 2 s at 5x */
    assert(near(e->dz, 10.0f));
    for (int i = 0; i < 2000; i++) ct_fly(e, &in, 0, 0.1f, CT_FAST);
    assert(near(e->dz, CT_POS_LIM));
    in = (ct_input){0}; in.focal = -1;
    for (int i = 0; i < 2000; i++) ct_fly(e, &in, 0, 0.1f, CT_FAST);
    assert(near(e->focal, CT_FOCAL_MIN));
    e->x = 0.25f; e->dy = 0.14f; e->dz = -1.82f; e->pitch = 3.5f; e->yaw = -2.0f; e->focal = 8.5f;

    char ro[256];
    ct_readout(e, -17.0f, ro, sizeof ro);
    assert(strstr(ro, "pitch +3.5 (=-13.5)"));
    assert(strstr(ro, "atv22") && strstr(ro, "x 0.25") && strstr(ro, "dy 0.14") && strstr(ro, "yaw -2.0") && strstr(ro, "focal 8.5"));
    assert(strstr(ro, "unsaved") && strstr(ro, "I/K fwd/back") && strstr(ro, "J/L strafe") && strstr(ro, "T/G (Num+/-) up/down"));
    assert(strstr(ro, ",/. pitch") && strstr(ro, "N/M turn") && strstr(ro, "U/O focal") && strstr(ro, "F2 save"));

    /* write, then read into a fresh table: same values, all marked saved */
    ct_entry* b = ct_find(&t, "buggy01", 1);
    b->dy = 0.35f; b->dz = -0.9f; b->pitch = -6.0f; b->focal = 8.5f;
    char js[4096];
    const size_t w = ct_write_json(&t, js, sizeof js);
    assert(w == strlen(js) && w == ct_write_json(&t, NULL, 0));
    assert(strstr(js, "\"atv22\"") < strstr(js, "\"buggy01\""));   /* sorted */
    static ct_table u;
    assert(ct_parse_json(&u, js) == 2);
    const ct_entry* a2 = ct_find(&u, "atv22", 0);
    assert(a2 && a2->saved && near(a2->x, 0.25f) && near(a2->dy, 0.14f) && near(a2->dz, -1.82f) && near(a2->pitch, 3.5f));
    assert(near(a2->yaw, -2.0f) && near(a2->focal, 8.5f));
    assert(near(ct_find(&u, "buggy01", 0)->pitch, -6.0f));

    /* the generator's own shape (json.dumps), unknown keys ignored, missing ones 0; merging keeps other entries */
    assert(ct_parse_json(&u, "{\"bike03\": {\"dz\": -2.0, \"pitch\": 1.5, \"note\": 1}}") == 1);
    assert(u.n == 3 && near(ct_find(&u, "bike03", 0)->dz, -2.0f) && near(ct_find(&u, "bike03", 0)->dy, 0.0f));
    assert(near(ct_find(&u, "bike03", 0)->x, 0.0f) && near(ct_find(&u, "bike03", 0)->yaw, 0.0f));   /* the generator's defaults */
    assert(ct_parse_json(&u, "{}") == 0 && ct_parse_json(&u, " { } ") == 0);

    /* malformed files are refused */
    assert(ct_parse_json(&u, "") == -1);
    assert(ct_parse_json(&u, "[1]") == -1);
    assert(ct_parse_json(&u, "{\"a\": 1}") == -1);
    assert(ct_parse_json(&u, "{\"a\": {\"dy\": }}") == -1);
    assert(ct_parse_json(&u, "{\"a\\\"b\": {}}") == -1);
    assert(ct_parse_json(&u, "{\"a\": {\"dy\": 1}") == -1);

    /* a short buffer is not overrun and reports the size needed */
    char small[16];
    memset(small, 'x', sizeof small);
    assert(ct_write_json(&t, small, 8) == w && small[7] == 0 && small[8] == 'x');

    puts("test_cockpit_tune: OK");
    return 0;
}
