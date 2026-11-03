"""T115B: point tools/test_t115_pins.py at the renamed T115B entry points (same checks)."""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'tools/test_t115_pins.py'
t = p.read_text()


def rep(a, b):
    global t
    assert t.count(a) == 1, a
    t = t.replace(a, b)


rep("""    p = body(h, 'rsx_texmip_plan_make')
    legacy = body(h, 'rsx_texmip_legacy_cube_stride')
    return ('rsx_texture_mip_chain(fmt, w, h, mode ? want : 1u, 0, p->lv)' in p""",
    """    p = body(h, 'rsx_texmip_plan_make_pitched')
    legacy = body(h, 'rsx_texmip_legacy_cube_stride')
    return ('rsx_texture_mip_chain(fmt, w, h, mode ? want : 1u, pitch, p->lv)' in p
            and 'return rsx_texmip_plan_make_pitched(fmt, w, h, mips, cube, ea, mode, 0u, p);'
            in body(h, 'rsx_texmip_plan_make')""")
rep("""    i_plan = u.find('rsx_texmip_plan_make(fmt, w, h, mips, cube, off, texmip_mode(), &mp);')""",
    """    i_plan = u.find('rsx_texmip_plan_make_pitched(fmt, w, h, mips, cube, off, texmip_mode(), tpitch, &mp);')""")
rep("rsx_d3d12_texmip_fill(' in u.replace(", "rsx_d3d12_texmip_fill_ex(' in u.replace(")
rep("'if (mp.levels > 1) rsx_d3d12_texmip_copy(' in u", "'if (mp.levels > 1) rsx_d3d12_texmip_copy_ex(' in u")
rep("u.count('mp.levels = 1; mp.src_bytes = mp.lv[0].tl.face_bytes; td.MipLevels = 1;') == 2",
    "u.count('mp.levels = 1; mp.src_bytes = rsx_texmip_level_read_bytes(&mp.lv[0]); td.MipLevels = 1;') == 2")
p.write_text(t)
