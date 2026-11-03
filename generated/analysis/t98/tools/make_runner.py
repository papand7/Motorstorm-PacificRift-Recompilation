"""T98: derive run_t98.py from t96/t96i/run_t96i.py. Every edit is an exact, asserted replacement.
Changes: the T96I exe pin (read-only, no rebuild); 300 s session / 310 s host (fast_startup.MAX_TIMEOUT_S raised in
the runner only); any --target fast_startup adds is stripped (no milestone stop); race-only frame dumps
(CELLMARK_DUMP_MINDRAWS=200, every 25 qualifying presents, up to 40); PS3_FTRACE and GCM_WORD_STATS off.
Navigation, intro skip (PS3_DEV_SKIP_INTRO + GCM_STALL_INTRO), PT trace config, VP_NOFIXPROJ=1, RF_PHASE_MS=200,
RSX_VBO_DIAG=1, T96 VB default, RSXI/TEX_SAVE/RSX_RT_READBACK off: unchanged."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
T = HERE.parent
src = (T.parent / 't96' / 't96i' / 'run_t96i.py').read_text(encoding='utf-8')
R = [
    ('"""T96I: t94/run_t94.py', '"""T98: t96/t96i/run_t96i.py with the same T96I exe (3fd97ab6..., 95a906d): 300 s session, 310 s host,\n'
     'no target, race-only frame dumps (MINDRAWS 200, every 25), PS3_FTRACE/GCM_WORD_STATS off. One launch.\n\n'
     'T96I: t94/run_t94.py'),
    ("ROOT = HERE.parents[3]", "ROOT = HERE.parents[2]"),
    ("HARD_KILL_S = 205.0", "HARD_KILL_S = 300.0"),
    ("EXE = HERE / 'exe' / 'MotorStormPacificRiftRecomp.exe'   # the T96I exe pin, used read-only",
     "EXE = HERE.parent / 't96' / 't96i' / 'exe' / 'MotorStormPacificRiftRecomp.exe'   # the T96I exe pin, used read-only"),
    ("CFG = HERE / 'pb_stall_t96i.cfg'   # byte-identical copy of t94/pb_stall_t94.cfg",
     "CFG = HERE / 'pb_stall_t98.cfg'   # byte-identical copy of t96/t96i/pb_stall_t96i.cfg"),
    ("RUN_NAME = 't96i-race-present'", "RUN_NAME = 't98-visible-race'"),
    ("(HERE.parents[1] / 't30' / 'loader'", "(HERE.parents[0] / 't30' / 'loader'"),
    ("'CELLMARK_DUMP': '160', 'CELLMARK_DUMP_EVERY': '60', 'CELLMARK_DUMP_MINDRAWS': '1',",
     "'CELLMARK_DUMP': '40', 'CELLMARK_DUMP_EVERY': '25', 'CELLMARK_DUMP_MINDRAWS': '200',   # T98: race presents only"),
    ("        'PS3_FTRACE': f'150:30:{rtdir / \"ftrace.txt\"}',\n", ""),
    ("        'GCM_WORD_STATS': '5',\n", ""),
    ("            '--timeout', '210']", "            '--timeout', '310']"),
    ("    fast_startup.HDD1 = HDD1\n",
     "    fast_startup.HDD1 = HDD1\n    fast_startup.MAX_TIMEOUT_S = 310.0   # T98: authorized 310 s host cap (runner only)\n"),
    ("        a = list(a)\n        for i, v in enumerate(a):",
     "        a = list(a)\n        while '--target' in a:   # T98: fast_startup adds a default target; no milestone stop\n"
     "            j = a.index('--target'); del a[j:j + 2]\n        for i, v in enumerate(a):"),
]
for a, b in R:
    assert src.count(a) == 1, a[:80]
    src = src.replace(a, b)
for bad in ("'RSXI_", "'--capture-", "'PS3_FTRACE'", "'GCM_WORD_STATS'", 't96i-race-present', "'--timeout', '210'"):
    assert bad not in src, bad
(T / 'run_t98.py').write_text(src, encoding='utf-8')
print('wrote run_t98.py')
