"""Re-lift one generated SPU image exactly as spu_program_pipeline.py does.
usage: python lift.py <tree> <generated image dir> <out dir> <image id> [lifter args...]"""
import subprocess, sys, shutil
from pathlib import Path
tree, src, out, img = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
extra = sys.argv[5:]
sys.path.insert(0, str(tree / 'tools'))
from find_spu_functions import detect_functions
blob = (src / 'image.elf').read_bytes()
_, (offset, base, size) = detect_functions(blob, verbose=False)
out.mkdir(parents=True, exist_ok=True)
for f in ('image.elf', 'code.bin', 'functions.json'):
    shutil.copy2(src / f, out / f)
prefix = src.name + '_'
cmd = [sys.executable, str(tree / 'tools/spu_lifter.py'), str(out / 'code.bin'), '--base', str(base),
       '--functions', str(out / 'functions.json'), '--symbol-prefix', prefix, '--report', str(out / 'lift.json'),
       '--output', str(out), '--image-id', img] + extra
r = subprocess.run(cmd, capture_output=True, text=True)
(out / 'lift.log').write_text(r.stdout + r.stderr)
from build_spu_workloads import debase_includes
for f in ('spu_recomp.c', 'spu_recomp.h'):
    debase_includes(str(out / f))
print(r.stdout[-800:], r.stderr[-1500:])
sys.exit(r.returncode)
