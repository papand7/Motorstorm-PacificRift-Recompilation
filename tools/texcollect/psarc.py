# Public-tree code: no game data. A reader for PSARC archives (zlib blocks) and the 'EVOSBIG ' resource
# packs inside them, written from the public PSARC description and the project's own notes.
import hashlib
import struct
import zlib


class Psarc:
    """A PSARC: header, TOC, zlib block table; entry 0 is the manifest of member names."""

    def __init__(self, path):
        self.path = path
        self.f = open(path, 'rb')
        head = self.f.read(32)
        if head[:4] != b'PSAR' or head[8:12] != b'zlib':
            raise ValueError('not a zlib PSARC: ' + path)
        toc_len, self.entry_len, self.count, self.block, _flags = struct.unpack('>5I', head[12:32])
        if self.entry_len != 30:
            raise ValueError('unexpected PSARC entry length')
        self.toc = self.f.read(self.count * self.entry_len)
        self.blocks = self.f.read(toc_len - 32 - self.count * self.entry_len)
        self.by_hash = {self.toc[i * 30:i * 30 + 16]: i for i in range(self.count)}
        self.names = self.read(0).decode('latin1').split('\n')

    def read(self, i):
        e = self.toc[i * 30:(i + 1) * 30]
        z = int.from_bytes(e[16:20], 'big')
        size = int.from_bytes(e[20:25], 'big')
        off = int.from_bytes(e[25:30], 'big')
        out = bytearray()
        self.f.seek(off)
        for k in range((size + self.block - 1) // self.block):
            n = struct.unpack_from('>H', self.blocks, (z + k) * 2)[0] or self.block
            chunk = self.f.read(n)
            if n != self.block:
                try:
                    chunk = zlib.decompress(chunk)
                except zlib.error:
                    pass        # a block stored raw
            out += chunk
        return bytes(out[:size])

    def index_of(self, name):
        return self.by_hash[hashlib.md5(name.upper().encode('latin1')).digest()]

    def members(self):
        """(name, index) for every named member."""
        for n in self.names:
            if n:
                try:
                    yield n, self.index_of(n)
                except KeyError:
                    pass


def be(fmt, d, o):
    return struct.unpack_from('>' + fmt, d, o)


def evosbig_sections(d):
    """Every section of an 'EVOSBIG ' resource pack: (type u16, names, section bytes without its 16-byte
    magic+id). Empty when d is not such a pack."""
    if d[:8] != b'EVOSBIG ':
        return []
    try:
        (slen,) = be('I', d, 8)
        o = 12 + slen
        _dsize, doff = be('II', d, o)
        if d[doff:doff + 8] != b'EVOSBIG ':
            return []
        D = doff
        _v, _z, _s, nent, _nn, _nd, nlen, plen = be('HHIIIIII', d, D + 16)
        p = D + 16 + 36
        nb = d[p:p + nlen]
        p += nlen + plen
        out = []
        for _ in range(nent):
            size, off = be('II', d, p + 8)
            p += 16
            (nd,) = be('H', d, p)
            p += 2 + 8 * nd
            (nn,) = be('H', d, p)
            p += 2
            names = []
            for k in range(nn):
                a = be('I', d, p + 4 * k)[0]
                names.append(nb[a:nb.index(b'\0', a)].decode('latin1'))
            p += 4 * nn
            (npth,) = be('H', d, p)
            p += 2 + 4 * npth
            if d[off:off + 8] == b'EVOSBIG ':
                out.append((be('H', d, off + 8)[0], names, d[off + 16:off + size]))
        return out
    except (struct.error, ValueError, IndexError):
        return []
