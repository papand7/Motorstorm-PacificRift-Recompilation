r"""run_vk.py: Kk77, one race of the PGO + ISA exe (build_pgo.cmd isa: AVX2 BMI1/2 LZCNT MOVBE POPCNT,
Zen 5 tuning, no FMA) with its own SPIR-V cache ab2/spirv_cache_isa (REWARM_BD=build\motorstorm-vkgame-pgoisa
build_spirv_rewarm_pgo.cmd). Compare with the PGO runs Kk72/Kk75. LF file. usage: py -3 add_arm_k77.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk77'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k75'] = K_BY_TAG['k74']"
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k77'] = ('r', {**ARMS['K'][1], 'PS3RECOMP_SPIRV_CACHE': str(HERE / 'spirv_cache_isa')})"
             "   # Kk77: PGO + ISA exe, own SPIR-V cache\n") + s[i:]
a = "'Kk75', 'Kk76', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk75', 'Kk76', 'Kk77', 'Yy1']")
a = 'MAX_LAUNCHES = 126'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 127')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
