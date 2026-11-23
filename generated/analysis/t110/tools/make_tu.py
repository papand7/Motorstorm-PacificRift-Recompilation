MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""T110: exact project compile lines for the changed TUs. Starts from T108's
tu_t108.cmd (itself from build/motorstorm-t96i/build.ninja) and retargets it
with str.replace (sed mangles the backslashes); rsx_fp_decompiler.c reuses the
rsx_commands.c line, the same target and flags. Writes tu_t110.cmd."""
import pathlib
M = pathlib.Path(MS_ROOT)
src = (M / 'generated/analysis/t108/tools/tu_t108.cmd').read_text()
out = src.replace('ps3recomp-t108', 'ps3recomp-t110').replace(r'analysis\t108', r'analysis\t110')
assert 'ps3recomp-t108' not in out and r'analysis\t108' not in out
lines = out.splitlines()
cmd_line = next(l for l in lines if l.endswith('rsx_commands.c.log" 2>&1'))
extra = cmd_line.replace('rsx_commands.c', 'rsx_fp_decompiler.c')
assert extra.count('rsx_fp_decompiler.c') == cmd_line.count('rsx_commands.c') > 0
lines += [extra, 'echo rsx_fp_decompiler.c rc=%ERRORLEVEL%']
(M / 'generated/analysis/t110/logs/tu').mkdir(parents=True, exist_ok=True)
(M / 'generated/analysis/t110/tools/tu_t110.cmd').write_text('\n'.join(lines) + '\n')
print(len(lines), 'lines')
