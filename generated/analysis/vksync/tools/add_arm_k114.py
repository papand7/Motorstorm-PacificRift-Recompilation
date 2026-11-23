r"""run_vk.py: Kk114 (2026-11-06), exe 71deee8c. Camera shake under vfps: who writes the camera context's rate
(25.0f = 0x41C80000 at [ctx+0x10], ctx ~0x1909B440 in Kk70, read by camerasystem::VehicleView 0x431200)?
PPU_WVAL logs stores of that value into 0x18000000-0x1A000000 while ab2/wval_gate_k114 exists (created at
race entry by tools/gate_at_race.py). usage: py -3 add_arm_k114.py; launch with RUN_VK_PLAY=1 RUN_VK_RACE_S=90"""
import pathlib

ab2 = pathlib.Path(__file__).resolve().parents[1] / 'ab2'
p = ab2 / 'run_vk.py'
s = p.read_text(encoding='utf-8')
if "'Kk114'" in s:
    print('already edited'); raise SystemExit
gate = ab2 / 'wval_gate_k114'
add = (f"K_BY_TAG['k114'] = ('r', {{**ARMS['K'][1], 'PPU_WVAL': '0x41C80000', 'PPU_WVAL_LO': '0x18000000', "
       f"'PPU_WVAL_HI': '0x1A000000', 'PPU_WVAL_GATE': {str(gate)!r}}})"
       "   # Kk114: exe 71deee8c, who writes the camera rate 25.0 (vfps shake)\n")
a = "K_BY_TAG['k113'] = "
assert s.count(a) == 1
i = s.index('\n', s.index(a)) + 1
s = s[:i] + add + s[i:]
a = "'Kk112', 'Kk113', 'Yy1']"
assert s.count(a) == 1
s = s.replace(a, "'Kk112', 'Kk113', 'Kk114', 'Yy1']")
a = 'MAX_LAUNCHES = 163'
assert s.count(a) == 1
s = s.replace(a, 'MAX_LAUNCHES = 164')
p.write_text(s, encoding='utf-8', newline='\n')
print('edited', p.name)
