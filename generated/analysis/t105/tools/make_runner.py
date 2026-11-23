MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T105: derive t105/run_t105.py from t98/run_t98.py (same controller, route and caps) and copy the PT cfg."""
import pathlib, shutil
A = pathlib.Path((MS_ROOT + r'\generated\analysis'))
s = (A / 't98' / 'run_t98.py').read_text(encoding='utf-8')


def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep('"""T98: t96/t96i/run_t96i.py',
    '"""T105: t98/run_t98.py with the T105 exe (ps3recomp-t105 36d0fb7 = T100 5288949 + T99 db2aa90 + T102 1e5d534\n'
    '+ T103 c2e9eec/26f262e + RACE_PRESENT_PROBE). Same route, intro skip, 300 s session / 310 s host cap, no target,\n'
    'race milestones log-only. Adds: presenting-only dumps (12, every 8), PS3_PRESENT_DIAG, RTPOOL_LOG and\n'
    'RACE_PRESENT_PROBE (12 race Presents, every 20th). PREPARED ONLY: building and launching need authorization.\n\n'
    'T98: t96/t96i/run_t96i.py')
rep("SRC_EXE = ROOT / 'build' / 'motorstorm-t96i' / 'MotorStormPacificRiftRecomp.exe'",
    "SRC_EXE = ROOT / 'build' / 'motorstorm-t105' / 'MotorStormPacificRiftRecomp.exe'   # the authorized T105 build")
rep("EXE = HERE.parent / 't96' / 't96i' / 'exe' / 'MotorStormPacificRiftRecomp.exe'   # the T96I exe pin, used read-only",
    "EXE = HERE / 'exe' / 'MotorStormPacificRiftRecomp.exe'   # private copy of SRC_EXE, made by `prepare`")
rep("EXE_SHA = '3fd97ab601301edbe0db5fe7f6a2eb6d6aebc754c71b8624d022da79bb94bb05'",
    "EXE_SHA = None   # PIN after the authorized build: the sha256 `prepare` prints. preflight refuses while None")
rep("CFG = HERE / 'pb_stall_t98.cfg'   # byte-identical copy of t96/t96i/pb_stall_t96i.cfg",
    "CFG = HERE / 'pb_stall_t105.cfg'   # byte-identical copy of t98/pb_stall_t98.cfg")
rep("EMPTYTEX|SCREENTEX|", "EMPTYTEX|SCREENTEX|RACE_|RTPOOL|")
rep("RUN_NAME = 't98-visible-race'", "RUN_NAME = 't105-race-probe'")
rep("""    if MAN.exists():
        raise SystemExit(f'{MAN} exists')
""", """    if MAN.exists():
        raise SystemExit(f'{MAN} exists')
    if not EXE.exists():
        EXE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SRC_EXE, EXE)
    if EXE_SHA is None:
        raise SystemExit(f'exe copied; pin EXE_SHA = {sha(EXE)!r} in this file, then rerun prepare')
""")
rep("""    want = EXE_SHA
    got = sha(EXE)""", """    want = EXE_SHA
    if not want:
        raise SystemExit('PREFLIGHT FAIL: EXE_SHA not pinned')
    got = sha(EXE)""")
rep("""        'CELLMARK_DUMP': '40', 'CELLMARK_DUMP_EVERY': '25', 'CELLMARK_DUMP_MINDRAWS': '200',   # T98: race presents only
""", """        # T105: presenting replays only (T100 729caed), period 7 passes
        'CELLMARK_DUMP': '12', 'CELLMARK_DUMP_EVERY': '8', 'CELLMARK_DUMP_MINDRAWS': '200', 'CELLMARK_DUMP_PRESENT_ONLY': '1',
        'PS3_PRESENT_DIAG_MS': '5000', 'PS3_PRESENT_DIAG_MAX': '64',   # real Present counts per stage
        'RTPOOL_LOG': '64',                                              # T100: live RT losses
        # T105: scene / composition source / backbuffer classification, 12 race Presents about 5 s apart
        'RACE_PRESENT_PROBE': '12', 'RACE_PRESENT_PROBE_MINDRAWS': '200', 'RACE_PRESENT_PROBE_EVERY': '20',
""")
rep("RX_PAD = re.compile(", "RX_PROBE = re.compile(r'\\[race-probe\\] n=(\\d+) replay=(\\d+) present=(\\d+).* verdict=(\\S+)')\nRX_PAD = re.compile(")
rep("""        m = RX_PAD.search(line)
        if m:""", """        m = RX_PROBE.search(line)
        if m:   # T105: log-only, never stops the session
            self.note('race_probe', n=int(m.group(1)), replay=int(m.group(2)), present=int(m.group(3)),
                      verdict=m.group(4), line=line[:600])
            return
        m = RX_PAD.search(line)
        if m:""")
out = A / 't105' / 'run_t105.py'
out.write_text(s, encoding='utf-8')
shutil.copyfile(A / 't98' / 'pb_stall_t98.cfg', A / 't105' / 'pb_stall_t105.cfg')
print('wrote', out)
