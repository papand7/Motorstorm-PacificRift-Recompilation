"""T103: derive tu_t103.cmd from T96's TU compile script (exact project flags)."""
import pathlib
here = pathlib.Path(__file__).resolve().parent
src = here.parent.parent / 't96' / 'tools' / 'tu_t96.cmd'
s = src.read_text()
BS = '\\'
s = s.replace('ps3recomp-t96' + BS, 'ps3recomp-t103' + BS)
s = s.replace(BS.join(['analysis', 't96', 'logs', 'tu']), BS.join(['analysis', 't103', 'logs', 'tu']))
assert ('ps3recomp-t96' + BS) not in s and BS.join(['t96', 'logs']) not in s, 'leftover t96 path'
(here / 'tu_t103.cmd').write_text(s)
print('written, t103 refs:', s.count('t103'))
