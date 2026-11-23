r"""run_vk.py: Kk78, one race of the base build with RSX_SHADOW_CAP (rsx_shadow_cap.h): from 75 s after the
first draw (about 25 s into the race), 600 frames of the shadow pass's per-cascade transform state and the
first shadow-reading scene draw, into ab2/shadowcap_k78.bin (private). Kk70's configuration otherwise.
Read with tools/shadow_cap.py. LF file. usage: py -3 add_arm_k78.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk78'" in s:
    print('already edited'); raise SystemExit
a = "K_BY_TAG['k77'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k78'] = ('r', {**ARMS['K'][1], 'RSX_SHADOW_CAP': str(HERE / 'shadowcap_k78.bin'), "
             "'RSX_SHADOW_CAP_AFTER': '75', 'RSX_SHADOW_CAP_FRAMES': '600'})"
             "   # Kk78: base + shadow-pass capture\n") + s[i:]
a = "'Kk76', 'Kk77', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk76', 'Kk77', 'Kk78', 'Yy1']")
a = 'MAX_LAUNCHES = 127'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 128')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
