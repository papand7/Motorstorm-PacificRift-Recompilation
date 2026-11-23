"""run_vk.py: keep the pending K arms launchable after newer K lines (each K line replaces ARMS['K']).
K_BY_TAG maps a tag to the configuration its line built; main() uses it for `launch|dryrun K <tag>`.
Pending: Kk68 (PBR 1.0, soft maps), Kk69 (eager readback + probes); Kk70 is the last line.
LF file. usage: py -3 add_k_by_tag.py"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / 'ab2' / 'run_vk.py'
s = p.read_text(encoding='utf-8')
k69 = "ARMS['K'] = ('r', {**{k: v for k, v in ARMS['K'][1].items() if not k.startswith('RSX_TEX_PBR')}, 'RSX_RT_READBACK_EAGER'"
assert s.count(k69) == 1
s = s.replace(k69, "K_BY_TAG = {'k68': ARMS['K']}   # pending K arms stay launchable after newer K lines (main)\n" + k69)
k70 = "ARMS['K'] = ('r', {**ARMS['K'][1], 'MSPR_PATCH': 'drs,vfps'})   # Kk70:"
assert s.count(k70) == 1
s = s.replace(k70, "K_BY_TAG['k69'] = ARMS['K']\n" + k70)
a = "    REQ = f'{arm}{tag}'\n"
assert s.count(a) == 1
s = s.replace(a, a + "    if arm == 'K' and tag in K_BY_TAG:\n        ARMS['K'] = K_BY_TAG[tag]   # a pending arm's own configuration\n")
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
