"""Regression: `texpack.py upscale --pbr` must add PBR maps for textures already in the pack (made by an
earlier run without --pbr), without running Real-ESRGAN. Synthetic images only.
Run: py -3 test_texpack_pbr.py"""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import texpack  # noqa: E402

def run():
    rng = np.random.default_rng(1)
    with tempfile.TemporaryDirectory() as t:
        dump, pack = Path(t, 'dump'), Path(t, 'pack')
        dump.mkdir()
        pack.mkdir()
        colour = rng.integers(0, 255, (16, 16, 4), dtype=np.uint8)
        colour[:, :, 3] = 255
        texpack.write_dds(dump / '16x16_colour.dds', colour, 'bc1')
        texpack.write_dds(pack / '16x16_colour.dds', np.kron(colour, np.ones((2, 2, 1), np.uint8)), 'bc1')
        normal = np.zeros((16, 16, 4), np.uint8)
        normal[:] = (128, 128, 255, 255)
        texpack.write_dds(dump / '16x16_normal.dds', normal, 'bc1')
        texpack.write_dds(pack / '16x16_normal.dds', np.kron(normal, np.ones((2, 2, 1), np.uint8)), 'bc1')
        rc = texpack.main(['upscale', '--dump', str(dump), '--pack', str(pack), '--scale', '2', '--pbr',
                           '--esrgan', str(Path(t, 'no-esrgan.exe'))])
        assert rc == 0, rc
        assert (pack / 'pbr' / '16x16_colour.dds').exists(), 'no PBR map for the already-upscaled colour texture'
        assert not (pack / 'pbr' / '16x16_normal.dds').exists(), 'normal maps get no PBR map'
        # without --pbr nothing is added
        (pack / 'pbr' / '16x16_colour.dds').unlink()
        assert texpack.main(['upscale', '--dump', str(dump), '--pack', str(pack), '--scale', '2']) == 0
        assert not (pack / 'pbr' / '16x16_colour.dds').exists()
    print('test_texpack_pbr: ok')


def run_skips():
    """Tiny, flat and normal-map textures are resized and exact duplicates copied, all without Real-ESRGAN,
    in the same DDS layout (2x size, full mip chain); a second run finds nothing to do."""
    rng = np.random.default_rng(2)
    with tempfile.TemporaryDirectory() as t:
        dump, pack = Path(t, 'dump'), Path(t, 'pack')
        dump.mkdir()
        flat = np.zeros((64, 32, 4), np.uint8)
        flat[:] = (90, 120, 30, 255)
        flat[:, :, 0] += rng.integers(0, 4, (64, 32), dtype=np.uint8)
        texpack.write_dds(dump / '32x64_86_flat.dds', flat, 'bc1')
        texpack.write_dds(dump / '32x64_88_flatdup.dds', flat, 'bc1')     # same pixels, another key
        tiny = rng.integers(0, 255, (8, 8, 4), dtype=np.uint8)
        tiny[:, :, 3] = 128
        texpack.write_dds(dump / '8x8_88_tiny.dds', tiny, 'rgba')
        normal = np.zeros((32, 32, 4), np.uint8)
        normal[:] = (128, 128, 255, 255)
        normal[:, :, :2] += rng.integers(0, 60, (32, 32, 2), dtype=np.uint8)
        texpack.write_dds(dump / '32x32_86_normal.dds', normal, 'bc1')
        args = ['upscale', '--dump', str(dump), '--pack', str(pack), '--scale', '2', '--pbr',
                '--esrgan', str(Path(t, 'no-esrgan.exe'))]
        assert texpack.main(args) == 0
        for key, (w, h), four_cc in (('32x64_86_flat', (64, 128), b'DXT1'), ('32x64_88_flatdup', (64, 128), b'DXT1'),
                                     ('8x8_88_tiny', (16, 16), b'DXT5'), ('32x32_86_normal', (64, 64), b'DXT1')):
            hd = (pack / (key + '.dds')).read_bytes()[:128]
            assert hd[:4] == b'DDS ' and hd[84:88] == four_cc, key
            assert (int.from_bytes(hd[16:20], 'little'), int.from_bytes(hd[12:16], 'little')) == (w, h), key
            assert int.from_bytes(hd[28:32], 'little') == max(w, h).bit_length(), key   # full mip chain
        assert (pack / '32x64_88_flatdup.dds').read_bytes() == (pack / '32x64_86_flat.dds').read_bytes()
        assert (pack / 'pbr' / '32x64_88_flatdup.dds').exists() and not (pack / 'pbr' / '32x32_86_normal.dds').exists()
        assert texpack.main(args) == 0   # resume: everything is already in the pack
        assert not (pack / '_work').exists()
    print('test_texpack_skips: ok')


if __name__ == '__main__':   # worker processes (texpack --jobs) re-import this file on Windows
    run()
    run_skips()
