r"""run_vk.py: Kk80, Kk79 again on exe 20ba7377 (37f18d28 + RSX_TEX_BORDER) with RSX_TEX_BORDER=1: BORDER
texture units sample the guest's border colour instead of transparent black. Kk79 found the full-res
ground decals (pipe 146: depth-reconstructed projection of a 16x16 B8 blob, alpha = c - tex.z) drawing as
flat dark boxes with hard edges, the "transparency" look the user reports. The run log's
"[rsx engine] texture border colour" lines and draws.txt's per-texture wrap/border words show which units
use BORDER; the pass dump (same 62 s point, 420 passes, alpha) shows the decals again. Into
ab2/passdump_k80 (private). LF file. usage: py -3 add_arm_k80.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk80'" in s:
    print('already edited'); raise SystemExit
(p.parent / 'passdump_k80').mkdir(exist_ok=True)
a = "K_BY_TAG['k79'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k80'] = ('r', {**ARMS['K'][1], 'RSX_TEX_BORDER': '1', "
             "'RSX_ENGINE_PASS_DUMP': str(HERE / 'passdump_k80'), "
             "'RSX_ENGINE_PASS_DUMP_AFTER': '62', 'RSX_ENGINE_PASS_DUMP_MAX': '420', "
             "'RSX_ENGINE_PASS_DUMP_DRAWS': '1', 'RSX_ENGINE_PASS_DUMP_ALPHA': '1'})"
             "   # Kk80: Kk79 + guest texture border colour\n") + s[i:]
a = "'Kk77', 'Kk78', 'Kk79', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk77', 'Kk78', 'Kk79', 'Kk80', 'Yy1']")
a = 'MAX_LAUNCHES = 129'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 130')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
