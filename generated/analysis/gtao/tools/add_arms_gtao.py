r"""run_vk.py: adds the GTAO look pair (exe slot gt1 = build/gtao-link) BEFORE 'Klt5t' (after the launched Kbl2a/Kbl2b; visual-only
arms; the timing arms stay last; ORDER must keep matching launches_used.jsonl). Klt19 = enhanced + GTAO (RSX_FX_AO=gtao, the new default), Klt19c = the same exe and setup with the
classic AO (RSX_FX_AO=old); both log GPU timestamps of the AO passes (RSX_FX_TIME=1). usage: py -3 add_arms_gtao.py"""
import pathlib
root = pathlib.Path(__file__).resolve().parents[4]
ab2 = root / 'generated' / 'analysis' / 'vksync' / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
BASE = {'RSX_LIGHTING': '1', 'RSX_LIGHTING_CASCADES': '3', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_FX_SSSHADOW_FAR': '450',
        'RSX_FX_TIME': '1', 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}
arms = [
    ('lt19', {**BASE, 'RSX_FX_AO': 'gtao'}, 'gt1'),
    ('lt19c', {**BASE, 'RSX_FX_AO': 'old'}, 'gt1'),
]
add = ''; order = ''
for tag, extra, slot in arms:
    if f"K_BY_TAG['{tag}']" in s: continue
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    ex = ''.join(f", {k!r}: {v!r}" for k, v in extra.items())
    add += (f"K_BY_TAG['{tag}'] = ('{slot}', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '60'{ex}}})   # K{tag}: GTAO look arm (gtao/tools/add_arms_gtao.py)\n")
    order += f"'K{tag}', "
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    i = s.index('ORDER = ')
    j = s.index("'Klt5t'", i)
    s = s[:j] + order + s[j:]
    p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
