"""T172: moves the test_stencil_exact pins to the RSX_DEPTH_VOLUME text; syntax-checks the backend with the T171 build's flags."""
import re, subprocess, sys
from pathlib import Path

M = Path(__file__).resolve().parents[4]
T = M / 'ps3recomp-t172'
if sys.argv[1] == 'pins':
    p = T / 'tools' / 'test_stencil_exact.py'
    s = p.read_text('utf-8', newline='')
    for a, b in (("if (ds_state_on()) return dr->g_ds_key;", "if (ds_state_on() || dr_volume(dr)) return dr->g_ds_key;"),
                 ("be.count('ds_bind_exact() && zeta_sampled_only_as_color(dr, z)') == 1", "be.count('(ds_bind_exact() || dr_volume(dr)) && zeta_sampled_only_as_color(dr, z)') == 1"),
                 ("be.count('((dr->fp_units >> _u) & 1u) && ds_bind_exact() &&') == 1", "be.count('((dr->fp_units >> _u) & 1u) && (ds_bind_exact() || dr_volume(dr)) &&') == 1"),
                 ("be.count('if (ds_bind_exact() && cur_z >= 0 &&') == 1", "be.count('if ((ds_bind_exact() || (depth_volume_on() && !dr_volume(dr))) && cur_z >= 0 &&') == 1")):
        assert a in s, a
        s = s.replace(a, b)
    p.write_text(s, 'utf-8', newline='')
else:
    n = (M / 'build' / 'motorstorm-t171' / 'build.ninja').read_text('utf-8', 'replace')
    i = n.index('rsx_d3d12_backend.c.obj: C_COMPILER')
    blk = n[i:i + 6000]
    inc = re.search(r'INCLUDES = (.*)', blk)[1].replace('ps3recomp-t171', 'ps3recomp-t172')
    fl = re.search(r'\n  DEFINES = (.*)', blk)
    args = ['clang-cl', '/nologo', '/Zs', '/std:c17', '-w'] + (fl[1].split() if fl else []) + inc.split() + [str(T / 'libs' / 'video' / 'rsx_d3d12_backend.c')]
    r = subprocess.run(args, capture_output=True, text=True)
    print('rc', r.returncode, (r.stdout + r.stderr)[-1500:])
