r"""run_vk.py: adds lighting look arms (exe slot l) BEFORE the timing pair Klt5t (visual-only arms; Klt5t/Klt6t stay
last because they need EA Desktop/Epic closed). usage: py -3 add_arms_before.py"""
import pathlib
root = pathlib.Path(__file__).resolve().parents[4]
ab2 = root / 'generated' / 'analysis' / 'vksync' / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
BASE = {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '2', 'RSX_LIGHTING_CASTSTAT': '1'}
arms = [
    ('lt9', dict(BASE)),                                   # anchored per-frame fit + screen-space sun shadows (default on)
    ('lt10', {**BASE, 'RSX_FX_DEBUG': '7'}),               # the screen-space shadow term alone (white = lit)
    ('lt11', {**BASE, 'RSX_SHOTS_MAX': '12'}),             # Klt9 again (its shots and race logs were lost to a full C: drive)
    ('lt12', {**BASE, 'RSX_SHOTS_MAX': '12'}, 'l2'),       # + AO by default (exe slot l2: AO weighted to the ambient share)
    # brightness: darker tone curve (exposure 0.5, white 1.2), smaller sun wrap and sky fill; the launcher's exposure
    # readback (ASYNC=0). lt13 enhanced, lt13o the original look on the same exe and settings: the matched pair.
    ('lt13', {**BASE, 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}, 'l3'),
    ('lt13o', {'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}, 'l3'),
    # strict continuity (centre from our camera pose only, D/size/tile latched, no fallback flips), kept cascade = middle
    # (KEEP=1: the widest lost the nearby trees' ground shadows), per-frame box log; matched against Klt13o
    ('lt14', {**BASE, 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0', 'RSX_LIGHTING_KEEP': '1',
              'RSX_LIGHTING_BOXLOG': str(root / 'generated' / 'analysis' / 'lighting' / 'boxlog_lt14.csv')}, 'l4'),
    ('lt15', {**BASE, 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0', 'RSX_LIGHTING_KEEP': '0',
              'RSX_LIGHTING_BOXLOG': str(root / 'generated' / 'analysis' / 'lighting' / 'boxlog_lt15.csv')}, 'l4'),
    # world-anchored window (camera position only, snapped to the world texel grid), kept = nearest (KEEP default 0),
    # matched against lt16o (the original look, same exe)
    ('lt16', {**BASE, 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0',
              'RSX_LIGHTING_BOXLOG': str(root / 'generated' / 'analysis' / 'lighting' / 'boxlog_lt16.csv')}, 'l5'),
    ('lt16o', {'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}, 'l5'),
    # RSX_SHADOW_WORLD: every cascade drawn, all texel grids world-fixed (power-of-two sizes, one origin on the coarsest
    # grid, windows ahead by D_i); lt17 enhanced (+ SS shadows from 450 m, overlapping the map's end), lt17w the ORIGINAL
    # look with only the world-fixed shadows, lt17o the original baseline on the same exe
    ('lt17', {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '3', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_FX_SSSHADOW_FAR': '450',
              'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}, 'l6'),
    ('lt17w', {'RSX_SHADOW_WORLD': '1', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}, 'l6'),
    ('lt17o', {'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}, 'l6'),
    # colour grading: Klt17's enhanced setup + the built-in tropical LUT (RSX_FX_GRADE=tropical); compare with Klt17
    ('lt18', {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '3', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_FX_SSSHADOW_FAR': '450',
              'RSX_FX_GRADE': 'tropical', 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}, 'l7'),
]
add = ''; order = ''
for arm in arms:
    tag, extra = arm[0], arm[1]
    slot = arm[2] if len(arm) > 2 else 'l'
    if f"K_BY_TAG['{tag}']" in s: continue
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    ex = ''.join(f", {k!r}: {v!r}" for k, v in extra.items())
    add += (f"K_BY_TAG['{tag}'] = ('{slot}', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '60'{ex}}})   # K{tag}: lighting look arm (lighting/FINDINGS.md)\n")
    order += f"'K{tag}', "
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    a = "'Klt5t'"
    i = s.index('ORDER = ')
    j = s.index(a, i)
    s = s[:j] + order + s[j:]
    p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
