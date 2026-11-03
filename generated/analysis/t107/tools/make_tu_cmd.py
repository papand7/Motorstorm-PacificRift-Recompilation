"""T107: derive tu_t107.cmd from T103's TU compile script (exact project
flags) and add rsx_commands.c, which T107 also changes."""
import pathlib
here = pathlib.Path(__file__).resolve().parent
src = here.parent.parent / 't103' / 'tools' / 'tu_t103.cmd'
s = src.read_text()
BS = '\\'
s = s.replace('ps3recomp-t103' + BS, 'ps3recomp-t107' + BS)
s = s.replace(BS.join(['analysis', 't103', 'logs', 'tu']), BS.join(['analysis', 't107', 'logs', 'tu']))
assert ('ps3recomp-t103' + BS) not in s and BS.join(['t103', 'logs']) not in s, 'leftover t103 path'
lines = s.splitlines()
# Duplicate the cellGcmSys.c compile + echo pair for rsx_commands.c.
idx = [i for i, l in enumerate(lines) if 'cellGcmSys.c' in l]
assert len(idx) >= 2, idx
pair = [lines[i] for i in idx]
extra = [l.replace('cellGcmSys.c', 'rsx_commands.c') for l in pair]
assert all('rsx_commands.c' in l for l in extra)
s = '\n'.join(lines + extra) + '\n'
(here / 'tu_t107.cmd').write_text(s)
print('written, t107 refs:', s.count('t107'), 'rsx_commands refs:', s.count('rsx_commands.c'))
