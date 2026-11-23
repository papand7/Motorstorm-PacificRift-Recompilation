r"""run_vk.py: Kk86 (2026-11-06), exe ec5ce88e (20ba7377 + RSX_SHADOW_STABLE, rsx_shadow_stable.h,
test_shadow_stable 31/31, Kk78 replay clean). Kk71's configuration + RSX_SHADOW_STABLE=1 (fixed cascade
axes, laddered size, texel-snapped offsets, exact half lookup) + RSX_SHADOW_CAP from 20 s for 2400 frames:
the menu's garage backdrop (scene draws' 512 vertex constants: is c38 still 0 on Vulkan?) and the race
(cascade matrices as bound: tools/shadow_cap.py must show fixed axes and whole-texel moves). Into
ab2/shadowcap_k86.bin (private). LF file. usage: py -3 add_arm_k86.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk86'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k85'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k86'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_STABLE': '1', "
             "'RSX_SHADOW_CAP': str(HERE / 'shadowcap_k86.bin'), 'RSX_SHADOW_CAP_AFTER': '20', "
             "'RSX_SHADOW_CAP_FRAMES': '2400'})   # Kk86: exe ec5ce88e, stable shadows + capture (menu garage, race)\n") + s[i:]
a = "'Kk85', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk85', 'Kk86', 'Yy1']")
a = 'MAX_LAUNCHES = 135'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 136')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
