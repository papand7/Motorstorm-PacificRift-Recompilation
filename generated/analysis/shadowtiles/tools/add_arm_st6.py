r"""run_vk.py: slot exe_st4 (the fixed static layer / cache, 2026-11-23) and the look arms Kst4, Kst5, Kst5b, inserted
BEFORE 'Klt5t' like add_arm.py (never touches ORDER's existing entries; refuses if ORDER's launched prefix would change).
usage: py -3 add_arm_st6.py <exe>
Kst6: the mesh/instance static classes (instanced meshes baked; movers told by their instances), probe every 20 s;
Kst6o: the same with the static layer off (shots to compare). Drive: RUN_VK_VISUAL_ONLY=1 RUN_VK_RACE_S=200, auto_drive.py st6 4 6 160 / st6o 4 6 160.
Older text:
Kst4: phase 2 in the user's Enhanced setup (RSX_TEX_PBR + pack: the static layer used to be refused with it), store
coverage probed every 30 s. Kst5 fills a fresh cache (period save 45 s: the save hitch), Kst5b starts from it.
Drive each with auto_drive.py (RUN_VK_VISUAL_ONLY=1 RUN_VK_RACE_S=150):  st4: 4 6 110   st5: 4 6 110   st5b: 4 1 110"""
import hashlib, json, pathlib, shutil, sys
root = pathlib.Path(__file__).resolve().parents[4]
ab2 = root / 'generated' / 'analysis' / 'vksync' / 'ab2'
ST = root / 'generated' / 'analysis' / 'shadowtiles'
PACK = root / 'build' / 'texpack' / 'ms2'   # the user's pack (play/textures/pack links here), read only
BASE = {'RSX_LIGHTING': '1', 'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_FX_AO': 'old',
        'RSX_FX_SSSHADOW_FAR': '450', 'RSX_ZSNAP_ON_WRITE': '1', 'RSX_TEX_BORDER': '1', 'RSX_RT_READBACK_ASYNC': '0',
        'RSX_TEX_PBR': '1', 'RSX_TEX_PACK': PACK.as_posix(), 'RSX_LIGHTING_CASTSTAT': '1',
        'RSX_SHOTS_EVERY': '90', 'RSX_SHOTS_MAX': '40'}
ARMS = {
    'st6': {**BASE, 'RSX_SHADOW_TILES_PROBE_S': '20', 'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st6.csv')},
    'st6o': {**BASE, 'RSX_SHADOW_TILES_STATIC': '0', 'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st6o.csv')},
}
_UNUSED = {
    'st5': {**BASE, 'RSX_SHADOW_TILES_CACHE': str(ST / 'cache_st5'), 'RSX_SHADOW_TILES_CACHE_SAVE_S': '45',
            'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st5.csv')},
    'st5b': {**BASE, 'RSX_SHADOW_TILES_CACHE': str(ST / 'cache_st5'), 'RSX_SHADOW_TILES_CACHE_SAVE_S': '0',
             'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st5b.csv')},
}
SLOT = 'st6'
exe = pathlib.Path(sys.argv[1])
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
i = s.index('ORDER = '); j = s.index('\n', i)
ORDER = eval(s[i + 8:j])
used = [json.loads(l)['tag'] for l in (ab2 / 'launches_used.jsonl').read_text().splitlines() if l.strip()]
assert ORDER[:len(used)] == used, 'ORDER prefix differs from launches_used'
k = ORDER.index('Klt5t')
assert k >= len(used), 'Klt5t already launched: arms cannot go before it'
d = ab2 / f'exe_{SLOT}'; d.mkdir(exist_ok=True)
shutil.copy2(exe, d / 'MotorStormPacificRiftRecomp.exe')
h = hashlib.sha256((d / 'MotorStormPacificRiftRecomp.exe').read_bytes()).hexdigest()
(ab2 / f'exe_{SLOT}.sha256').write_text(h + '\n')
print('slot', SLOT, h)
add = ''; order = []
for tag, env in ARMS.items():
    if f"K_BY_TAG['{tag}']" in s: print('already', tag); continue
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    ex = ''.join(f", {k2!r}: {v!r}" for k2, v in env.items())
    add += (f"K_BY_TAG['{tag}'] = ('{SLOT}', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}{ex}}})   # K{tag}: static shadow layer, mesh/instance classes (st6o: static off) (shadowtiles/RESULTS.md)\n")
    order.append(f'K{tag}')
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    i = s.index('ORDER = ')
    jj = s.index("'Klt5t'", i)   # after every launched/pending look arm; timing arms stay last
    s = s[:jj] + ''.join(f"'{t}', " for t in order) + s[jj:]
    i = s.index('ORDER = '); j = s.index('\n', i)
    new = eval(s[i + 8:j])
    assert new == ORDER[:k] + order + ORDER[k:] and new[:len(used)] == used
    p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
