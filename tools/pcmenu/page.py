# Read-only (no game data included): page-segment helpers (base-relative offsets) for MotorStorm PR .gui packs.
import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pack import page_section
class Page:
    def __init__(self, f=None, data=None, rel=None):
        if f is not None:
            d = open(f, 'rb').read(); ps = page_section(d)
            self.ps = ps; B = ps['base']; N = ps['datasize']
            data = d[B:B+N]
            rt = d[B+N:B+N+ps['relocsize']]
            rel = [struct.unpack_from('>I', rt, 4*i)[0] for i in range(len(rt)//4)]
        self.data = bytes(data); self.N = len(self.data)
        self.rel = list(rel); self.relset = set(self.rel)
    def u(self, o): return struct.unpack_from('>I', self.data, o)[0] if 0 <= o <= self.N-4 else None
    def i(self, o): return struct.unpack_from('>i', self.data, o)[0]
    def f(self, o): return struct.unpack_from('>f', self.data, o)[0]
    def s(self, o, maxlen=200):
        if o is None or not (0 < o < self.N): return None
        e = self.data.find(b'\0', o); t = self.data[o:e]
        return t.decode('latin1') if all(32 <= c < 127 for c in t) and len(t) < maxlen else None
    def word(self, o):
        v = self.u(o); r = '*' if o in self.relset else ' '
        fl = self.f(o)
        txt = f'{v:08x}{r}'
        if o in self.relset:
            st = self.s(v)
            if st is not None: txt += f' "{st}"'
            else: txt += f' ->{v:#x}'
        elif v and (0x30000000 < v < 0x50000000 or 0xb0000000 < v < 0xd0000000): txt += f' {fl:.5g}'
        elif v == 0xffffffff: txt += ' -1'
        elif v < 0x10000: txt += f' {v}'
        return txt
    def dump(self, lo, hi, prefix=''):
        for o in range(lo, hi, 4): print(f'{prefix}{o:#07x} +{o-lo:#04x} {self.word(o)}')
if __name__ == '__main__':
    p = Page(sys.argv[1])
    p.dump(int(sys.argv[2], 0), int(sys.argv[3], 0))
