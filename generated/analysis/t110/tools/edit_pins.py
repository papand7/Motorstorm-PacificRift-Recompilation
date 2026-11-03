"""T110: keep T101's and T107's pins truthful after the opt-in corrections.
  py -3 -I edit_pins.py <tree>"""
import sys
from pathlib import Path
T = Path(sys.argv[1])
def rep(p, old, new):
    s = p.read_text(encoding='utf-8'); assert s.count(old) == 1, (p, old[:120]); p.write_text(s.replace(old, new), encoding='utf-8')

p = T / 'tools/test_t101_pins.py'
rep(p, '''    # VP-path uploads reject a draw when attribute 0's array is off (6 sites).
    ("attr0 gate x6",
     lambda t: len(re.findall(r"if \(!state->vertex_attribs\[0\]\.enabled\) \{ da_fail\(DA_R_POSITION_ATTRIB_DISABLED\); return 0; \}", t)) == 6),''',
'''    # VP-path uploads reject a draw when attribute 0's array is off (6 sites).
    # T110: through a0_drop / rsx_attr0_gate.h, which keeps that rule unless
    # RSX_ATTR0_CONST=1 (the model below is the default behaviour).
    ("attr0 gate x6",
     lambda t: len(re.findall(r"if \(a0_drop\(state\)\) \{ da_fail\(DA_R_POSITION_ATTRIB_DISABLED\); return 0; \}", t)) == 6
     and "if (!fix) return RSX_A0_DROP_LEGACY;" in (ROOT / "libs/video/rsx_attr0_gate.h").read_text(encoding="utf-8")
     and 'getenv("RSX_ATTR0_CONST"); fix = (e && e[0] == \'1\' && !e[1]) ? 1 : 0;' in t),''')
rep(p, '''    ("evict !used",
     lambda t: "if (slot < 0) {   /* evict an entry not used this frame */" in t
     and "if (!s_d3d.off_rt[i].used) { slot = i; break; }" in t),''',
'''    # T110: through rsx_rtpool_victim.h, whose rule without RSX_RTPOOL_GF=1 is this one.
    ("evict !used",
     lambda t: "if (slot < 0) {   /* evict an entry not used this frame */" in t
     and "slot = rsx_rtpool_victim(MAX_OFF_RTS, u_, g_, gf_rule, &fb);" in t
     and "if (!used[i]) { *fallback = frame_rule; return i; }" in (ROOT / "libs/video/rsx_rtpool_victim.h").read_text(encoding="utf-8")),''')

p = T / 'tools/test_d3d12_color_xfer.py'
rep(p, '''  - the guest-FP compile still goes through rsx_fp_decompile_shadow_ex and
    never calls rsx_fp_apply_srgb_output, so "host_xfer":"none" is accurate.
    When a later change honours the transfer, update host_xfer and this pin.''',
'''  - the guest-FP compile applies a transfer only under RSX_COLOR_XFER (T110):
    without it the request is NULL, the program compiles through
    rsx_fp_decompile_shadow_ex and no sRGB output is added, and RSXI says
    "host_xfer":"none"; with it RSXI names the mode.''')
rep(p, '''check('rsx_fp_decompile_shadow_ex' in pso and 'rsx_fp_apply_srgb_output' not in be,
      'guest-FP path applies no transfer, so host_xfer "none" is accurate')''',
'''xr = body(be, 'dr_xfer_req')
check('rsx_fp_decompile_shadow_ex' in pso and be.count('rsx_fp_apply_srgb_output(') == 1 and
      'if (xs && rsx_fp_apply_srgb_output(hlsl, sizeof(hlsl)) <= 0)' in pso and 'xs = xf->srgb_output;' in pso and
      'if (!m || !dr_color_xfer(dr, dr->rt_fmt, x)) return NULL;' in xr and
      'm = e ? (int)(strtoul(e, NULL, 0) & 7u) : 0;' in be,
      'guest-FP path applies a transfer only under RSX_COLOR_XFER')
check('if (xfer_mode())' in od and '\\\\"host_xfer\\\\":\\\\"none\\\\"' in od,
      'host_xfer is "none" unless RSX_COLOR_XFER is set')''')
print('ok')
