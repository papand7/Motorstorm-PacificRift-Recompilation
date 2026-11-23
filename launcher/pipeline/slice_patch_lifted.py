"""MSPR_SLICE_MS: the main thread's per-frame time slice in func_005346A8 (1.00), through
mspr_slice_ms() in the lifted tree (port-vkgame/main.cpp).

func_005346A8 is the frame's task loop. With the flag at obj+0x91 set it polls its task list,
re-reading sys_time_get_system_time, until the elapsed time in ms (func_00434D48, us / 1000)
is above 11: about 12 ms of the main thread every frame, mostly polling (K3036 profile, K3037
fnstat: 11.6 ms a call on average, once a frame). Made for the 30 fps lock (33 ms frames), it
caps a real frame rate near 80 fps. The edit is the compare after the call at 0x0053500C:
  cmpwi cr7,r3,11  ->  cmpwi cr7,r3,mspr_slice_ms(11)
in every lifted copy (func_005346A8 and its linear entry copies), asserted by count. 1.00 only.

Idempotent. Usage: py -3 slice_patch_lifted.py <lifted 1.00 staging dir>"""
import os
import pathlib
import shutil
import sys

ST = pathlib.Path(sys.argv[1])
DECL = 'extern "C" int mspr_slice_ms(int game_ms);   /* port main.cpp: MSPR_SLICE_MS */'
CALL = 'ctx->lr = 0x0053500C; func_00757768(ctx);'
OLD = 'int64_t b = (int64_t)0xB;'
NEW = 'int64_t b = (int64_t)mspr_slice_ms(11);'
WANT = 18

total = 0
for path in sorted(ST.glob('ppu_recomp_*.cpp')):
    raw = path.read_bytes().decode('latin-1')
    if CALL not in raw:
        continue
    if os.stat(path).st_nlink > 1:
        tmp = path.with_suffix('.cpp.slice-tmp')
        shutil.copyfile(path, tmp)
        os.replace(tmp, path)
    lines = raw.split('\n')
    n = 0
    for i, l in enumerate(lines):
        if CALL in l:
            j = i + 2   # the call, ld r2,0x28(r1), then the compare
            if NEW in lines[j]:
                n += 1
            elif OLD in lines[j]:
                lines[j] = lines[j].replace(OLD, NEW)
                n += 1
            else:
                sys.exit(f'{path.name}:{j + 1}: unexpected line after the 0x0053500C call')
    if DECL not in lines[1] + lines[2] + lines[3]:
        assert lines[1].startswith('#include "ppu_recomp.h"'), lines[1]
        eol = '\r' if lines[1].endswith('\r') else ''
        lines.insert(2, DECL + eol)
    path.write_bytes('\n'.join(lines).encode('latin-1'))
    print(f'{path.name}: {n} compares')
    total += n
assert total == WANT, f'{total} compares patched, want {WANT}'
