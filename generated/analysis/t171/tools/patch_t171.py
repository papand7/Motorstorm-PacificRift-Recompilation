"""T171: default RSX_SHADER_WINDOW on. usage: py -3 patch_t171.py <ps3recomp tree>"""
import sys
T = sys.argv[1]


def sub(path, pairs):
    p = f'{T}/{path}'
    s = open(p, encoding='utf-8', newline='').read()
    nl = '\r\n' if '\r\n' in s else '\n'
    for a, b in pairs:
        a, b = a.replace('\n', nl), b.replace('\n', nl)
        assert a in s, a
        s = s.replace(a, b)
    open(p, 'w', encoding='utf-8', newline='').write(s)


sub('libs/video/rsx_shader_window.h', [
    (""" * RSX_SHADER_WINDOW=1 (read once, off by default) remaps WPOS reads, for
 * programs that make them, to the guest window: the pipeline key gains the
 * window only for those programs, so every other pipeline is unchanged.
""", """ * WPOS reads are remapped, for programs that make them, to the guest window
 * (read once, on by default; RSX_SHADER_WINDOW=0 restores SV_Position): the
 * pipeline key gains the window only for those programs, so every other
 * pipeline is unchanged. MotorStorm's tyre tracks (fp 0x022CD841) relight the
 * scene under them through this lookup: mirrored, they showed the top of the
 * screen in the ground (T171).
"""),
    ("return e && e[0] == '1' && !e[1]; }", "return !(e && e[0] == '0' && !e[1]); }"),
])
sub('libs/video/rsx_d3d12_backend.c', [
    ("/* RSX_SHADER_WINDOW=1 (read once, off by default): the draw's window",
     "/* RSX_SHADER_WINDOW (read once, on by default, =0 off): the draw's window"),
    ('msaa=%d depth_state=%d mrt_state=%d rt_reinterp=%d%c",', 'msaa=%d depth_state=%d mrt_state=%d rt_reinterp=%d shader_window=%d%c",'),
    ('rt_feedback_on(), msaa_on(), ds_state_on(), mrt_state_on(), rt_reinterp_on(), 10);',
     'rt_feedback_on(), msaa_on(), ds_state_on(), mrt_state_on(), rt_reinterp_on(), shader_window_on(), 10);'),
])
sub('tools/test_shader_window.py', [
    ("the switch opt-in and read once", "the switch on by default and read once"),
    ("""'RSX_SHADER_WINDOW is opt-in ("1") and read once'""", """'RSX_SHADER_WINDOW is on by default ("0" off) and read once'"""),
    ("""check('if (!shader_window_on()) return 0u;' in be, 'switch off: no request, every pipeline as before')""",
     """check('if (!shader_window_on()) return 0u;' in be and "e[0] == '0' && !e[1]" in sw, 'RSX_SHADER_WINDOW=0: no request, every pipeline as before')"""),
])
print('patched')
