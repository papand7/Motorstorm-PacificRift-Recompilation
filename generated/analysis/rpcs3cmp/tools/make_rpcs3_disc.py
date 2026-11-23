"""Hard-link mirror of original/game for RPCS3, with the game's data under USRDIR in lower case.

Our disc extraction kept the ISO9660 names (MS2.PSARC, GUI/...), but the game asks for lower-case paths
(ms2.psarc, gui/video/...). RPCS3's sys_fs_stat on /dev_bdvd is case-sensitive, so FIOS failed
"stat: err = -129" on ms2.psarc and the boot crashed (VM read of 0x0 at 0x531338). The PS3 system files
(PS3_DISC.SFB, PS3_GAME/*, USRDIR/EBOOT.BIN, TROPDIR) keep their names. Hard links: no copy, original/
untouched. Output is private (game data): build/rpcs3disc, never committed.
usage: py -3 make_rpcs3_disc.py"""
import os, pathlib

root = pathlib.Path(__file__).resolve().parents[4]
src = root / 'original' / 'game'
dst = root / 'build' / 'rpcs3disc'
n = 0
for p in src.rglob('*'):
    if not p.is_file() or p.name == 'manifest.json':
        continue
    rel = p.relative_to(src).parts
    if len(rel) > 3 and rel[:2] == ('PS3_GAME', 'USRDIR'):
        rel = rel[:2] + tuple(s.lower() for s in rel[2:])
    elif len(rel) == 3 and rel[:2] == ('PS3_GAME', 'USRDIR') and rel[2] not in ('EBOOT.BIN',):
        rel = rel[:2] + (rel[2].lower(),)
    q = dst.joinpath(*rel)
    q.parent.mkdir(parents=True, exist_ok=True)
    if not q.exists():
        os.link(p, q); n += 1
print('linked', n, 'files into', dst)
