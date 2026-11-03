#!/usr/bin/env python3
"""T167: D3DCompile cost of the game's vertex programs on the CPU path and on the GPU-fetch path.

  py -3 vs_compile_bench_t167.py <gvf_sample.hlsl> <repeats> <shader root> [...]

gvf_sample.hlsl is rsx_vp_decompile_gvf_ex's output for a one-instruction program: its prologue (everything before
'struct VSOutput') and its input lines are spliced into each captured program in place of the CPU-path ones, which is the only
text difference between the two decompiler modes. Inputs are deduplicated by the program text. Stays private: prints only
hashes and metrics.

Variants: cpu   as captured
          gvf   the T162 prologue (all 16 inputs fetched)
          mask  the T162 prologue, fetching only the inputs the program's text reads
         loop  all 16 inputs, one [loop] over the slots and one [loop] over the components, [branch] on the format
         lmask loop, skipping the inputs the program's text does not read
Flags are the backend's (vs_5_0, flags 0)."""
import ctypes, glob, hashlib, os, re, statistics as S, sys, time

d3dc = ctypes.WinDLL('d3dcompiler_47.dll')
d3dc.D3DCompile.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p,
                            ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
d3dc.D3DCompile.restype = ctypes.c_long


def compile_ms(src):
    b = src.encode()
    code, err = ctypes.c_void_p(), ctypes.c_void_p()
    t0 = time.perf_counter()
    hr = d3dc.D3DCompile(b, len(b), b'guest_vp2', None, None, b'main', b'vs_5_0', 0, 0, ctypes.byref(code), ctypes.byref(err))
    return (time.perf_counter() - t0) * 1000.0, hr >= 0


sample = open(sys.argv[1], encoding='utf-8').read()
HEAD = sample[:sample.index('struct VSOutput')]
GVF_LINE = '    [unroll] for (uint _k = 0u; _k < 16u; _k++) v[_k] = gvf_fetch(_k, input.vid);\n'
assert GVF_LINE in sample
INPUTS = re.compile(r'    v\[0\]=input\.a0;.*?v\[15\]=input\.a15;\n', re.S)
reps = int(sys.argv[2])
progs = {}
for root in sys.argv[3:]:
    for p in glob.glob(os.path.join(root, '**', 'vp_*.hlsl'), recursive=True):
        t = open(p, encoding='utf-8', errors='replace').read()
        if 'struct VSInput' not in t or not INPUTS.search(t):
            continue
        body = t[t.index('struct VSOutput'):]
        progs.setdefault(hashlib.sha256(body.encode()).hexdigest()[:12], body)
print(f'unique programs {len(progs)}')
tot = {'cpu': [], 'gvf': [], 'mask': [], 'loop': [], 'lmask': []}
NL = chr(10)
LHEAD = HEAD.replace('[unroll] for (uint c', 'float q[4] = {o.x, o.y, o.z, o.w};' + NL + '    [loop] for (uint c').replace('o[c] = v;', 'q[c] = v;').replace('    return o;' + NL + '}', '    return float4(q[0], q[1], q[2], q[3]);' + NL + '}').replace('if (t == 6u)', '[branch] if (t == 6u)').replace('if (t == 3u)', '[branch] if (t == 3u)')
assert LHEAD != HEAD
print('hash hlsl_len inputs_read ' + ' '.join(k + '_ms' for k in tot))
fails = 0
for h, body in sorted(progs.items()):
    code = body[body.index('float4 r[32]'):]
    used = sorted({int(x) for x in re.findall(r'\bv\[(\d+)\]', code)})
    mask = sum(1 << i for i in used)
    cpu_head = 'struct VSInput {\n' + ''.join(f'    float4 a{i}:ATTR{i};\n' for i in range(16)) + '};\n'
    v = {'cpu': cpu_head + body,
         'gvf': HEAD + INPUTS.sub(lambda m: GVF_LINE, body),
         'mask': HEAD + INPUTS.sub(lambda m: ''.join(f'    v[{i}] = gvf_fetch({i}u, input.vid);\n' for i in used), body),
         'loop': LHEAD + INPUTS.sub(lambda m: GVF_LINE.replace('[unroll]', '[loop]'), body),
         'lmask': LHEAD + INPUTS.sub(lambda m: f'    [loop] for (uint _k = 0u; _k < 16u; _k++) {{ if ({mask}u >> _k & 1u) v[_k] = gvf_fetch(_k, input.vid); else v[_k] = (float4)0; }}' + chr(10), body)}
    row = {}
    for k, src in v.items():
        ms = []
        for _ in range(reps):
            t, ok = compile_ms(src)
            if not ok and not fails:
                print('first failure:', k, h)
            fails += not ok
            ms.append(t)
        row[k] = S.median(ms)
        tot[k].append(row[k])
    print(f"{h} {len(v['gvf'])} {len(used)} " + ' '.join(f'{row[k]:.1f}' for k in tot), flush=True)
print('compile failures', fails)
for k, x in tot.items():
    print(f'{k:5s} n={len(x)} total_ms={sum(x):.0f} mean={S.mean(x):.1f} median={S.median(x):.1f} max={max(x):.1f}')
