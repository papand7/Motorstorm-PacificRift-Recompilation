"""T94: rewrite the T92 TU compile command lines (first line of t92/logs/tu_ps3recomp-t92/*.log) for ps3recomp-t94."""
from pathlib import Path
HERE = Path(__file__).resolve().parent
A = HERE.parents[1]
cmds = []
for f in ('cellGcmSys.c', 'rsx_d3d12_backend.c'):
    l = (A / 't92' / 'logs' / 'tu_ps3recomp-t92' / f'{f}.log').read_text(errors='replace').splitlines()[0]
    l = l.replace(r't92\logs\tu_ps3recomp-t92', r't94\logs\tu').replace('ps3recomp-t92', 'ps3recomp-t94')
    assert 't92' not in l, l
    cmds.append((f, l))
out = ['@echo off',
       r'call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1']
for f, l in cmds:
    out += [f'{l} > "{A / "t94" / "logs" / "tu" / (f + ".log")}" 2>&1', f'echo {f} rc=%ERRORLEVEL%']
(HERE / 'tu_t94.cmd').write_text('\r\n'.join(out) + '\r\n')
print('ok')
