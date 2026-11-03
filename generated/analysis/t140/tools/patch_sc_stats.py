"""T140: PS3_VM_STATS counters in ppu_stwcx32 / ppu_stdcx64 (one load each while off)."""
import sys
from pathlib import Path

p = Path(sys.argv[1]) / 'runtime/ppu/ppu_loader.cpp'
s = p.read_bytes().decode('utf-8')


def sub(old, new, count):
    global s
    assert s.count(old) == count, (old, s.count(old))
    s = s.replace(old, new)


sub('if (self && self->reserve_addr != (uint32_t)ea) { resv_unlock(L); return 0; }   /* reservation lost */',
    'if (self && self->reserve_addr != (uint32_t)ea) { resv_unlock(L); vm_stat(VMS_SC_LOST); return 0; }   /* reservation lost */', 1)
sub('    if (self && self->reserve_addr != (uint32_t)ea) { resv_unlock(L); return 0; }\r\n',
    '    if (self && self->reserve_addr != (uint32_t)ea) { resv_unlock(L); vm_stat(VMS_SC_LOST); return 0; }\r\n', 1)
sub('    if (ok) ppu_resv_break(ea);\r\n    resv_unlock(L);\r\n',
    '    if (ok) ppu_resv_break(ea);\r\n    resv_unlock(L);\r\n'
    '    vm_stat(ok ? VMS_SC_OK : VMS_SC_VALUE); if (coh) vm_stat(VMS_SC_COH);\r\n', 1)
sub('    if (ok) { ppu_resv_break(ea); ppu_resv_break(ea + 4); }  /* 8-byte store spans two words */\r\n    resv_unlock(L);\r\n',
    '    if (ok) { ppu_resv_break(ea); ppu_resv_break(ea + 4); }  /* 8-byte store spans two words */\r\n    resv_unlock(L);\r\n'
    '    vm_stat(ok ? VMS_SC_OK : VMS_SC_VALUE); if (coh) vm_stat(VMS_SC_COH);\r\n', 1)
p.write_bytes(s.encode('utf-8'))
print('ok')
