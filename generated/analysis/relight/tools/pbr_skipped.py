"""Which sun-lit, shadowed census programs the PBR rewrite (rsx_pbr.h) left alone, and why it may have.

usage: py -3 pbr_skipped.py <census dir> <rewritten dir>"""
import pathlib
import re
import sys

cen, rew = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
lit = skipped = 0
for f in sorted(cen.glob('*_s1.hlsl')):
    s = f.read_text(errors='replace')
    if '_rsx_shadow13' not in s or not re.search(r'dot\([^;]*fp_constants', s):
        continue
    lit += 1
    if (rew / f.name).exists():
        continue
    skipped += 1
    print(f.name)
    for m in re.findall(r'(?:_rsx_gamma_input\()?rsx_tex\[[0-5]\]\.Sample\w*\(rsx_samp\[\d+\], [^;]{0,50}', s)[:3]:
        print('   sample', m)
    for m in re.findall(r'dot\([^;]*fp_constants[^;]*', s)[:3]:
        print('   dot   ', m[:140])
    used = sorted(set(int(u) for u in re.findall(r'rsx_tex\[(\d+)\]\.', s)))
    print('   units', used)
print('lit', lit, 'skipped', skipped)
