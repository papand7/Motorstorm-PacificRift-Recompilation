"""T146: resolve the T143 (e2f9435) cherry-pick against T122/T144 in rsx_d3d12_backend.c."""
import re, sys
p = sys.argv[1]
s = open(p, 'rb').read().decode('utf-8')
nl = '\r\n' if '\r\n' in s else '\n'
s = s.replace('\r\n', '\n')
pat = re.compile(r'<<<<<<< HEAD\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n', re.S)
ms = list(pat.finditer(s))
assert len(ms) == 7, len(ms)

def r0(a, b):  # wait wrapper: T122 per-site counting + T143 timing in one function pair
    a = a.replace('/* wait_for_gpu() is wait_for_gpu_at(__LINE__): RSX_GPU_SYNC counts each call\n * site\'s waits on its own. */\nstatic void wait_for_gpu_at(int line)\n',
                  '/* wait_for_gpu() is wait_for_gpu_at(__LINE__): RSX_GPU_SYNC counts each call\n'
                  ' * site\'s waits on its own; RSX_GPU_PROF times every wait (T146: one wrapper\n'
                  ' * for both, T122 + T143). */\n'
                  'static void wait_for_gpu_at_(int line);\n'
                  'static void wait_for_gpu_at(int line)\n')
    assert 'wait_for_gpu_at_(int line);' in a
    return a

def r3(a, b):  # PSO / stencil ref: T143 dedup + T144's shared-depth log
    log = a[a.index('                    /* The shared depth buffer'):]
    return b + log

res = [r0,
       lambda a, b: a + b,
       lambda a, b: a + b,
       r3,
       lambda a, b: a + b,
       lambda a, b: a + b,
       lambda a, b: a + b.split('\n', 1)[1]]
out, i = [], 0
for m, f in zip(ms, res):
    out.append(s[i:m.start()]); out.append(f(m.group(1), m.group(2))); i = m.end()
out.append(s[i:])
s = ''.join(out)

# the body after the wrapper: T143 named it wait_for_gpu_(void); T122's body uses `line`
old_hdr = ('{\n    if (!s_gp.on) { wait_for_gpu_(); return; }\n    const double t0 = gp_now_ms();\n    wait_for_gpu_();\n'
           '    s_gp.cur.t[GP_T_CPU_WAIT] += gp_now_ms() - t0;\n    s_gp.cur.c[GP_C_WAIT]++;\n}\nstatic void wait_for_gpu_(void)\n{\n')
new_hdr = ('{\n    if (!s_gp.on) { wait_for_gpu_at_(line); return; }\n    const double t0 = gp_now_ms();\n    wait_for_gpu_at_(line);\n'
           '    s_gp.cur.t[GP_T_CPU_WAIT] += gp_now_ms() - t0;\n    s_gp.cur.c[GP_C_WAIT]++;\n}\nstatic void wait_for_gpu_at_(int line)\n{\n')
assert s.count(old_hdr) == 1
s = s.replace(old_hdr, new_hdr)

# one ResourceBarrier wrapper feeding both counters
t143 = '#define ResourceBarrier(self, n, ...)                ResourceBarrier((GP_N(GP_C_BARRIER, (n)), self), n, __VA_ARGS__)\n'
both = ('/* RSX_GPU_SYNC (T122) and RSX_GPU_PROF (T143): every ResourceBarrier call adds its\n'
        ' * NumBarriers to s_gsy_barriers (one add per call, always on; [gpu-sync] reports\n'
        ' * it) and, with the profile on, to GP_C_BARRIER. One wrapper for both (T146). */\n'
        'static unsigned long long s_gsy_barriers;\n'
        '#define ResourceBarrier(self, n, ...)                ResourceBarrier((s_gsy_barriers += (unsigned)(n), GP_N(GP_C_BARRIER, (n)), self), n, __VA_ARGS__)\n')
assert s.count(t143) == 1
s = s.replace(t143, both)
t122 = ('/* RSX_GPU_SYNC (T122): every ResourceBarrier call adds its NumBarriers to\n'
        ' * s_gsy_barriers (one add per call, always on; [gpu-sync] reports it). */\n'
        'static unsigned long long s_gsy_barriers;\n'
        '#define ResourceBarrier(l, n, b) ResourceBarrier((s_gsy_barriers += (unsigned)(n), (l)), (n), (b))\n'
        '#ifdef __clang__\n'
        '#pragma clang diagnostic ignored "-Wdisabled-macro-expansion"   /* the macro above names itself */\n'
        '#endif\n\n')
assert s.count(t122) == 1
s = s.replace(t122, '')
assert '<<<<<<<' not in s and '>>>>>>>' not in s
assert s.count('#define ResourceBarrier') == 1 and s.count('#define wait_for_gpu()') == 1
open(p, 'wb').write(s.replace('\n', nl).encode('utf-8'))
print('ok')
