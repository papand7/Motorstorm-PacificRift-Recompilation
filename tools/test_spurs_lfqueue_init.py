"""Check a bounded native startup trace against the original SPU queue path.

Run with the stderr from a probe that sets SPURS_LFQ_TRACE=1 and
SPU_LFQ_ATOM_EA to the queue EA. This is an integration regression for the
guest queue layout, not a PushBody test.
"""

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: test_spurs_lfqueue_init.py STARTUP_STDERR", file=sys.stderr)
        return 2
    log = Path(sys.argv[1]).read_text(errors="replace")
    rows = {}
    for offset, data in re.findall(r"\[spurs-lfq\] q\+([0-9A-F]{2}):((?: [0-9A-F]{2}){16})", log):
        rows[int(offset, 16)] = bytes.fromhex(data)
    if not all(offset in rows for offset in range(0, 128, 16)):
        raise AssertionError("missing complete PPU queue snapshot")
    queue = b"".join(rows[offset] for offset in range(0, 128, 16))
    read16 = lambda offset: int.from_bytes(queue[offset:offset + 2], "big")
    read32 = lambda offset: int.from_bytes(queue[offset:offset + 4], "big")
    read64 = lambda offset: int.from_bytes(queue[offset:offset + 8], "big")
    assert read32(0x10) == 32 and read32(0x14) == 12
    assert read16(0x0E) == 0, "producer reservation pointer is not empty"
    assert read32(0x24) == 3, "SPU consumer would miss ANY2ANY branch"
    assert read64(0x18) & 1, "ANY2ANY buffer marker is missing"
    assert queue[0x20:0x22] == b"\xff\xff"
    assert read32(0x28) == 0xFFFFFFFF
    assert read16(0x30) == read16(0x50) == 0xFFFF
    assert read16(0x04) == 1, "original SPU did not register its waiter"
    assert "[spu-lfq] cmd=B4" in log, "original SPU did not commit the queue line"
    print("PASS: guest ANY2ANY empty state and original SPU waiter registration")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
