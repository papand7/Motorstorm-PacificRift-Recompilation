"""Focused evidence gates for local SPU overlay AOT discovery."""
import tempfile
import unittest
from pathlib import Path

from discover_spu_overlays import discover, fnv64


class OverlayDiscoveryTest(unittest.TestCase):
    def test_requires_branch_and_exact_resident_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            captures = Path(tmp)
            first = bytearray(0x300)
            second = bytearray(0x300)
            first[0x90:0xB0] = bytes(range(32))
            second[0x90:0xB0] = bytes(range(32, 64))
            entries = []
            for ea, raw in ((0x1000, first), (0x2000, second)):
                path = captures / f"ovl_{ea:08X}.bin"
                path.write_bytes(raw)
                entries.append(f"[spu-ovl-version] img=7 ea=0x{ea:08X} lsa=0x35000 "
                               f"size={len(raw)} hash={fnv64(raw):016X} file={path}")
            branch = "[spu] img=7 branched into unlifted LS 0x35090 (lr=0x100)"
            ls_first = "      LS[0x35090]: " + " ".join(first[0x90+i:0x90+i+4].hex().upper() for i in range(0, 32, 4))
            ls_second = "      LS[0x35090]: " + " ".join(second[0x90+i:0x90+i+4].hex().upper() for i in range(0, 32, 4))
            self.assertEqual(discover([entries[0]], captures), [])
            self.assertEqual(discover([entries[0], branch, ls_second], captures), [])
            self.assertEqual(len(discover([entries[0], branch, ls_first], captures)), 1)
            self.assertEqual(discover([entries[0], entries[1], branch, ls_first], captures), [])
            self.assertEqual(discover([entries[0], entries[1], branch, ls_second], captures)[0]["ea"], 0x2000)
            reload_first = ("[spu-ovl] image=7 prior=99 resident=88 LS=0x35000 "
                            f"EA=0x00001000 span=0x300 hash={fnv64(first):016X}")
            self.assertEqual(discover([entries[0], entries[1], reload_first, branch, ls_first],
                                      captures)[0]["ea"], 0x1000)
            self.assertEqual(discover([reload_first, branch, ls_first], captures)[0]["ea"], 0x1000)
            owner = {99: {"image": 7, "ea": 0x2000, "base": 0x35000,
                          "size": len(second), "path": captures / "ovl_00002000.bin",
                          "raw": bytes(second), "sha256": "synthetic"}}
            exec_miss = "[spu-ovl-exec] image=7 pc=0x35090 lr=0x00100 owner=99 MISS"
            self.assertEqual(discover([exec_miss, branch, ls_second], captures, owner)[0]["ea"], 0x2000)
            self.assertEqual(discover([entries[1].replace("size=768", "size=767"), branch, ls_second], captures), [])


if __name__ == "__main__":
    unittest.main()
