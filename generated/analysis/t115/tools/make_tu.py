MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T115: exact project compile line for rsx_d3d12_backend.c (from t110/tools/tu_t110.cmd, itself from
build/motorstorm-t96i/build.ninja), once for the T110 base tree and once for ps3recomp-t115. Writes tu_t115.cmd."""
import pathlib
M = pathlib.Path(MS_ROOT)
BS = chr(92)
src = (M / 'generated/analysis/t110/tools/tu_t110.cmd').read_text().splitlines()
bl = next(l for l in src if l.endswith('rsx_d3d12_backend.c.log" 2>&1'))
out = ['@echo off', r'set "PATH=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer;%PATH%"', src[1]]
old = BS.join(['analysis', 't110', 'logs', 'tu'])
for tree, tag in (('ps3recomp-t110', 'base'), ('ps3recomp-t115', 't115')):
    (M / 'generated' / 'analysis' / 't115' / 'logs' / 'tu' / tag).mkdir(parents=True, exist_ok=True)
    l = bl.replace('ps3recomp-t110', tree).replace(old, BS.join(['analysis', 't115', 'logs', 'tu', tag]))
    assert old not in l
    out += [l, f'echo {tag} rsx_d3d12_backend.c rc=%ERRORLEVEL%']
(M / 'generated/analysis/t115/tools/tu_t115.cmd').write_text('\r\n'.join(out) + '\r\n')
