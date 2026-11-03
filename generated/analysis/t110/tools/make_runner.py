MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T110 (from t108/tools/make_runner.py): derive t110/run_t110.py from t108/run_t108.py (same controller, route,
caps, probes and dumps) with one argument more, the arm, which selects the T110 corrections, and per-arm fresh
private HDD copies. Copies the PT cfg and writes configure/build scripts for build/motorstorm-t110.
PREPARED ONLY: nothing here builds or launches."""
import pathlib, shutil
A = pathlib.Path((MS_ROOT + r'\generated\analysis'))
s = (A / 't108' / 'run_t108.py').read_text(encoding='utf-8')


def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep('"""T108: t98/run_t98.py with the T108 exe',
    '"""T110: t108/run_t108.py with the T110 exe (ps3recomp-t110 = T108 6b1a7e4 + 3c1eb4d samplers, 2692ec0 attr0,\n'
    '9ca3877 colour transfer, 089d17a RT pool, e3b961d tests). Same route, caps, probes and dumps as T108.\n'
    '  py -3 run_t110.py prepare|dryrun|launch <arm>     arm A..E (default A):\n'
    '    A  no correction (T108 behaviour)       B  A + RSX_GUEST_SAMPLERS=15\n'
    '    C  B + RSX_ATTR0_CONST=1                D  C + RSX_RTPOOL_GF=1\n'
    '    E  D + RSX_COLOR_XFER=7 (only if arm A logs [XFER] requests on the frames under study)\n'
    'Each arm gets its own fresh, hash-verified hdd0/hdd1 copies. PREPARED ONLY: building and launching need authorization.\n\n'
    'T108: t98/run_t98.py with the T108 exe')
rep("SRC_EXE = ROOT / 'build' / 'motorstorm-t108' / 'MotorStormPacificRiftRecomp.exe'   # the authorized T108 build",
    "SRC_EXE = ROOT / 'build' / 'motorstorm-t110' / 'MotorStormPacificRiftRecomp.exe'   # the authorized T110 build")
rep("_SFX = ''\nHDD0, HDD1 = HERE / 'hdd0', HERE / 'hdd1'      # fresh private copies (prepare)",
    "ARM = (sys.argv[2] if len(sys.argv) > 2 else 'A').upper()\n"
    "ARMS = {\n"
    "    'A': {},\n"
    "    'B': {'RSX_GUEST_SAMPLERS': '15'},\n"
    "    'C': {'RSX_GUEST_SAMPLERS': '15', 'RSX_ATTR0_CONST': '1', 'RSX_ATTR0_LOG': '16'},\n"
    "    'D': {'RSX_GUEST_SAMPLERS': '15', 'RSX_ATTR0_CONST': '1', 'RSX_ATTR0_LOG': '16', 'RSX_RTPOOL_GF': '1'},\n"
    "    'E': {'RSX_GUEST_SAMPLERS': '15', 'RSX_ATTR0_CONST': '1', 'RSX_ATTR0_LOG': '16', 'RSX_RTPOOL_GF': '1',\n"
    "          'RSX_COLOR_XFER': '7'},\n"
    "}\n"
    "if ARM not in ARMS:\n"
    "    raise SystemExit(f'arm must be one of {sorted(ARMS)}')\n"
    "_SFX = '_' + ARM\n"
    "HDD0, HDD1 = HERE / f'hdd0{_SFX}', HERE / f'hdd1{_SFX}'      # fresh private copies per arm (prepare)")
rep("CFG = HERE / 'pb_stall_t108.cfg'   # byte-identical copy of t98/pb_stall_t98.cfg",
    "CFG = HERE / 'pb_stall_t110.cfg'   # byte-identical copy of t108/pb_stall_t108.cfg")
rep("RUN_NAME = 't108-race-validation'", "RUN_NAME = 't110-visual-' + ARM.lower()")
rep("""    if MAN.exists():
        raise SystemExit(f'{MAN} exists')
""", """    if MAN.exists():   # T110: a later arm adds its own copies to the manifest
        if (HDD0.exists() or HDD1.exists()):
            raise SystemExit(f'{HDD0} / {HDD1} exist: arm {ARM} is already prepared (or used)')
        return prepare_b()
""")
rep("""        'CELLMARK_DUMP_DIR': str(frames),""", """        **ARMS[ARM],   # T110 corrections for this arm (unset = T108 behaviour)
        'CELLMARK_DUMP_DIR': str(frames),""")
rep("""    rtdir = HERE / f'runtime-{time.strftime("%Y%m%d-%H%M%S")}'""",
    """    rtdir = HERE / f'runtime-{ARM}-{time.strftime("%Y%m%d-%H%M%S")}'""")
rep("""        print(f'DRY RUN (nothing launched). exe sha256 OK = {got}  scrubbed={dropped}  HDD0={HDD0} HDD1={HDD1}')""",
    """        print(f'DRY RUN (nothing launched). arm {ARM} {ARMS[ARM]} exe sha256 OK = {got}  scrubbed={dropped}  HDD0={HDD0} HDD1={HDD1}')""")
# T110: the admitted-draw and sampler lines in the controller timeline (log-only)
rep(r"INTEREST = re.compile(r'\[XFER\]|", r"INTEREST = re.compile(r'\[XFER\]|\[attr0\]|\[samplers\]|\[d3d12\] render-target pool|")

out = A / 't110'
(out / 'run_t110.py').write_text(s, encoding='utf-8')
shutil.copy2(A / 't108' / 'pb_stall_t108.cfg', out / 'pb_stall_t110.cfg')
for name in ('configure', 'build'):
    c = (A / 't108' / f'{name}_t108.cmd').read_text(encoding='utf-8')
    c = c.replace('motorstorm-t108', 'motorstorm-t110').replace('ps3recomp-t108', 'ps3recomp-t110')
    c = c.replace('configure_t108.cmd', 'configure_t110.cmd')
    c = c.replace('T108:', 'T110:').replace('agent/t108-renderer-validation, 6b1a7e4', 'agent/t110-rsx-visual-fidelity, e3b961d')
    assert 't108' not in c.lower(), c
    (out / f'{name}_t110.cmd').write_text(c, encoding='utf-8')
print('ok')
