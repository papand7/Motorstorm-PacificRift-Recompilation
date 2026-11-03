MS_ROOT = str(__import__('pathlib').Path(__file__).resolve().parents[4])  # repository root
"""Negative control: lifter+header of T189 (no flags, no macros) vs the unmodified 766d3575 tree
(ps3recomp-t183): identical lifted C bodies and identical disassembly of every lifted function."""
import importlib.util, re, subprocess, sys
from pathlib import Path
M = Path(MS_ROOT)
sys.path.insert(0, str(M / 'ps3recomp-t189/tools'))
import ppu_difftest as D
import bench_ppu_regpromo as B


def load_lifter(tree):
    spec = importlib.util.spec_from_file_location(f'lifter_{tree}', M / tree / 'tools/ppu_lifter.py')
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(M / tree / 'tools'))
    spec.loader.exec_module(m)
    return m


old, new = load_lifter('ps3recomp-t183'), load_lifter('ps3recomp-t189')
out = M / 'generated/analysis/t189/scratch/default_equiv'
bad = 0
progs = [('kernels', D.kernel_program())] + [(f'random{s}', D.random_program(s, nfuncs=6, body=60)) for s in (1, 2, 3)]
for name, p in progs:
    res = {}
    for tag, L in (('old', old), ('new', new)):
        D.ppu_lifter = L
        h, s = D.lift(p, name.startswith('random') and name.endswith('2'))
        body = s[s.index('\nvoid func_'):]
        exe, _, _ = D.build(out / name, tag, h, s, p)
        dis = subprocess.run([B.objdump(), '-d', '--no-show-raw-insn', '--no-leading-addr', '-M', 'intel',
                              str(exe.parent / 'lifted.obj')], capture_output=True, text=True).stdout
        fn = {}
        cur = None
        for line in dis.splitlines():
            m = re.match(r'^<\??(func_[0-9A-F]{8})', line)
            if m:
                cur = m.group(1); fn[cur] = []
            elif line.startswith('<'):
                cur = None
            elif cur and line.strip():
                fn[cur].append(re.sub(r'#.*', '', line).strip())
        res[tag] = (body, fn)
    same_c = res['old'][0] == res['new'][0]
    same_x = res['old'][1] == res['new'][1]
    n = len(res['new'][1])
    print(f'{name}: lifted C identical={same_c}, x64 of {n} functions identical={same_x}')
    bad += not (same_c and same_x)
print('default_equiv:', 'PASS' if not bad else f'FAIL ({bad})')
sys.exit(1 if bad else 0)
