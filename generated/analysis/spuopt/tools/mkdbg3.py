"""Debug copy of a generated native file: prints r1 at each label named on argv."""
import sys
src, dst = sys.argv[1], sys.argv[2]
labels = sys.argv[3:]
s = open(src).read()
for lab in labels:
    s = s.replace(lab + ':\n',
                  lab + ':\n    fprintf(stderr, "NAT ' + lab + ' %s r1=%08X\\n", __func__, R[1]._u32[0]);\n')
s = '#include <stdio.h>\n' + s
open(dst, 'w').write(s)
