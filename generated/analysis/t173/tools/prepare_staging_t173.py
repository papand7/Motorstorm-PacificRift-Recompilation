"""Make generated/ppu-t173-staging (the T173 build's RECOMP_DIR) from private inputs.

  1. lift MotorStorm with the T173 lifter (ps3recomp-t173) as docs/BUILD.md does, into a scratch directory:
       py -3 ps3recomp-t173/tools/ppu_lifter.py generated/decrypted/EBOOT.elf --functions generated/analysis/EBOOT.functions.json
          --hle-stubs generated/analysis/EBOOT.imports.json --output <scratch> --jobs 6 --trace-hooks
  2. staging = generated/ppu-hooked-staging with ONLY the two chunks the fix changes replaced by the scratch lift's
     (hard links for the other files, a copy of ppu_hle_nids.cpp because the build rewrites it). The older staging was lifted
     before ps3recomp's raw-store coherence change, so a whole new lift would also change unrelated chunks; this keeps the delta
     to the jump table.

usage: py -3 prepare_staging_t173.py <repo root> <scratch lift> [ppu_recomp_006.cpp=<sha256> ppu_recomp_026.cpp=<sha256>]
The optional hashes make it refuse a lift that is not the one T173 verified. Everything it touches is private (generated/)."""
import hashlib, os, shutil, sys
from pathlib import Path

root, fixed = Path(sys.argv[1]), Path(sys.argv[2])
CHANGED = ('ppu_recomp_006.cpp', 'ppu_recomp_026.cpp')
src, dst = root / 'generated' / 'ppu-hooked-staging', root / 'generated' / 'ppu-t173-staging'
if dst.exists():
    raise SystemExit(f'{dst} exists; refusing to overwrite')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 22), b''):
            h.update(c)
    return h.hexdigest()


for a in sys.argv[3:]:
    n, _, want = a.partition('=')
    if n in CHANGED and sha(fixed / n) != want.lower():
        raise SystemExit(f'{n}: sha256 {sha(fixed / n)} != expected {want}')
dst.mkdir()
for f in sorted(src.iterdir()):
    if not f.is_file():
        continue
    if f.name in CHANGED:
        shutil.copy2(fixed / f.name, dst / f.name)
    elif f.name == 'ppu_hle_nids.cpp':
        shutil.copy2(f, dst / f.name)
    else:
        os.link(f, dst / f.name)
print('staging ready:', dst, '|', ', '.join(f'{n} {sha(dst / n)}' for n in CHANGED))
