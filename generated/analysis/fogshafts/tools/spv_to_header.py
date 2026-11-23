# Regenerates an rsx_vk_scenefx*_comp.spv.h in the existing layout: a 2-line preamble, then 8 words per line.
import sys, struct
spv, hdr, name = sys.argv[1], sys.argv[2], sys.argv[3]
data = open(spv, 'rb').read()
assert len(data) % 4 == 0 and struct.unpack('<I', data[:4])[0] == 0x07230203, 'not SPIR-V'
words = struct.unpack('<%dI' % (len(data) // 4), data)
lines = []
for i in range(0, len(words), 8):
    lines.append('\t' + ','.join('0x%08x' % w for w in words[i:i + 8]) + (',' if i + 8 < len(words) else ''))
out = '\t// 1116.2.0\n\t #pragma once\nconst uint32_t %s[] = {\n%s\n};\n' % (name, '\n'.join(lines))
open(hdr, 'w', newline='\n').write(out)
print(hdr, len(words), 'words')
