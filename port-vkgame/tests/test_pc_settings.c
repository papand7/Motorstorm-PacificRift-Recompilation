/* pc_settings.h: settings.ini parsing and writing, and the variables the
 * choices give (a set variable wins, defaults set nothing, MSPR_PATCH list,
 * ownership of variables, choices that cannot be used here), plus the page
 * table (pc_pages.h) every setting and key row must be on.
 *   generated\analysis\pcmenu\tools\build_tests.cmd */
#include <stdio.h>
#include <string.h>
#include "cellPad.h"
#include "pc_pages.h"
#include "pad_wheel.h"   /* the wheel rows must agree with the mapping's tables */

static int fails;
#define CHECK(c) do { if (!(c)) { printf("FAIL line %d: %s\n", __LINE__, #c); fails++; } } while (0)

/* A fake environment: names already set, and what pcs_apply set. */
static const char* s_preset[6];
static char s_set[32][2][1100];
static int s_nset;
static const char* fake_get(const char* name)
{
    for (int i = 0; i < 6 && s_preset[i]; i++)
        if (!strcmp(s_preset[i], name)) return "x";
    return NULL;
}
static void fake_set(const char* name, const char* value)
{
    snprintf(s_set[s_nset][0], sizeof s_set[0][0], "%s", name);
    snprintf(s_set[s_nset][1], sizeof s_set[0][1], "%s", value);
    s_nset++;
}
static const char* set_value(const char* name)
{
    for (int i = 0; i < s_nset; i++)
        if (!strcmp(s_set[i][0], name)) return s_set[i][1];
    return NULL;
}
static void reset_env(void) { memset(s_preset, 0, sizeof s_preset); s_nset = 0; }

/* What is missing: the texture pack and the FSR 3 runtime. */
static int s_missing_pack, s_missing_fsr3;
static const char* fake_avail(const char* key, int choice)
{
    if (choice <= 0) return NULL;
    if (s_missing_pack && (!strcmp(key, "textures") || !strcmp(key, "pbr"))) return "No pack";
    if (s_missing_fsr3 && !strcmp(key, "fsrmode") && choice == 1) return "No FSR3 DLL";
    return NULL;
}

/* The environment a setting sets, for the one choice, in a fresh state. */
static const char* env_for(int i, int c, const char* base)
{
    pcs_state s;
    pcs_defaults(&s);
    s.idx[i] = c;
    reset_env();
    pcs_apply(&s, base, fake_get, fake_set, NULL);
    return set_value(k_pcs_defs[i].env ? k_pcs_defs[i].env : "MSPR_PATCH");
}

