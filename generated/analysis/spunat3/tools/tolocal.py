"""spunat3: straight-line statements of one lifted function in local-register form (hand-native helper).

  python tolocal.py <spu_recomp.c> <prefix> <addr> [--stop-at-branch]

Prints the statements with ctx->gpr[n] -> R_n, LS access through `ls` with the diagnostic gate 0,
SPU_RA(x) kept (reloc lifts), and lists the registers read before written (inputs) and written."""
import re
import sys

src, prefix, addr = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
t = open(src, encoding='utf-8').read()
head = f'void {prefix}spu_func_{addr:08X}(spu_context* ctx) {{\n'
i = t.index(head) + len(head)
j = t.index('\n}\n', i)
body = [l.strip() for l in t[i:j].split('\n')]
out, rd, wr = [], [], []
for l in body:
    if not l or l in ('/* nop */;', '/* branch hint (ignored) */;') or re.fullmatch(r'loc_[0-9A-F]{8}:', l):
        continue
    m = re.match(r'ctx->gpr\[(\d+)\] = (.*);$', l)
    rhs = m.group(2) if m else l
    for r in re.findall(r'ctx->gpr\[(\d+)\]', rhs):
        if int(r) not in wr and int(r) not in rd:
            rd.append(int(r))
    if m and int(m.group(1)) not in wr:
        wr.append(int(m.group(1)))
    l = re.sub(r'spu_ls_read128\(ctx, ', 'spu_ls_read128_ls(ctx, ls, 0, ', l)
    l = re.sub(r'spu_ls_write128\(ctx, ', 'spu_ls_write128_ls(ctx, ls, 0, ', l)
    l = re.sub(r'ctx->gpr\[(\d+)\]', r'R_\1', l)
    out.append(l)
print('\n'.join('    ' + l for l in out))
print('/* inputs:', ' '.join(f'r{r}' for r in rd), '*/')
print('/* written:', ' '.join(f'r{r}' for r in sorted(wr)), '*/')
