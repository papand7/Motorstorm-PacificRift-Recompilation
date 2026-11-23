import pathlib
p = pathlib.Path(r'ps3recomp-vkgame/libs/video/tests/test_shadow_tiles.c'); t = p.read_text(newline='')
if 'st_cleared_bad' in t: raise SystemExit('already')
def rep(a, b):
    global t
    assert t.count(a) == 1, a[:60]
    t = t.replace(a, b, 1)
rep("    double prev_c[2] = { 0, 0 }; int have_prev_c = 0;\n",
    "    double prev_c[2] = { 0, 0 }; int have_prev_c = 0;\n"
    "    /* phase 2: the static region (3072 m store) and its clears; fixed points must keep their store texel */\n"
    "    const double SL = 3072.0; const int SN = (int)(SL / RSX_ST_TS);\n"
    "    long long sr0[2] = { 0, 0 }; int s_had = 0; rsx_st_rect scr[8]; int skc = 0;\n"
    "    long long sidx[NPT][2]; int shave[NPT]; memset(shave, 0, sizeof shave);\n"
    "    u32 st_cleared_bad = 0, st_obs = 0, st_moved = 0, bake_out = 0;\n")
rep("                if (rsx_st_window(&m, x)) moved++;\n",
    "                if (rsx_st_window(&m, x)) moved++;\n"
    "                { long long r0[2]; rsx_st_region_origin(&m, SN, r0);\n"
    "                  skc = rsx_st_region_clears(s_had, sr0[0], sr0[1], r0[0], r0[1], SN, scr);\n"
    "                  long long b0[2]; rsx_st_bake_origin(&m, 4092u, b0);   /* the bake window lies in the region */\n"
    "                  if (b0[0] < r0[0] || b0[1] < r0[1] || b0[0] + 4092 > r0[0] + SN || b0[1] + 4092 > r0[1] + SN) bake_out++;\n"
    "                  if (!s_had || r0[0] != sr0[0] || r0[1] != sr0[1]) st_moved++;\n"
    "                  sr0[0] = r0[0]; sr0[1] = r0[1]; s_had = 1; }\n")
rep("                rsx_st_model_reader(c47, lut, off, a3, pts[k], ru);\n",
    "                rsx_st_model_reader(c47, lut, off, a3, pts[k], ru);\n"
    "                {   /* the static store texel of this world point: fixed, and never cleared while it stays in the region */\n"
    "                    const float px = (float)pts[k][0], py = (float)pts[k][1], pz = (float)pts[k][2];\n"
    "                    float lp0 = c47[0] * px + c47[4] * py + c47[8] * pz + c47[12], lp1 = c47[1] * px + c47[5] * py + c47[9] * pz + c47[13];\n"
    "                    const float coord[2] = { lp0 * lut[0] + lut[2], lp1 * lut[1] + lut[3] };\n"
    "                    double sg[2]; rsx_st_model_static(coord, SN, SL, sg);\n"
    "                    const long long ix = (long long)floor(sg[0] + 0.5), iy = (long long)floor(sg[1] + 0.5);\n"
    "                    if (shave[k] && (sidx[k][0] != ix || sidx[k][1] != iy)) st_cleared_bad++;   /* moved texel */\n"
    "                    if (shave[k] && in_rects(scr, skc, rsx_st_mod(ix, SN), rsx_st_mod(iy, SN)) &&\n"
    "                        ix >= sr0[0] && ix < sr0[0] + SN && iy >= sr0[1] && iy < sr0[1] + SN) {\n"
    "                        /* cleared although inside the new region: only right if it was outside the old one */\n"
    "                    }\n"
    "                    sidx[k][0] = ix; sidx[k][1] = iy; shave[k] = 1; st_obs++;\n"
    "                }\n")
rep("    CHECK(passes > 0 && readers > 0);\n",
    "    printf(\"  static layer: region moves %u, bake window outside the region %u, fixed points' store texel changed %u of %u\n\",\n"
    "           st_moved, bake_out, st_cleared_bad, st_obs);\n"
    "    CHECK(bake_out == 0 && st_cleared_bad == 0);\n"
    "    CHECK(passes > 0 && readers > 0);\n")
p.write_text(t, newline=''); print('ok')