int main(void)
{
    pcs_state s;
    char buf[1024];

    /* The table itself: every row has what the page needs. */
    for (int i = 0; i < PCS_COUNT; i++) {
        const pcs_def* d = &k_pcs_defs[i];
        CHECK(d->key && d->name && d->info && *d->info);
        CHECK(d->count >= 2 && d->count <= PCS_MAX_CHOICES && d->def >= 0 && d->def < d->count);
        CHECK(strlen(d->name) < 24 && strlen(d->info) < 100);
        for (int c = 0; c < d->count; c++) CHECK(d->labels[c] && d->values[c] && strlen(d->labels[c]) < 24);
        for (int j = i + 1; j < PCS_COUNT; j++) CHECK(strcmp(d->key, k_pcs_defs[j].key));
        CHECK(pcs_find(d->key) == i);
    }
    CHECK(PCS_COUNT <= 31);   /* explicit_mask */
    CHECK(pcs_find("bloom") < 0);   /* the bloom is fixed at half (rsx_bloom.h default 0.5): no setting */

    /* Defaults: every setting but the upscaler, the frame rate and the lighting sets nothing; the upscaler mode,
     * the rate (30 FPS, with its camera mode) and the lighting are always set, and the MSPR_PATCH default is the port's. */
    pcs_defaults(&s);
    pcs_mspr_spec(&s, buf, sizeof buf);
    CHECK(!strcmp(buf, PCS_MSPR_DEFAULT));
    reset_env();
    CHECK(pcs_apply(&s, "C:/game", fake_get, fake_set, fake_avail) == 4);
    CHECK(set_value("RSX_LIGHTING") && !strcmp(set_value("RSX_LIGHTING"), "1"));   /* Enhanced, the default */
    CHECK(s_nset == 4 && set_value("RSX_FSR_MODE") && !strcmp(set_value("RSX_FSR_MODE"), "1"));   /* FSR 1, the default */
    CHECK(!strcmp(set_value("PS3_SIM_PACE_HZ"), "30") && !strcmp(set_value("MSPR_CAM_MODE"), "0"));
    CHECK(!set_value("RSX_FSR") && !set_value("MSPR_PATCH"));
    /* the default FSR 1 needs no DLL: set without the FSR 3.1 DLLs too */
    s_missing_fsr3 = 1;
    reset_env();
    CHECK(pcs_apply(&s, "C:/game", fake_get, fake_set, fake_avail) == 4 && s_nset == 4);
    CHECK(!strcmp(set_value("RSX_FSR_MODE"), "1"));
    s_missing_fsr3 = 0;
    CHECK(!pcs_owns_env(&s, "RSX_FSR") && pcs_owns_env(&s, "RSX_FSR_MODE") == 0);

    /* Every setting: each non-default choice gives its variable (a folder value
     * joined to the executable's folder), the default gives none, and the choice
     * is read back by its label and by its value. */
    for (int i = 0; i < PCS_COUNT; i++) {
        const pcs_def* d = &k_pcs_defs[i];
        for (int c = 0; c < d->count; c++) {
            const char* got = env_for(i, c, "C:/game");
            if (d->env) {
                /* hidden under the default Fidelity (Enhanced): sets nothing; the Original case is tested below */
                if (!strcmp(d->key, "shadows")) { CHECK(!got); continue; }
                if (c == d->def && !d->always) CHECK(!got);
                else {
                    char want[1100];
                    if (d->folder && *d->values[c]) snprintf(want, sizeof want, "C:/game/%s", d->values[c]);
                    else snprintf(want, sizeof want, "%s", d->values[c]);
                    CHECK(got && !strcmp(got, want));
                }
            } else {
                /* a patch: only MSPR_PATCH, and only when the list differs from the default */
                pcs_state t;
                pcs_defaults(&t);
                t.idx[i] = c;
                pcs_mspr_spec(&t, buf, sizeof buf);
                CHECK(!strcmp(buf, PCS_MSPR_DEFAULT) == (got == NULL));
                if (got) CHECK(!strcmp(got, buf));
            }
            pcs_state r;
            pcs_defaults(&r);
            snprintf(buf, sizeof buf, "%s = %s\n", d->key, d->labels[c]);
            CHECK(pcs_parse(&r, buf) == 1 && r.idx[i] == c);
            if (*d->values[c]) {
                pcs_defaults(&r);
                snprintf(buf, sizeof buf, "%s=%s\n", d->key, d->values[c]);
                CHECK(pcs_parse(&r, buf) == 1 && r.idx[i] == c);
            }
        }
    }

    /* The new settings by name. */
    CHECK(!strcmp(env_for(pcs_find("fsr"), 2, "."), "quality"));
    CHECK(!strcmp(env_for(pcs_find("fsr"), 1, "."), "ultra"));
    CHECK(!strcmp(env_for(pcs_find("fsr"), 4, "."), "performance"));
    CHECK(!strcmp(env_for(pcs_find("fsrmode"), 1, "."), "3"));   /* FSR 3.1 chosen */
    CHECK(!strcmp(env_for(pcs_find("fsrmode"), 0, "."), "1"));   /* FSR 1, the default: set explicitly too */
    CHECK(k_pcs_defs[pcs_find("fsrmode")].def == 0);              /* as the launcher's default (settings.js) */
    CHECK(!strcmp(env_for(pcs_find("hdr"), 1, "."), "1"));
    CHECK(!strcmp(env_for(pcs_find("pbr"), 1, "."), "1"));
    CHECK(!strcmp(env_for(pcs_find("textures"), 1, "D:/g"), "D:/g/textures/pack"));
    CHECK(!strcmp(k_pcs_defs[pcs_find("fsr")].env, "RSX_FSR") && !strcmp(k_pcs_defs[pcs_find("fsrmode")].env, "RSX_FSR_MODE"));
    CHECK(!strcmp(k_pcs_defs[pcs_find("hdr")].env, "RSX_HDR"));
    /* Ray-traced shadows are hidden: no row, and no setting sets RSX_RT_SHADOW (environment only). */
    CHECK(pcs_find("rtshadow") < 0);
    for (int i = 0; i < PCS_COUNT; i++)
        CHECK(!k_pcs_defs[i].env || strcmp(k_pcs_defs[i].env, "RSX_RT_SHADOW"));
    pcs_defaults(&s);
    CHECK(pcs_parse(&s, "rtshadow = On\n") == 0 && s.explicit_mask == 0 && !pcs_owns_env(&s, "RSX_RT_SHADOW"));
    /* World-fixed sun shadows are a default of the executable (k_defaults), not a setting: no row owns or sets
     * RSX_SHADOW_TILES, in either lighting (RSX_SHADOW_TILES=0 stays an environment-only switch for testing). */
    for (int i = 0; i < PCS_COUNT; i++)
        CHECK(!k_pcs_defs[i].env || (strcmp(k_pcs_defs[i].env, "RSX_SHADOW_TILES") && strcmp(k_pcs_defs[i].env, "RSX_SHADOW_TILES_STATIC")));
    pcs_defaults(&s);
    CHECK(!pcs_owns_env(&s, "RSX_SHADOW_TILES"));

    /* Choices by label or value, case-insensitive; junk ignored. */
    pcs_defaults(&s);
    CHECK(pcs_parse(&s, "# c\nresolution = 1080P\r\nvsync=off\n aniso =16\nbogus = 1\nframerate = 45\n"
                        "motionblur = Off\ntextures = On\ndisplay\nfsr = ultra quality\nhdr = 1\n") == 8);
    CHECK(s.idx[pcs_find("resolution")] == 1);
    CHECK(s.idx[pcs_find("vsync")] == 1);
    CHECK(s.idx[pcs_find("aniso")] == 4);
    CHECK(s.idx[pcs_find("framerate")] == 1);   /* "45" is the middle choice */
    CHECK(s.idx[pcs_find("display")] == 0);
    CHECK(s.idx[pcs_find("motionblur")] == 1);
    CHECK(s.idx[pcs_find("fsr")] == 1 && s.idx[pcs_find("hdr")] == 1);
    CHECK((s.explicit_mask & (1u << pcs_find("fsr"))) && !(s.explicit_mask & (1u << pcs_find("display"))));

    /* Their variables. */
    reset_env();
    CHECK(pcs_apply(&s, "C:/game", fake_get, fake_set, NULL) == 10);   /* nine variables and the MSPR list */
    CHECK(set_value("RSX_FSR_MODE") && !strcmp(set_value("RSX_FSR_MODE"), "1"));
    CHECK(set_value("RSX_RES_SCALE") && !strcmp(set_value("RSX_RES_SCALE"), "1.5"));
    CHECK(!set_value("RSX_PRESENT_INTERVAL"));   /* V-Sync Off is the default: main.cpp k_defaults gives 0 */
    CHECK(set_value("PS3_SIM_PACE_HZ") && !strcmp(set_value("PS3_SIM_PACE_HZ"), "45"));
    CHECK(set_value("MSPR_CAM_MODE") && !strcmp(set_value("MSPR_CAM_MODE"), "1"));
    CHECK(set_value("PS3_ANISO") && !strcmp(set_value("PS3_ANISO"), "16"));
    CHECK(set_value("RSX_TEX_PACK") && !strcmp(set_value("RSX_TEX_PACK"), "C:/game/textures/pack"));
    CHECK(set_value("RSX_FSR") && !strcmp(set_value("RSX_FSR"), "ultra"));
    CHECK(set_value("RSX_HDR") && !strcmp(set_value("RSX_HDR"), "1"));
    CHECK(set_value("MSPR_PATCH") && !strcmp(set_value("MSPR_PATCH"), "drs,vfps,mblur,audiothread"));
    CHECK(!set_value("PS3RECOMP_VK_FULLSCREEN"));

    /* A variable the user set wins. */
    reset_env();
    s_preset[0] = "RSX_RES_SCALE";
    s_preset[1] = "MSPR_PATCH";
    s_preset[2] = "RSX_FSR";
    { const int nn = pcs_apply(&s, "C:/game", fake_get, fake_set, NULL);
      if (nn != 7) { printf("apply=%d:", nn); for (int q = 0; q < s_nset; q++) printf(" %s", s_set[q][0]); puts(""); }
      CHECK(nn == 7); }   /* presets skip resolution, MSPR and FSR; FSR_MODE and LIGHTING are always set; 45 FPS gives two */
    CHECK(!set_value("RSX_RES_SCALE") && !set_value("MSPR_PATCH") && !set_value("RSX_FSR"));

    /* A choice whose feature is missing is not applied; the others are. */
    pcs_defaults(&s);
    pcs_parse(&s, "textures = On\npbr = On\nfsrmode = FSR 3.1\nhdr = On\n");
    s_missing_pack = s_missing_fsr3 = 1;
    reset_env();
    CHECK(pcs_apply(&s, "C:/game", fake_get, fake_set, fake_avail) == 4);   /* hdr, and the always-set rate, camera and lighting */
    CHECK(set_value("RSX_HDR") && !set_value("RSX_TEX_PACK") &&
          !set_value("RSX_TEX_PBR") && !set_value("RSX_FSR_MODE"));
    s_missing_pack = 0;
    reset_env();
    CHECK(pcs_apply(&s, "C:/game", fake_get, fake_set, fake_avail) == 6);   /* hdr, textures, pbr, rate, camera, lighting */
    s_missing_fsr3 = 0;
    reset_env();
    CHECK(pcs_apply(&s, "C:/game", fake_get, fake_set, fake_avail) == 7);
    CHECK(set_value("RSX_FSR_MODE") && !strcmp(set_value("RSX_FSR_MODE"), "3"));
    CHECK(!set_value("RSX_RT_SHADOW"));
    CHECK(!strcmp(pcs_value_text(&s, pcs_find("textures"), "No pack"), "No pack"));
    CHECK(!strcmp(pcs_value_text(&s, pcs_find("textures"), NULL), "On"));

    /* The file owns the variables of the settings it names (a motorstorm.cfg line
     * for them is ignored), and only those. */
    pcs_defaults(&s);
    pcs_parse(&s, "fsr = Off\nframerate = 60 FPS\n");
    CHECK(pcs_owns_env(&s, "RSX_FSR"));       /* named, at its default: still owned */
    CHECK(pcs_owns_env(&s, "PS3_SIM_PACE_HZ") && pcs_owns_env(&s, "MSPR_CAM_MODE") && !pcs_owns_env(&s, "MSPR_PATCH"));
    pcs_parse(&s, "dynres = On\n");
    CHECK(pcs_owns_env(&s, "MSPR_PATCH"));
    CHECK(!pcs_owns_env(&s, "RSX_HDR") && !pcs_owns_env(&s, "PS3_VFS_ROOT") && !pcs_owns_env(&s, "RSX_FSR_MODE"));
    pcs_defaults(&s);
    pcs_parse(&s, "display = Windowed\n");
    CHECK(pcs_owns_env(&s, "PS3RECOMP_VK_FULLSCREEN") && !pcs_owns_env(&s, "MSPR_PATCH"));

    /* The patch lists: every patch off still has the audio thread. */
    pcs_defaults(&s);
    pcs_parse(&s, "dynres = On\nframerate = 30 FPS\n");
    pcs_mspr_spec(&s, buf, sizeof buf);
    CHECK(!strcmp(buf, "vfps,audiothread"));   /* vfps stays in every list */
    reset_env();
    CHECK(pcs_apply(&s, ".", fake_get, fake_set, NULL) == 5);   /* MSPR_PATCH, RSX_FSR_MODE, rate, camera and lighting */
    CHECK(set_value("MSPR_PATCH") && !strcmp(set_value("MSPR_PATCH"), "vfps,audiothread"));
    CHECK(!strcmp(set_value("PS3_SIM_PACE_HZ"), "30") && !strcmp(set_value("MSPR_CAM_MODE"), "0"));   /* camera fix off at 30 */
    pcs_parse(&s, "framerate = 60 FPS\n");
    pcs_mspr_spec(&s, buf, sizeof buf);
    CHECK(!strcmp(buf, "vfps,audiothread"));
    reset_env();
    s_preset[0] = "MSPR_CAM_MODE";   /* a set camera mode wins, the rate is still the choice's */
    pcs_parse(&s, "framerate = 30 FPS\n");
    pcs_apply(&s, ".", fake_get, fake_set, NULL);
    CHECK(!set_value("MSPR_CAM_MODE") && !strcmp(set_value("PS3_SIM_PACE_HZ"), "30"));

    /* Frame rate: 30 (default, always set), 45, 60; camera fix on above 30; old values map; vsync defaults Off. */
    { const int f = pcs_find("framerate");
      CHECK(k_pcs_defs[f].def == 0 && !strcmp(k_pcs_defs[f].labels[0], "30 FPS") && k_pcs_defs[f].always);
      CHECK(!strcmp(env_for(f, 0, "."), "30") && !strcmp(env_for(f, 1, "."), "45") && !strcmp(env_for(f, 2, "."), "60"));
      pcs_defaults(&s);
      CHECK(pcs_parse(&s, "framerate = Variable\n") == 1 && s.idx[f] == 2);
      pcs_defaults(&s);
      CHECK(pcs_parse(&s, "framerate = 60 FPS\n") == 1 && s.idx[f] == 2);
      pcs_defaults(&s);
      CHECK(pcs_parse(&s, "framerate = 30 FPS\n") == 1 && s.idx[f] == 0);
      const int v = pcs_find("vsync");
      CHECK(k_pcs_defs[v].def == 1 && !strcmp(env_for(v, 0, "."), "1") && !env_for(v, 1, "."));   /* On = 1 */ }

    /* Stepping clamps at both ends. */
    pcs_defaults(&s);
    const int r = pcs_find("resolution");
    CHECK(pcs_step(&s, r, -1) == 0);
    CHECK(pcs_step(&s, r, 1) == 1);
    for (int k = 0; k < 9; k++) pcs_step(&s, r, 1);
    CHECK(s.idx[r] == 3);

    /* The written file reads back to the same choices. */
    pcs_state t;
    pcs_defaults(&s);
    pcs_parse(&s, "display = Fullscreen\nresolution = 2160p\nframerate = 60 FPS\ndynres = On\naniso = 8x\n"
                  "fsr = Balanced\nfsrmode = FSR 3.1\nhdr = On\npbr = On\ntextures = On\n");
    CHECK(pcs_format(&s, buf, sizeof buf) > 0);
    pcs_defaults(&t);
    CHECK(pcs_parse(&t, buf) == PCS_COUNT);
    CHECK(!memcmp(s.idx, t.idx, sizeof s.idx));
    CHECK(t.explicit_mask == (1u << PCS_COUNT) - 1);

    /* The page table: consecutive rows from 0, at most 8 a page, every setting
     * and every key row on exactly one page. */
    int next = 0;
    for (int p = 0; p < PCP_COUNT; p++) {
        const pcp_page* g = &k_pcp_pages[p];
        CHECK(g->first == next && g->rows >= 1 && g->rows <= PCP_ROWS_MAX);
        CHECK(g->file && g->title && g->label && g->info && strlen(g->label) < 16 && strlen(g->title) < 24);
        CHECK(!strncmp(g->file, "options-pc", 10));
        for (int q = p + 1; q < PCP_COUNT; q++) CHECK(strcmp(g->file, k_pcp_pages[q].file));
        /* a page holds settings or keys, not both */
        CHECK((g->first < PCS_COUNT) == (g->first + g->rows <= PCS_COUNT));
        next += g->rows;
    }
    CHECK(next == PCP_ROWS);
    CHECK(PCP_COUNT == 7);   /* the hub: seven items (four Options slots and three more) */
    CHECK(k_pcp_pages[PCP_COUNT - 1].first == PCS_COUNT + 13 && k_pcp_pages[PCP_COUNT - 1].rows == 4);   /* arrows: UP..RIGHT */
    CHECK(PCP_ROWS == PCS_COUNT + PCK_COUNT);


    /* The racing-wheel rows (the "Racing Wheel" page): the page's choices give the values pad_wheel.h reads
     * back, in the same order as its tables, and the wheel page holds exactly those rows. */
    {
        const int w0 = pcs_find("wheelmode");
        CHECK(w0 >= 0 && pcs_find("wheelffbstrength") == w0 + 7);
        for (int i = 0; i < 8; i++) CHECK(k_pcs_defs[w0 + i].env && !strncmp(k_pcs_defs[w0 + i].env, "PAD_WHEEL", 9) && !k_pcs_defs[w0 + i].restart);
        pcs_defaults(&s);
        reset_env();
        pcs_apply(&s, "C:/game", fake_get, fake_set, fake_avail);
        for (int i = 0; i < s_nset; i++) CHECK(strncmp(s_set[i][0], "PAD_WHEEL", 9));   /* defaults set nothing */
        pcw_cfg d;
        pcw_cfg_default(&d);
        /* the page's defaults are the mapping's defaults */
        CHECK(!strcmp(k_pcs_defs[w0].labels[k_pcs_defs[w0].def], "Auto") && d.mode == PCW_MODE_AUTO);
        CHECK(!strcmp(k_pcs_defs[w0 + 1].values[k_pcs_defs[w0 + 1].def], "270") && d.range_deg == 270);
        CHECK(!strcmp(k_pcs_defs[w0 + 2].values[k_pcs_defs[w0 + 2].def], "1") && d.deadzone_pct == 1);
        CHECK(!strcmp(k_pcs_defs[w0 + 7].values[k_pcs_defs[w0 + 7].def], "60") && d.ffb_pct == 60);
        CHECK(!strcmp(k_pcs_defs[w0 + 6].labels[k_pcs_defs[w0 + 6].def], "Off") && d.ffb == PCW_FFB_OFF);   /* FFB off by default */
        /* choice c of each row is table entry c of the mapping */
        CHECK(k_pcs_defs[w0 + 1].count == 7 && !strcmp(k_pcs_defs[w0 + 1].values[0], "device") && k_pcw_range_deg[0] == 0);
        for (int c = 1; c < 7; c++) CHECK(atoi(k_pcs_defs[w0 + 1].values[c]) == k_pcw_range_deg[c]);
        CHECK(k_pcs_defs[w0 + 2].count == 6);
        for (int c = 0; c < 6; c++) CHECK(atoi(k_pcs_defs[w0 + 2].values[c]) == k_pcw_dead_pct[c]);
        CHECK(k_pcs_defs[w0 + 3].count == 5 && k_pcs_defs[w0 + 7].count == 5);
        for (int c = 0; c < 5; c++) CHECK(atoi(k_pcs_defs[w0 + 3].values[c]) == c);
        for (int c = 0; c < 5; c++) CHECK(atoi(k_pcs_defs[w0 + 7].values[c]) == k_pcw_ffb_pct[c]);
        /* the pedal and ffb words are the ones pcw_cfg_from_env understands */
        CHECK(!strcmp(k_pcs_defs[w0 + 4].values[2], "combined") && !strcmp(k_pcs_defs[w0 + 5].values[2], "inverted"));
        CHECK(!strcmp(k_pcs_defs[w0 + 6].values[1], "center") && !strcmp(k_pcs_defs[w0 + 6].values[3], "both"));
        /* a page of its own with eight rows, on the wheel rows */
        int found = 0;
        for (int p = 0; p < PCP_COUNT; p++)
            if (!strcmp(k_pcp_pages[p].file, "options-pcw")) { found = 1; CHECK(k_pcp_pages[p].first == w0 && k_pcp_pages[p].rows == 8); }
        CHECK(found);
        /* settings.ini names the wheel rows (the wheel.* lines are not choices) */
        pcs_defaults(&s);
        CHECK(pcs_parse(&s, "wheelmode = Any Device\nwheelrange = 540 deg\nwheelffb = Both\nwheel.steer.axis = Rx\n") == 3);
        CHECK(s.idx[w0] == 1 && s.idx[w0 + 1] == 4 && s.idx[w0 + 6] == 3);
        CHECK(pcs_owns_env(&s, "PAD_WHEEL") && pcs_owns_env(&s, "PAD_WHEEL_RANGE") && !pcs_owns_env(&s, "PAD_WHEEL_CURVE"));
    }

  /* Cheats switches: On (or 1) turns one on; the last line wins; absent, Off, or another key: off */
  CHECK(pcs_ini_switch("unlockvehicles = On\n", "unlockvehicles") == 1);
  CHECK(pcs_ini_switch("unlockvehicles=on\r\n", "unlockvehicles") == 1);
  CHECK(pcs_ini_switch("unlockvehicles = 1\n", "unlockvehicles") == 1);
  CHECK(pcs_ini_switch("unlockvehicles = Off\n", "unlockvehicles") == 0);
  CHECK(pcs_ini_switch("unlockvehicles = Yes\n", "unlockvehicles") == 0);
  CHECK(pcs_ini_switch("# unlockvehicles = On\n", "unlockvehicles") == -1);
  CHECK(pcs_ini_switch("unlockvehiclesx = On\n", "unlockvehicles") == -1);
  CHECK(pcs_ini_switch("drs = On\n", "unlockvehicles") == -1);
  CHECK(pcs_ini_switch("", "unlockvehicles") == -1);
  CHECK(pcs_ini_switch(NULL, "unlockvehicles") == -1);
  CHECK(pcs_unlock_vehicles("unlockvehicles = On\nunlockvehicles = Off\n") == 0);
  CHECK(pcs_unlock_vehicles("unlockvehicles = Off\nunlockvehicles = On\n") == 1);
  CHECK(pcs_unlock_vehicles("unlockall = On\n") == 1);                          /* the old key */
  CHECK(pcs_unlock_vehicles("unlockall = On\nunlockvehicles = Off\n") == 0);    /* the new key wins */
  CHECK(pcs_unlock_vehicles("unlocktracks = On\n") == 0);                       /* separate switches */
  CHECK(pcs_unlock_vehicles(NULL) == 0);
  CHECK(pcs_unlock_tracks("unlocktracks = On\n") == 1);
  CHECK(pcs_unlock_tracks("unlockvehicles = On\nunlockall = On\n") == 0);
  CHECK(pcs_unlock_tracks("unlocktracks = Off\n") == 0);
  CHECK(pcs_env_switch(NULL) == -1);
  CHECK(pcs_env_switch("") == -1);
  CHECK(pcs_env_switch("1") == 1);
  CHECK(pcs_env_switch("on") == 1);
  CHECK(pcs_env_switch("0") == 0);
  CHECK(pcs_env_switch("Off") == 0);

    /* Shadows: a Graphics row, hidden unless Fidelity is Original, its choice kept while hidden,
     * and its variable set only then (MSPR_NO_SHADOWS=1 with Off). */
    {
        const int sh = pcs_find("shadows"), lf = pcs_find("lighting");
        CHECK(sh >= 0 && lf >= 0 && sh == lf + 2 && pcs_find("prompts") == lf + 1);   /* last cell of the Graphics page */
        CHECK(sh == k_pcp_pages[1].first + k_pcp_pages[1].rows - 1);
        CHECK(k_pcs_defs[sh].env && !strcmp(k_pcs_defs[sh].env, "MSPR_NO_SHADOWS") && k_pcs_defs[sh].env2 == NULL);
        CHECK(!strcmp(k_pcs_defs[sh].values[0], "0") && !strcmp(k_pcs_defs[sh].values[1], "1"));
        CHECK(k_pcs_defs[sh].def == 0 && k_pcs_defs[sh].always == 0);
        CHECK(k_pcp_pages[1].first <= sh && sh < k_pcp_pages[1].first + k_pcp_pages[1].rows);   /* Graphics page */
        pcs_state t;
        pcs_defaults(&t);
        CHECK(t.idx[lf] == 1 && pcs_row_hidden(&t, sh));    /* the port's default Fidelity is Enhanced: hidden */
        t.idx[lf] = 0;
        CHECK(!pcs_row_hidden(&t, sh) && !pcs_row_hidden(&t, lf));   /* Original: shown */
        t.idx[sh] = 1;
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(set_value("MSPR_NO_SHADOWS") && !strcmp(set_value("MSPR_NO_SHADOWS"), "1"));
        t.idx[lf] = 1;                                       /* Enhanced: hidden, its choice kept, nothing set */
        CHECK(pcs_row_hidden(&t, sh) && t.idx[sh] == 1);
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("MSPR_NO_SHADOWS"));
        t.idx[lf] = 0;                                       /* back to Original: the kept Off applies again */
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(set_value("MSPR_NO_SHADOWS") && !strcmp(set_value("MSPR_NO_SHADOWS"), "1"));
        /* settings.ini: the label or the value, and the Original/Enhanced rule for the file's own lines */
        pcs_defaults(&t);
        pcs_parse(&t, "lighting = Original\nshadows = Off\n");
        CHECK(t.idx[lf] == 0 && t.idx[sh] == 1 && !pcs_row_hidden(&t, sh));
        pcs_parse(&t, "shadows = 0\n");
        CHECK(t.idx[sh] == 0);
    }
    /* Volumetric Fog: a restart setting on the Effects page (one row, its own hub item), Enhanced only: with Fidelity
     * Original it is unused (kept, not applied, shown as needing Enhanced); with Enhanced it sets RSX_FX_VOLFOG. */
    {
        const int vf = pcs_find("volfog"), lf = pcs_find("lighting");
        CHECK(vf >= 0 && vf == PCS_COUNT - 3 && lf >= 0 && lf != vf);
        CHECK(!strcmp(k_pcs_defs[vf].env, "RSX_FX_VOLFOG") && k_pcs_defs[vf].def == 0 && k_pcs_defs[vf].count == 2);
        CHECK(k_pcs_defs[vf].restart == 1 && k_pcs_defs[vf].env2 == NULL && !k_pcs_defs[vf].folder);
        CHECK(!strcmp(k_pcs_defs[vf].values[0], "0") && !strcmp(k_pcs_defs[vf].values[1], "1"));
        int ep = -1;
        for (int p = 0; p < PCP_COUNT; p++)
            if (!strcmp(k_pcp_pages[p].file, "options-pcf")) ep = p;
        CHECK(ep >= 0 && k_pcp_pages[ep].first == vf && k_pcp_pages[ep].rows == 3);   /* fog, ruts, effects quality */
        CHECK(!strcmp(k_pcp_pages[ep].label, "EFFECTS") && ep == 3);   /* the fourth hub item, after Racing Wheel */
        pcs_state t;
        pcs_defaults(&t);
        CHECK(t.idx[lf] == 1 && t.idx[vf] == 0 && !pcs_row_unused(&t, vf));   /* Enhanced, off by default */
        CHECK(!pcs_row_hidden(&t, vf));                                        /* shown on its page always */
        for (int i = 0; i < PCS_COUNT; i++) CHECK(!pcs_row_unused(&t, i));   /* Enhanced: every row applies */
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("RSX_FX_VOLFOG"));                                    /* off: nothing set */
        t.idx[vf] = 1;
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(set_value("RSX_FX_VOLFOG") && !strcmp(set_value("RSX_FX_VOLFOG"), "1"));
        t.idx[lf] = 0;                                                         /* Original: kept On, not applied */
        CHECK(t.idx[vf] == 1 && pcs_row_unused(&t, vf) && !pcs_row_hidden(&t, vf));
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("RSX_FX_VOLFOG"));
        pcs_defaults(&t);
        CHECK(pcs_parse(&t, "volfog = On\n") == 1 && t.idx[vf] == 1 && (t.explicit_mask & (1u << vf)));
        CHECK(pcs_parse(&t, "volfog = 0\n") == 1 && t.idx[vf] == 0);
        CHECK(pcs_owns_env(&t, "RSX_FX_VOLFOG") && !pcs_owns_env(&t, "RSX_FX_FOG"));
    }
    /* Wheel Ruts: the second Effects row, the last setting; as Volumetric Fog: restart, Enhanced only, off by default */
    {
        const int ru = pcs_find("ruts"), lf = pcs_find("lighting");
        CHECK(ru == PCS_COUNT - 2 && !strcmp(k_pcs_defs[ru].env, "RSX_FX_RUTS") && k_pcs_defs[ru].def == 0);
        CHECK(k_pcs_defs[ru].count == 2 && k_pcs_defs[ru].restart == 1 && k_pcs_defs[ru].env2 == NULL);
        pcs_state t;
        pcs_defaults(&t);
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("RSX_FX_RUTS"));                                      /* off: nothing set */
        t.idx[ru] = 1;
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(set_value("RSX_FX_RUTS") && !strcmp(set_value("RSX_FX_RUTS"), "1"));
        t.idx[lf] = 0;                                                         /* Original: kept On, not applied */
        CHECK(pcs_row_unused(&t, ru) && !pcs_row_hidden(&t, ru));
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("RSX_FX_RUTS"));
        pcs_defaults(&t);
        CHECK(pcs_parse(&t, "ruts = On\n") == 1 && t.idx[ru] == 1 && (t.explicit_mask & (1u << ru)));
        CHECK(pcs_owns_env(&t, "RSX_FX_RUTS"));
    }
    /* Effects Quality: the last setting, Enhanced only; Light sets RSX_FX_QUALITY=1, Full sets nothing */
    {
        const int fq = pcs_find("fxquality"), lf = pcs_find("lighting");
        CHECK(fq == PCS_COUNT - 1 && !strcmp(k_pcs_defs[fq].env, "RSX_FX_QUALITY") && k_pcs_defs[fq].def == 0 && k_pcs_defs[fq].count == 3);
        pcs_state t;
        pcs_defaults(&t);
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("RSX_FX_QUALITY"));
        t.idx[fq] = 1;
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(set_value("RSX_FX_QUALITY") && !strcmp(set_value("RSX_FX_QUALITY"), "1"));
        t.idx[lf] = 0;
        CHECK(pcs_row_unused(&t, fq));
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("RSX_FX_QUALITY"));
    }
    /* Level of Detail Low: bias +1 and cull x1.5; Original (the default, now the second choice) sets nothing */
    {
        const int ld = pcs_find("lod");
        CHECK(ld >= 0 && k_pcs_defs[ld].count == 4 && k_pcs_defs[ld].def == 1 && !strcmp(k_pcs_defs[ld].labels[1], "Original"));
        pcs_state t;
        pcs_defaults(&t);
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(!set_value("MSPR_LOD_BIAS") && !set_value("MSPR_CULL_SCALE"));
        CHECK(pcs_parse(&t, "lod = Low\n") == 1 && t.idx[ld] == 0);
        reset_env();
        pcs_apply(&t, ".", fake_get, fake_set, fake_avail);
        CHECK(set_value("MSPR_LOD_BIAS") && !strcmp(set_value("MSPR_LOD_BIAS"), "1"));
        CHECK(set_value("MSPR_CULL_SCALE") && !strcmp(set_value("MSPR_CULL_SCALE"), "1.5"));
        CHECK(pcs_parse(&t, "lod = Ultra\n") == 1 && t.idx[ld] == 3);
    }
    printf("test_pc_settings: %d failure(s)\n", fails);
    return fails ? 1 : 0;
}
