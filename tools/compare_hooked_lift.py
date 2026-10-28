"""Check a --trace-hooks relift against the existing private lift.

Removes the hook statements (and the header/table additions that come with
them) from every staged file and compares the result byte for byte with
generated/ppu. Any other difference means the lifter or its inputs changed
since the current lift and the hooked tree must not be swapped in blindly.

  py -3 tools/compare_hooked_lift.py generated/ppu-hooked-staging
"""

import argparse
import hashlib
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
HOOKS = re.compile(rb" PPU_TR_(?:ENTER|BB)\(ctx, 0x[0-9A-F]{8}u\);"
                   rb"| PPU_TR_RET\(ctx, 0x[0-9A-F]{8}u, 0x[0-9A-F]{8}u\);")
HEADER_BLOCK = re.compile(rb"/\* Runtime trace hooks \(runtime/ppu/ppu_trace\.h\).*?"
                          rb"#define PPU_TR_BB\([^\n]*\n\r?\n", re.S)
TABLE_MARK = re.compile(rb"#ifdef __cplusplus\r?\nextern \"C\"\r?\n#endif\r?\n"
                        rb"uint32_t ppu_trace_hook_level = 1;\r?\n")


def strip(data):
    return TABLE_MARK.sub(b"", HEADER_BLOCK.sub(b"", HOOKS.sub(b"", data)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("staging", type=Path)
    parser.add_argument("--current", type=Path, default=ROOT / "generated/ppu")
    args = parser.parse_args()
    staged = sorted(p for p in args.staging.iterdir() if p.suffix in (".cpp", ".h"))
    bad, counts = [], {"enter": 0, "ret": 0, "bb": 0}
    for path in staged:
        data = path.read_bytes()
        counts["enter"] += data.count(b"PPU_TR_ENTER(ctx")
        counts["ret"] += data.count(b"PPU_TR_RET(ctx")
        counts["bb"] += data.count(b"PPU_TR_BB(ctx")
        current = args.current / path.name
        same = current.is_file() and strip(data) == current.read_bytes()
        if not same:
            bad.append(path.name)
        print(f"{'same' if same else 'DIFF'} {path.name} "
              f"sha256(hooked)={hashlib.sha256(data).hexdigest()[:16]}")
    # ppu_hle_nids.cpp comes from gen_hle_nids.py, not the lifter.
    extra = sorted({p.name for p in args.current.iterdir() if p.suffix in (".cpp", ".h")}
                   - {p.name for p in staged} - {"ppu_hle_nids.cpp"})
    print(f"hooks: enter={counts['enter']} ret={counts['ret']} bb={counts['bb']}")
    if extra:
        print("only in current: " + " ".join(extra))
    if bad or extra:
        sys.exit(f"{len(bad)} file(s) differ after removing hooks")
    print(f"PASS: {len(staged)} files equal the current lift once hooks are removed")


if __name__ == "__main__":
    main()
