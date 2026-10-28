"""Check bounded native startup evidence through repeated Edge Zlib jobs."""

import argparse
import re
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stderr_log", type=Path)
    parser.add_argument("stdout_log", type=Path)
    args = parser.parse_args()
    err = args.stderr_log.read_text(encoding="utf-8", errors="replace")
    out = args.stdout_log.read_text(encoding="utf-8", errors="replace")
    push = re.search(
        r"PushBody rc=0 q=([0-9A-F]+).*?slot=0 item=([0-9A-F]+) size=32 "
        r"pop=0000000000010000->0000000004010000 "
        r"push=0000000000000000->0001000000000001 "
        r"recipient=0 taskset=([0-9A-F]+)", err,
    )
    assert push, "captured first push transition absent"
    q, slot, taskset = (int(value, 16) for value in push.groups())
    assert slot == q + 0x80
    assert (
        "[spurs-lfq] ring-slot: 40 5E 61 0F 40 5E 50 00 00 00 02 E8 "
        "00 00 13 F7 40 49 50 2D 40 49 4D 80 00 01 00 00 00 00 00 00"
    ) in err, "original 32-byte work item was not preserved in the ring"
    assert f"signal task 0 (taskset 0x{taskset:08X})" in err
    assert err.index("WAIT_SIGNAL#1") < push.start() < err.index("WAIT_SIGNAL#2")
    assert "[spu-lfq] cmd=B4" in err[push.end():], "original SPU atomic commit absent"
    assert "EventFlagWait WAKE" in err[push.end():], "PPU completion event absent"
    assert len(re.findall(r"PushBody rc=0", err)) >= 20, \
        "original PPU did not publish repeated Edge Zlib jobs"
    assert len(re.findall(r"EventFlagWait WAKE", err)) >= 20, \
        "repeated original SPU completions were not observed"
    assert "PushBody rc=80410723" not in err, "unsupported LFQueue state recurred"
    assert "edgezlib_inflate_queue.cpp:420 (0 == ret) -- assertion failed" not in out
    assert "[RSX] CLEAR_SURFACE" in err, "later original RSX commands absent"
    print("PASS: repeated original SPU jobs completed; Edge Zlib submission assertion absent")


if __name__ == "__main__":
    main()
