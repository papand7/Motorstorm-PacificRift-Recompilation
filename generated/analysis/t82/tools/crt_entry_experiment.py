#!/usr/bin/env python3
"""T82 experiment (analysis only): does a job whose entry calls its body by manual link -- the CRT entry
every one of the 31 MotorStorm WWS modules has (`ila $r0, post; a $r0,$r0,$r126; brz $r81, body`) -- end in
spu_restart_dispatch? Synthetic module (no game bytes), lifted by the given tree, run with the real runtime
under PS3_SPU_AOT_PROF; prints the counters, the unwind flag and the state comparison with the interpreter.

  py -3 crt_entry_experiment.py <ps3recomp tree>     (under vcvars + LLVM, CC = cc shim)"""
import os, struct, subprocess, sys, tempfile
from pathlib import Path

TREE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TREE / 'tests')); sys.path.insert(0, str(TREE / 'tools'))
from test_spu_reloc_job import RR, RI10, RI16, RI18, Asm  # noqa: E402
from test_spu_switch_linkret import build, lift  # noqa: E402


def crt_module(seed=11, loops=12):
    a = Asm(); I = a.I
    def il(rt, v): I('il', lambda pc, L: RI16(0x081, rt, v))
    def ai(rt, ra, v): I('ai', lambda pc, L: RI10(0x1C, rt, ra, v))
    def lqd(rt, off, ra): I('lqd', lambda pc, L: RI10(0x34, rt, ra, off >> 4))
    def stqd(rt, off, ra): I('stqd', lambda pc, L: RI10(0x24, rt, ra, off >> 4))
    def rr(mn, op, rt, ra, rb): I(mn, lambda pc, L: RR(op, rt, ra, rb))
    def wrch(ch, rt): I('wrch', lambda pc, L: RR(0x10D, rt, ch))
    def rdch(rt, ch): I('rdch', lambda pc, L: RR(0x00D, rt, ch))
    def bi(ra): I('bi', lambda pc, L: RR(0x1A8, 0, ra))
    def dma(ls_reg, ea_reg, size, cmd):
        wrch(16, ls_reg); il(7, 0); wrch(17, 7); wrch(18, ea_reg); il(7, size); wrch(19, 7)
        il(8, 3); wrch(20, 8); il(59, cmd); wrch(21, 59)
        il(59, 8); wrch(22, 59); il(59, 2); wrch(23, 59); rdch(59, 24)
    bi(0)
    a.L('H'); rr('a', 0x0C0, 20, 10, 11); rr('xor', 0x241, 20, 20, 12); bi(0)
    a.L('body')                                   # the job body: work, calls, PUT, `bi $r0` to post
    stqd(0, 16, 1); ai(1, 1, -32)
    il(31, loops); il(40, 0)
    a.L('loop')
    I('brsl', lambda pc, L: RI16(0x066, 0, (L['H'] - pc) >> 2))
    rr('a', 0x0C0, 40, 40, 20)
    I('ori', lambda pc, L: RI10(0x04, 10, 20, 0))
    ai(31, 31, -1)
    I('brnz', lambda pc, L: RI16(0x042, 31, (L['loop'] - pc) >> 2))
    stqd(40, 64, 5); ai(6, 5, 64); dma(6, 4, 64, 0x20)
    ai(1, 1, 32); lqd(0, 16, 1); bi(0)
    a.L('entry')
    stqd(0, 16, 1); ai(1, 1, -32)
    I('brsl', lambda pc, L: RI16(0x066, 126, 1))
    a.L('next')
    I('il', lambda pc, L: RI16(0x081, 125, L['next']))
    rr('sf', 0x040, 126, 125, 126)
    I('ila', lambda pc, L: RI18(0x21, 5, L['bss'])); rr('a', 0x0C0, 5, 5, 126)
    dma(5, 3, 64, 0x40)
    lqd(10, 0, 5); lqd(11, 16, 5); lqd(12, 32, 5)
    il(81, 0)
    I('ila', lambda pc, L: RI18(0x21, 0, L['post'])); rr('a', 0x0C0, 0, 0, 126)   # manual link
    I('brz', lambda pc, L: RI16(0x040, 81, (L['body'] - pc) >> 2))
    I('br', lambda pc, L: RI16(0x064, 0, (L['body'] - pc) >> 2))
    a.L('post')
    stqd(40, 80, 5)
    ai(1, 1, 32); lqd(0, 16, 1); bi(0)
    a.align(16); a.raw(b't82 synthetic crt-entry job\0'); a.align(16)
    a.L('bss')
    body = a.build(0x30); size = 0x30 + len(body)
    guid = b''.join(struct.pack('>I', RI18(0x21, 2, (seed * 0x9E37 + k * 0x1F3) & 0x3FFFF)) for k in range(4))
    hdr = guid + struct.pack('>8I', a.labels['entry'], size + 0x20, 0x200, 0, 0xC0DEC0DE, 8, 0x4000, 4)
    return hdr + body, a.labels


img, L = crt_module()
tmp = Path(tempfile.mkdtemp(prefix='t82-crt-'))
(tmp / 'CRT.bin').write_bytes(img)
exe = build(tmp, lift(TREE, tmp, img))
env = {k: v for k, v in os.environ.items() if not k.startswith(('SPU_', 'SPURS_', 'PS3_', 'YDKJ_', 'LBP_'))}
print(f'labels: body 0x{L["body"]:X} post 0x{L["post"]:X} entry 0x{L["entry"]:X} (offsets; base 0x8C00)')
dumps = {}
for mode, extra in (('interp', {}), ('aot', {'PS3_SPU_AOT_PROF': '3600'})):
    r = subprocess.run([str(exe), 'run', mode, str(tmp / 'CRT.bin'), '8C00', str(tmp / f'{mode}.dump')],
                       capture_output=True, text=True, env=dict(env, **extra), timeout=120)
    for l in r.stdout.splitlines():
        if l.startswith(('run ', '[spu-aot-prof]')):
            print(f'{mode}: {l}')
    dumps[mode] = (tmp / f'{mode}.dump').read_bytes()
print('aot state == interpreter state:', dumps['aot'] == dumps['interp'])
