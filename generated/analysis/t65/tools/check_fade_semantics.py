# T65 offline regression check: the loading-screen whiteout is the original fade term, rendered faithfully.
# usage (repo root): py -3 -I generated/analysis/t65/tools/check_fade_semantics.py
# Private: reads the decrypted EBOOT and private run captures; prints PASS/FAIL per check, exit 1 on any FAIL.
import json, re, struct, sys
ROOT = '.'
EBOOT = ROOT + '/generated/decrypted/EBOOT.elf'
RUN = ROOT + '/generated/runs/20261026-130707-t63-first-race/rsxi'
fails = 0
def check(name, ok, info=''):
    global fails
    fails += not ok
    print(('PASS ' if ok else 'FAIL ') + name + (' -- ' + info if info else ''))

elf = open(EBOOT, 'rb').read()
phoff = struct.unpack('>Q', elf[0x20:0x28])[0]; phn = struct.unpack('>H', elf[0x38:0x3A])[0]
segs = []
for i in range(phn):
    t, f, off, va, pa, fs, ms, al = struct.unpack('>IIQQQQQQ', elf[phoff + i * 56:phoff + i * 56 + 56])
    if t == 1: segs.append((va, off, fs))
def u32(a):
    for va, off, fs in segs:
        if va <= a < va + fs: return struct.unpack('>I', elf[off + a - va:off + a - va + 4])[0]
def f32(a): return struct.unpack('>f', struct.pack('>I', u32(a)))[0]
TOC = 0x109FBF0
def bl_target(a):
    w = u32(a); li = w & 0x3FFFFFC
    if li & 0x2000000: li -= 0x4000000
    return a + li if (w >> 26) == 18 and (w & 3) == 1 else None

# 1. Original fade term: c59.w = 1.0 + (-0.5) * t, t = now - start in seconds, no clamp in the loop.
check('TOC constants 0.0 / 1.0 / -0.5', (f32(TOC + 0x3D84), f32(TOC + 0x3D88), f32(TOC + 0x3D8C)) == (0.0, 1.0, -0.5))
check('0x3291CC fmadds f31,f31,f0,f29 (w = t*-0.5 + 1)', u32(0x3291CC) == 0xEFFFE83A, '%08X' % u32(0x3291CC))
check('0x3291DC li r4,0x3B (slot 59); 0x3291A0 li r4,0x37 (slot 55)', u32(0x3291DC) == 0x3880003B and u32(0x3291A0) == 0x38800037)
check('0x3291F0 stfs f31,0xC(r9) (w lane)', u32(0x3291F0) == 0xD3E9000C)
check('constant upload 0x7351E0 emits method 0x1EFC', u32(0x7351E4) == 0x3C000014 and u32(0x7351FC) == 0x60001EFC)
fp_ops = [a for a in range(0x329048, 0x329410, 4) if (u32(a) >> 26) == 63 and (((u32(a) >> 1) & 0x1F) == 23 or ((u32(a) >> 1) & 0x3FF) in (0, 32))]
check('no fsel/fcmpu/fcmpo in loop 0x329048-0x329410', not fp_ops, ' '.join('%X' % a for a in fp_ops))
check('time base: 0x4361B0 -> sys_time_get_system_time stub 0xCC011C, x1e-6', bl_target(0x4361C0) == 0xCC011C and abs(struct.unpack('>d', bytes.fromhex('%08X%08X' % (u32(TOC + 0x7248), u32(TOC + 0x724C))))[0] - 1e-6) < 1e-15)
# 2. Race loader brackets LoadRace with the loading screen.
check('0x8EA00: start 0x329660 @0x8EA64, LoadRace 0x89230 @0x8EA88, stop 0x329D90 @0x8EE88/0x8F0A4',
      bl_target(0x8EA64) == 0x329660 and bl_target(0x8EA88) == 0x89230 and bl_target(0x8EE88) == 0x329D90 and bl_target(0x8F0A4) == 0x329D90)
# 3. T63 RSXI frame 6287: constants follow the original term; draws go straight to the 8-bit display.
draws = [json.loads(l) for l in open(RUN + '/frames/f006287/events.jsonl') if '"e":"draw"' in l]
for d in draws:
    vc = {c[0]: c[1:] for c in d['guest']['vp_consts']}
    t, w = vc[55][0], vc[59][3]
    check('f6287 op%d c59.w == 1 - 0.5*c55.x' % d['op'], abs(w - (1 - 0.5 * t)) < 1e-3, 't=%.4f w=%.4f gain=%.2f' % (t, w, 1 - w))
    check('f6287 op%d display target, straight alpha' % d['op'], d['guest']['rt'] == '0x00000000' and d['guest']['blend_key'] == '0x0122418B')
# 4. Translated shaders: output = tex + w*(tc1 - tex), tc1 from VP o[8] = c[59]; no saturate on tc1 path.
for fp in ('fp_02537E81', 'fp_02538941'):
    s = open(RUN + '/../../20261023-172442-present-stall/rsxi/shaders/%s.hlsl' % fp).read() if fp == 'fp_02538941' else \
        open(ROOT + '/generated/runs/20261026-130707-t63-first-race/rsxi/shaders/%s.hlsl' % fp).read()
    check(fp + ' reads tc1 unsaturated, final MAD by .w', 'saturate(input.tc1)' not in s and 'input.tc1' in s and re.search(r'\(\(h\[\d\]\)\.wwww\) \* \(\(h\[\d\]\)\.xyzw\) \+', s) is not None)
for vp in ('vp_FF398E97', 'vp_F69565E0'):
    s = open(ROOT + '/generated/runs/20261026-130707-t63-first-race/rsxi/shaders/%s.hlsl' % vp).read()
    check(vp + ' o[8] (TEX1) = c[59]', 'o[8].xyzw = _v.xyzw' in s and '(vp_c[59]).xyzw' in s)
print('FAILURES', fails)
sys.exit(1 if fails else 0)
