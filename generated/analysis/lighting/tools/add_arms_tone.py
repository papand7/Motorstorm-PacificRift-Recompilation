r"""run_vk.py: copies a private exe into slot exe_<slot> and adds visual-only look arms BEFORE 'Klt5t' (timing arms stay
last). Never touches ORDER's launched entries (checks ORDER[:len(launches_used.jsonl)] is unchanged).
usage: py -3 add_arms_tone.py <exe> <slot> <tag> [<tag> ...]   (arms defined in ARMS by tag)"""
import pathlib, shutil, hashlib, sys, json, re
root = pathlib.Path(__file__).resolve().parents[4]
ab2 = root / 'generated' / 'analysis' / 'vksync' / 'ab2'
ST = root / 'generated' / 'analysis' / 'shadowtiles'
# enhanced lighting on the world-tile shadows (dynamic map + static layer), as the user asked; same shadow settings in
# every arm and its baseline
BASE = {'RSX_LIGHTING': '1', 'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_FX_SSSHADOW_FAR': '450',
        'RSX_FX_TIME': '1', 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0'}
FR = {'RSX_SHOTS_FROM': '1560', 'RSX_SHOTS_EVERY': '6'}   # frame-indexed shots, the same frames in both arms
ARMS = {
    'tg4o': ({**BASE, 'RSX_FX_AO': 'old', 'RSX_FX_GROUNDTOE': '1.0', **FR}, 'ground toe off (previous look) matched baseline'),
    'tg4':  ({**BASE, 'RSX_FX_AO': 'old', **FR}, 'ground toe 0.65 (new default) look arm'),
}
exe, slot, tags = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
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
    if f"K_BY_TAG['{tag}']" in s: print('already', tag); continue
    env, what = ARMS[tag]
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    ex = ''.join(f", {k!r}: {v!r}" for k, v in env.items())
    add += (f"K_BY_TAG['{tag}'] = ('{slot}', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '60'{ex}}})   # K{tag}: {what} (lighting/FINDINGS.md)\n")
    order += f"'K{tag}', "
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    i = s.index('ORDER = ')
    j = s.index("'Klt5t'", i)
    s = s[:j] + order + s[j:]
    order1 = eval(re.search(r"^ORDER = (\[.*?\])", s, re.M).group(1))
    assert order1[:len(used)] == used, 'insert would change the launched prefix'
    p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
