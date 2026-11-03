"""Classify the bctr sites the lifter left without a jump table (JT_UNRESOLVED report), from the ELF.
For each: the instruction that defines the mtctr source, whether an indexed load/bound compare appears in the previous 120
instructions, and the next instruction (a tail-call `bctr` normally follows a function-descriptor load).
usage: classify_bctr_t173.py <elf> <ps3recomp tools dir> <unresolved.txt>"""
import struct, sys
from collections import Counter

sys.path.insert(0, sys.argv[2])
import ppu_disasm

d = open(sys.argv[1], 'rb').read()
phoff, phes, phn = struct.unpack('>Q', d[32:40])[0], *struct.unpack('>HH', d[54:58])
SEG = []
for i in range(phn):
    t, fl, off, va, _, fsz, _, _ = struct.unpack('>IIQQQQQQ', d[phoff + i * phes:phoff + i * phes + 56])
    if t == 1 and fl & 1:
        SEG.append((va, off, fsz))


def insn(a):
    for va, off, fsz in SEG:
        if va <= a < va + fsz:
            return ppu_disasm.decode(struct.unpack('>I', d[off + a - va:off + a - va + 4])[0], a)


cls, rows = Counter(), []
for line in open(sys.argv[3]):
    a = int(line.split()[0], 16)
    back = [insn(a - 4 * k) for k in range(1, 121)]
    mt = next((x for x in back if x.mnemonic == 'mtctr'), None)
    src = mt.operands.strip() if mt else '?'
    dfn = next((x for x in back if x.addr < (mt.addr if mt else a) and x.operands.split(',')[0].strip() == src
                and not x.mnemonic.startswith(('st', 'cmp', 'b'))), None)
    dm = dfn.mnemonic if dfn else '?'
    idx = any(x.mnemonic in ('lwzx', 'lwax') for x in back)
    bound = any(x.mnemonic in ('cmplwi', 'cmpwi', 'cmpldi', 'cmpdi') for x in back[:40])
    key = f'ctr<-{dm}' + ('+indexed-load-in-120' if idx else '') + ('+bound' if idx and bound else '')
    cls[key] += 1
    rows.append((a, key, f'{dfn.mnemonic} {dfn.operands}' if dfn else '?'))
for k, v in cls.most_common():
    print(f'{v:4d} {k}')
print('--- sites with an indexed load in the previous 120 instructions:')
for a, k, dtxt in rows:
    if 'indexed' in k:
        print(f'  {a:08X} {k}  [{dtxt}]')
print('--- stack-reload sites:')
for line in open(sys.argv[3]):
    if 'stack-reload' in line:
        a = int(line.split()[0], 16)
        for k in range(-16, 1):
            x = insn(a + 4 * k)
            print(f'  {x.addr:08X}  {x.mnemonic} {x.operands}')
        print('  ---')
