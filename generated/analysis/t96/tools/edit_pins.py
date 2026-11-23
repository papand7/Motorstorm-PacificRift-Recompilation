MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T96: move four existing source pins to the intended new behaviour (same protections)."""
import sys
sys.path.insert(0, __import__('tempfile').gettempdir())
from t96rep import R

W = (MS_ROOT + r'\ps3recomp-t96\tools')
r = R(W + r'\test_draw_rejection.py')
r.rep("""      and all('ps3_prim_stream_max_tris(&s_prim_stream, count)' in bodies[h] for h in ('upload_strip_vp', 'upload_strip_vp_indexed')),""",
      """      and all('vp_strip_verts(&s_prim_stream, state, first, count,' in bodies[h] for h in ('upload_strip_vp', 'upload_strip_vp_indexed')),""")
r.rep("""      and 's_d3d.vp_vb_offset);' in gr,
      'growth copies the frame already uploaded to the same parity offset (records stay valid)')""",
      """      and 'copy);' in gr and 'const u32 copy = s_vpvb_at_end > 0 ? 0u : s_d3d.vp_vb_offset;' in gr,
      'growth before the replay (VPVB_GROW_AT_FRAME_END=0) copies the frame already uploaded to the same parity offset '
      '(records stay valid); at the frame end (T96 default) there is nothing to copy')""")
r.save()

r = R(W + r'\test_present_gate.py')
r.rep("""check('ps3_pg_display_clear(&s_pg, have_display_draws, s_d3d.draw_count,' in cb""",
      """check('ps3_pg_display_clear(&s_pg, have_display_draws, vpf_frame_draws(&s_vpf, s_d3d.draw_count),' in cb   # T96: + early-replayed draws""")
r.save()

r = R(W + r'\test_rf_phase.py')
r.rep("""    check('s_vpvb_at_end = (e && atoi(e) > 0) ? 1 : 0;' in rf and 'static int s_vpvb_at_end = -1;' in d3d,
          'VPVB_GROW_AT_FRAME_END is off unless set')
    check('if (!s_vpvb_at_end && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {' in rf, 'off: the entry growth is the original one')""",
      """    check('s_vpvb_at_end = (e && atoi(e) <= 0) ? 0 : 1;' in rf and 'static int s_vpvb_at_end = -1;' in d3d,
          'VPVB_GROW_AT_FRAME_END is on unless set to 0 (T96 default)')
    check('if (!s_vpvb_at_end && !s_vpf.in_flush && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {' in rf,
          'off: the entry growth is the original one (not inside an early replay)')""")
r.rep("""    i_end = rf.find('if (s_vpvb_at_end > 0 && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {')""",
      """    i_end = rf.find('if (s_vpvb_at_end > 0 && !s_vpf.in_flush && s_d3d.vp_vb && s_d3d.vp_vb_mapped) {')""")
r.save()
print('ok')
