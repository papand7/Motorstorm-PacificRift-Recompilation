"""Check captured original-firmware LFQueue transitions; logs stay private."""

import argparse
import re
from pathlib import Path


def tty_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    marker = "\nREF spu_initialize="
    if marker not in text:
        raise AssertionError("RPCS3 TTY output is missing")
    return "REF spu_initialize=" + text.rsplit(marker, 1)[1].split("End RPCS3 TTY Section.", 1)[0]


def result(text: str, name: str) -> int:
    match = re.search(rf"^REF {re.escape(name)}=([0-9a-f]{{8}})(?:\s|$)", text, re.M)
    if not match:
        raise AssertionError(f"missing {name}")
    return int(match.group(1), 16)


def blocks(text: str, name: str) -> list[bytes]:
    pattern = rf"^REF {re.escape(name)}\n((?:[0-9a-f]{{2}}: [0-9a-f]+\n)+)"
    found = []
    for match in re.finditer(pattern, text, re.M):
        found.append(bytes.fromhex("".join(line.split(": ", 1)[1]
                                          for line in match.group(1).splitlines())))
    if not found:
        raise AssertionError(f"missing block {name}")
    return found


def no_waiter(text: str) -> None:
    for name in ("spu_initialize", "spurs_attr", "spurs_init", "taskset_create",
                 "lfq_init", "push_result", "push_2_result", "push_3_result",
                 "push_4_result", "pop_result", "wrap_push_result",
                 "taskset_shutdown", "taskset_join", "spurs_finalize"):
        assert result(text, name) == 0, name
    before = blocks(text, "queue_before")[0]
    first = blocks(text, "queue_after")[0]
    next_states = blocks(text, "queue_next")
    after_pop = blocks(text, "queue_after_pop")[0]
    after_wrap = blocks(text, "queue_after_wrap")[0]
    assert before[:16] == bytes(16)
    for count, state in enumerate([first, *next_states], 1):
        assert state[:8] == bytes(8)
        assert state[8:16] == count.to_bytes(2, "big") + bytes(4) + count.to_bytes(2, "big")
    assert after_pop[:8] == bytes.fromhex("0001000000000001")
    assert after_wrap[8:16] == bytes.fromhex("0005000000000005")
    assert blocks(text, "popped")[0] == bytes(range(0xA0, 0xC0))
    assert blocks(text, "ring_after_wrap")[0][:32] == bytes(range(0xE0, 0x100))


def ppu_waiter(text: str) -> None:
    for name in ("lfq_init", "ppu_waiter_attach", "ppu_waiter_create", "push_result",
                 "ppu_waiter_pop", "ppu_waiter_join", "ppu_waiter_detach"):
        assert result(text, name) == 0, name
    waiting = blocks(text, "queue_with_ppu_waiter")[0]
    assert waiting[4:6] == bytes.fromhex("0001")
    assert blocks(text, "ppu_waiter_item")[0] == bytes(range(0xA0, 0xC0))


def spu_task(text: str) -> None:
    for name in ("spu_initialize", "spurs_init", "taskset_create", "lfq_init",
                 "spu_task_create", "taskset_shutdown", "taskset_join",
                 "spurs_finalize"):
        assert result(text, name) == 0, name
    assert blocks(text, "spu_marker_after")[0][:16] == bytes.fromhex(
        "4c465130112233445566778899aabbcc")


def spu_wait_control(text: str) -> None:
    assert result(text, "spu_task_create") == 0
    assert blocks(text, "queue_with_spu_waiter")[0][4:6] == b"\x00\x01"
    assert blocks(text, "taskset_with_spu_waiter")[0][0x50:0x60] == bytes(16)
    assert blocks(text, "spu_marker_held")[0][:16] == bytes.fromhex(
        "4c465130112233445566778899aabbcc")
    assert blocks(text, "spu_wait_codes_held")[0] == bytes.fromhex(
        "000000008041090f0000000000000000")
    assert blocks(text, "taskset_held")[0][0x50:0x60] == bytes(16)
    assert "REF push_result=" not in text


def spu_blocked_control(text: str) -> None:
    assert result(text, "spu_task_create") == 0
    assert blocks(text, "queue_with_spu_waiter")[0][4:6] == b"\x00\x01"
    held = blocks(text, "taskset_held")[0]
    assert held[0x50:0x60] == bytes.fromhex("80000000") + bytes(12)
    assert blocks(text, "spu_marker_held")[0] == bytes(32)
    assert "REF push_result=" not in text


def spu_blocked_push_unnotified(text: str) -> None:
    assert result(text, "spu_queue_attach") == 0
    assert result(text, "spu_task_create") == 0
    assert result(text, "push_result") == 0
    assert "waiting=1" in text and "observed=0" in text
    for name in ("taskset_blocked", "taskset_blocked_held",
                 "taskset_after_spu_wake"):
        assert blocks(text, name)[0][0x50:0x60] == \
            bytes.fromhex("80000000") + bytes(12)
    assert blocks(text, "spu_marker_blocked_held")[0] == bytes(32)
    assert blocks(text, "spu_marker_after")[0] == bytes(32)
    assert blocks(text, "queue_with_spu_waiter")[0][4:6] == b"\x00\x01"
    assert blocks(text, "queue_after")[0][:16] == bytes.fromhex(
        "00000000040100000001000000000001")
    assert blocks(text, "ring_after")[0][:32] == bytes(range(0xA0, 0xC0))


def direct_task_signal_unresumed(text: str) -> None:
    """Firmware signal succeeds but this isolated task still cannot resume."""
    assert result(text, "spu_task_create") == 0
    assert result(text, "direct_signal_result") == 0
    assert "REF direct_signal_spins=201 observed=0" in text
    before = blocks(text, "taskset_blocked")[0]
    signalled = blocks(text, "taskset_after_direct_signal")[0]
    after = blocks(text, "taskset_after_direct_wait")[0]
    assert before[0x40:0x44] == bytes(4)
    assert signalled[0x40:0x44] == bytes.fromhex("80000000")
    assert after[0x40:0x44] == bytes(4)
    for state in (before, signalled, after):
        assert state[0x50:0x54] == bytes.fromhex("80000000")
    assert blocks(text, "spu_marker_after_direct_signal")[0] == bytes(32)
    assert "REF push_result=" not in text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("no-waiter", "ppu-waiter", "spu-task",
                                         "spu-wait-control", "spu-blocked-control",
                                         "spu-blocked-push-unnotified",
                                         "direct-task-signal-unresumed"))
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    text = tty_text(args.log)
    {"no-waiter": no_waiter, "ppu-waiter": ppu_waiter,
     "spu-task": spu_task, "spu-wait-control": spu_wait_control,
     "spu-blocked-control": spu_blocked_control,
     "spu-blocked-push-unnotified": spu_blocked_push_unnotified,
     "direct-task-signal-unresumed": direct_task_signal_unresumed}[args.mode](text)
    print(f"PASS {args.mode}: {args.log}")


if __name__ == "__main__":
    main()
