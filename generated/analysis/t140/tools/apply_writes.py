"""T140: replace the vm_write* block of runtime/ppu/ppu_loader.cpp with tools/patch_writes.txt (keeps line endings)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
p = Path(sys.argv[1]) / 'runtime/ppu/ppu_loader.cpp'
s = p.read_bytes().decode('utf-8')
start = '/* Runtime tracer store watch: one compare while no watch is armed. */'
end = '    v = __builtin_bswap64(v); VM_WRITE_COH(a, &v, 8); }'
a = s.index(start)
b = s.index(end, a)
b = s.index('\n', b) + 1
nl = '\r\n' if '\r\n' in s[:4000] else '\n'
new = (HERE / 'patch_writes.txt').read_text(encoding='utf-8').replace('\r\n', '\n')
if nl != '\n':
    new = new.replace('\n', nl)
p.write_bytes((s[:a] + new + s[b:]).encode('utf-8'))
print('replaced', b - a, 'bytes with', len(new), 'newline', repr(nl))
