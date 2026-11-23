r"""run_vk.py: slot exe_st9 and the debug arms Kst9 / Kst9o inserted right AFTER 'Ksh3' in ORDER (refuses if that would
change ORDER's launched prefix). Shot folders are pre-created (the exe does not create them).
Kst7: static layer, Kst7 classes (camera-still mover evidence, unsure meshes, streaming kept, small meshes out, instance
table rebuilt), probe every 20 s, RSX_SHADOW_TILES_BAKECHECK=6 (bake target / dynamic map / store read back around the
first 6 merges), RSX_SHADOW_TILES_CDUMP (object constants with the camera, for the view-dependence question).
Kst7o: the same with the static layer off. Drive: RUN_VK_VISUAL_ONLY=1 RUN_VK_RACE_S=200, auto_drive.py st7|st7o 4 6 160.
usage: py -3 add_arm_st7.py <exe>"""
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
    'st9': {**BASE, 'RSX_SHADOW_TILES_STATIC': '0', 'RSX_SHADOW_TILES_DEBUG': '1', 'RSX_SHADOW_TILES_READLOG': '8',
            'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st9.csv')},
    'st9o': {**BASE, 'RSX_SHADOW_TILES_STATIC': '0', 'RSX_SHADOW_TILES_DEBUG': '2', 'RSX_SHADOW_TILES_READLOG': '8',
             'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st9o.csv')},
}
SLOT = 'st9'
AFTER = 'Ksh3'
exe = pathlib.Path(sys.argv[1])
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
i = s.index('ORDER = '); j = s.index('\n', i)
ORDER = eval(s[i + 8:j])
used = [json.loads(l)['tag'] for l in (ab2 / 'launches_used.jsonl').read_text().splitlines() if l.strip()]
assert ORDER[:len(used)] == used, 'ORDER prefix differs from launches_used'
k = ORDER.index(AFTER) + 1
assert k >= len(used), f'{AFTER} already launched and followed: arms cannot go right after it'
d = ab2 / f'exe_{SLOT}'; d.mkdir(exist_ok=True)
shutil.copy2(exe, d / 'MotorStormPacificRiftRecomp.exe')
h = hashlib.sha256((d / 'MotorStormPacificRiftRecomp.exe').read_bytes()).hexdigest()
(ab2 / f'exe_{SLOT}.sha256').write_text(h + '\n')
print('slot', SLOT, h)
add = ''; order = []
for tag, env in ARMS.items():
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    if f"K_BY_TAG['{tag}']" in s: print('already', tag); continue
    ex = ''.join(f", {k2!r}: {v!r}" for k2, v in env.items())
    add += (f"K_BY_TAG['{tag}'] = ('{SLOT}', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}{ex}}})   # K{tag}: static shadow layer, phase-1 receiver debug: st9 DEBUG=1 (window reads shadowed), st9o DEBUG=2 (depth difference)\n")
    order.append(f'K{tag}')
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    i = s.index('ORDER = ')
    jj = s.index(f"'{AFTER}', ", i) + len(f"'{AFTER}', ")
    s = s[:jj] + ''.join(f"'{t}', " for t in order) + s[jj:]
    i = s.index('ORDER = '); j = s.index('\n', i)
    new = eval(s[i + 8:j])
    assert new == ORDER[:k] + order + ORDER[k:] and new[:len(used)] == used
    p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
