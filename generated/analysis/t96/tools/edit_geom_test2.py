MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T96: randomized exact-reservation case for test_geom_expand.c and updated source pins."""
import sys
sys.path.insert(0, __import__('tempfile').gettempdir())
from t96rep import R

W = (MS_ROOT + r'\ps3recomp-t96')
r = R(W + r'\libs\video\tests\test_geom_expand.c')
r.rep('''    /* 11. what 786,433 expanded vertices means in guest terms */''',
'''    /* 12. exact reservation against the reference on random restart-heavy
     * streams: strips and fans, u16 and u32, restarts anywhere (first and
     * last index of a batch, runs of restarts, across batch seams). */
    { uint32_t seed = 0x9E3779B9u, bad = 0, n_str = 0; uint64_t tot = 0, bnd = 0;
      for (int t = 0; t < 400; t++) {
          seed = seed * 1664525u + 1013904223u;
          const int u16 = (seed >> 8) & 1, fan = (seed >> 9) & 1;
          const uint32_t rv = u16 ? 0xFFFFu : 0xFFFFFFFFu, len = 1 + ((seed >> 12) % 900);
          const uint32_t per = 1 + ((seed >> 4) % 9);
          m1(0x1DAC, 1); m1(0x1DB0, rv);
          for (uint32_t k = 0; k < len; k++) {
              seed = seed * 1664525u + 1013904223u;
              put_idx(u16, k, ((seed >> 16) % per) == 0 ? rv : (seed >> 3) % 5000);
          }
          draw_index(fan ? RSX_PRIMITIVE_TRIANGLE_FAN : RSX_PRIMITIVE_TRIANGLE_STRIP, 0, len, u16); run();
          a = expand_fresh(&ref, &rt);
          if (a.want != ref || a.emitted != ref) bad++;
          tot += a.want; bnd += a.bound; n_str++;
      }
      m1(0x1DAC, 0);
      CHECK(bad == 0, "random restart streams: exact want == writes == reference in %u of %u (bound/exact %.2f)",
            n_str - bad, n_str, (double)bnd / (double)(tot ? tot : 1)); }
    /* count_tris without restart equals the old bound; the 32-bit conversion refuses overflow */
    { ps3_prim_stream s; memset(&s, 0, sizeof s); ps3_prim_stream_batch(&s, 1, 6, 0, 0);
      g_fetch_indexed = 0; g_fetch_first = 0;
      int ok1, ok2, ok3;
      const uint32_t v1 = ps3_prim_tris_to_verts(ps3_prim_stream_count_tris(&s, 256, 0, 0, fetch, NULL), &ok1);
      const uint32_t v2 = ps3_prim_tris_to_verts(0x55555555ull, &ok2);
      const uint32_t v3 = ps3_prim_tris_to_verts(0x55555556ull, &ok3);
      CHECK(v1 == 762 && ok1 && v1 == ps3_prim_stream_max_tris(&s, 256) * 3, "no restart: exact == bound (762)");
      CHECK(ok2 && v2 == 0xFFFFFFFFu && !ok3 && v3 == 0, "tris->verts: 0x55555555 fits, 0x55555556 overflows"); }

    /* 11. what 786,433 expanded vertices means in guest terms */''')
r.save()

p = R(W + r'\tools\test_geom_expand.py')
p.rep("""                   ('upload_strip_vp', 'vp_reserve(tris * 3, state, fan ? "fan" : "strip", 0,'),""",
      """                   ('upload_strip_vp', 'vp_reserve(vp_strip_verts(&s_prim_stream, state, first, count, 0), state, fan ? "fan" : "strip", 0,'),""")
p.rep("""                   ('upload_strip_vp_indexed', 'vp_reserve(tris * 3, state, fan ? "fan" : "strip", 1,')):""",
      """                   ('upload_strip_vp_indexed', 'vp_reserve(vp_strip_verts(&s_prim_stream, state, first, count, 1), state, fan ? "fan" : "strip", 1,')):""")
p.rep("""check(d3d.count('u32 tris = ps3_prim_stream_max_tris(&s_prim_stream, count);') == 2,
      'strip/fan want is the stream upper bound (restart over-reserves)')""",
"""check('ps3_prim_stream_max_tris(&s_prim_stream' not in d3d and 'ps3_prim_stream_count_tris(s, count, restart, st->restart_index,' in d3d,
      'strip/fan want is the exact restart-aware count (T96), not the upper bound')""")
p.save()
print('ok')
