"""spunat3 generator for chained (--chain-chunks) lifts: Codex's gen_native.py (copied here) plus
  - the production lift as input (the regcache dispatch lines `if (!_spu_lsd) { ... goto loc_X_c; }`
    are dropped first: the native implements the plain path, which computes the same state);
  - the spu_nx.h speculation of straight-line single-precision regions (natives without channel
    calls only), MXCSR left at every exit;
  - the FNREC entry recorder, LIFT() symbol names and nat_register_all for mkpair.py.

  python gen_chain.py <production spu_recomp.c> <prefix> <image id> <out.c> --entry loc_000XXXXX [...]
         [--no-nx] [--mutate nxflag]"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nxpass import nx_region, RE_DEF, sink_stores

ap = argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('prefix'); ap.add_argument('image_id', type=int); ap.add_argument('out')
ap.add_argument('--entry', action='append', required=True)
ap.add_argument('--no-nx', action='store_true')
ap.add_argument('--mutate', default='')
a = ap.parse_args()
img = a.prefix[:-1]
tmpd = HERE.parent / 'tmp' / 'gen_chain' / img
tmpd.mkdir(parents=True, exist_ok=True)
src = Path(a.src).read_text(encoding='utf-8')
src = '\n'.join(l for l in src.split('\n') if 'if (!_spu_lsd) {' not in l)
(tmpd / 'spu_recomp.c').write_text(src, encoding='utf-8')
raw = tmpd / 'gen.c'
cmd = [sys.executable, str(HERE / 'gen_native.py'), str(tmpd / 'spu_recomp.c'), str(a.image_id), str(raw),
       '--fast', '--scalar', '--dirty']
for e in a.entry:
    cmd += ['--entry', e]
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout[-2000:], r.stderr[-2000:])
if r.returncode:
    sys.exit(r.returncode)
t = raw.read_text(encoding='utf-8')
t = re.sub(re.escape(a.prefix) + r'(spu_(?:func|grp)_[0-9A-F]{8})', r'LIFT(\1)', t)
t = re.sub(r'void [A-Za-z0-9_]*spu_natives_register\(void\) \{', 'static void nat_register_all(void) {', t)
lines = t.split('\n')
out, i = [], 0
fn = None
while i < len(lines):
    l = lines[i]
    m = re.match(r'static int nat_([0-9A-F]{8})\(spu_context\* ctx\) \{', l)
    if m:
        fn = m.group(1)
        # find the function end to decide nx eligibility
        j = i
        while lines[j] != '}':
            j += 1
        body = lines[i:j]
        calls = any(re.search(r'spu_(?:rdch|wrch|rchcnt|stop|halt|unsupported)\(|int_enable =', b) for b in body)
        use_nx = not a.no_nx and not calls and any(re.search(r'\bspu_(fa|fs|fm|fma|fms|fnms)\(', b) for b in body)
        out.append(l)
        out.append(f'    SPU_FNREC(ctx, 0x{int(fn, 16):X}u);')
        out.append('    const int _spu_lsd = 0; (void)_spu_lsd;')
        k = i + 1
        if use_nx:
            sd = next(q for q in range(i, j) if lines[q].startswith('#define STORE_ALL()'))
            sunk, nslots = sink_stores(lines[sd + 1:j])
            lines[sd + 1:j] = sunk
            j = sd + 1 + len(sunk)
            out.append(f'    uint32_t _sta[{max(1, nslots)}]; u128 _stv[{max(1, nslots)}]; (void)_sta; (void)_stv;')
        # copy prologue up to STORE_ALL definition, then the body with speculation
        region = []

        def flush_region():
            if not region:
                return
            if use_nx and any(re.search(r'\bspu_(fa|fs|fm|fma|fms|fnms)\(', x) for x in region):
                rd, wr = set(), set()
                for x in region:
                    mm = RE_DEF.match(x)
                    rhs = mm.group(3) if mm else x
                    rd |= {int(v) for v in re.findall(r'\bR_(\d+)\b', rhs)}
                    if mm:
                        wr.add(int(mm.group(1)))
                sv = sorted(rd & wr)
                out.append('    { ' + ' '.join(f'const u128 _s{v} = R_{v};' for v in sv) + ' __m128i _nxb = _mm_setzero_si128();')
                out.extend('    ' + x.strip() for x in nx_region([x.strip() for x in region]))
                chk = '0' if a.mutate == 'nxflag' else 'NX_ANY(_nxb)'
                out.append(f'    if (__builtin_expect({chk}, 0)) {{ NX_LEAVE(_csr); ' + ' '.join(f'R_{v} = _s{v};' for v in sv))
                out.extend(region)
                out.append('    NX_ENTER(_csr0); } }')
            else:
                out.extend(region)
            region.clear()

        while k < j:
            x = lines[k]
            if x.startswith('#define STORE_ALL()'):
                if use_nx:
                    out.append('    unsigned _csr, _csr0; NX_ENTER(_csr); (void)_csr0;')
                    x = x.replace('#define STORE_ALL() do { ', '#define STORE_ALL() do { NX_LEAVE(_csr); ')
                out.append(x)
            elif (RE_DEF.match(x.strip()) or x.strip().startswith('_st')) and x.startswith('    ') and use_nx:
                region.append(x)
            else:
                flush_region()
                out.append(x)
            k += 1
        flush_region()
        i = j
        continue
    out.append(l)
    i += 1
hdr = ['#pragma STDC FENV_ACCESS ON',
       '#pragma clang attribute push (__attribute__((target("avx2,fma"))), apply_to = function)',
       '#include "../harness/spu_nx.h"', f'#define NAT_IMG {a.image_id}', '#include "../harness/spu_fnrec.h"']
res = '\n'.join(out)
res = res.replace('#include "spu_helpers.h"\n', '#include "spu_helpers.h"\n' + '\n'.join(hdr) + '\n', 1)
res += '\n#pragma clang attribute pop\n#pragma STDC FENV_ACCESS OFF\n'
Path(a.out).write_text(res, encoding='utf-8')
print('wrote', a.out)
