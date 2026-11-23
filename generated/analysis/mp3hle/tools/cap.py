"""Parse PS3_MP3_CAPTURE job files."""
import struct, sys
from pathlib import Path
LS = 0x40000
CMDN = {0x20:'PUT',0x40:'GET',0x24:'PUTL',0x44:'GETL',0x21:'PUTB',0x22:'PUTF',0x41:'GETB',0x42:'GETF'}
class Job:
    def __init__(s, p):
        b = Path(p).read_bytes(); s.path = p
        h = struct.unpack_from('<8I', b, 0); o = 32
        s.base, s.ret, s.entry, s.spu, s.img = h[2], h[3], h[4], h[5], h[6]
        s.gin = [struct.unpack_from('<4I', b, o + 16*i) for i in range(128)]; o += 2048
        s.lin = b[o:o+LS]; o += LS
        s.gout = [struct.unpack_from('<4I', b, o + 16*i) for i in range(128)]; o += 2048
        s.lout = b[o:o+LS]; o += LS
        s.ents = []
        if o + 8 <= len(b):
            n, dl = struct.unpack_from('<II', b, o); o += 8
            ents = [struct.unpack_from('<4IQII', b, o + 32*i) for i in range(n)]; o += 32*n
            data = b[o:o+dl]
            for cmd, lsa, size, tag, ea, doff, ph in ents:
                s.ents.append(dict(cmd=cmd, lsa=lsa, size=size, tag=tag, ea=ea, phase=ph, data=data[doff:doff+size]))
    def w(s, ls, a): return struct.unpack_from('>I', ls, a)[0]
if __name__ == '__main__':
    for p in sys.argv[1:]:
        j = Job(p)
        print(p, 'base %05X ret %05X entry %05X spu %d r3 %08X r4 %08X' % (j.base, j.ret, j.entry, j.spu, j.gin[3][0], j.gin[4][0]))
        for e in j.ents:
            print("  pc%08X %-4s lsa=%05X ea=%08X size=%5X tag=%d" % (e["phase"], CMDN.get(e['cmd'] & 0xFF, hex(e['cmd'])), e['lsa'], e['ea'], e['size'], e['tag']))
