r"""run_vk.py: Kk81-Kk85 (2026-11-06, quiet PC: no SSX, Nightfire or BF1943 running).
Kk81/Kk83: base exe 9531e520, Kk71's configuration (drs,vfps uncapped, RES_SCALE 1.5, pack).
Kk82/Kk84: PGO exe 8df22c49, the same with its own SPIR-V cache (= Kk72/Kk74).
Kk85: exe 20ba7377 with MSPR_PATCH unset: the default must log "(default drs)".
LF file. usage: py -3 add_arm_k81.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk81'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k80'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k81'] = K_BY_TAG['k83'] = ARMS['K']   # Kk81/Kk83: quiet PGO A/B, base 9531e520 (Kk71 configuration)\n"
             "K_BY_TAG['k82'] = K_BY_TAG['k84'] = K_BY_TAG['k74']   # Kk82/Kk84: quiet PGO A/B, PGO 8df22c49, own SPIR-V cache\n"
             "K_BY_TAG['k85'] = ('r', {k: v for k, v in ARMS['K'][1].items() if k != 'MSPR_PATCH'})"
             "   # Kk85: exe 20ba7377, MSPR_PATCH unset (default drs)\n") + s[i:]
a = "'Kk79', 'Kk80', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk79', 'Kk80', 'Kk81', 'Kk82', 'Kk83', 'Kk84', 'Kk85', 'Yy1']")
a = 'MAX_LAUNCHES = 130'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 135')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
