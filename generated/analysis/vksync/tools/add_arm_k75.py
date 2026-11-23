"""run_vk.py: Kk75/Kk76, the PGO confirmation pair after Kk74 ran under outside load (SSX Tricky at a
full core, present wait 19 ms a frame). Kk75 = PGO exe 8df22c49 with ab2/spirv_cache_pgo (Kk72/Kk74's
arm), Kk76 = base 9531e520 with ab2/spirv_cache (Kk71/Kk73's arm). set_pin.py + `prepare r` between.
LF file. usage: py -3 add_arm_k75.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk75'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k72'] = K_BY_TAG['k74'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k75'] = K_BY_TAG['k74']   # Kk75: PGO confirmation (Kk76 = base, ARMS['K'])\n") + s[i:]
a = "'Kk74', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk74', 'Kk75', 'Kk76', 'Yy1']")
a = 'MAX_LAUNCHES = 124'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 126')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
