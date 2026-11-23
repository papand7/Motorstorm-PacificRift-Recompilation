MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T96: switch test_geom_expand.c to the exact reservation and the corrected T94 fixture."""
import sys
sys.path.insert(0, __import__('tempfile').gettempdir())
from t96rep import R

r = R((MS_ROOT + r'\ps3recomp-t96\libs\video\tests\test_geom_expand.c'))
r.rep(''' * then expanded the way the D3D12 VP path does (prim_stream.h assembly,
 * vp_vb_budget.h reservation: want = upper bound, emitted = triangles * 3),''',
''' * then expanded the way the D3D12 VP path does (prim_stream.h assembly,
 * vp_vb_budget.h reservation: want = ps3_prim_stream_count_tris * 3, exact
 * since T96; the old restart-blind bound is kept alongside as `bound`),''')
r.rep('typedef struct { uint64_t want, emitted, tris, degenerate; } acct;',
      'typedef struct { uint64_t want, emitted, tris, degenerate, bound; } acct;')
r.rep('''static ps3_prim_stream g_ps;
static acct backend_expand(const batch* b, int n, vpvb_budget* bud, uint32_t* used)
{
    acct a = { 0, 0, 0, 0 };''', '''static ps3_prim_stream g_ps;
static uint32_t g_fetch_dma, g_fetch_first; static int g_fetch_indexed;
static uint32_t fetch(void* ctx, uint32_t k)
{
    (void)ctx;
    return g_fetch_indexed ? get_idx(g_fetch_dma, g_fetch_first + k) : g_fetch_first + k;
}
static acct backend_expand(const batch* b, int n, vpvb_budget* bud, uint32_t* used)
{
    acct a = { 0, 0, 0, 0, 0 };''')
r.rep('''        uint32_t want, o = 0;
        if (x->prim == RSX_PRIMITIVE_TRIANGLES) {
            want = x->count; o = x->count;
        } else if (x->prim == RSX_PRIMITIVE_QUADS) {
            want = x->count / 4 * 6; o = want;''', '''        uint32_t want, o = 0, bound;
        if (x->prim == RSX_PRIMITIVE_TRIANGLES) {
            want = x->count; o = x->count; bound = want;
        } else if (x->prim == RSX_PRIMITIVE_QUADS) {
            want = x->count / 4 * 6; o = want; bound = want;''')
r.rep('''            want = ps3_prim_stream_max_tris(&g_ps, x->count) * 3;''', '''            bound = ps3_prim_stream_max_tris(&g_ps, x->count) * 3;
            g_fetch_dma = x->dma; g_fetch_first = x->first; g_fetch_indexed = x->indexed;
            int ok;
            want = ps3_prim_tris_to_verts(ps3_prim_stream_count_tris(&g_ps, x->count, rs, x->rval, fetch, NULL), &ok);
            if (!ok) want = 0xFFFFFFFFu;''')
r.rep('''        a.want += want; a.emitted += o; a.tris += o / 3;''',
      '''        a.want += want; a.emitted += o; a.tris += o / 3; a.bound += bound;''')
r.rep('''      CHECK(a.want == 756 && a.want - a.emitted == 9 * 50, "want %llu = upper bound; over-reservation 9 x 50 restarts = %llu",
            (unsigned long long)a.want, (unsigned long long)(a.want - a.emitted)); }''',
'''      CHECK(a.want == 306 && a.bound == 756 && a.bound - a.want == 9 * 50,
            "want %llu = exact (T96); old bound %llu over-reserved 9 x 50 restarts", (unsigned long long)a.want,
            (unsigned long long)a.bound); }''')
r.rep('''     * as 4-index strips (quads) between restarts, continuing batch 0. */''',
'''     * as 4-index strips (quads) between restarts, continuing batch 0. Batch 1
     * has restarts at its positions 0, 5, .., 250 (51) and five indices after
     * the last one, the fifth repeating 4797 (205 non-restart indices, 204
     * distinct: idx_max stays 4797). Any layout matching the record writes
     * at least 3 * (205 - 2 * 51) = 309 (T97 cross-check). */''')
r.rep('''put_idx(1, 44434 + k, (k % 5 == 1) ? 0xFFFFu : v++);''',
      '''put_idx(1, 44434 + k, k == 511 ? 4797u : (k % 5 == 1) ? 0xFFFFu : v++);''')
r.rep('''      backend_expand(g_b + 1, 1, &bud, &used);
      const uint64_t want1 = bud.frame_want - w0, emit1 = used - u0;
      CHECK(want1 == 768 && emit1 == 306, "T94 record batch: want %llu (record: 768), writes %llu (51 quads x 6)",
            (unsigned long long)want1, (unsigned long long)emit1);
      printf("[INFO] T94 batch: reservation/writes = %.2f; unique vertices 204 -> 306 expanded (1.5x)\\n",
             (double)want1 / (double)emit1); }''', '''      const acct a1 = backend_expand(g_b + 1, 1, &bud, &used);
      const uint64_t want1 = bud.frame_want - w0, emit1 = used - u0;
      uint32_t nr = 0, lo = 0xFFFFFFFFu, hi = 0;
      for (uint32_t i = 0; i < 256; i++) { const uint32_t x = get_idx(0x10, 44690 + i);
          if (x == 0xFFFF) nr++; else { if (x < lo) lo = x; if (x > hi) hi = x; } }
      CHECK(nr == 51 && lo == 4594 && hi == 4797, "T94 fixture matches the record: %u restarts, idx %u..%u", nr, lo, hi);
      CHECK(a1.bound == 768 && want1 == 309 && emit1 == 309,
            "T94 record batch: old reservation %llu (record: 768), exact %llu, writes %llu (50 quads + a 5-index strip)",
            (unsigned long long)a1.bound, (unsigned long long)want1, (unsigned long long)emit1);
      printf("[INFO] T94 batch: old reservation/writes = %.2f, now 1.00\\n", (double)a1.bound / (double)emit1); }''')
r.save()
print('ok')
