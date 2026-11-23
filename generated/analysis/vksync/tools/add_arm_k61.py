"""Add launch Kk61: the PBR lighting race. Kk49's configuration (1080p, MSPR_PATCH=drs, the upscaled pack
build/texpack/ms2, now with pbr/<key>.dds maps) + RSX_TEX_PBR=1 and RSX_TEX_PBR_AB=150 (on and off by
turns every 150 frames, for pictures of both in one race), plus [main-cyc]. Exe 000ad59d.

usage: py -3 add_arm_k61.py"""
import pathlib

root = pathlib.Path(__file__).resolve().parents[4]
p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
lines = s.split('\n')
i = [k for k, l in enumerate(lines) if l.startswith("ARMS['K']") and '   # Kk60: ' in l][0]
pack = (root / 'build' / 'texpack' / 'ms2').as_posix()
lines.insert(i + 1, "ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if not k.startswith('RSX_ENGINE_')}, "
                    "'RSX_RES_SCALE': '1.5', 'RSX_TEX_PACK': '%s', 'RSX_TEX_PBR': '1', 'RSX_TEX_PBR_AB': '150'})"
                    "   # Kk61: exe 000ad59d, Kk49's configuration + PBR lighting from the pack's maps, on/off every 150 frames"
                    % pack)
s = '\n'.join(lines)


def sub(a, b):
    global s
    assert s.count(a) == 1, (a, s.count(a))
    s = s.replace(a, b)


sub("'Kk59', 'Kk60', 'Yy1']", "'Kk59', 'Kk60', 'Kk61', 'Yy1']")
sub("MAX_LAUNCHES = 107", "MAX_LAUNCHES = 108")
p.write_bytes(s.encode('utf-8'))
print('ok')
