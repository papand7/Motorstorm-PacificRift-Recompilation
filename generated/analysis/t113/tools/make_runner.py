MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T113 (from t110/run_t110.py): same controller, race route, intro skip, caps, T108 probes and presenting-only
dumps; the T113 exe; arms isolate the exposure write-back. Copies cfg/configure/build. PREPARED ONLY."""
import pathlib, shutil
A = pathlib.Path((MS_ROOT + r'\generated\analysis'))
s = (A / 't110' / 'run_t110.py').read_text(encoding='utf-8')
def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)
rep('"""T110: t108/run_t108.py with the T110 exe',
    '"""T113: t110/run_t110.py with the T113 exe (ps3recomp-t113 = T110 e3b961d + 19d6b6d: CPU-read render targets\n'
    'written back by default). py -3 run_t113.py prepare|dryrun|launch <arm>:\n'
    '    A  RSX_RT_READBACK=0 (old behaviour = T108/T110 arm A)   B  default (write-back on)\n'
    '    C  B + RSX_ATTR0_CONST=1                                    D  C + RSX_RTPOOL_GF=1\n'
    'Every arm logs [rtrb] decisions (RSX_RT_READBACK_LOG=64). PREPARED ONLY.\n\n'
    'T110: t108/run_t108.py with the T110 exe')
a = s.index("ARMS = {\n"); b = s.index("}\n", a) + 2
s = s[:a] + ("ARMS = {\n"
    "    'A': {'RSX_RT_READBACK': '0'},\n"
    "    'B': {'RSX_RT_READBACK_LOG': '64'},\n"
    "    'C': {'RSX_RT_READBACK_LOG': '64', 'RSX_ATTR0_CONST': '1', 'RSX_ATTR0_LOG': '16'},\n"
    "    'D': {'RSX_RT_READBACK_LOG': '64', 'RSX_ATTR0_CONST': '1', 'RSX_ATTR0_LOG': '16', 'RSX_RTPOOL_GF': '1'},\n"
    "}\n") + s[b:]
rep("motorstorm-t110' / 'MotorStormPacificRiftRecomp.exe'   # the authorized T110 build",
    "motorstorm-t113' / 'MotorStormPacificRiftRecomp.exe'   # the authorized T113 build")
rep("CFG = HERE / 'pb_stall_t110.cfg'   # byte-identical copy of t108/pb_stall_t108.cfg",
    "CFG = HERE / 'pb_stall_t113.cfg'   # byte-identical copy of t110/pb_stall_t110.cfg")
rep("RUN_NAME = 't110-visual-' + ARM.lower()", "RUN_NAME = 't113-exposure-' + ARM.lower()")
rep(r"INTEREST = re.compile(r'\[XFER\]|", r"INTEREST = re.compile(r'\[rtrb\]|\[XFER\]|")
out = A / 't113'
(out / 'run_t113.py').write_text(s, encoding='utf-8')
shutil.copy2(A / 't110' / 'pb_stall_t110.cfg', out / 'pb_stall_t113.cfg')
for n in ('configure', 'build'):
    c = (A / 't110' / f'{n}_t110.cmd').read_text(encoding='utf-8')
    c = c.replace('t110', 't113').replace('T110', 'T113').replace('agent/t113-rsx-visual-fidelity, e3b961d', 'agent/t113-black-race-repair, 19d6b6d')
    (out / f'{n}_t113.cmd').write_text(c, encoding='utf-8')
print('ok')
