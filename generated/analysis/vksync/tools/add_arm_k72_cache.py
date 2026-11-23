"""run_vk.py: Kk72/Kk74 (PGO exe 8df22c49) get their own SPIR-V cache, ab2/spirv_cache_pgo,
rewarmed for the PGO build's stamp by build_spirv_rewarm_pgo.cmd. With the shared cache every pin
switch would leave the next arm cold (the Kk56 Present timeout / Kk57 stall). Kk71/Kk73 keep
ab2/spirv_cache. LF file. usage: py -3 add_arm_k72_cache.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "K_BY_TAG['k72']" in s:
    print('already edited'); raise SystemExit
k71 = "ARMS['K'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'PS3_TRACE_FILE'})   # Kk71-Kk74:"
assert s.count(k71) == 1
i = s.index('\n', s.index(k71)) + 1
s = s[:i] + ("K_BY_TAG['k72'] = K_BY_TAG['k74'] = ('r', {**ARMS['K'][1], 'PS3RECOMP_SPIRV_CACHE': str(HERE / 'spirv_cache_pgo')})"
             "   # Kk72/Kk74: PGO exe, own SPIR-V cache (build_spirv_rewarm_pgo.cmd)\n") + s[i:]
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
