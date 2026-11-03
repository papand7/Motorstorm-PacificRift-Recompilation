"""T140: move the PS3_VM_STATS block ahead of ppu_stwcx32 so the store-conditionals can count too."""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'runtime/ppu/ppu_loader.cpp'
s = p.read_bytes().decode('utf-8')
nl = '\r\n'
head = '/* ---------------------------------------------------------------------------' + nl + ' * PS3_VM_STATS=<ms>'
a = s.index(head)
end_marker = '    if ((++n & 0x3FFFu) == 0) vm_stats_flush(c);' + nl + '}' + nl
b = s.index(end_marker, a) + len(end_marker)
block = s[a:b]
s = s[:a] + s[b:]
# vm_store_slow_init calls vm_stats_on(): its forward declaration stays valid.
anchor = 'extern "C" int ppu_stwcx32(uint64_t ea, uint32_t expected, uint32_t val)'
i = s.index(anchor)
s = s[:i] + block + nl + s[i:]
p.write_bytes(s.encode('utf-8'))
print('moved', len(block), 'bytes')
