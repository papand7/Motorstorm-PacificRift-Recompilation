MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T115B: exact project compile line for rsx_d3d12_backend.c (from t115/tools/tu_t115.cmd, itself from
t110/tools/tu_t110.cmd and build/motorstorm-t96i/build.ninja) for ps3recomp-t115b. Writes tu_t115b.cmd."""
import pathlib
M = pathlib.Path(MS_ROOT)
BS = chr(92)
s = (M / 'generated/analysis/t115/tools/tu_t115.cmd').read_text().splitlines()
l = next(x for x in s if ('ps3recomp-t115' + BS) in x and 'clang-cl' in x)
l = l.replace('ps3recomp-t115' + BS, 'ps3recomp-t115b' + BS)
l = l.replace(BS.join(['analysis', 't115', 'logs', 'tu', 't115']), BS.join(['analysis', 't115b', 'logs', 'tu', 't115b']))
assert 'ps3recomp-t115' + BS not in l and BS.join(['t115', 'logs']) not in l
(M / 'generated/analysis/t115b/logs/tu/t115b').mkdir(parents=True, exist_ok=True)
out = s[:3] + [l, 'echo t115b rsx_d3d12_backend.c rc=%ERRORLEVEL%']
(M / 'generated/analysis/t115b/tools/tu_t115b.cmd').write_text('\r\n'.join(out) + '\r\n')
