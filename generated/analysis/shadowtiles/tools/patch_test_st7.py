"""Replaces the mesh-model simulation in test_shadow_tiles.c with the Kst7 rules (camera-still evidence, unsure meshes,
one vertex rewrite = new content, instance 12 s). usage: py -3 patch_test_st7.py"""
import pathlib
p = pathlib.Path(__file__).resolve().parents[4] / 'ps3recomp-vkgame' / 'libs' / 'video' / 'tests' / 'test_shadow_tiles.c'
s = p.read_text(encoding='utf-8')
a = s.index('/* A model of eng_st_bake_draw')
b = s.index('    /* fingerprints: content only, order-free set */')
new = r'''/* A model of eng_st_bake_draw's tables for one mesh: instances by (object-constant hash, vertex sample). The camera
 * stands still from frame g_still (moving before it; g_still = ~0u: always moving). */
typedef struct { unsigned long long cbh, vbh; double first; unsigned draws, last_frame; int baked; } sim_inst;
typedef struct { rsx_st_mesh m; sim_inst in[4096]; int n; int emptied, bakes, unsure_baked; } sim_mesh;
static unsigned g_still = ~0u;
static void sim_init(sim_mesh* s, unsigned n_verts, double now, unsigned frame)
{ memset(s, 0, sizeof *s); rsx_st_mesh_init(&s->m, 1, n_verts, now, frame); }
static int sim_draw(sim_mesh* s, unsigned long long cbh, unsigned long long vbh, unsigned f)
{
    const double now = f / 30.0;
    const unsigned still_since = (g_still != ~0u && f >= g_still) ? g_still : f;
    const unsigned cl = s->m.cand >= 0 ? s->in[s->m.cand].last_frame : 0u;
    const int still = s->m.cand >= 0 && still_since <= s->m.cand_frame;
    const int mf = rsx_st_mesh_frame(&s->m, f, cl, still);
    if (mf == 1) { s->emptied++; for (int i = 0; i < s->n; i++) s->in[i].baked = 0; s->m.baked = 0; }
    if (mf == 3) s->unsure_baked++;
    if (rsx_st_mesh_vb(&s->m, vbh, now) == 1) { s->emptied++; for (int i = 0; i < s->n; i++) s->in[i].baked = 0; s->m.baked = 0; }
    if (s->m.mover || s->m.vol) return 0;
    int i = 0;
    while (i < s->n && (s->in[i].cbh != cbh || s->in[i].vbh != vbh)) i++;
    if (i == s->n) {
        if (s->n == 4096) return 0;
        s->in[i].cbh = cbh; s->in[i].vbh = vbh; s->in[i].first = now; s->in[i].draws = 1; s->in[i].last_frame = f;
        s->in[i].baked = 0; s->n++;
        rsx_st_mesh_new(&s->m, i, f);
        return 0;
    }
    if (s->in[i].last_frame != f) s->in[i].draws++;
    s->in[i].last_frame = f;
    if (s->in[i].baked || !rsx_st_inst_static(&s->m, s->in[i].first, s->in[i].draws, now)) return 0;
    s->in[i].baked = 1; s->m.baked++; s->bakes++;
    return 1;
}

static void synthetic_classes(void)
{
    static sim_mesh S;
    unsigned f;
    g_still = ~0u;   /* a race: the camera moves */
    /* 1. an instanced rock (5 instances, 3 cascades, every frame, 120 s): baked, never emptied */
    sim_init(&S, 300, 0.0, 0);
    for (f = 1; f < 3600; f++) for (int k = 0; k < 5; k++) for (int c = 0; c < 3; c++) sim_draw(&S, 100 + k, 1, f);
    CHECK(!S.m.mover && !S.m.vol && !S.m.unsure && S.bakes == 5 && S.emptied == 0);
    /* 2. instances coming into view and leaving it as the camera drives (instance k: frames 10 k .. 10 k + 400):
     * baked k 21..563 (gone before the mesh was 20 s known, or seen < 12 s before the end) */
    sim_init(&S, 300, 0.0, 0);
    for (f = 1; f < 6000; f++) for (int k = 0; k < 600; k++) if (f >= 10u * k && f < 10u * k + 400u) sim_draw(&S, 1000 + k, 1, f);
    CHECK(!S.m.mover && !S.m.unsure && S.emptied == 0 && S.bakes == 543);
    if (S.bakes != 543) printf("scenario 2: bakes %d\n", S.bakes);
    /* 3. a far instance its cascade redraws only every 8 frames: not unsure */
    sim_init(&S, 300, 0.0, 0);
    for (f = 1; f < 3000; f++) { sim_draw(&S, 7, 1, f); if (f % 8u == 0) sim_draw(&S, 8 + f / 2000u, 1, f); }
    CHECK(!S.m.mover && !S.m.unsure && S.emptied == 0 && S.bakes == 3);
    /* 4. a vehicle: grid 6.4 s, driving 60 s, still 40 s (the finish), driving: unsure ~1 s after the start, never
     * baked, the store never emptied */
    sim_init(&S, 900, 0.0, 0);
    unsigned unsure_at = 0;
    for (f = 1; f < 192; f++) for (int c = 0; c < 3; c++) sim_draw(&S, 5, 1, f);
    for (; f < 192 + 1800; f++) { for (int c = 0; c < 3; c++) sim_draw(&S, 10000 + f, 1, f); if (S.m.unsure && !unsure_at) unsure_at = f; }
    for (; f < 192 + 1800 + 1200; f++) for (int c = 0; c < 3; c++) sim_draw(&S, 77, 1, f);
    for (; f < 192 + 1800 + 1200 + 600; f++) for (int c = 0; c < 3; c++) sim_draw(&S, 50000 + f, 1, f);
    CHECK(S.m.unsure && unsure_at > 192 && unsure_at - 192 <= 35 && S.bakes == 0 && S.emptied == 0);
    /* 5. Kst6's first emptying: a mesh with camera-dependent constants, baked while the camera stood still at a wall
     * (27 s known), then the camera moves on: unsure, store KEPT (old rule: emptied) */
    sim_init(&S, 393, 0.0, 0);
    g_still = 300;
    for (f = 300; f < 812; f++) sim_draw(&S, 42, 1, f);                 /* camera still 300..811: one instance */
    g_still = ~0u;
    for (; f < 1200; f++) sim_draw(&S, 100000 + f, 1, f);              /* camera moving: a new instance a frame */
    CHECK(S.bakes == 1 && S.emptied == 0 && S.m.unsure && S.unsure_baked == 1 && !S.m.mover);
    /* 6. a vehicle that waits 25 s with the camera still before it first moves would be baked; it drives off while the
     * camera still stands (an AI car leaving a still player): mover, the store emptied once */
    sim_init(&S, 900, 0.0, 0);
    g_still = 1;
    for (f = 1; f < 750; f++) for (int c = 0; c < 3; c++) sim_draw(&S, 5, 1, f);
    for (; f < 900; f++) for (int c = 0; c < 3; c++) sim_draw(&S, 20000 + f, 1, f);
    CHECK(S.m.mover && S.bakes == 1 && S.emptied == 1);
    g_still = ~0u;
    /* 7. Kst6's second emptying: new content once at a baked mesh's address (streaming): kept; content rewritten
     * twice within 10 s (skinned): volatile, emptied */
    sim_init(&S, 126, 0.0, 0);
    for (f = 1; f < 1320; f++) sim_draw(&S, 9, 1, f);
    for (; f < 1500; f++) sim_draw(&S, 9, 2, f);
    CHECK(S.bakes == 1 && S.emptied == 0 && !S.m.vol && S.m.vb_changes == 1);
    for (; f < 1600; f++) sim_draw(&S, 9, 3, f);
    CHECK(S.m.vol && S.emptied == 1);
    /* 8. a world instance appearing 1 s after the anchor: baked once the mesh is 20 s known */
    sim_init(&S, 300, 0.0, 0);
    int baked_at = -1;
    for (f = 30; f < 1200 && baked_at < 0; f++) if (sim_draw(&S, 3, 1, f)) baked_at = (int)f;
    CHECK(baked_at == 600);
    /* table upkeep */
    CHECK(rsx_st_inst_keep(1, 0, 10000, 150) && rsx_st_inst_keep(0, 9900, 10000, 150) && !rsx_st_inst_keep(0, 9800, 10000, 150));

'''
s = s[:a] + new + s[b:]
p.write_text(s, encoding='utf-8', newline='\n')
print('patched')
