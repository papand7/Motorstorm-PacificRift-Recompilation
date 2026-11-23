r"""run_vk.py: copies the fog/shafts exe into slot exe_<slot> and adds two visual-only look arms (RSX_FX_FOG and
RSX_FX_SHAFTS on, and both off) BEFORE 'Klt5t' in ORDER. Same mechanism as gi/tools/add_arms_gi.py; the launched prefix of
ORDER is checked and must not change. Nothing is launched here.
usage: py -3 add_arms_fog.py <exe> <slot> <tag_on> <tag_off>"""
import pathlib, shutil, hashlib, sys, json, re
root = pathlib.Path(__file__).resolve().parents[4]
ab2 = root / 'generated' / 'analysis' / 'vksync' / 'ab2'
BASE = {'RSX_LIGHTING': '1', 'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_FX_SSSHADOW_FAR': '450',
        'RSX_FX_TIME': '1', 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}
ARMS = {
    'fs1':  ({**BASE, 'RSX_FX_FOG': '1', 'RSX_FX_SHAFTS': '1'}, 'enhanced look, height fog and sun shafts on (defaults)'),
    'fs1o': ({**BASE, 'RSX_FX_FOG': '0', 'RSX_FX_SHAFTS': '0'}, 'matched baseline, height fog and sun shafts off'),
    # world-anchored fog (estimated ground level, warm sand tint near the ground)
    'fs2':  ({**BASE, 'RSX_FX_FOG': '1', 'RSX_FX_SHAFTS': '1'}, 'enhanced look, world-anchored height fog + sun shafts on'),
    'fs2o': ({**BASE, 'RSX_FX_FOG': '0', 'RSX_FX_SHAFTS': '0'}, 'matched baseline, height fog and sun shafts off'),
}
exe, slot, tags = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
assert len(tags) == 2 and all(t in ARMS for t in tags) and tags[1] == tags[0] + 'o'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
assert not any(f"K_BY_TAG['{t}']" in s for t in tags), 'tags already exist'
assert f"'exe_{slot}'" not in s and not (ab2 / f'exe_{slot}').exists(), 'slot in use'
used = [json.loads(x)['tag'] for x in (ab2 / 'launches_used.jsonl').read_text().splitlines() if x.strip()]
order0 = eval(re.search(r"^ORDER = (\[.*?\])", s, re.M).group(1))
assert order0[:len(used)] == used, 'ORDER prefix != launched list'
d = ab2 / f'exe_{slot}'; d.mkdir(exist_ok=True)
shutil.copy2(exe, d / 'MotorStormPacificRiftRecomp.exe')
h = hashlib.sha256((d / 'MotorStormPacificRiftRecomp.exe').read_bytes()).hexdigest()
(ab2 / f'exe_{slot}.sha256').write_text(h + '\n')
print('slot', slot, h)
add = ''; order = ''
for tag in tags:
    env, what = ARMS[tag]
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    ex = ''.join(f", {k!r}: {v!r}" for k, v in env.items())
    add += (f"K_BY_TAG['{tag}'] = ('{slot}', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '60'{ex}}})   # K{tag}: {what} (fogshafts/RESULTS.md)\n")
    order += f"'K{tag}', "
a = "\nif __name__ == '__main__':"
assert s.count(a) == 1
s = s.replace(a, '\n' + add + a)
i = s.index('ORDER = ')
j = s.index("'Klt5t'", i)
s = s[:j] + order + s[j:]
order1 = eval(re.search(r"^ORDER = (\[.*?\])", s, re.M).group(1))
assert order1[:len(used)] == used, 'insert would change the launched prefix'
assert all(order1.index('K' + t) < order1.index('Klt5t') for t in tags)
p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
