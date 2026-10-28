"""Integration gate for the explicitly unsupported ANY2ANY PushBody path.

This verifies honest failure and preserves the observed consumer wait. It does
not certify a working producer protocol; replace this gate when that exists.
"""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stderr_log", type=Path)
    args = parser.parse_args()
    text = args.stderr_log.read_text(encoding="utf-8", errors="replace")
    required = (
        "[spurs-lfq] PushBody unsupported",
        "mode=3 size=32 depth=12 dir=3 waiter=0001",
        "guest state unchanged",
        "WAIT_SIGNAL#1 enter task=0",
        "EventFlagWait BLOCKED",
    )
    for token in required:
        if token not in text:
            raise AssertionError(f"Missing startup evidence: {token}")
    if "[spurs-lfq] unresolved PushBody" in text:
        raise AssertionError("NID still unresolved")
    print("PARTIAL: NID resolves and fails explicitly; original SPU remains waiting")


if __name__ == "__main__":
    main()
