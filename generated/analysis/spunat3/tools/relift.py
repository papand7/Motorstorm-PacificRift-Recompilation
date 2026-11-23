"""spunat3: re-lift one production SPU ELF image exactly as the game build's pipeline does (same code.bin,
functions.json, base, image id, lifter arguments, regcache env), optionally with SPU_NATIVE_FILE, into
<out>/spu_recomp.{c,h} -- the form the game executable compiles. With --check, the lift without natives
must be byte-identical to the production lift (proof that the copy reproduces the baseline).

  python relift.py <production image dir> <image id> <out dir> [--native-file F] [--check] [-- lifter args]"""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[3] / 'ps3recomp-spunat3'
sys.path.insert(0, str(TREE / 'tools'))
from find_spu_functions import detect_functions  # noqa: E402

argv = sys.argv[1:]
extra = argv[argv.index('--') + 1:] if '--' in argv else []
argv = argv[:argv.index('--')] if '--' in argv else argv
src, image_id, out = Path(argv[0]), argv[1], Path(argv[2])
nf = argv[argv.index('--native-file') + 1] if '--native-file' in argv else None
out.mkdir(parents=True, exist_ok=True)
blob = (src / 'image.elf').read_bytes()
_, (_off, base, _size) = detect_functions(blob, verbose=False)
prefix = src.name + '_'
env = dict(os.environ)
env.pop('SPU_NATIVE_FILE', None)
if nf:
    env['SPU_NATIVE_FILE'] = str(Path(nf).resolve())
cmd = [sys.executable, str(TREE / 'tools/spu_lifter.py'), str(src / 'code.bin'), '--base', str(base),
       '--functions', str(src / 'functions.json'), '--symbol-prefix', prefix, '--report', str(out / 'lift.json'),
       '--output', str(out), '--image-id', image_id] + extra
r = subprocess.run(cmd, capture_output=True, text=True, env=env)
(out / 'lift.log').write_text(r.stdout + r.stderr)
if r.returncode:
    sys.exit('lifter failed\n' + r.stdout[-2000:] + r.stderr[-2000:])
for fn in ('spu_recomp.c', 'spu_recomp.h'):
    p = out / fn
    t = p.read_text(encoding='utf-8')
    t = t.replace('#include "../../runtime/spu/spu_context.h"', '#include "spu_context.h"')
    t = t.replace('#include "../../runtime/spu/spu_helpers.h"', '#include "spu_helpers.h"')
    p.write_text(t, encoding='utf-8')
if '--check' in argv:
    for fn in ('spu_recomp.c', 'spu_recomp.h'):
        a, b = (out / fn).read_bytes(), (src / fn).read_bytes()
        print(fn, 'IDENTICAL' if a == b else f'DIFFERENT ({len(a)} vs {len(b)} bytes)')
print('lifted', out)
