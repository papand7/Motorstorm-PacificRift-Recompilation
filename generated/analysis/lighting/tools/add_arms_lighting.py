r"""run_vk.py: lighting arms (exe slot l = build/lighting-link, RSX_LIGHTING). lt0 original, lt1 enhanced
(sun wrap + sky fill), lt2 enhanced + baked vertex colour removed, lt3 enhanced without the tone mapping (lt1 has it: RSX_LIGHTING
implies RSX_FX_TONEMAP=1), lt4 + one cascade (look), lt5t/lt6t timing pair: original vs enhanced+one
cascade with RSX_DRAIN_PROF and caster statistics (need a non-visual-only run: EA Desktop/Epic closed). Same env as Kk105 (K base, HDR on, no RT).
usage: py -3 add_arms_lighting.py ; then per arm: RUN_VK_PLAY=1 RUN_VK_RACE_S=150 py -3 run_vk.py launch K <tag>
alongside py -3 ../tools/auto_drive.py <tag> 6 12 6"""
import pathlib
root = pathlib.Path(__file__).resolve().parents[4]
ab2 = root / 'generated' / 'analysis' / 'vksync' / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
add = ''; order = ''
for tag, extra in (('lt0', {}), ('lt1', {'RSX_LIGHTING': '1'}), ('lt2', {'RSX_LIGHTING': '1', 'RSX_LIGHTING_BAKE': '0'}), ('lt3', {'RSX_LIGHTING': '1', 'RSX_FX_TONEMAP': '0'}), ('lt4', {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '1', 'RSX_LIGHTING_CASTSTAT': '1'}), ('lt5t', {'RSX_LIGHTING_CASTSTAT': '1', 'RSX_DRAIN_PROF': '1'}), ('lt6t', {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '1', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_DRAIN_PROF': '1'}), ('lt7', {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '1', 'RSX_LIGHTING_CASTSTAT': '1'}), ('lt8', {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '2', 'RSX_LIGHTING_CASTSTAT': '1'})):
    if f"K_BY_TAG['{tag}']" in s: continue
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    ex = ''.join(f", {k!r}: {v!r}" for k, v in extra.items())
    add += (f"K_BY_TAG['{tag}'] = ('l', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '60'{ex}}})   # K{tag}: lighting A/B (lighting/FINDINGS.md)\n")
    order += f", 'K{tag}'"
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    a = "'Yy1']"
    assert s.count(a) == 1
    s = s.replace(a, order[2:] + ", 'Yy1']")
    p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
