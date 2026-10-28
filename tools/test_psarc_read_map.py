#!/usr/bin/env python3
"""psarc_read_map on a synthetic archive (no game data)."""
import hashlib
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psarc_read_map as prm  # noqa: E402

BLOCK = 65536


def make_psarc(path: Path, files: dict[str, bytes]):
    """Minimal zlib PSARC: manifest is entry 0, one block list, 30-byte entries."""
    names = list(files)
    payloads = ['\n'.join(names).encode()] + [files[n] for n in names]
    blocks, lens, ents = [], [], []
    for data in payloads:
        z = len(lens)
        for i in range(0, max(1, len(data)), BLOCK):
            raw = data[i:i + BLOCK]
            comp = zlib.compress(raw)
            if len(comp) >= BLOCK:
                comp = raw                                  # stored raw, length 0 = full block
            lens.append(0 if len(comp) == BLOCK else len(comp))
            blocks.append(comp)
        ents.append((z, len(data), len(blocks) - (len(lens) - z)))
    count = len(payloads)
    toc_len = 32 + 30 * count + 2 * len(lens)
    out = bytearray(b'PSAR' + struct.pack('>I', 0x00010004) + b'zlib' +
                    struct.pack('>5I', toc_len, 30, count, BLOCK, 0))
    offs, pos, bi = [], toc_len, 0
    for z, size, _ in ents:
        offs.append(pos)
        n = max(1, (size + BLOCK - 1) // BLOCK)
        pos += sum(len(b) for b in blocks[bi:bi + n])
        bi += n
    for i, (z, size, _) in enumerate(ents):
        md5 = hashlib.md5((names[i - 1] if i else '').upper().encode()).digest()
        out += md5 + z.to_bytes(4, 'big') + size.to_bytes(5, 'big') + offs[i].to_bytes(5, 'big')
    out += b''.join(struct.pack('>H', L) for L in lens)
    out += b''.join(blocks)
    path.write_bytes(out)
    return offs


class PsarcReadMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        files = {'/gui/frontend.gui': b'a' * 100, '/worlds/track_garage_x.rpk': bytes(range(256)) * 600,
                 '/gui/mainmenu.gui': b'm' * 50}
        self.offs = make_psarc(self.d / 'a.psarc', files)
        self.spans = prm.load_index(self.d / 'a.psarc')

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_names_and_spans(self):
        names = [n for _, _, n in self.spans]
        self.assertEqual(names, ['<manifest>', '/gui/frontend.gui', '/worlds/track_garage_x.rpk', '/gui/mainmenu.gui'])
        for (s, e, _), o in zip(self.spans, self.offs):
            self.assertEqual(s, o)
            self.assertGreater(e, s)
        self.assertEqual(self.spans[1][1], self.spans[2][0])          # contiguous

    def test_overlap(self):
        starts = [s for s, _, _ in self.spans]
        g0, g1, _ = self.spans[2]
        self.assertEqual(prm.touched(self.spans, starts, g0, 1), ['/worlds/track_garage_x.rpk'])
        self.assertEqual(prm.touched(self.spans, starts, g0 - 1, 2), ['/gui/frontend.gui', '/worlds/track_garage_x.rpk'])
        self.assertEqual(prm.touched(self.spans, starts, 0, 32), [])               # header only
        self.assertEqual(prm.touched(self.spans, starts, self.spans[-1][1] + 10, 5), [])

    def test_run_report(self):
        run = self.d / 'run'
        run.mkdir()
        g0 = self.spans[2][0]
        (run / 'stderr.log').write_text(
            '[fsread] fd=5 want=32 got=32 pos=0\n'
            f'[fsread] fd=9 want=4 got=4 pos={g0}\n'               # other descriptor: ignored with --fd 5
            f'noise\n[fsread] fd=5 want=64 got=64 pos={g0 + 8}\n')
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            prm.main([str(run), '--fd', '5', '--archive', str(self.d / 'a.psarc')])
        out = buf.getvalue()
        self.assertIn('2 reads, 96 bytes', out)
        self.assertIn('first "garage" member: stderr:4', out)
        self.assertIn('first "mainmenu" member: none read', out)

    def test_shared_and_nested_spans(self):
        spans = [(0, 100, 'big'), (10, 20, 'inner'), (10, 20, 'dup'), (100, 150, 'next')]
        starts = [a for a, _, _ in spans]
        self.assertEqual(prm.touched(spans, starts, 50, 1), ['big'])
        self.assertEqual(prm.touched(spans, starts, 15, 1), ['big', 'inner', 'dup'])
        self.assertEqual(prm.touched(spans, starts, 99, 2), ['big', 'next'])

    def test_rejects_non_psarc(self):
        p = self.d / 'x.bin'
        p.write_bytes(b'\0' * 64)
        with self.assertRaises(ValueError):
            prm.load_index(p)


if __name__ == '__main__':
    unittest.main(verbosity=1)
