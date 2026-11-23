r"""run_vk.py: Kk79, one race of exe 37f18d28 (f72c31ab + RSX_ENGINE_PASS_DUMP_ALPHA) with a pass dump of
about six race frames from 62 s after the first draw (about 12 s into the race, the pack still close, so
dust and smoke in view): colour targets with their alpha (_a.pgm), depth, draws.txt with the alpha blend
factors, and every pipeline's HLSL, into ab2/passdump_k79 (private). For the user's report that vehicle
dust/smoke shows through the ground and looks like a transparency problem. Kk70's configuration
otherwise. LF file. usage: py -3 add_arm_k79.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk79'" in s:
    print('already edited'); raise SystemExit
d = p.parent / 'passdump_k79'
d.mkdir(exist_ok=True)
a = "K_BY_TAG['k78'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + ("K_BY_TAG['k79'] = ('r', {**ARMS['K'][1], 'RSX_ENGINE_PASS_DUMP': str(HERE / 'passdump_k79'), "
             "'RSX_ENGINE_PASS_DUMP_AFTER': '62', 'RSX_ENGINE_PASS_DUMP_MAX': '420', "
             "'RSX_ENGINE_PASS_DUMP_DRAWS': '1', 'RSX_ENGINE_PASS_DUMP_ALPHA': '1', "
             "'RSX_ENGINE_SHADER_DUMP': str(HERE / 'passdump_k79')})"
             "   # Kk79: dust/smoke pass dump with alpha\n") + s[i:]
a = "'Kk77', 'Kk78', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk77', 'Kk78', 'Kk79', 'Yy1']")
a = 'MAX_LAUNCHES = 128'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 129')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
