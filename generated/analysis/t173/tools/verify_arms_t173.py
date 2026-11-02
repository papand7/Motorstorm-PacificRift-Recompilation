"""Compare the lifted switch for the dispatcher at 0x00CB7E74 against a table decode done directly from the ELF
(independent of ppu_lifter), and check every arm has exactly one label inside the same function.
usage: verify_arms_t173.py <elf> <lifted chunk.cpp> <function name, e.g. func_00CB7D80>"""
import re, struct, sys

d = open(sys.argv[1], 'rb').read()
phoff, phes, phn = struct.unpack('>Q', d[32:40])[0], *struct.unpack('>HH', d[54:58])
SEG = [struct.unpack('>IIQQQQQQ', d[phoff + i * phes:phoff + i * phes + 56]) for i in range(phn)]


def rd(a):
    for t, fl, off, va, _, fsz, _, _ in SEG:
        if t == 1 and va <= a < va + fsz:
            return struct.unpack('>I', d[off + a - va:off + a - va + 4])[0]


R2 = 0x010CE894
base = rd(R2 + 0x65D8)
want = set()
for k in range(29):
    v = rd(base + 4 * k)
    want.add((base + (v - (1 << 32) if v & 0x80000000 else v)) & 0xFFFFFFFF)
print(f'ELF: table base 0x{base:08X}, 29 entries, {len(want)} distinct targets')

lines = open(sys.argv[2], 'r', encoding='utf-8', errors='replace').read().splitlines()
start = next(i for i, l in enumerate(lines) if l.startswith(f'void {sys.argv[3]}('))
end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith('void '))
body = lines[start:end]
sw = [l for l in body if 'switch ((uint32_t)ctx->ctr)' in l and '0x00CB7E48u' in l and '0x00CB8BD8u' in l]
print('switch lines carrying the table:', len(sw))
arms = set(int(x, 16) for x in re.findall(r'case 0x([0-9A-F]{8})u: goto loc_', sw[0]))
print(f'lifted: {len(arms)} arms; equal to ELF decode: {arms == want}')
labels = {}
for l in body:
    m = re.match(r'^loc_([0-9A-F]{8}):', l)
    if m:
        labels[int(m.group(1), 16)] = labels.get(int(m.group(1), 16), 0) + 1
print('every arm has exactly one label in this function:', all(labels.get(a) == 1 for a in arms))
print('default arm keeps the indirect call:', 'default: ps3_indirect_call(ctx); return; } return;' in sw[0])
print('mtctr feeding it is unchanged:', any(l.strip() == 'ctx->ctr = ctx->gpr[11];' for l in body))
sys.exit(0 if arms == want else 1)
