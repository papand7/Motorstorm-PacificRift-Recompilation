r"""run_vk.py: copies a private RSX_SHADOW_TILES exe into slot exe_<slot> and adds visual-only look arms BEFORE 'Kbl2a'
(timing arms stay last). Never touches ORDER's existing entries. usage: py -3 add_arm.py <exe> <slot> <tag> [<tag> ...]
Arms are defined in ARMS below by tag."""
import pathlib, shutil, hashlib, sys
root = pathlib.Path(__file__).resolve().parents[4]
ab2 = root / 'generated' / 'analysis' / 'vksync' / 'ab2'
ST = root / 'generated' / 'analysis' / 'shadowtiles'
ARMS = {
    # original look (no RSX_LIGHTING, no tiles): vehicle ground decals kept (vd1o) / dropped (vd2o, RSX_DECAL_SKIP=1)
    'vd1o': {'RSX_FSR_MODE': '3', 'RSX_FSR': 'performance', 'MSPR_CAM_MODE': '0', 'PS3_SIM_PACE_HZ': '30',
            'MSPR_LOD_BIAS': '-2', 'MSPR_CULL_SCALE': '0.25', 'RSX_TEX_BORDER': '1', 'RSX_ZSNAP_ON_WRITE': '1',
            'RSX_RT_READBACK_ASYNC': '0', 'RSX_HDR': '0', 'MSPR_PATCH': 'drs,vfps,mblur,audiothread',
            'RSX_SHOTS_EVERY': '30', 'RSX_SHOTS_MAX': '24', 'RSX_DECAL_SKIP': '0'},
    'vd2o': {'RSX_FSR_MODE': '3', 'RSX_FSR': 'performance', 'MSPR_CAM_MODE': '0', 'PS3_SIM_PACE_HZ': '30',
            'MSPR_LOD_BIAS': '-2', 'MSPR_CULL_SCALE': '0.25', 'RSX_TEX_BORDER': '1', 'RSX_ZSNAP_ON_WRITE': '1',
            'RSX_RT_READBACK_ASYNC': '0', 'RSX_HDR': '0', 'MSPR_PATCH': 'drs,vfps,mblur,audiothread',
            'RSX_SHOTS_EVERY': '30', 'RSX_SHOTS_MAX': '24', 'RSX_DECAL_SKIP': '1'},
    # the square dark boxes round vehicles in Enhanced (user, 2026-11-23): the same Enhanced setup twice, vehicle ground
    # decals kept (vd1) / dropped (vd2, RSX_DECAL_SKIP=1); shots one per 30 frames from the drive's F9
    'vd1': {'RSX_LIGHTING': '1', 'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_FX_AO': 'old',
            'RSX_FX_SSSHADOW_FAR': '450', 'RSX_ZSNAP_ON_WRITE': '1', 'RSX_TEX_BORDER': '1', 'RSX_RT_READBACK_ASYNC': '0',
            'RSX_SHOTS_EVERY': '30', 'RSX_SHOTS_MAX': '24', 'RSX_DECAL_SKIP': '0'},
    'vd2': {'RSX_LIGHTING': '1', 'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_FX_AO': 'old',
            'RSX_FX_SSSHADOW_FAR': '450', 'RSX_ZSNAP_ON_WRITE': '1', 'RSX_TEX_BORDER': '1', 'RSX_RT_READBACK_ASYNC': '0',
            'RSX_SHOTS_EVERY': '30', 'RSX_SHOTS_MAX': '24', 'RSX_DECAL_SKIP': '1'},
    # Kvs1/Kvs2 again with shots spread one per 30 frames from the drive's F9 (race entry + wait + rec), and the
    # [tsr-obj] stats every 300 frames (exe fix2)
    'vs3': {'RSX_FSR_MODE': '3', 'RSX_FSR': 'performance', 'MSPR_CAM_MODE': '0', 'PS3_SIM_PACE_HZ': '30',
            'MSPR_LOD_BIAS': '-2', 'MSPR_CULL_SCALE': '0.25', 'RSX_TEX_BORDER': '1', 'RSX_RT_READBACK_ASYNC': '1',
            'RSX_HDR': '0', 'MSPR_PATCH': 'drs,vfps,mblur,audiothread', 'RSX_SHOTS_MAX': '24', 'RSX_SHOTS_EVERY': '30', 'RSX_FSR_OBJ_FIX': '0'},
    'vs4': {'RSX_FSR_MODE': '3', 'RSX_FSR': 'performance', 'MSPR_CAM_MODE': '0', 'PS3_SIM_PACE_HZ': '30',
            'MSPR_LOD_BIAS': '-2', 'MSPR_CULL_SCALE': '0.25', 'RSX_TEX_BORDER': '1', 'RSX_RT_READBACK_ASYNC': '1',
            'RSX_HDR': '0', 'MSPR_PATCH': 'drs,vfps,mblur,audiothread', 'RSX_SHOTS_MAX': '24', 'RSX_SHOTS_EVERY': '30', 'RSX_FSR_OBJ_FIX': '1'},
    # vehicle shadows far from the vehicles (user, Lighting Original, FSR 3.1): the user's settings, A/B of
    # RSX_FSR_OBJ_FIX (instance keys, no object motion for decals) on the same exe; shots at the race start
    'vs1': {'RSX_FSR_MODE': '3', 'RSX_FSR': 'performance', 'MSPR_CAM_MODE': '0', 'PS3_SIM_PACE_HZ': '30',
            'MSPR_LOD_BIAS': '-2', 'MSPR_CULL_SCALE': '0.25', 'RSX_TEX_BORDER': '1', 'RSX_RT_READBACK_ASYNC': '1',
            'RSX_HDR': '0', 'MSPR_PATCH': 'drs,vfps,mblur,audiothread', 'RSX_SHOTS_MAX': '24', 'RSX_FSR_OBJ_FIX': '0'},
    'vs2': {'RSX_FSR_MODE': '3', 'RSX_FSR': 'performance', 'MSPR_CAM_MODE': '0', 'PS3_SIM_PACE_HZ': '30',
            'MSPR_LOD_BIAS': '-2', 'MSPR_CULL_SCALE': '0.25', 'RSX_TEX_BORDER': '1', 'RSX_RT_READBACK_ASYNC': '1',
            'RSX_HDR': '0', 'MSPR_PATCH': 'drs,vfps,mblur,audiothread', 'RSX_SHOTS_MAX': '24', 'RSX_FSR_OBJ_FIX': '1'},
    # phase 1: original look, the game's shadows replaced by the world-fixed map (all casters every frame, 0.125 m)
    'st1': {'RSX_SHADOW_TILES': '1', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_SHOTS_MAX': '12', 'RSX_RT_READBACK_ASYNC': '0',
            'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st1.csv')},
    # phase 2: + the static layer (static casters baked once into a 0.25 m world-fixed store, 3072 m, used towards the
    # dynamic map's edge and beyond it)
    'st2': {'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_SHOTS_MAX': '12',
            'RSX_RT_READBACK_ASYNC': '0', 'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st2.csv')},
    # phase 3: + the per-track disk cache. st3 fills it (saves every 40 s while new casters bake), st3b starts with it:
    # its far static shadows should be there from the first race frames
    'st3': {'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_SHOTS_MAX': '12',
            'RSX_RT_READBACK_ASYNC': '0', 'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st3.csv'),
            'RSX_SHADOW_TILES_CACHE': str(ST / 'cache'), 'RSX_SHADOW_TILES_CACHE_SAVE_S': '40'},
    'st3b': {'RSX_SHADOW_TILES': '1', 'RSX_SHADOW_TILES_STATIC': '1', 'RSX_LIGHTING_CASTSTAT': '1', 'RSX_SHOTS_MAX': '12',
             'RSX_RT_READBACK_ASYNC': '0', 'RSX_SHADOW_TILES_LOG': str(ST / 'passlog_st3b.csv'),
             'RSX_SHADOW_TILES_CACHE': str(ST / 'cache'), 'RSX_SHADOW_TILES_CACHE_SAVE_S': '40'},
}
exe, slot, tags = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3:]
d = ab2 / f'exe_{slot}'; d.mkdir(exist_ok=True)
shutil.copy2(exe, d / 'MotorStormPacificRiftRecomp.exe')
h = hashlib.sha256((d / 'MotorStormPacificRiftRecomp.exe').read_bytes()).hexdigest()
(ab2 / f'exe_{slot}.sha256').write_text(h + '\n')
print('slot', slot, h)
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
add = ''; order = ''
for tag in tags:
    if f"K_BY_TAG['{tag}']" in s: print('already', tag); continue
    shots = root / 'build' / 'shots' / tag; shots.mkdir(parents=True, exist_ok=True)
    ex = ''.join(f", {k!r}: {v!r}" for k, v in ARMS[tag].items())
    add += (f"K_BY_TAG['{tag}'] = ('{slot}', {{**ARMS['K'][1], 'RSX_HDR': '1', 'MSPR_PATCH': 'drs,vfps,mblur', "
            f"'RSX_SHOTS': {str(shots)!r}, 'RSX_SHOTS_MAX': '60'{ex}}})   # K{tag}: world-fixed shadows look arm (shadowtiles/RESULTS.md)\n")
    order += f"'K{tag}', "
if add:
    a = "\nif __name__ == '__main__':"
    assert s.count(a) == 1
    s = s.replace(a, '\n' + add + a)
    i = s.index('ORDER = ')
    j = s.index("'Klt5t'", i)   # after every launched/pending look arm; timing arms stay last
    s = s[:j] + order + s[j:]
    p.write_text(s, encoding='utf-8', newline='\n')
print('ok', order)
